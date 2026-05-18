from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from src.domain.shared.entity import TenantAwareEntity
from src.domain.shared.errors import BusinessRuleViolationError


@dataclass(eq=False)
class Professional(TenantAwareEntity):
    """Professional aggregate root.

    Represents a staff member who provides services at a business
    (stylist, vet, mechanic, etc.). Linked to a User account for login.

    Lifecycle:
        Created → Active (default) → Inactive (soft delete)
    """

    business_id: UUID = UUID(int=0)
    user_id: UUID | None = None
    name: str = ""
    phone: str | None = None
    is_active: bool = True

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        business_id: UUID,
        name: str,
        user_id: UUID | None = None,
        phone: str | None = None,
    ) -> Professional:
        """Factory for creating a new professional."""
        if not name.strip():
            raise BusinessRuleViolationError("Professional name cannot be empty")

        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            user_id=user_id,
            name=name.strip(),
            phone=phone.strip() if phone else None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        name: str | None = None,
        phone: str | None = None,
    ) -> None:
        """Update professional details."""
        if name is not None:
            if not name.strip():
                raise BusinessRuleViolationError("Professional name cannot be empty")
            self.name = name.strip()

        if phone is not None:
            self.phone = phone.strip() if phone.strip() else None

        self.updated_at = datetime.utcnow()

    def deactivate(self) -> None:
        """Soft delete: mark professional as inactive."""
        if not self.is_active:
            return
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def activate(self) -> None:
        """Reactivate an inactive professional."""
        if self.is_active:
            return
        self.is_active = True
        self.updated_at = datetime.utcnow()
