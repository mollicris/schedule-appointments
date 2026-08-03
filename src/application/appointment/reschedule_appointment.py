from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from src.application.appointment.slot_occupancy import evaluate_slot
from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.appointment.repository import AppointmentRepository
from src.domain.appointment.value_objects import AppointmentStatus
from src.domain.service.repository import ServiceRepository
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
    spots_left: int | None = None   # free places at the new time (group classes)


class RescheduleAppointmentUseCase(UseCase[RescheduleAppointmentInput, RescheduleAppointmentOutput]):
    """Reschedule an existing appointment to a new time.

    Checks the new slot with the same rules as booking (``evaluate_slot``), so
    group-class capacity is respected here too. The appointment being moved is
    excluded from the count.

    ``services`` is optional: without it every service is treated as one-to-one,
    which is the historical behaviour.
    """

    def __init__(
        self,
        appointments: AppointmentRepository,
        uow: UnitOfWork,
        services: ServiceRepository | None = None,
    ) -> None:
        self._appointments = appointments
        self._services = services
        self._uow = uow

    async def execute(self, input_data: RescheduleAppointmentInput) -> RescheduleAppointmentOutput:
        if input_data.new_scheduled_at.tzinfo is None:
            raise ValidationError("new_scheduled_at must be timezone-aware (UTC)")

        async with self._uow:
            apt = await self._appointments.get_by_id(input_data.appointment_id)
            if not apt:
                raise NotFoundError(f"Appointment '{input_data.appointment_id}' not found")

            capacity = 1
            capacity_by_service: dict[UUID, int] = {}
            if self._services is not None:
                # Lock first so a concurrent booking cannot fill the class in between
                service = await self._services.lock_for_update(apt.service_id)
                if service is not None:
                    capacity = service.capacity

            new_end = input_data.new_scheduled_at + timedelta(minutes=apt.duration_minutes)
            booked = await self._appointments.list_active_in_range(
                business_id=apt.business_id,
                start=input_data.new_scheduled_at,
                end=new_end,
                professional_id=apt.professional_id,
            )

            if self._services is not None:
                capacity_by_service = await self._services.get_capacity_map(
                    list({a.service_id for a in booked} | {apt.service_id})
                )

            evaluation = evaluate_slot(
                slot_start=input_data.new_scheduled_at,
                slot_end=new_end,
                service_id=apt.service_id,
                capacity=capacity,
                booked=booked,
                capacity_by_service=capacity_by_service,
                exclude_appointment_id=apt.id,
            )
            if not evaluation.is_bookable:
                if capacity > 1 and not evaluation.blocked:
                    raise ConflictError("This class is already full. Please choose another time.")
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
            spots_left=(evaluation.remaining - 1) if capacity > 1 else None,
        )
