from __future__ import annotations

from src.domain.service.service import Service
from src.infrastructure.persistence.models import ServiceModel


class ServiceMapper:
    """Map between domain Service aggregate and ORM ServiceModel."""

    @staticmethod
    def fromPersistence(service: Service) -> ServiceModel:
        """Domain → ORM."""
        return ServiceModel(
            id=service.id,
            tenant_id=service.tenant_id,
            business_id=service.business_id,
            name=service.name,
            description=service.description,
            duration_minutes=service.duration_minutes,
            price=service.price,
            is_active=service.is_active,
            created_at=service.created_at,
            updated_at=service.updated_at,
        )

    @staticmethod
    def toPersistence(model: ServiceModel | None) -> Service | None:
        """ORM → Domain."""
        if not model:
            return None

        return Service(
            id=model.id,
            tenant_id=model.tenant_id,
            business_id=model.business_id,
            name=model.name,
            description=model.description,
            duration_minutes=model.duration_minutes,
            price=model.price,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
