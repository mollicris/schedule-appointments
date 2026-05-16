from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.business.repository import BusinessRepository


@dataclass(frozen=True)
class ListBusinessesInput:
    page: int = 1
    page_size: int = 10


@dataclass(frozen=True)
class BusinessSummary:
    business_id: UUID
    name: str
    slug: str
    phone: str
    is_active: bool


@dataclass(frozen=True)
class ListBusinessesOutput:
    businesses: list[BusinessSummary]
    total: int
    page: int
    page_size: int


class ListBusinessesUseCase(UseCase[ListBusinessesInput, ListBusinessesOutput]):
    """List all businesses for the current tenant (paginated)."""

    def __init__(self, businesses: BusinessRepository) -> None:
        self._businesses = businesses

    async def execute(self, input_data: ListBusinessesInput) -> ListBusinessesOutput:
        # Validate pagination
        page = max(1, input_data.page)
        page_size = max(1, min(100, input_data.page_size))  # Cap at 100

        offset = (page - 1) * page_size

        # Fetch businesses
        businesses = await self._businesses.list_active(
            limit=page_size,
            offset=offset,
        )
        total = await self._businesses.count_active()

        return ListBusinessesOutput(
            businesses=[
                BusinessSummary(
                    business_id=b.id,
                    name=b.name,
                    slug=b.slug,
                    phone=b.phone,
                    is_active=b.is_active,
                )
                for b in businesses
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
