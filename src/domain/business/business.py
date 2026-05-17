from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from src.domain.shared.entity import TenantAwareEntity
from src.domain.shared.errors import BusinessRuleViolationError


@dataclass(eq=False)
class Business(TenantAwareEntity):
    """Business aggregate root.

    Represents a physical or virtual business location (salon, vet clinic,
    workshop, etc.) that belongs to a tenant. A tenant can have multiple
    businesses for multi-location support.

    Lifecycle:
        Created → Active (default) → Inactive (soft delete)
    """

    name: str = ""
    slug: str = ""  # URL-friendly, unique per tenant
    description: str | None = None
    phone: str = ""
    email: str | None = None
    address: str | None = None
    timezone: str = "UTC"
    is_active: bool = True
    whatsapp_phone_number_id: str | None = None
    whatsapp_app_secret: str | None = None
    owner_whatsapp: str | None = None

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        name: str,
        slug: str,
        phone: str,
        timezone: str = "UTC",
        description: str | None = None,
        email: str | None = None,
        address: str | None = None,
    ) -> Business:
        """Factory for creating a new business."""
        if not name.strip():
            raise BusinessRuleViolationError("Business name cannot be empty")
        if not phone.strip():
            raise BusinessRuleViolationError("Phone number is required")
        if not slug.strip():
            raise BusinessRuleViolationError("Business slug cannot be empty")

        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name.strip(),
            slug=slug.strip().lower(),
            phone=phone.strip(),
            timezone=timezone,
            description=description,
            email=email,
            address=address,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        timezone: str | None = None,
    ) -> None:
        """Update business details."""
        if name is not None:
            if not name.strip():
                raise BusinessRuleViolationError("Business name cannot be empty")
            self.name = name.strip()

        if phone is not None:
            if not phone.strip():
                raise BusinessRuleViolationError("Phone number is required")
            self.phone = phone.strip()

        if timezone is not None:
            self.timezone = timezone

        if description is not None:
            self.description = description

        if email is not None:
            self.email = email

        if address is not None:
            self.address = address

        self.updated_at = datetime.utcnow()

    def deactivate(self) -> None:
        """Soft delete: mark business as inactive."""
        if not self.is_active:
            return
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def activate(self) -> None:
        """Reactivate an inactive business."""
        if self.is_active:
            return
        self.is_active = True
        self.updated_at = datetime.utcnow()
