from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.service.service import Service


class ServiceRepository(Protocol):
    """Repository port for Service aggregate.

    All queries are scoped to a single tenant (enforced by RLS).
    """

    async def get_by_id(self, service_id: UUID) -> Service | None:
        """Get a service by ID."""
        ...

    async def list_by_business(self, business_id: UUID, limit: int = 50, offset: int = 0) -> list[Service]:
        """List active services for a specific business (paginated)."""
        ...

    async def count_by_business(self, business_id: UUID) -> int:
        """Count active services for a specific business."""
        ...

    async def get_capacity_map(self, service_ids: list[UUID]) -> dict[UUID, int]:
        """Return service_id → capacity for the given ids (includes inactive ones).

        Used when evaluating slots: the capacity of an already-booked service
        decides whether it blocks a group class.
        """
        ...

    async def lock_for_update(self, service_id: UUID) -> Service | None:
        """Get a service taking a row lock (SELECT … FOR UPDATE).

        Serialises concurrent bookings of the same group class so capacity is
        counted reliably. Must run inside a transaction.
        """
        ...

    async def add(self, service: Service) -> None:
        """Create a new service."""
        ...

    async def update(self, service: Service) -> None:
        """Update an existing service."""
        ...

    async def delete(self, service_id: UUID) -> bool:
        """Soft delete a service (returns True if found, False otherwise)."""
        ...

    async def list_professional_ids(self, service_id: UUID) -> list[UUID]:
        """Return the IDs of professionals that can perform this service."""
        ...

    async def set_professionals(self, service_id: UUID, professional_ids: list[UUID]) -> None:
        """Replace the set of professionals assigned to a service."""
        ...
