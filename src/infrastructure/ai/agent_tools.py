from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

import structlog

from src.application.appointment.book_appointment import BookAppointmentInput, BookAppointmentUseCase
from src.application.appointment.cancel_appointment import CancelAppointmentInput, CancelAppointmentUseCase
from src.application.appointment.get_available_slots import GetAvailableSlotsInput, GetAvailableSlotsUseCase
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.appointment.repository import AppointmentRepository
from src.domain.appointment.value_objects import AppointmentStatus
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.client.repository import ClientRepository
from src.domain.professional.repository import ProfessionalRepository
from src.domain.service.repository import ServiceRepository
from src.infrastructure.ai.date_parser import parse_date, parse_time

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
        "name": "transfer_to_human",
        "description": (
            "Escalate the conversation to a human staff member. "
            "Use when: the client requests a person, asks something outside your scope, "
            "expresses frustration, or you cannot resolve the request after trying."
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
    services: ServiceRepository
    appointments: AppointmentRepository
    professionals: ProfessionalRepository
    business_hours: BusinessHourRepository
    clients: ClientRepository
    uow: UnitOfWork
    # Set by transfer_to_human tool; read by ProcessInboundMessageUseCase
    escalation_triggered: bool = False
    escalation_reason: str = ""


# ── Tool executors ────────────────────────────────────────────────────────────

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
        }
        for s in items
    ])


async def _get_professionals(inputs: dict, ctx: ToolContext) -> str:
    service_id_raw = inputs.get("service_id")
    # ProfessionalRepository.list_by_business doesn't filter by service yet — list all
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
    ))
    return json.dumps({
        "date": output.date.isoformat(),
        "service_duration_minutes": output.service_duration_minutes,
        "available_slots": output.slots,
    })


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
    return json.dumps({
        "appointment_id": str(output.appointment_id),
        "scheduled_at": output.scheduled_at.isoformat(),
        "ends_at": output.ends_at.isoformat(),
        "status": output.status.value,
        "duration_minutes": output.duration_minutes,
    })


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
            "scheduled_at": a.scheduled_at.isoformat(),
            "ends_at": a.ends_at.isoformat(),
            "status": a.status.value,
        }
        for a in client_items
    ])


def _transfer_to_human(inputs: dict, ctx: ToolContext) -> str:
    ctx.escalation_triggered = True
    ctx.escalation_reason = inputs.get("reason", "")
    return json.dumps({"status": "escalated", "reason": ctx.escalation_reason})


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
