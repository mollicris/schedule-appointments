from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from src.application.appointment.slot_occupancy import SlotEvaluation, evaluate_slot
from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.appointment.appointment import Appointment
from src.domain.appointment.repository import AppointmentRepository
from src.domain.appointment.value_objects import AppointmentStatus
from src.domain.client.client import Client
from src.domain.client.repository import ClientRepository
from src.domain.professional.repository import ProfessionalRepository
from src.domain.service.repository import ServiceRepository
from src.domain.service.service import Service
from src.domain.shared.errors import ConflictError, NotFoundError, ValidationError


@dataclass(frozen=True)
class BookAppointmentInput:
    business_id: UUID
    service_id: UUID
    scheduled_at: datetime          # UTC-aware
    client_name: str
    client_whatsapp: str            # E.164, used to find-or-create the client
    professional_id: UUID | None = None
    notes: str | None = None
    client_email: str | None = None


@dataclass(frozen=True)
class BookAppointmentOutput:
    appointment_id: UUID
    business_id: UUID
    service_id: UUID
    client_id: UUID
    professional_id: UUID | None
    scheduled_at: datetime
    duration_minutes: int
    status: AppointmentStatus
    ends_at: datetime
    spots_left: int | None = None   # free places after this booking (group classes)
    already_booked: bool = False    # True when the client already had this seat


class BookAppointmentUseCase(UseCase[BookAppointmentInput, BookAppointmentOutput]):
    """Book a new appointment.

    Flow:
      1. Load and validate service (must exist, must be active).
      2. Find-or-create client by WhatsApp number.
      3. Lock the service row and re-check availability inside the transaction
         (race-condition guard, and capacity guard for group classes).
      4. Create and persist Appointment in PENDING status.

    Availability is decided by ``evaluate_slot`` — the same helper that produced
    the offered slots — so a slot the agent offered is still validated here
    against concurrent bookings.
    """

    def __init__(
        self,
        appointments: AppointmentRepository,
        services: ServiceRepository,
        clients: ClientRepository,
        uow: UnitOfWork,
        professionals: ProfessionalRepository | None = None,
    ) -> None:
        self._appointments = appointments
        self._services = services
        self._clients = clients
        self._professionals = professionals
        self._uow = uow

    async def execute(self, input_data: BookAppointmentInput) -> BookAppointmentOutput:
        self._validate_input(input_data)
        tenant = get_current_tenant()

        async with self._uow:
            # 1. Validate service
            service = await self._services.get_by_id(input_data.service_id)
            if not service or not service.is_active:
                raise NotFoundError(f"Service '{input_data.service_id}' not found or inactive")
            if service.business_id != input_data.business_id:
                raise ValidationError("Service does not belong to this business")

            # 1b. Validate professional (if provided)
            if input_data.professional_id is not None and self._professionals is not None:
                professional = await self._professionals.get_by_id(input_data.professional_id)
                if not professional:
                    raise NotFoundError(
                        f"Professional '{input_data.professional_id}' not found"
                    )
                if professional.business_id != input_data.business_id:
                    raise ValidationError("Professional does not belong to this business")
                if not professional.is_active:
                    raise ValidationError("Professional is inactive")

                # If the service has explicit professional assignments, enforce them.
                # No assignments = anyone can do it (intentional fallback).
                assigned_ids = await self._services.list_professional_ids(service.id)
                if assigned_ids and input_data.professional_id not in assigned_ids:
                    raise ValidationError(
                        "This professional cannot perform the selected service"
                    )

            # 2. Find or create client
            client = await self._clients.get_by_whatsapp(input_data.client_whatsapp)
            if client is None:
                client = Client.create(
                    tenant_id=tenant.tenant_id,
                    whatsapp_number=input_data.client_whatsapp,
                    name=input_data.client_name,
                    email=input_data.client_email,
                )
                await self._clients.add(client)

            # 3. Idempotency: the same client, service and start time is the same
            # booking. A client confirming twice — or an agent re-issuing the call
            # in a later turn — must not take two seats in the same class.
            existing = await self._appointments.get_active_for_client_at(
                client_id=client.id,
                service_id=service.id,
                scheduled_at=input_data.scheduled_at,
            )
            if existing is not None:
                await self._uow.commit()
                return BookAppointmentOutput(
                    appointment_id=existing.id,
                    business_id=existing.business_id,
                    service_id=existing.service_id,
                    client_id=existing.client_id,
                    professional_id=existing.professional_id,
                    scheduled_at=existing.scheduled_at,
                    duration_minutes=existing.duration_minutes,
                    status=existing.status,
                    ends_at=existing.ends_at,
                    already_booked=True,
                )

            # 4. Re-check availability inside the transaction (capacity + races)
            evaluation = await self._ensure_slot_available(input_data, service)

            # 5. Book
            appointment = Appointment.book(
                tenant_id=tenant.tenant_id,
                business_id=input_data.business_id,
                service_id=input_data.service_id,
                client_id=client.id,
                professional_id=input_data.professional_id,
                scheduled_at=input_data.scheduled_at,
                duration_minutes=service.duration_minutes,
                notes=input_data.notes,
            )
            await self._appointments.add(appointment)

            # Update client stats
            client.increment_appointment_count(at=input_data.scheduled_at)
            await self._clients.update(client)

            await self._uow.commit()

        return BookAppointmentOutput(
            appointment_id=appointment.id,
            business_id=appointment.business_id,
            service_id=appointment.service_id,
            client_id=appointment.client_id,
            professional_id=appointment.professional_id,
            scheduled_at=appointment.scheduled_at,
            duration_minutes=appointment.duration_minutes,
            status=appointment.status,
            ends_at=appointment.ends_at,
            spots_left=(evaluation.remaining - 1) if service.capacity > 1 else None,
        )

    async def _ensure_slot_available(
        self,
        input_data: BookAppointmentInput,
        service: Service,
    ) -> SlotEvaluation:
        """Re-check the slot inside the transaction; raise if it cannot be booked.

        Locking the service row first serialises concurrent bookings of the same
        group class, so the capacity count cannot be stale.
        """
        await self._services.lock_for_update(service.id)

        slot_end = input_data.scheduled_at + timedelta(minutes=service.duration_minutes)
        booked = await self._appointments.list_active_in_range(
            business_id=input_data.business_id,
            start=input_data.scheduled_at,
            end=slot_end,
            professional_id=input_data.professional_id,
        )
        capacity_by_service = await self._services.get_capacity_map(
            list({apt.service_id for apt in booked} | {service.id})
        )
        evaluation = evaluate_slot(
            slot_start=input_data.scheduled_at,
            slot_end=slot_end,
            service_id=service.id,
            capacity=service.capacity,
            booked=booked,
            capacity_by_service=capacity_by_service,
        )

        if evaluation.is_bookable:
            return evaluation

        if service.capacity > 1 and not evaluation.blocked:
            raise ConflictError("This class is already full. Please choose another time.")
        raise ConflictError(
            "The requested time slot is no longer available. Please choose another time."
        )

    def _validate_input(self, data: BookAppointmentInput) -> None:
        if not data.client_name.strip():
            raise ValidationError("Client name is required")
        if not data.client_whatsapp.strip():
            raise ValidationError("Client WhatsApp number is required")
        if data.scheduled_at.tzinfo is None:
            raise ValidationError("scheduled_at must be timezone-aware (UTC)")
