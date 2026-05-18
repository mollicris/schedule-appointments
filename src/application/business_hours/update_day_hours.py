from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class UpdateDayHoursInput:
    business_id: UUID
    day_of_week: int
    open_at: time | None = None
    close_at: time | None = None
    is_closed: bool | None = None


@dataclass(frozen=True)
class UpdateDayHoursOutput:
    day_of_week: int
    day_name: str
    open_at: time
    close_at: time
    is_closed: bool


_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class UpdateDayHoursUseCase(UseCase[UpdateDayHoursInput, UpdateDayHoursOutput]):
    """Patch a single day's schedule without touching the rest of the week."""

    def __init__(self, business_hours: BusinessHourRepository, uow: UnitOfWork) -> None:
        self._business_hours = business_hours
        self._uow = uow

    async def execute(self, input_data: UpdateDayHoursInput) -> UpdateDayHoursOutput:
        async with self._uow:
            # Get all ranges for this day (now supports multiple ranges)
            ranges = await self._business_hours.get_by_business_and_day(
                business_id=input_data.business_id,
                day_of_week=input_data.day_of_week,
            )
            if not ranges:
                raise NotFoundError(
                    f"No schedule found for business {input_data.business_id} "
                    f"on day {input_data.day_of_week}"
                )

            # Update the first range (sequence 1)
            bh = ranges[0]
            bh.update(
                open_at=input_data.open_at,
                close_at=input_data.close_at,
                is_closed=input_data.is_closed,
            )

            await self._business_hours.upsert(bh)
            await self._uow.commit()

        return UpdateDayHoursOutput(
            day_of_week=bh.day_of_week,
            day_name=_DAY_NAMES[bh.day_of_week],
            open_at=bh.open_at,
            close_at=bh.close_at,
            is_closed=bh.is_closed,
        )
