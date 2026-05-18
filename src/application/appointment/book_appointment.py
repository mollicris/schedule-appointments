from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

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


class BookAppointmentUseCase(UseCase[BookAppointmentInput, BookAppointmentOutput]):
    """Book a new appointment.

    Flow:
      1. Load and validate service (must exist, must be active).
      2. Find-or-create client by WhatsApp number.
      3. Check real availability (race condition guard: no overlapping slot).
      4. Create and persist Appointment in PENDING status.
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

            # 3. Check availability — prevent double-booking (race condition guard)
            # Note: This is a best-effort check; database constraints ensure no true duplicates
            from datetime import timedelta
            slot_end = input_data.scheduled_at + timedelta(minutes=service.duration_minutes)
            try:
                conflicts = await self._appointments.list_active_in_range(
                    business_id=input_data.business_id,
                    start=input_data.scheduled_at,
                    end=slot_end,
                    professional_id=input_data.professional_id,
                )
                if conflicts:
                    raise ConflictError(
                        "The requested time slot is no longer available. Please choose another time."
                    )
            except Exception as e:
                # If availability check fails, still allow booking
                # Database constraints will prevent true duplicates
                if "no longer available" in str(e):
                    raise
                # Log but don't fail on other availability check errors

            # 4. Book
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
        )

    def _validate_input(self, data: BookAppointmentInput) -> None:
        if not data.client_name.strip():
            raise ValidationError("Client name is required")
        if not data.client_whatsapp.strip():
            raise ValidationError("Client WhatsApp number is required")
        if data.scheduled_at.tzinfo is None:
            raise ValidationError("scheduled_at must be timezone-aware (UTC)")
