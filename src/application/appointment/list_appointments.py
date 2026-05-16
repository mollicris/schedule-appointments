from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.appointment.repository import AppointmentRepository
from src.domain.appointment.value_objects import AppointmentStatus


@dataclass(frozen=True)
class ListAppointmentsInput:
    business_id: UUID
    on_date: date | None = None
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True)
class AppointmentSummary:
    appointment_id: UUID
    service_id: UUID
    client_id: UUID
    professional_id: UUID | None
    scheduled_at: datetime
    duration_minutes: int
    ends_at: datetime
    status: AppointmentStatus


@dataclass(frozen=True)
class ListAppointmentsOutput:
    appointments: list[AppointmentSummary]
    total: int
    page: int
    page_size: int


class ListAppointmentsUseCase(UseCase[ListAppointmentsInput, ListAppointmentsOutput]):
    def __init__(self, appointments: AppointmentRepository) -> None:
        self._appointments = appointments

    async def execute(self, input_data: ListAppointmentsInput) -> ListAppointmentsOutput:
        offset = (input_data.page - 1) * input_data.page_size
        items = await self._appointments.list_by_business(
            business_id=input_data.business_id,
            on_date=input_data.on_date,
            limit=input_data.page_size,
            offset=offset,
        )
        total = await self._appointments.count_by_business(
            business_id=input_data.business_id,
            on_date=input_data.on_date,
        )
        return ListAppointmentsOutput(
            appointments=[
                AppointmentSummary(
                    appointment_id=a.id,
                    service_id=a.service_id,
                    client_id=a.client_id,
                    professional_id=a.professional_id,
                    scheduled_at=a.scheduled_at,
                    duration_minutes=a.duration_minutes,
                    ends_at=a.ends_at,
                    status=a.status,
                )
                for a in items
            ],
            total=total,
            page=input_data.page,
            page_size=input_data.page_size,
        )
