from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.business.business import Business
from src.domain.business.repository import BusinessRepository
from src.domain.shared.errors import ConflictError, ValidationError


@dataclass(frozen=True)
class CreateBusinessInput:
    name: str
    slug: str | None = None
    phone: str = ""
    timezone: str = "UTC"
    description: str | None = None
    email: str | None = None
    address: str | None = None


@dataclass(frozen=True)
class CreateBusinessOutput:
    business_id: UUID
    slug: str


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    lowered = normalized.lower().strip()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")[:48] or "business"


class CreateBusinessUseCase(UseCase[CreateBusinessInput, CreateBusinessOutput]):
    """Create a new business for the current tenant.

    The admin must be in ONBOARDING status to create their first business.
    Slug is auto-generated if not provided, with collision detection.
    """

    def __init__(
        self,
        businesses: BusinessRepository,
        uow: UnitOfWork,
    ) -> None:
        self._businesses = businesses
        self._uow = uow

    async def execute(self, input_data: CreateBusinessInput) -> CreateBusinessOutput:
        self._validate_input(input_data)
        tenant = get_current_tenant()

        async with self._uow:
            # Generate or validate slug
            slug = input_data.slug or _slugify(input_data.name)
            slug_candidate = slug
            suffix = 1

            # Handle slug collision
            while await self._businesses.slug_exists(slug_candidate):
                suffix += 1
                slug_candidate = f"{slug}-{suffix}"
                if suffix > 1000:
                    raise ConflictError("Unable to generate a unique slug")

            # Create business
            business = Business.create(
                tenant_id=tenant.tenant_id,
                name=input_data.name,
                slug=slug_candidate,
                phone=input_data.phone,
                timezone=input_data.timezone,
                description=input_data.description,
                email=input_data.email,
                address=input_data.address,
            )

            await self._businesses.add(business)
            await self._uow.commit()

        return CreateBusinessOutput(
            business_id=business.id,
            slug=business.slug,
        )

    def _validate_input(self, data: CreateBusinessInput) -> None:
        if not data.name.strip():
            raise ValidationError("Business name is required")
        if not data.phone.strip():
            raise ValidationError("Phone number is required")
        if data.slug and not data.slug.strip():
            raise ValidationError("Slug cannot be empty")
