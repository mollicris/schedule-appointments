from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.use_case import UseCase
from src.domain.appointment.repository import AppointmentRepository
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.service.repository import ServiceRepository
from src.domain.shared.errors import NotFoundError

logger = logging.getLogger(__name__)

_SLOT_INTERVAL = 15  # minutes


@dataclass(frozen=True)
class GetAvailableSlotsInput:
    business_id: UUID
    service_id: UUID
    on_date: date
    professional_id: UUID | None = None
    business_timezone: str = "UTC"


@dataclass(frozen=True)
class GetAvailableSlotsOutput:
    slots: list[str]  # ISO 8601 datetime strings (UTC)
    date: date
    service_duration_minutes: int


class GetAvailableSlotsUseCase(UseCase[GetAvailableSlotsInput, GetAvailableSlotsOutput]):
    """Return available time slots for booking a service on a given date.

    Supports multiple time ranges per day (e.g., lunch breaks: 09:00-12:00, 14:00-18:00).

    Slot generation:
      1. Resolve service duration.
      2. Load all business hour ranges for the requested day-of-week (may be multiple).
      3. For each range: Generate candidate slots every 15 minutes from open_at to (close_at - duration).
      4. Remove slots that overlap with existing active appointments.
      5. Return combined slots from all ranges, sorted chronologically.
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

        logger.info(f"Service found: {service.id}, duration: {service.duration_minutes} minutes")

        day_of_week = input_data.on_date.weekday()  # 0=Monday … 6=Sunday
        logger.info(f"Looking for business hours for business_id={input_data.business_id}, day_of_week={day_of_week}, date={input_data.on_date}")

        business_hours = await self._hours.get_by_business_and_day(input_data.business_id, day_of_week)
        logger.info(f"Found {len(business_hours)} business hour records")
        for bh in business_hours:
            logger.info(f"  - day {bh.day_of_week}: {bh.open_at}-{bh.close_at}, is_closed={bh.is_closed}")

        # If no hours configured, no slots available
        if not business_hours:
            logger.info("No business hours found, returning empty slots")
            return GetAvailableSlotsOutput(
                slots=[],
                date=input_data.on_date,
                service_duration_minutes=service.duration_minutes,
            )

        # Filter to only open ranges (is_closed=False)
        open_ranges = [bh for bh in business_hours if not bh.is_closed]
        logger.info(f"Found {len(open_ranges)} open ranges")

        # If all ranges are closed, no slots available
        if not open_ranges:
            logger.info("All ranges are closed, returning empty slots")
            return GetAvailableSlotsOutput(
                slots=[],
                date=input_data.on_date,
                service_duration_minutes=service.duration_minutes,
            )

        # Convert business hours (stored as local time) to UTC using the business timezone
        try:
            tz = ZoneInfo(input_data.business_timezone)
        except ZoneInfoNotFoundError:
            tz = timezone.utc

        logger.info(f"Using timezone: {tz}")

        d = input_data.on_date
        duration = timedelta(minutes=service.duration_minutes)
        logger.info(f"Service duration: {duration}")

        # Load existing active appointments for the entire day
        day_start = datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz).astimezone(timezone.utc)
        day_end = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=tz).astimezone(timezone.utc)
        booked = await self._appointments.list_active_in_range(
            business_id=input_data.business_id,
            start=day_start,
            end=day_end,
            professional_id=input_data.professional_id,
        )
        logger.info(f"Found {len(booked)} booked appointments for the day")

        # Generate slots for each operating range in the day
        available: list[str] = []
        for bh in open_ranges:
            open_dt = datetime(d.year, d.month, d.day, bh.open_at.hour, bh.open_at.minute, tzinfo=tz).astimezone(timezone.utc)
            close_dt = datetime(d.year, d.month, d.day, bh.close_at.hour, bh.close_at.minute, tzinfo=tz).astimezone(timezone.utc)
            logger.info(f"Range: {bh.open_at}-{bh.close_at} → UTC {open_dt.isoformat()}-{close_dt.isoformat()}")

            # Generate candidate slots for this range
            slot = open_dt
            range_slots = 0
            while slot + duration <= close_dt:
                slot_end = slot + duration
                if not _conflicts(slot, slot_end, booked):
                    available.append(slot.isoformat())
                    range_slots += 1
                slot += timedelta(minutes=_SLOT_INTERVAL)
            logger.info(f"Generated {range_slots} slots for this range")

        logger.info(f"Total available slots: {len(available)}")
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
