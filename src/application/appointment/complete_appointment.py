from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.appointment.repository import AppointmentRepository
from src.domain.appointment.value_objects import AppointmentStatus
from src.domain.shared.errors import ConflictError, NotFoundError


@dataclass(frozen=True)
class CompleteAppointmentInput:
    appointment_id: UUID
    amount_charged: int          # in cents; 0 means the service was not charged
    note: str | None = None


@dataclass(frozen=True)
class CompleteAppointmentOutput:
    appointment_id: UUID
    status: AppointmentStatus
    amount_charged: int
    completed_at: datetime


class CompleteAppointmentUseCase(UseCase[CompleteAppointmentInput, CompleteAppointmentOutput]):
    """Close an appointment with what was actually collected.

    This is what makes the revenue reports work: until an appointment is closed
    it contributes nothing, and the amount recorded here is the figure the
    reports sum — never the service's current price, which changes.
    """

    def __init__(self, appointments: AppointmentRepository, uow: UnitOfWork) -> None:
        self._appointments = appointments
        self._uow = uow

    async def execute(self, input_data: CompleteAppointmentInput) -> CompleteAppointmentOutput:
        async with self._uow:
            apt = await self._appointments.get_by_id(input_data.appointment_id)
            if not apt:
                raise NotFoundError(f"Appointment '{input_data.appointment_id}' not found")

            # Already closed is its own answer, not a rule violation: two tabs or
            # a double click must read as "someone got there first", so the panel
            # can say so calmly instead of showing a failure.
            if apt.status == AppointmentStatus.COMPLETED:
                raise ConflictError("This appointment was already marked as attended")

            apt.complete(amount_charged=input_data.amount_charged)
            if input_data.note:
                apt.notes = f"{apt.notes}\n{input_data.note}" if apt.notes else input_data.note

            await self._appointments.update(apt)
            await self._uow.commit()

        return CompleteAppointmentOutput(
            appointment_id=apt.id,
            status=apt.status,
            amount_charged=apt.amount_charged or 0,
            completed_at=apt.completed_at,
        )
