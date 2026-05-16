from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.business.business import Business


class BusinessRepository(Protocol):
    """Repository port for Business aggregate.

    All queries are scoped to a single tenant (enforced by RLS).
    """

    async def get_by_id(self, business_id: UUID) -> Business | None:
        """Get a business by ID."""
        ...

    async def get_by_slug(self, slug: str) -> Business | None:
        """Get a business by slug (unique per tenant)."""
        ...

    async def list_active(self, limit: int = 50, offset: int = 0) -> list[Business]:
        """List active businesses for the current tenant (paginated)."""
        ...

    async def count_active(self) -> int:
        """Count active businesses for the current tenant."""
        ...

    async def slug_exists(self, slug: str) -> bool:
        """Check if a slug is already taken (within this tenant)."""
        ...

    async def add(self, business: Business) -> None:
        """Create a new business."""
        ...

    async def update(self, business: Business) -> None:
        """Update an existing business."""
        ...

    async def delete(self, business_id: UUID) -> bool:
        """Soft delete a business (returns True if found, False otherwise)."""
        ...
