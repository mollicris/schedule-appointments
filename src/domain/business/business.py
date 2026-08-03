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
    whatsapp_waba_id: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_app_secret: str | None = None
    owner_whatsapp: str | None = None
    # Messenger and Instagram: one Facebook Page serves both channels
    facebook_page_id: str | None = None
    facebook_page_access_token: str | None = None
    instagram_account_id: str | None = None
    meta_app_secret: str | None = None

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

    def configure_whatsapp(
        self,
        *,
        phone_number_id: str | None,
        app_secret: str | None,
        owner_whatsapp: str | None,
        waba_id: str | None = None,
        access_token: str | None = None,
    ) -> None:
        """Set or clear WhatsApp integration credentials."""
        self.whatsapp_phone_number_id = phone_number_id.strip() if phone_number_id else None
        self.whatsapp_app_secret = app_secret.strip() if app_secret else None
        self.owner_whatsapp = owner_whatsapp.strip() if owner_whatsapp else None
        if waba_id is not None:
            self.whatsapp_waba_id = waba_id.strip() if waba_id else None
        if access_token is not None:
            self.whatsapp_access_token = access_token.strip() if access_token else None
        self.updated_at = datetime.utcnow()

    def configure_social_channels(
        self,
        *,
        facebook_page_id: str | None = None,
        facebook_page_access_token: str | None = None,
        instagram_account_id: str | None = None,
        meta_app_secret: str | None = None,
    ) -> None:
        """Set or clear the Messenger / Instagram credentials.

        Both channels are served by the same Facebook Page: one Page ID, one
        page access token, and the Instagram professional account linked to it.
        Passing ``None`` leaves a field untouched; passing an empty string
        clears it.
        """
        if facebook_page_id is not None:
            self.facebook_page_id = facebook_page_id.strip() or None
        if facebook_page_access_token is not None:
            self.facebook_page_access_token = facebook_page_access_token.strip() or None
        if instagram_account_id is not None:
            self.instagram_account_id = instagram_account_id.strip() or None
        if meta_app_secret is not None:
            self.meta_app_secret = meta_app_secret.strip() or None
        self.updated_at = datetime.utcnow()

    @property
    def has_messenger(self) -> bool:
        return bool(self.facebook_page_id and self.facebook_page_access_token)

    @property
    def has_instagram(self) -> bool:
        return bool(self.instagram_account_id and self.facebook_page_access_token)

    def connect_via_embedded_signup(
        self,
        *,
        waba_id: str,
        phone_number_id: str,
        access_token: str,
        phone_display: str | None = None,
    ) -> None:
        """Store credentials obtained from Meta Embedded Signup OAuth flow."""
        if not waba_id.strip():
            raise BusinessRuleViolationError("WABA ID cannot be empty")
        if not phone_number_id.strip():
            raise BusinessRuleViolationError("Phone Number ID cannot be empty")
        if not access_token.strip():
            raise BusinessRuleViolationError("Access token cannot be empty")

        self.whatsapp_waba_id = waba_id.strip()
        self.whatsapp_phone_number_id = phone_number_id.strip()
        self.whatsapp_access_token = access_token.strip()
        if phone_display:
            self.owner_whatsapp = phone_display.strip()
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
