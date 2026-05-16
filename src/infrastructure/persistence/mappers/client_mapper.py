from __future__ import annotations

from src.domain.client.client import Client
from src.infrastructure.persistence.models.client import ClientModel


class ClientMapper:
    @staticmethod
    def to_model(client: Client) -> ClientModel:
        """Domain → ORM."""
        return ClientModel(
            id=client.id,
            tenant_id=client.tenant_id,
            whatsapp_number=client.whatsapp_number,
            name=client.name,
            email=client.email,
            phone=client.phone,
            notes=client.notes,
            is_active=client.is_active,
            appointment_count=client.appointment_count,
            last_appointment_at=client.last_appointment_at,
            last_interaction_at=client.last_interaction_at,
            created_at=client.created_at,
            updated_at=client.updated_at,
        )

    @staticmethod
    def to_domain(model: ClientModel) -> Client:
        """ORM → Domain."""
        return Client(
            id=model.id,
            tenant_id=model.tenant_id,
            whatsapp_number=model.whatsapp_number,
            name=model.name,
            email=model.email,
            phone=model.phone,
            notes=model.notes,
            is_active=model.is_active,
            appointment_count=model.appointment_count,
            last_appointment_at=model.last_appointment_at,
            last_interaction_at=model.last_interaction_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
