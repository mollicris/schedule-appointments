from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.appointment.repository import AppointmentRepository
from src.domain.appointment.value_objects import AppointmentStatus
from src.domain.client.repository import ClientRepository
from src.domain.professional.repository import ProfessionalRepository
from src.domain.service.repository import ServiceRepository


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
    service_name: str
    client_id: UUID
    client_name: str
    professional_id: UUID | None
    professional_name: str | None
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
    def __init__(
        self,
        appointments: AppointmentRepository,
        clients: ClientRepository,
        services: ServiceRepository,
        professionals: ProfessionalRepository | None = None,
    ) -> None:
        self._appointments = appointments
        self._clients = clients
        self._services = services
        self._professionals = professionals

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

        summaries = []
        for a in items:
            client = await self._clients.get_by_id(a.client_id)
            client_name = client.name if client else "Unknown Client"

            service = await self._services.get_by_id(a.service_id)
            service_name = service.name if service else "Unknown Service"

            professional_name = None
            if a.professional_id and self._professionals:
                professional = await self._professionals.get_by_id(a.professional_id)
                professional_name = professional.name if professional else None

            summaries.append(
                AppointmentSummary(
                    appointment_id=a.id,
                    service_id=a.service_id,
                    service_name=service_name,
                    client_id=a.client_id,
                    client_name=client_name,
                    professional_id=a.professional_id,
                    professional_name=professional_name,
                    scheduled_at=a.scheduled_at,
                    duration_minutes=a.duration_minutes,
                    ends_at=a.ends_at,
                    status=a.status,
                )
            )

        return ListAppointmentsOutput(
            appointments=summaries,
            total=total,
            page=input_data.page,
            page_size=input_data.page_size,
        )
