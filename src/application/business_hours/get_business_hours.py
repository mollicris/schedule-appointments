from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.business_hours.repository import BusinessHourRepository


@dataclass(frozen=True)
class GetBusinessHoursInput:
    business_id: UUID


@dataclass(frozen=True)
class DayScheduleOutput:
    day_of_week: int
    day_name: str
    open_at: time
    close_at: time
    is_closed: bool


@dataclass(frozen=True)
class GetBusinessHoursOutput:
    business_id: UUID
    schedule: list[DayScheduleOutput]


_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class GetBusinessHoursUseCase(UseCase[GetBusinessHoursInput, GetBusinessHoursOutput]):
    """Get the full weekly schedule for a business."""

    def __init__(self, business_hours: BusinessHourRepository) -> None:
        self._business_hours = business_hours

    async def execute(self, input_data: GetBusinessHoursInput) -> GetBusinessHoursOutput:
        hours = await self._business_hours.get_by_business(input_data.business_id)

        return GetBusinessHoursOutput(
            business_id=input_data.business_id,
            schedule=[
                DayScheduleOutput(
                    day_of_week=h.day_of_week,
                    day_name=_DAY_NAMES[h.day_of_week],
                    open_at=h.open_at,
                    close_at=h.close_at,
                    is_closed=h.is_closed,
                )
                for h in hours
            ],
        )
