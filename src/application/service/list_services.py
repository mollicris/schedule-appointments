from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.service.repository import ServiceRepository


@dataclass(frozen=True)
class ListServicesInput:
    business_id: UUID
    page: int = 1
    page_size: int = 10


@dataclass(frozen=True)
class ServiceSummary:
    service_id: UUID
    name: str
    duration_minutes: int
    price: int | None
    is_active: bool
    professional_ids: list[UUID]


@dataclass(frozen=True)
class ListServicesOutput:
    services: list[ServiceSummary]
    total: int
    page: int
    page_size: int


class ListServicesUseCase(UseCase[ListServicesInput, ListServicesOutput]):
    """List all services for a specific business (paginated)."""

    def __init__(self, services: ServiceRepository) -> None:
        self._services = services

    async def execute(self, input_data: ListServicesInput) -> ListServicesOutput:
        # Validate pagination
        page = max(1, input_data.page)
        page_size = max(1, min(100, input_data.page_size))  # Cap at 100

        offset = (page - 1) * page_size

        # Fetch services
        services = await self._services.list_by_business(
            business_id=input_data.business_id,
            limit=page_size,
            offset=offset,
        )
        total = await self._services.count_by_business(business_id=input_data.business_id)

        # Fetch professional assignments for each service in this page
        summaries = []
        for s in services:
            professional_ids = await self._services.list_professional_ids(s.id)
            summaries.append(
                ServiceSummary(
                    service_id=s.id,
                    name=s.name,
                    duration_minutes=s.duration_minutes,
                    price=s.price,
                    is_active=s.is_active,
                    professional_ids=professional_ids,
                )
            )

        return ListServicesOutput(
            services=summaries,
            total=total,
            page=page,
            page_size=page_size,
        )
