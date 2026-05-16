from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.use_case import UseCase
from src.domain.appointment.repository import AppointmentRepository
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.service.repository import ServiceRepository
from src.domain.shared.errors import NotFoundError

_SLOT_INTERVAL = 15  # minutes


@dataclass(frozen=True)
class GetAvailableSlotsInput:
    business_id: UUID
    service_id: UUID
    on_date: date
    professional_id: UUID | None = None


@dataclass(frozen=True)
class GetAvailableSlotsOutput:
    slots: list[str]  # ISO 8601 datetime strings (UTC)
    date: date
    service_duration_minutes: int


class GetAvailableSlotsUseCase(UseCase[GetAvailableSlotsInput, GetAvailableSlotsOutput]):
    """Return available time slots for booking a service on a given date.

    Slot generation:
      1. Resolve service duration.
      2. Load business hours for the requested day-of-week.
      3. Generate candidate slots every 15 minutes from open_at to (close_at - duration).
      4. Remove slots that overlap with existing active appointments.
    """

    def __init__(
        self,
        business_hours: BusinessHourRepository,
        appointments: AppointmentRepository,
        services: ServiceRepository,
    ) -> None:
        self._hours = business_hours
        self._appointments = appointments
        self._services = services

    async def execute(self, input_data: GetAvailableSlotsInput) -> GetAvailableSlotsOutput:
        service = await self._services.get_by_id(input_data.service_id)
        if not service:
            raise NotFoundError(f"Service '{input_data.service_id}' not found")

        day_of_week = input_data.on_date.weekday()  # 0=Monday … 6=Sunday
        bh = await self._hours.get_by_business_and_day(input_data.business_id, day_of_week)

        if not bh or bh.is_closed:
            return GetAvailableSlotsOutput(
                slots=[],
                date=input_data.on_date,
                service_duration_minutes=service.duration_minutes,
            )

        # Build datetime boundaries in UTC (business hours are stored as local time —
        # for Phase 1 we treat them as UTC; timezone conversion is a Phase 2 concern)
        d = input_data.on_date
        open_dt = datetime(d.year, d.month, d.day, bh.open_at.hour, bh.open_at.minute, tzinfo=timezone.utc)
        close_dt = datetime(d.year, d.month, d.day, bh.close_at.hour, bh.close_at.minute, tzinfo=timezone.utc)
        duration = timedelta(minutes=service.duration_minutes)

        # Load existing active appointments that could block slots
        booked = await self._appointments.list_active_in_range(
            business_id=input_data.business_id,
            start=open_dt,
            end=close_dt,
            professional_id=input_data.professional_id,
        )

        available: list[str] = []
        slot = open_dt
        while slot + duration <= close_dt:
            slot_end = slot + duration
            if not _conflicts(slot, slot_end, booked):
                available.append(slot.isoformat())
            slot += timedelta(minutes=_SLOT_INTERVAL)

        return GetAvailableSlotsOutput(
            slots=available,
            date=input_data.on_date,
            service_duration_minutes=service.duration_minutes,
        )


def _conflicts(
    slot_start: datetime,
    slot_end: datetime,
    booked: list,
) -> bool:
    for apt in booked:
        if slot_start < apt.ends_at and slot_end > apt.scheduled_at:
            return True
    return False
