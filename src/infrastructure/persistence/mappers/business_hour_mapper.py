from __future__ import annotations

from src.domain.business_hours.business_hour import BusinessHour
from src.infrastructure.persistence.models import BusinessHourModel


class BusinessHourMapper:
    """Map between domain BusinessHour aggregate and ORM BusinessHourModel."""

    @staticmethod
    def fromPersistence(bh: BusinessHour) -> BusinessHourModel:
        """Domain → ORM."""
        return BusinessHourModel(
            id=bh.id,
            tenant_id=bh.tenant_id,
            business_id=bh.business_id,
            day_of_week=str(bh.day_of_week),
            open_at=bh.open_at,
            close_at=bh.close_at,
            is_closed=bh.is_closed,
            created_at=bh.created_at,
            updated_at=bh.updated_at,
        )

    @staticmethod
    def toPersistence(model: BusinessHourModel | None) -> BusinessHour | None:
        """ORM → Domain."""
        if not model:
            return None

        return BusinessHour(
            id=model.id,
            tenant_id=model.tenant_id,
            business_id=model.business_id,
            day_of_week=int(model.day_of_week),
            open_at=model.open_at,
            close_at=model.close_at,
            is_closed=model.is_closed,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
