from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.application.appointment.slot_occupancy import evaluate_slot
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
class SlotAvailability:
    """A bookable start time and how many places are left in it."""

    start: str          # ISO 8601 datetime string (UTC)
    remaining: int      # free places; always 1 for one-to-one services
    capacity: int       # total places for the service


@dataclass(frozen=True)
class GetAvailableSlotsOutput:
    slots: list[str]  # ISO 8601 datetime strings (UTC) — kept for existing consumers
    date: date
    service_duration_minutes: int
    slots_detail: list[SlotAvailability] = field(default_factory=list)
    capacity: int = 1


class GetAvailableSlotsUseCase(UseCase[GetAvailableSlotsInput, GetAvailableSlotsOutput]):
    """Return available time slots for booking a service on a given date.

    Supports multiple time ranges per day (e.g., lunch breaks: 09:00-12:00, 14:00-18:00).

    Slot generation:
      1. Resolve service duration and capacity.
      2. Load all business hour ranges for the requested day-of-week (may be multiple).
      3. For each range: generate candidate start times from open_at to (close_at - duration).
      4. Discard start times that are already taken.
      5. Return combined slots from all ranges, sorted chronologically.

    Slot step: every 15 minutes (``_SLOT_INTERVAL``) for one-to-one services —
    unchanged — and every ``duration_minutes`` for group classes, so a 60-minute
    class offers 18:00, 19:00, 20:00 instead of 18:00, 18:15, 18:30 …

    Whether a start time still has places is decided by ``evaluate_slot`` in
    ``slot_occupancy.py``, the same helper the booking use case applies, so a
    slot offered here is always bookable.
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
                capacity=service.capacity,
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
                capacity=service.capacity,
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

        is_group_class = service.capacity > 1
        # Group classes advance by the class duration so start times land on the
        # actual class schedule (18:00, 19:00 …) instead of every 15 minutes.
        step = timedelta(minutes=service.duration_minutes if is_group_class else _SLOT_INTERVAL)
        logger.info(f"Service capacity: {service.capacity}, slot step: {step}")

        # Capacities of the already-booked services decide whether they block a
        # group class (exclusive services do, other group classes do not).
        capacity_by_service = await self._services.get_capacity_map(
            list({apt.service_id for apt in booked} | {input_data.service_id})
        )

        # Generate slots for each operating range in the day
        detail: list[SlotAvailability] = []
        for bh in open_ranges:
            open_dt = datetime(d.year, d.month, d.day, bh.open_at.hour, bh.open_at.minute, tzinfo=tz).astimezone(timezone.utc)
            close_dt = datetime(d.year, d.month, d.day, bh.close_at.hour, bh.close_at.minute, tzinfo=tz).astimezone(timezone.utc)
            logger.info(f"Range: {bh.open_at}-{bh.close_at} → UTC {open_dt.isoformat()}-{close_dt.isoformat()}")

            range_detail = _slots_in_range(
                open_dt=open_dt,
                close_dt=close_dt,
                step=step,
                duration=duration,
                service_id=input_data.service_id,
                capacity=service.capacity,
                booked=booked,
                capacity_by_service=capacity_by_service,
            )
            logger.info(f"Generated {len(range_detail)} slots for this range")
            detail.extend(range_detail)

        logger.info(f"Total available slots: {len(detail)}")
        return GetAvailableSlotsOutput(
            slots=[s.start for s in detail],
            date=input_data.on_date,
            service_duration_minutes=service.duration_minutes,
            slots_detail=detail,
            capacity=service.capacity,
        )


def _slots_in_range(
    *,
    open_dt: datetime,
    close_dt: datetime,
    step: timedelta,
    duration: timedelta,
    service_id: UUID,
    capacity: int,
    booked: list,
    capacity_by_service: dict[UUID, int],
) -> list[SlotAvailability]:
    """Candidate start times inside one operating range that still have places."""
    slots: list[SlotAvailability] = []
    slot = open_dt

    while slot + duration <= close_dt:
        evaluation = evaluate_slot(
            slot_start=slot,
            slot_end=slot + duration,
            service_id=service_id,
            capacity=capacity,
            booked=booked,
            capacity_by_service=capacity_by_service,
        )
        if evaluation.is_bookable:
            slots.append(
                SlotAvailability(
                    start=slot.isoformat(),
                    remaining=evaluation.remaining,
                    capacity=capacity,
                )
            )
        slot += step

    return slots
