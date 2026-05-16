from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.professional.professional import Professional


class ProfessionalRepository(Protocol):
    """Repository port for Professional aggregate.

    All queries are scoped to a single tenant (enforced by RLS).
    """

    async def get_by_id(self, professional_id: UUID) -> Professional | None:
        """Get a professional by ID."""
        ...

    async def get_by_user_and_business(self, user_id: UUID, business_id: UUID) -> Professional | None:
        """Get a professional by their user account and business (unique pair)."""
        ...

    async def list_by_business(self, business_id: UUID, limit: int = 50, offset: int = 0) -> list[Professional]:
        """List active professionals for a specific business (paginated)."""
        ...

    async def count_by_business(self, business_id: UUID) -> int:
        """Count active professionals for a specific business."""
        ...

    async def user_in_business_exists(self, user_id: UUID, business_id: UUID) -> bool:
        """Check if a user is already registered as a professional in this business."""
        ...

    async def add(self, professional: Professional) -> None:
        """Create a new professional."""
        ...

    async def update(self, professional: Professional) -> None:
        """Update an existing professional."""
        ...

    async def delete(self, professional_id: UUID) -> bool:
        """Soft delete a professional (returns True if found, False otherwise)."""
        ...
