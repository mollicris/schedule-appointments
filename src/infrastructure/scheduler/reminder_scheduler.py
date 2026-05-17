"""Background scheduler that sends WhatsApp appointment reminders.

Runs every POLL_INTERVAL_SECONDS seconds inside the FastAPI lifespan.
Queries all tenants for appointments due for a reminder in the next 24 h
(configurable via REMINDER_HOURS_BEFORE) and sends interactive buttons.

No tenant context is set — this is a privileged background process with
direct DB access.  Button IDs are prefixed rem_confirm_ / rem_cancel_ /
rem_reschedule_ so the webhook can dispatch them without calling the AI.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.settings import get_settings
from src.infrastructure.messaging.whatsapp_client import WhatsAppClient
from src.infrastructure.persistence.database import get_session_factory
from src.infrastructure.persistence.models.appointment import AppointmentModel
from src.infrastructure.persistence.models.business import BusinessModel, ServiceModel
from src.infrastructure.persistence.models.client import ClientModel

log = structlog.get_logger(__name__)

POLL_INTERVAL_SECONDS = 15 * 60   # run every 15 min
REMINDER_HOURS_BEFORE = 24        # window centre
REMINDER_WINDOW_HOURS = 2         # ±1 h around the target: [23h, 25h] ahead


async def _send_reminders_once(session: AsyncSession) -> None:
    """Single pass: find pending reminders and send them."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    window_start = now + timedelta(hours=REMINDER_HOURS_BEFORE - REMINDER_WINDOW_HOURS / 2)
    window_end = now + timedelta(hours=REMINDER_HOURS_BEFORE + REMINDER_WINDOW_HOURS / 2)

    rows = await session.scalars(
        select(AppointmentModel).where(
            and_(
                AppointmentModel.status.in_(["pending", "confirmed"]),
                AppointmentModel.scheduled_at >= window_start,
                AppointmentModel.scheduled_at <= window_end,
                AppointmentModel.reminder_sent_at.is_(None),
            )
        )
    )
    appointments = list(rows)
    if not appointments:
        return

    log.info("reminder_scheduler_found", count=len(appointments))

    for apt in appointments:
        try:
            await _process_one(session, apt, settings)
        except Exception:
            log.exception("reminder_send_error", appointment_id=str(apt.id))


async def _process_one(session: AsyncSession, apt: AppointmentModel, settings) -> None:
    business: BusinessModel | None = await session.get(BusinessModel, apt.business_id)
    client: ClientModel | None = await session.get(ClientModel, apt.client_id)
    service: ServiceModel | None = await session.get(ServiceModel, apt.service_id)

    if not business or not client or not service:
        log.warning("reminder_missing_related_entity", appointment_id=str(apt.id))
        return

    if not business.whatsapp_phone_number_id:
        log.warning("reminder_no_phone_number_id", business_id=str(business.id))
        return

    # Format date/time in a friendly way
    scheduled = apt.scheduled_at
    day_str = scheduled.strftime("%d/%m/%Y")
    time_str = scheduled.strftime("%H:%M")

    body = (
        f"📅 *Recordatorio de cita* — {business.name}\n\n"
        f"Hola {client.name}, tienes una cita mañana:\n"
        f"*Servicio:* {service.name}\n"
        f"*Fecha:* {day_str} a las {time_str}\n\n"
        f"¿Confirmas tu asistencia?"
    )

    apt_id = str(apt.id)
    buttons = [
        {"id": f"rem_confirm_{apt_id}", "title": "Confirmar ✅"},
        {"id": f"rem_reschedule_{apt_id}", "title": "Reagendar 📅"},
        {"id": f"rem_cancel_{apt_id}", "title": "Cancelar ❌"},
    ]

    wa = WhatsAppClient(
        phone_number_id=business.whatsapp_phone_number_id,
        access_token=settings.whatsapp_access_token,
    )
    sent = await wa.send_interactive_buttons(
        to=client.whatsapp_number,
        body=body,
        buttons=buttons,
    )

    if sent:
        await session.execute(
            update(AppointmentModel)
            .where(AppointmentModel.id == apt.id)
            .values(reminder_sent_at=datetime.now(timezone.utc))
        )
        await session.commit()
        log.info("reminder_sent", appointment_id=apt_id, client=client.whatsapp_number)
    else:
        log.warning("reminder_send_failed", appointment_id=apt_id)


async def run_reminder_scheduler() -> None:
    """Infinite loop — meant to run as a background asyncio task."""
    log.info("reminder_scheduler_started", interval_seconds=POLL_INTERVAL_SECONDS)
    factory = get_session_factory()
    while True:
        try:
            async with factory() as session:
                await _send_reminders_once(session)
        except Exception:
            log.exception("reminder_scheduler_error")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
