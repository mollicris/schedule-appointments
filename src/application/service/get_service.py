from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.service.repository import ServiceRepository
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class GetServiceInput:
    service_id: UUID


@dataclass(frozen=True)
class GetServiceOutput:
    service_id: UUID
    business_id: UUID
    name: str
    description: str | None
    duration_minutes: int
    price: int | None
    is_active: bool


class GetServiceUseCase(UseCase[GetServiceInput, GetServiceOutput]):
    """Get a service by ID."""

    def __init__(self, services: ServiceRepository) -> None:
        self._services = services

    async def execute(self, input_data: GetServiceInput) -> GetServiceOutput:
        service = await self._services.get_by_id(input_data.service_id)

        if not service:
            raise NotFoundError(f"Service {input_data.service_id} not found")

        return GetServiceOutput(
            service_id=service.id,
            business_id=service.business_id,
            name=service.name,
            description=service.description,
            duration_minutes=service.duration_minutes,
            price=service.price,
            is_active=service.is_active,
        )
