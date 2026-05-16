from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.appointment.repository import AppointmentRepository
from src.domain.appointment.value_objects import AppointmentStatus
from src.domain.shared.errors import ConflictError, NotFoundError, ValidationError


@dataclass(frozen=True)
class RescheduleAppointmentInput:
    appointment_id: UUID
    new_scheduled_at: datetime   # UTC-aware


@dataclass(frozen=True)
class RescheduleAppointmentOutput:
    appointment_id: UUID
    scheduled_at: datetime
    duration_minutes: int
    ends_at: datetime
    status: AppointmentStatus


class RescheduleAppointmentUseCase(UseCase[RescheduleAppointmentInput, RescheduleAppointmentOutput]):
    """Reschedule an existing appointment to a new time.

    Checks for conflicts at the new slot before updating.
    """

    def __init__(self, appointments: AppointmentRepository, uow: UnitOfWork) -> None:
        self._appointments = appointments
        self._uow = uow

    async def execute(self, input_data: RescheduleAppointmentInput) -> RescheduleAppointmentOutput:
        if input_data.new_scheduled_at.tzinfo is None:
            raise ValidationError("new_scheduled_at must be timezone-aware (UTC)")

        async with self._uow:
            apt = await self._appointments.get_by_id(input_data.appointment_id)
            if not apt:
                raise NotFoundError(f"Appointment '{input_data.appointment_id}' not found")

            # Check new slot availability (excluding this appointment)
            from datetime import timedelta
            new_end = input_data.new_scheduled_at + timedelta(minutes=apt.duration_minutes)
            conflicts = await self._appointments.list_active_in_range(
                business_id=apt.business_id,
                start=input_data.new_scheduled_at,
                end=new_end,
                professional_id=apt.professional_id,
            )
            # Exclude self
            conflicts = [c for c in conflicts if c.id != apt.id]
            if conflicts:
                raise ConflictError(
                    "The requested time slot is no longer available. Please choose another time."
                )

            apt.reschedule(new_scheduled_at=input_data.new_scheduled_at)
            await self._appointments.update(apt)
            await self._uow.commit()

        return RescheduleAppointmentOutput(
            appointment_id=apt.id,
            scheduled_at=apt.scheduled_at,
            duration_minutes=apt.duration_minutes,
            ends_at=apt.ends_at,
            status=apt.status,
        )
