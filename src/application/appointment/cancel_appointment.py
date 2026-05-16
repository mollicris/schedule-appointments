from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.appointment.repository import AppointmentRepository
from src.domain.appointment.value_objects import AppointmentStatus
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class CancelAppointmentInput:
    appointment_id: UUID
    reason: str | None = None


@dataclass(frozen=True)
class CancelAppointmentOutput:
    appointment_id: UUID
    status: AppointmentStatus


class CancelAppointmentUseCase(UseCase[CancelAppointmentInput, CancelAppointmentOutput]):
    def __init__(self, appointments: AppointmentRepository, uow: UnitOfWork) -> None:
        self._appointments = appointments
        self._uow = uow

    async def execute(self, input_data: CancelAppointmentInput) -> CancelAppointmentOutput:
        async with self._uow:
            apt = await self._appointments.get_by_id(input_data.appointment_id)
            if not apt:
                raise NotFoundError(f"Appointment '{input_data.appointment_id}' not found")

            apt.cancel(reason=input_data.reason)
            await self._appointments.update(apt)
            await self._uow.commit()

        return CancelAppointmentOutput(
            appointment_id=apt.id,
            status=apt.status,
        )
