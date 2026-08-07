from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog

from src.application.appointment.book_appointment import BookAppointmentInput, BookAppointmentUseCase
from src.application.appointment.cancel_appointment import CancelAppointmentInput, CancelAppointmentUseCase
from src.application.appointment.get_available_slots import GetAvailableSlotsInput, GetAvailableSlotsUseCase
from src.application.appointment.reschedule_appointment import (
    RescheduleAppointmentInput,
    RescheduleAppointmentUseCase,
)
from src.application.membership.get_client_membership import (
    GetClientMembershipInput,
    GetClientMembershipUseCase,
)
from src.application.membership.list_membership_plans import (
    ListMembershipPlansInput,
    ListMembershipPlansUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.appointment.repository import AppointmentRepository
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.client.repository import ClientRepository
from src.domain.conversation.human_transfer import HumanTransfer
from src.domain.conversation.human_transfer_repository import HumanTransferRepository
from src.domain.conversation.messaging_provider import MessagingProvider
from src.domain.membership.repository import MembershipPlanRepository, MembershipRepository
from src.domain.shared.channel import Channel
from src.domain.professional.repository import ProfessionalRepository
from src.domain.service.repository import ServiceRepository
from src.infrastructure.ai.date_parser import parse_date

log = structlog.get_logger(__name__)

# ── Tool schema definitions (Anthropic format) ────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "get_services",
        "description": "List all active services offered by this business with their duration and price.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_professionals",
        "description": "List professionals available at this business, optionally filtered by service.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "UUID of the service to filter professionals by (optional).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "check_availability",
        "description": (
            "Return available time slots for a service on a specific date. "
            "Always call this before booking to confirm slots are open."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "UUID of the service.",
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format.",
                },
                "professional_id": {
                    "type": "string",
                    "description": "UUID of the preferred professional (optional).",
                },
            },
            "required": ["service_id", "date"],
        },
    },
    {
        "name": "book_appointment",
        "description": (
            "Book an appointment for the current client. "
            "Only call this after the client has confirmed the details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "string",
                    "description": "UUID of the service to book.",
                },
                "scheduled_at": {
                    "type": "string",
                    "description": "ISO 8601 UTC datetime, e.g. '2026-05-20T10:00:00+00:00'.",
                },
                "professional_id": {
                    "type": "string",
                    "description": "UUID of the professional (optional).",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes from the client.",
                },
            },
            "required": ["service_id", "scheduled_at"],
        },
    },
    {
        "name": "get_my_appointments",
        "description": "List the client's upcoming active appointments.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel one of the client's appointments by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "UUID of the appointment to cancel.",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional reason for cancellation.",
                },
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "reschedule_appointment",
        "description": (
            "Move one of the client's appointments to a new date and time. "
            "Check availability first, and only call this after the client confirms."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "UUID of the appointment to move.",
                },
                "new_scheduled_at": {
                    "type": "string",
                    "description": "New ISO 8601 UTC datetime, e.g. '2026-05-20T10:00:00+00:00'.",
                },
            },
            "required": ["appointment_id", "new_scheduled_at"],
        },
    },
    {
        "name": "get_membership_plans",
        "description": (
            "List the membership plans this business sells (name, price, billing period, "
            "included services). Use it when the client asks about plans, prices or "
            "monthly fees. Mention at most 3 plans per message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_my_membership",
        "description": (
            "Check the membership of the current client: plan, status, expiry date and "
            "days left. Use it when the client asks about their membership, or before "
            "booking a class to know whether their plan is current."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "capture_lead",
        "description": (
            "Register an interested person so reception can call them back. Use it on "
            "Facebook and Instagram, where you cannot book: once you have their name "
            "and phone number, call this and confirm that reception will contact them. "
            "Ask for the phone number in a natural way; never invent it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {
                    "type": "string",
                    "description": "Name the person gave.",
                },
                "telefono": {
                    "type": "string",
                    "description": "Phone number, digits only, as the person wrote it.",
                },
                "interes": {
                    "type": "string",
                    "description": "What they want, in one sentence (service, plan, schedule).",
                },
            },
            "required": ["nombre", "telefono", "interes"],
        },
    },
    {
        "name": "notify_staff",
        "description": (
            "Send the staff a heads-up WITHOUT handing the conversation over: you keep "
            "talking to the client normally. Use it for sales leads and anything "
            "reception must follow up on off-chat — the client wants to buy or renew a "
            "plan, asks to pay, or needs an invoice. Never use it for complaints or "
            "when the client asks for a person: that is transfer_to_human."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "What staff should follow up on, in one sentence.",
                },
            },
            "required": ["reason"],
        },
    },
    {
        "name": "transfer_to_human",
        "description": (
            "Hand the conversation over to a human and STOP replying. Use only when: "
            "the client explicitly asks for a person, makes a complaint, or you cannot "
            "resolve the request after trying. For sales leads use notify_staff instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief reason for the escalation (shown to staff).",
                },
            },
            "required": ["reason"],
        },
    },
]


# Tools available on Meta's social inboxes. Everything that books, cancels or
# reveals a client's history is left out: on Facebook and Instagram there is no
# way to verify who is writing, and the product decision is that social is for
# answering questions and capturing leads.
_SOCIAL_TOOL_NAMES = frozenset({
    "get_services",
    "get_professionals",
    "check_availability",
    "get_membership_plans",
    "capture_lead",
    "transfer_to_human",
})


def tools_for_channel(channel: Channel) -> list[dict]:
    """Tool definitions the agent may use on a given channel."""
    if not channel.is_social:
        return TOOL_DEFINITIONS
    return [t for t in TOOL_DEFINITIONS if t["name"] in _SOCIAL_TOOL_NAMES]


# ── Tool execution context ────────────────────────────────────────────────────

@dataclass
class ToolContext:
    """Repositories and client info available to tool executors."""
    tenant_id: UUID
    business_id: UUID
    client_id: UUID
    client_name: str
    client_whatsapp: str
    conversation_id: UUID
    business_timezone: str
    business_name: str
    services: ServiceRepository
    appointments: AppointmentRepository
    professionals: ProfessionalRepository
    business_hours: BusinessHourRepository
    clients: ClientRepository
    uow: UnitOfWork
    # Optional: without them the membership tools report "not configured", which
    # keeps every existing caller (and non-gym businesses) working unchanged.
    membership_plans: MembershipPlanRepository | None = None
    memberships: MembershipRepository | None = None
    human_transfers: HumanTransferRepository | None = None
    # Which inbox the client wrote from. Social channels get a read-only
    # toolset (see tools_for_channel) and cannot book.
    channel: Channel = Channel.WHATSAPP
    # Always a WhatsApp provider: staff alerts never go out over the inbound
    # channel, because a Facebook page cannot message its own owner.
    staff_notifier: MessagingProvider | None = None
    owner_whatsapp: str | None = None
    # Set by transfer_to_human tool; read by ProcessInboundMessageUseCase
    escalation_triggered: bool = False
    escalation_reason: str = ""


# ── Tool executors ────────────────────────────────────────────────────────────

def _business_tz(timezone_name: str) -> ZoneInfo | timezone:
    try:
        return ZoneInfo(timezone_name or "UTC")
    except ZoneInfoNotFoundError:
        return timezone.utc


def _to_local_time(moment: datetime | str, timezone_name: str) -> str:
    """UTC instant → 'HH:MM' in the business timezone (what the client is told)."""
    value = datetime.fromisoformat(moment) if isinstance(moment, str) else moment
    return value.astimezone(_business_tz(timezone_name)).strftime("%H:%M")


def _to_local_date(moment: datetime | str, timezone_name: str) -> str:
    """UTC instant → 'YYYY-MM-DD' in the business timezone."""
    value = datetime.fromisoformat(moment) if isinstance(moment, str) else moment
    return value.astimezone(_business_tz(timezone_name)).strftime("%Y-%m-%d")


async def execute_tool(name: str, inputs: dict, ctx: ToolContext) -> str:
    """Dispatch a tool call and return a JSON string result."""
    try:
        if name == "get_services":
            return await _get_services(ctx)
        if name == "get_professionals":
            return await _get_professionals(inputs, ctx)
        if name == "check_availability":
            return await _check_availability(inputs, ctx)
        if name == "book_appointment":
            return await _book_appointment(inputs, ctx)
        if name == "get_my_appointments":
            return await _get_my_appointments(ctx)
        if name == "cancel_appointment":
            return await _cancel_appointment(inputs, ctx)
        if name == "reschedule_appointment":
            return await _reschedule_appointment(inputs, ctx)
        if name == "get_membership_plans":
            return await _get_membership_plans(ctx)
        if name == "get_my_membership":
            return await _get_my_membership(ctx)
        if name == "notify_staff":
            return await _notify_staff(inputs, ctx)
        if name == "capture_lead":
            return await _capture_lead(inputs, ctx)
        if name == "transfer_to_human":
            return _transfer_to_human(inputs, ctx)
        return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as exc:
        log.exception("tool_execution_error", tool=name, error=str(exc))
        return json.dumps({"error": str(exc)})


async def _get_services(ctx: ToolContext) -> str:
    items = await ctx.services.list_by_business(ctx.business_id)
    return json.dumps([
        {
            "id": str(s.id),
            "name": s.name,
            "duration_minutes": s.duration_minutes,
            "price_cents": s.price,
            # Only meaningful for group classes; 1 means one-to-one.
            "capacity": s.capacity,
            "is_group_class": s.is_group_class,
        }
        for s in items
    ])


async def _get_professionals(inputs: dict, ctx: ToolContext) -> str:
    service_id_raw = inputs.get("service_id")
    if service_id_raw:
        try:
            service_uuid = UUID(service_id_raw)
            # First check if the service has explicit professional assignments
            assigned_ids = await ctx.services.list_professional_ids(service_uuid)
            if assigned_ids:
                items = await ctx.professionals.list_by_service(service_uuid)
            else:
                # No restrictions → any active professional can perform it
                items = await ctx.professionals.list_by_business(ctx.business_id)
        except ValueError:
            items = await ctx.professionals.list_by_business(ctx.business_id)
    else:
        items = await ctx.professionals.list_by_business(ctx.business_id)

    return json.dumps([
        {"id": str(p.id), "name": p.name}
        for p in items
        if p.is_active
    ])


async def _check_availability(inputs: dict, ctx: ToolContext) -> str:
    today = datetime.now(timezone.utc).date()
    on_date = parse_date(inputs["date"], today) or today

    professional_id = None
    if pid := inputs.get("professional_id"):
        try:
            professional_id = UUID(pid)
        except ValueError:
            pass

    uc = GetAvailableSlotsUseCase(
        business_hours=ctx.business_hours,
        appointments=ctx.appointments,
        services=ctx.services,
    )
    output = await uc.execute(GetAvailableSlotsInput(
        business_id=ctx.business_id,
        service_id=UUID(inputs["service_id"]),
        on_date=on_date,
        professional_id=professional_id,
        business_timezone=ctx.business_timezone,
    ))
    # Every slot carries both times: hora_local is what the client is told,
    # inicio_utc is what book_appointment must receive verbatim.
    slots = []
    for s in output.slots_detail:
        slot = {
            "inicio_utc": s.start,
            "hora_local": _to_local_time(s.start, ctx.business_timezone),
        }
        if output.capacity > 1:
            slot["spots_left"] = s.remaining
        slots.append(slot)

    result = {
        "date": output.date.isoformat(),
        "timezone": ctx.business_timezone,
        "service_duration_minutes": output.service_duration_minutes,
        "slots": slots,
    }
    if output.capacity > 1:
        result["capacity"] = output.capacity
    return json.dumps(result)


async def _book_appointment(inputs: dict, ctx: ToolContext) -> str:
    try:
        scheduled_at = datetime.fromisoformat(inputs["scheduled_at"])
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    except ValueError:
        return json.dumps({"error": "Invalid scheduled_at format. Use ISO 8601."})

    professional_id = None
    if pid := inputs.get("professional_id"):
        try:
            professional_id = UUID(pid)
        except ValueError:
            pass

    uc = BookAppointmentUseCase(
        appointments=ctx.appointments,
        services=ctx.services,
        clients=ctx.clients,
        professionals=ctx.professionals,
        uow=ctx.uow,
    )
    output = await uc.execute(BookAppointmentInput(
        business_id=ctx.business_id,
        service_id=UUID(inputs["service_id"]),
        scheduled_at=scheduled_at,
        client_name=ctx.client_name,
        client_whatsapp=ctx.client_whatsapp,
        professional_id=professional_id,
        notes=inputs.get("notes"),
    ))
    result = {
        "appointment_id": str(output.appointment_id),
        "inicio_utc": output.scheduled_at.isoformat(),
        "hora_local": _to_local_time(output.scheduled_at, ctx.business_timezone),
        "fecha_local": _to_local_date(output.scheduled_at, ctx.business_timezone),
        "status": output.status.value,
        "duration_minutes": output.duration_minutes,
    }
    if output.spots_left is not None:
        result["spots_left"] = output.spots_left
    if output.already_booked:
        # Tell the agent it is the same seat, so it confirms instead of
        # apologising or booking again.
        result["already_booked"] = True
        result["nota"] = "El cliente ya tenía esta reserva; no se duplicó."
    return json.dumps(result)


async def _get_my_appointments(ctx: ToolContext) -> str:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    items = await ctx.appointments.list_active_in_range(
        business_id=ctx.business_id,
        start=now,
        end=now + timedelta(days=60),
    )
    # Filter to this client only
    client_items = [a for a in items if a.client_id == ctx.client_id]
    return json.dumps([
        {
            "appointment_id": str(a.id),
            "service_id": str(a.service_id),
            "inicio_utc": a.scheduled_at.isoformat(),
            "hora_local": _to_local_time(a.scheduled_at, ctx.business_timezone),
            "fecha_local": _to_local_date(a.scheduled_at, ctx.business_timezone),
            "status": a.status.value,
        }
        for a in client_items
    ])


def _transfer_to_human(inputs: dict, ctx: ToolContext) -> str:
    ctx.escalation_triggered = True
    ctx.escalation_reason = inputs.get("reason", "")
    return json.dumps({"status": "escalated", "reason": ctx.escalation_reason})


async def _notify_staff(inputs: dict, ctx: ToolContext) -> str:
    """Ping the owner and keep the conversation alive.

    Unlike transfer_to_human this does NOT escalate: the bot stays in charge, so
    a client who asks to buy a plan can still book a class in the same chat.
    """
    reason = (inputs.get("reason") or "").strip()

    if not ctx.owner_whatsapp or ctx.staff_notifier is None:
        # No owner number configured. This is an operator problem, not the
        # client's: instruct the agent to route them to the counter and say
        # nothing about internal configuration.
        log.warning(
            "notify_staff_no_owner",
            business_id=str(ctx.business_id),
            hint="Configura businesses.owner_whatsapp para recibir los avisos de venta.",
        )
        return json.dumps({
            "status": "ok",
            "instruccion": (
                "Invita al cliente a pasar por recepción para completar la compra "
                "y sigue atendiéndolo. NO menciones nada técnico ni de configuración."
            ),
            "keep_talking": True,
        })

    body = (
        f"🔔 *{ctx.business_name}* — seguimiento pendiente\n\n"
        f"Canal: {ctx.channel.label_es}\n"
        f"Cliente: {ctx.client_name} ({ctx.client_whatsapp})\n"
        f"Motivo: {reason}\n\n"
        "El bot sigue atendiendo la conversación normalmente."
    )
    sent = await ctx.staff_notifier.send_text(to=ctx.owner_whatsapp, body=body)
    log.info("notify_staff_sent", reason=reason, delivered=sent, channel=ctx.channel.value)

    return json.dumps({
        "status": "staff_notified" if sent else "staff_notification_failed",
        "reason": reason,
        "keep_talking": True,
    })


async def _capture_lead(inputs: dict, ctx: ToolContext) -> str:
    """Register an interested person from a social channel.

    Three things happen, and none of them silences the bot:
      1. name and phone are stored on the client, so the lead is reachable;
      2. a HumanTransfer with kind="lead" lands in the follow-up queue;
      3. reception gets a WhatsApp alert.
    """
    nombre = (inputs.get("nombre") or "").strip()
    telefono = (inputs.get("telefono") or "").strip()
    interes = (inputs.get("interes") or "").strip()

    if not telefono:
        return json.dumps({
            "error": "Falta el teléfono: pídeselo al cliente antes de registrar el lead."
        })

    # 1. Keep the contact details on the client record
    client = await ctx.clients.get_by_id(ctx.client_id)
    if client is not None:
        client.record_contact_details(name=nombre or None, phone=telefono)
        await ctx.clients.update(client)

    # 2. Queue it for reception — one enquiry, one row
    reason = f"Lead de {ctx.channel.label_es}: {interes or 'sin detalle'}"
    snapshot = [{"sender": "lead", "content": f"{nombre} · {telefono} · {interes}"}]
    already_queued = False
    if ctx.human_transfers is not None:
        existing = await ctx.human_transfers.get_pending_lead(ctx.conversation_id)
        if existing is not None:
            existing.refresh_lead(reason=reason, context_snapshot=snapshot)
            await ctx.human_transfers.update(existing)
            already_queued = True
        else:
            await ctx.human_transfers.add(
                HumanTransfer.create(
                    tenant_id=ctx.tenant_id,
                    business_id=ctx.business_id,
                    conversation_id=ctx.conversation_id,
                    client_id=ctx.client_id,
                    reason=reason,
                    context_snapshot=snapshot,
                    kind="lead",
                )
            )

    # 3. Tell reception right away — but only the first time, so a retry does
    #    not buzz their phone again for the same person.
    delivered = False
    if already_queued:
        log.info("lead_already_queued", client_id=str(ctx.client_id))
        return json.dumps({
            "status": "lead_ya_registrado",
            "instruccion": (
                "Este contacto ya estaba tomado en esta conversación. No lo anuncies "
                "de nuevo: seguí la charla desde donde estaba."
            ),
            "keep_talking": True,
        })

    if ctx.owner_whatsapp and ctx.staff_notifier is not None:
        body = (
            f"🌟 *{ctx.business_name}* — nuevo contacto por {ctx.channel.label_es}\n\n"
            f"Nombre: {nombre or ctx.client_name}\n"
            f"Teléfono: {telefono}\n"
            f"Interés: {interes or 'no especificado'}\n\n"
            "Escribile por WhatsApp para cerrar la reserva."
        )
        delivered = await ctx.staff_notifier.send_text(to=ctx.owner_whatsapp, body=body)

    log.info(
        "lead_captured",
        channel=ctx.channel.value,
        client_id=str(ctx.client_id),
        notified=delivered,
    )
    return json.dumps({
        "status": "lead_registrado",
        "instruccion": (
            "Confírmale que recepción lo contactará a ese número y ofrécele "
            "seguir respondiendo dudas. No prometas una reserva confirmada."
        ),
        "keep_talking": True,
    })


async def _cancel_appointment(inputs: dict, ctx: ToolContext) -> str:
    try:
        appointment_id = UUID(inputs["appointment_id"])
    except ValueError:
        return json.dumps({"error": "Invalid appointment_id."})

    # Verify ownership before cancelling
    apt = await ctx.appointments.get_by_id(appointment_id)
    if not apt or apt.client_id != ctx.client_id:
        return json.dumps({"error": "Appointment not found or does not belong to this client."})

    uc = CancelAppointmentUseCase(appointments=ctx.appointments, uow=ctx.uow)
    output = await uc.execute(CancelAppointmentInput(
        appointment_id=appointment_id,
        reason=inputs.get("reason"),
    ))
    return json.dumps({
        "appointment_id": str(output.appointment_id),
        "status": output.status.value,
    })


async def _reschedule_appointment(inputs: dict, ctx: ToolContext) -> str:
    try:
        appointment_id = UUID(inputs["appointment_id"])
    except ValueError:
        return json.dumps({"error": "Invalid appointment_id."})

    try:
        new_scheduled_at = datetime.fromisoformat(inputs["new_scheduled_at"])
        if new_scheduled_at.tzinfo is None:
            new_scheduled_at = new_scheduled_at.replace(tzinfo=timezone.utc)
    except ValueError:
        return json.dumps({"error": "Invalid new_scheduled_at format. Use ISO 8601."})

    # Verify ownership before moving the appointment
    apt = await ctx.appointments.get_by_id(appointment_id)
    if not apt or apt.client_id != ctx.client_id:
        return json.dumps({"error": "Appointment not found or does not belong to this client."})

    uc = RescheduleAppointmentUseCase(
        appointments=ctx.appointments,
        services=ctx.services,
        uow=ctx.uow,
    )
    output = await uc.execute(RescheduleAppointmentInput(
        appointment_id=appointment_id,
        new_scheduled_at=new_scheduled_at,
    ))
    result = {
        "appointment_id": str(output.appointment_id),
        "inicio_utc": output.scheduled_at.isoformat(),
        "hora_local": _to_local_time(output.scheduled_at, ctx.business_timezone),
        "fecha_local": _to_local_date(output.scheduled_at, ctx.business_timezone),
        "status": output.status.value,
    }
    if output.spots_left is not None:
        result["spots_left"] = output.spots_left
    return json.dumps(result)


async def _get_membership_plans(ctx: ToolContext) -> str:
    if ctx.membership_plans is None:
        return json.dumps({"error": "This business does not sell membership plans."})

    uc = ListMembershipPlansUseCase(plans=ctx.membership_plans)
    output = await uc.execute(
        ListMembershipPlansInput(business_id=ctx.business_id, page=1, page_size=20)
    )
    return json.dumps({
        "total": output.total,
        "plans": [
            {
                "id": str(p.membership_plan_id),
                "name": p.name,
                "description": p.description,
                "price_cents": p.price,
                "billing_period": p.billing_period.value,
                "period_label_es": p.billing_period.label_es,
                # Empty list means the plan includes every service.
                "included_service_ids": [str(sid) for sid in p.service_ids],
            }
            for p in output.plans
        ],
    })


async def _get_my_membership(ctx: ToolContext) -> str:
    if ctx.memberships is None or ctx.membership_plans is None:
        return json.dumps({"error": "This business does not manage memberships."})

    uc = GetClientMembershipUseCase(
        memberships=ctx.memberships,
        plans=ctx.membership_plans,
    )
    output = await uc.execute(
        GetClientMembershipInput(client_id=ctx.client_id, business_id=ctx.business_id)
    )
    return json.dumps({
        "has_membership": output.has_membership,
        "plan_name": output.plan_name,
        "status": output.status.value if output.status else None,
        "is_current": output.is_current,
        "ends_at": output.ends_at.isoformat() if output.ends_at else None,
        "days_remaining": output.days_remaining,
        "price_cents": output.price_paid,
        "billing_period": output.billing_period.value if output.billing_period else None,
        # Short sentence to relay when the membership does not allow attending.
        "warning": output.warning,
    })
