from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.business_hours.business_hour import BusinessHour


class BusinessHourRepository(Protocol):
    """Repository port for BusinessHour aggregate.

    All queries are scoped to a single tenant (enforced by RLS).
    A business can have multiple ranges per day_of_week (e.g., lunch breaks).
    """

    async def get_by_business(self, business_id: UUID) -> list[BusinessHour]:
        """Get all ranges for a business across all days (may return fewer if not yet set)."""
        ...

    async def get_by_business_and_day(self, business_id: UUID, day_of_week: int) -> list[BusinessHour]:
        """Get all time ranges for one specific day, ordered by sequence.

        Returns empty list if day is closed or not configured.
        """
        ...

    async def upsert(self, business_hour: BusinessHour) -> None:
        """Insert or replace the schedule entry for a business/day pair."""
        ...

    async def upsert_many(self, business_hours: list[BusinessHour]) -> None:
        """Bulk upsert — used when setting the full weekly schedule at once."""
        ...
