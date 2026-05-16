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
                for h in sorted(all_hours, key=lambda x: x.day_of_week)
            ],
        )

    def _validate_input(self, data: SetBusinessHoursInput) -> None:
        if not data.schedule:
            raise ValidationError("At least one day schedule is required")
        seen_days: set[int] = set()
        for day in data.schedule:
            if day.day_of_week in seen_days:
                raise ValidationError(
                    f"Duplicate entry for day_of_week={day.day_of_week}"
                )
            seen_days.add(day.day_of_week)
