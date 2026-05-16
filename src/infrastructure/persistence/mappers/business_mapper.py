from __future__ import annotations

from src.domain.business.business import Business
from src.infrastructure.persistence.models import BusinessModel


class BusinessMapper:
    """Map between domain Business aggregate and ORM BusinessModel."""

    @staticmethod
    def fromPersistence(business: Business) -> BusinessModel:
        """Domain → ORM."""
        return BusinessModel(
            id=business.id,
            tenant_id=business.tenant_id,
            name=business.name,
            slug=business.slug,
            description=business.description,
            phone=business.phone,
            email=business.email,
            address=business.address,
            timezone=business.timezone,
            is_active=business.is_active,
            created_at=business.created_at,
            updated_at=business.updated_at,
        )

    @staticmethod
    def toPersistence(model: BusinessModel | None) -> Business | None:
        """ORM → Domain."""
        if not model:
            return None

        return Business(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            slug=model.slug,
            description=model.description,
            phone=model.phone,
            email=model.email,
            address=model.address,
            timezone=model.timezone,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
