from __future__ import annotations

from src.domain.professional.professional import Professional
from src.infrastructure.persistence.models import ProfessionalModel


class ProfessionalMapper:
    """Map between domain Professional aggregate and ORM ProfessionalModel."""

    @staticmethod
    def fromPersistence(professional: Professional) -> ProfessionalModel:
        """Domain → ORM."""
        return ProfessionalModel(
            id=professional.id,
            tenant_id=professional.tenant_id,
            business_id=professional.business_id,
            user_id=professional.user_id,
            name=professional.name,
            phone=professional.phone,
            is_active=professional.is_active,
            created_at=professional.created_at,
            updated_at=professional.updated_at,
        )

    @staticmethod
    def toPersistence(model: ProfessionalModel | None) -> Professional | None:
        """ORM → Domain."""
        if not model:
            return None

        return Professional(
            id=model.id,
            tenant_id=model.tenant_id,
            business_id=model.business_id,
            user_id=model.user_id,
            name=model.name,
            phone=model.phone,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
