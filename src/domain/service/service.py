from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from src.domain.shared.entity import TenantAwareEntity
from src.domain.shared.errors import BusinessRuleViolationError


@dataclass(eq=False)
class Service(TenantAwareEntity):
    """Service aggregate root.

    Represents a service offered by a business (haircut, veterinary checkup, etc.).
    Services belong to a business and define duration, pricing, and description.

    `capacity` is how many clients may book the same start time:
      - capacity == 1 (default): one-to-one service. Any overlapping appointment
        blocks the slot.
      - capacity > 1: group class (gym class, workshop). The slot stays open
        while booked < capacity.

    Lifecycle:
        Created → Active (default) → Inactive (soft delete)
    """

    business_id: UUID = UUID(int=0)
    name: str = ""
    description: str | None = None
    duration_minutes: int = 30
    price: int | None = None  # in cents
    capacity: int = 1
    is_active: bool = True

    @property
    def is_group_class(self) -> bool:
        """True when several clients share the same start time."""
        return self.capacity > 1

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        business_id: UUID,
        name: str,
        duration_minutes: int = 30,
        description: str | None = None,
        price: int | None = None,
        capacity: int = 1,
    ) -> Service:
        """Factory for creating a new service."""
        if not name.strip():
            raise BusinessRuleViolationError("Service name cannot be empty")
        if duration_minutes < 1:
            raise BusinessRuleViolationError("Service duration must be at least 1 minute")
        if price is not None and price < 0:
            raise BusinessRuleViolationError("Service price cannot be negative")
        if capacity < 1:
            raise BusinessRuleViolationError("Service capacity must be at least 1")

        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            name=name.strip(),
            duration_minutes=duration_minutes,
            description=description,
            price=price,
            capacity=capacity,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        duration_minutes: int | None = None,
        price: int | None = None,
        capacity: int | None = None,
    ) -> None:
        """Update service details."""
        if name is not None:
            if not name.strip():
                raise BusinessRuleViolationError("Service name cannot be empty")
            self.name = name.strip()

        if duration_minutes is not None:
            if duration_minutes < 1:
                raise BusinessRuleViolationError("Service duration must be at least 1 minute")
            self.duration_minutes = duration_minutes

        if price is not None:
            if price < 0:
                raise BusinessRuleViolationError("Service price cannot be negative")
            self.price = price

        if capacity is not None:
            if capacity < 1:
                raise BusinessRuleViolationError("Service capacity must be at least 1")
            self.capacity = capacity

        if description is not None:
            self.description = description

        self.updated_at = datetime.utcnow()

    def deactivate(self) -> None:
        """Soft delete: mark service as inactive."""
        if not self.is_active:
            return
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def activate(self) -> None:
        """Reactivate an inactive service."""
        if self.is_active:
            return
        self.is_active = True
        self.updated_at = datetime.utcnow()
