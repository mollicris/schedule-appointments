from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.appointment.repository import AppointmentRepository
from src.domain.appointment.value_objects import AppointmentStatus
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class GetAppointmentInput:
    appointment_id: UUID


@dataclass(frozen=True)
class GetAppointmentOutput:
    appointment_id: UUID
    business_id: UUID
    service_id: UUID
    client_id: UUID
    professional_id: UUID | None
    scheduled_at: datetime
    duration_minutes: int
    ends_at: datetime
    status: AppointmentStatus
    notes: str | None
    cancelled_reason: str | None
    cancelled_at: datetime | None
    created_at: datetime


class GetAppointmentUseCase(UseCase[GetAppointmentInput, GetAppointmentOutput]):
    def __init__(self, appointments: AppointmentRepository) -> None:
        self._appointments = appointments

    async def execute(self, input_data: GetAppointmentInput) -> GetAppointmentOutput:
        apt = await self._appointments.get_by_id(input_data.appointment_id)
        if not apt:
            raise NotFoundError(f"Appointment '{input_data.appointment_id}' not found")

        return GetAppointmentOutput(
            appointment_id=apt.id,
            business_id=apt.business_id,
            service_id=apt.service_id,
            client_id=apt.client_id,
            professional_id=apt.professional_id,
            scheduled_at=apt.scheduled_at,
            duration_minutes=apt.duration_minutes,
            ends_at=apt.ends_at,
            status=apt.status,
            notes=apt.notes,
            cancelled_reason=apt.cancelled_reason,
            cancelled_at=apt.cancelled_at,
            created_at=apt.created_at,
        )
