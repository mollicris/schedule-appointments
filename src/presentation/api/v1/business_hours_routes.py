from __future__ import annotations

from datetime import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, model_validator

from src.application.business_hours.get_business_hours import (
    GetBusinessHoursInput,
    GetBusinessHoursOutput,
    GetBusinessHoursUseCase,
)
from src.application.business_hours.set_business_hours import (
    DayScheduleInput,
    SetBusinessHoursInput,
    SetBusinessHoursOutput,
    SetBusinessHoursUseCase,
)
from src.application.business_hours.update_day_hours import (
    UpdateDayHoursInput,
    UpdateDayHoursOutput,
    UpdateDayHoursUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.business_hours.repository import BusinessHourRepository
from src.presentation.dependencies import (
    get_business_hours_repository,
    get_unit_of_work,
)
from src.presentation.schemas import SuccessResponse, success_response

router = APIRouter(prefix="/businesses/{business_id}/hours", tags=["business-hours"])


class DayScheduleRequest(BaseModel):
    day_of_week: int = Field(ge=0, le=6, description="0=Monday … 6=Sunday")
    open_at: time
    close_at: time
    is_closed: bool = False

    @model_validator(mode="after")
    def close_after_open(self) -> DayScheduleRequest:
        if not self.is_closed and self.close_at <= self.open_at:
            raise ValueError("close_at must be after open_at")
        return self


class SetBusinessHoursRequest(BaseModel):
    schedule: list[DayScheduleRequest] = Field(min_length=1, max_length=7)


class UpdateDayHoursRequest(BaseModel):
    open_at: time | None = None
    close_at: time | None = None
    is_closed: bool | None = None


class DayScheduleResponse(BaseModel):
    day_of_week: int
    day_name: str
    open_at: time
    close_at: time
    is_closed: bool


class BusinessHoursResponse(BaseModel):
    business_id: UUID
    schedule: list[DayScheduleResponse]


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Get weekly schedule",
    description="Retrieve the full operating schedule for the business.",
)
async def get_business_hours(
    business_id: UUID,
    business_hours: Annotated[BusinessHourRepository, Depends(get_business_hours_repository)],
) -> SuccessResponse:
    use_case = GetBusinessHoursUseCase(business_hours=business_hours)
    output: GetBusinessHoursOutput = await use_case.execute(
        GetBusinessHoursInput(business_id=business_id)
    )
    return success_response(
        message="Business hours retrieved successfully",
        code="BUSINESS_HOURS_FOUND",
        data=BusinessHoursResponse(
            business_id=output.business_id,
            schedule=[
                DayScheduleResponse(
                    day_of_week=d.day_of_week,
                    day_name=d.day_name,
                    open_at=d.open_at,
                    close_at=d.close_at,
                    is_closed=d.is_closed,
                )
                for d in output.schedule
            ],
        ),
    )


@router.put(
    "",
    status_code=status.HTTP_200_OK,
    summary="Set weekly schedule",
    description=(
        "Set (or replace) business hours for one or more days. "
        "Missing days keep their current schedule. "
        "Sending all 7 days replaces the full week."
    ),
)
async def set_business_hours(
    business_id: UUID,
    payload: SetBusinessHoursRequest,
    business_hours: Annotated[BusinessHourRepository, Depends(get_business_hours_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = SetBusinessHoursUseCase(business_hours=business_hours, uow=uow)
    output: SetBusinessHoursOutput = await use_case.execute(
        SetBusinessHoursInput(
            business_id=business_id,
            schedule=[
                DayScheduleInput(
                    day_of_week=d.day_of_week,
                    open_at=d.open_at,
                    close_at=d.close_at,
                    is_closed=d.is_closed,
                )
                for d in payload.schedule
            ],
        )
    )
    return success_response(
        message="Business hours updated successfully",
        code="BUSINESS_HOURS_UPDATED",
        data=BusinessHoursResponse(
            business_id=output.business_id,
            schedule=[
                DayScheduleResponse(
                    day_of_week=d.day_of_week,
                    day_name=d.day_name,
                    open_at=d.open_at,
                    close_at=d.close_at,
                    is_closed=d.is_closed,
                )
                for d in output.schedule
            ],
        ),
    )


@router.patch(
    "/{day_of_week}",
    status_code=status.HTTP_200_OK,
    summary="Update a single day",
    description="Patch one day's schedule (open_at, close_at, or is_closed) without changing others.",
)
async def update_day_hours(
    business_id: UUID,
    day_of_week: int,
    payload: UpdateDayHoursRequest,
    business_hours: Annotated[BusinessHourRepository, Depends(get_business_hours_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = UpdateDayHoursUseCase(business_hours=business_hours, uow=uow)
    output: UpdateDayHoursOutput = await use_case.execute(
        UpdateDayHoursInput(
            business_id=business_id,
            day_of_week=day_of_week,
            open_at=payload.open_at,
            close_at=payload.close_at,
            is_closed=payload.is_closed,
        )
    )
    return success_response(
        message="Day schedule updated successfully",
        code="DAY_HOURS_UPDATED",
        data=DayScheduleResponse(
            day_of_week=output.day_of_week,
            day_name=output.day_name,
            open_at=output.open_at,
            close_at=output.close_at,
            is_closed=output.is_closed,
        ),
    )
