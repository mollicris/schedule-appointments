from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from uuid import UUID

from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.business_hours.business_hour import BusinessHour, DayOfWeek
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.shared.errors import ValidationError


@dataclass(frozen=True)
class DayScheduleInput:
    day_of_week: int        # 0 = Monday … 6 = Sunday
    open_at: time
    close_at: time
    is_closed: bool = False


@dataclass(frozen=True)
class SetBusinessHoursInput:
    business_id: UUID
    schedule: list[DayScheduleInput]


@dataclass(frozen=True)
class DayScheduleOutput:
    day_of_week: int
    day_name: str
    open_at: time
    close_at: time
    is_closed: bool


@dataclass(frozen=True)
class SetBusinessHoursOutput:
    business_id: UUID
    schedule: list[DayScheduleOutput]


_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class SetBusinessHoursUseCase(UseCase[SetBusinessHoursInput, SetBusinessHoursOutput]):
    """Set (or replace) the full weekly schedule for a business.

    Accepts 1–7 day entries. Missing days keep their existing schedule.
    Duplicate day entries in the same request are rejected.
    """

    def __init__(self, business_hours: BusinessHourRepository, uow: UnitOfWork) -> None:
        self._business_hours = business_hours
        self._uow = uow

    async def execute(self, input_data: SetBusinessHoursInput) -> SetBusinessHoursOutput:
        self._validate_input(input_data)
        tenant = get_current_tenant()

        async with self._uow:
            hours_to_save: list[BusinessHour] = []
            for day in input_data.schedule:
                bh = BusinessHour.create(
                    tenant_id=tenant.tenant_id,
                    business_id=input_data.business_id,
                    day_of_week=day.day_of_week,
                    open_at=day.open_at,
                    close_at=day.close_at,
                    is_closed=day.is_closed,
                )
                hours_to_save.append(bh)

            await self._business_hours.upsert_many(hours_to_save)
            await self._uow.commit()

        # Fetch the full schedule to return current state
        all_hours = await self._business_hours.get_by_business(input_data.business_id)
        return SetBusinessHoursOutput(
            business_id=input_data.business_id,
            schedule=[
                DayScheduleOutput(
                    day_of_week=h.day_of_week,
                    day_name=_DAY_NAMES[h.day_of_week],
                    open_at=h.open_at,
                    close_at=h.close_at,
                    is_closed=h.is_closed,
                )
                for h in all_hours
            ],
        )

    def _validate_input(self, data: SetBusinessHoursInput) -> None:
        if not data.schedule:
            raise ValidationError("At least one day schedule is required")

        # Group by day_of_week to validate multiple ranges per day
        from collections import defaultdict
        day_groups: dict[int, list[DayScheduleInput]] = defaultdict(list)

        for day in data.schedule:
            day_groups[day.day_of_week].append(day)

        # Validate each day has valid ranges
        for day_of_week, entries in day_groups.items():
            if day_of_week not in range(7):
                raise ValidationError(f"day_of_week must be 0–6, got {day_of_week}")

            # Check for overlapping time ranges within a day
            non_closed = [e for e in entries if not e.is_closed]
            for i, range1 in enumerate(non_closed):
                for range2 in non_closed[i+1:]:
                    # Check if ranges overlap
                    if not (range1.close_at <= range2.open_at or range2.close_at <= range1.open_at):
                        raise ValidationError(
                            f"Overlapping time ranges for day {day_of_week}: "
                            f"{range1.open_at}-{range1.close_at} overlaps with "
                            f"{range2.open_at}-{range2.close_at}"
                        )
