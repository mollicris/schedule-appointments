from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.business.repository import BusinessRepository
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class GetBusinessInput:
    business_id: UUID


@dataclass(frozen=True)
class GetBusinessOutput:
    business_id: UUID
    name: str
    slug: str
    phone: str
    email: str | None
    address: str | None
    description: str | None
    timezone: str
    is_active: bool
    whatsapp_phone_number_id: str | None = None
    owner_whatsapp: str | None = None
    has_whatsapp_app_secret: bool = False


class GetBusinessUseCase(UseCase[GetBusinessInput, GetBusinessOutput]):
    """Get a business by ID."""

    def __init__(self, businesses: BusinessRepository) -> None:
        self._businesses = businesses

    async def execute(self, input_data: GetBusinessInput) -> GetBusinessOutput:
        business = await self._businesses.get_by_id(input_data.business_id)

        if not business:
            raise NotFoundError(f"Business {input_data.business_id} not found")

        return GetBusinessOutput(
            business_id=business.id,
            name=business.name,
            slug=business.slug,
            phone=business.phone,
            email=business.email,
            address=business.address,
            description=business.description,
            timezone=business.timezone,
            is_active=business.is_active,
            whatsapp_phone_number_id=business.whatsapp_phone_number_id,
            owner_whatsapp=business.owner_whatsapp,
            has_whatsapp_app_secret=bool(business.whatsapp_app_secret),
        )
