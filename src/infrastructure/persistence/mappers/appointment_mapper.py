from __future__ import annotations

from src.domain.appointment.appointment import Appointment
from src.domain.appointment.value_objects import AppointmentStatus
from src.infrastructure.persistence.models.appointment import AppointmentModel


class AppointmentMapper:
    @staticmethod
    def to_model(appointment: Appointment) -> AppointmentModel:
        """Domain → ORM."""
        return AppointmentModel(
            id=appointment.id,
            tenant_id=appointment.tenant_id,
            business_id=appointment.business_id,
            service_id=appointment.service_id,
            professional_id=appointment.professional_id,
            client_id=appointment.client_id,
            scheduled_at=appointment.scheduled_at,
            duration_minutes=appointment.duration_minutes,
            status=appointment.status.value,
            notes=appointment.notes,
            cancelled_reason=appointment.cancelled_reason,
            cancelled_at=appointment.cancelled_at,
            created_at=appointment.created_at,
            updated_at=appointment.updated_at,
        )

    @staticmethod
    def to_domain(model: AppointmentModel) -> Appointment:
        """ORM → Domain."""
        return Appointment(
            id=model.id,
            tenant_id=model.tenant_id,
            business_id=model.business_id,
            service_id=model.service_id,
            professional_id=model.professional_id,
            client_id=model.client_id,
            scheduled_at=model.scheduled_at,
            duration_minutes=model.duration_minutes,
            status=AppointmentStatus(model.status),
            notes=model.notes,
            cancelled_reason=model.cancelled_reason,
            cancelled_at=model.cancelled_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
