from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.business_hours.business_hour import BusinessHour


class BusinessHourRepository(Protocol):
    """Repository port for BusinessHour aggregate.

    All queries are scoped to a single tenant (enforced by RLS).
    A business has at most one record per day_of_week.
    """

    async def get_by_business(self, business_id: UUID) -> list[BusinessHour]:
        """Get all 7 day-entries for a business (may return fewer if not yet set)."""
        ...

    async def get_by_business_and_day(self, business_id: UUID, day_of_week: int) -> BusinessHour | None:
        """Get the schedule for one specific day."""
        ...

    async def upsert(self, business_hour: BusinessHour) -> None:
        """Insert or replace the schedule entry for a business/day pair."""
        ...

    async def upsert_many(self, business_hours: list[BusinessHour]) -> None:
        """Bulk upsert — used when setting the full weekly schedule at once."""
        ...
