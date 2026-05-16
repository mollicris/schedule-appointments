from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.service.service import Service
from src.domain.service.repository import ServiceRepository
from src.domain.shared.errors import ValidationError


@dataclass(frozen=True)
class CreateServiceInput:
    business_id: UUID
    name: str
    duration_minutes: int = 30
    description: str | None = None
    price: int | None = None


@dataclass(frozen=True)
class CreateServiceOutput:
    service_id: UUID
    name: str
    duration_minutes: int


class CreateServiceUseCase(UseCase[CreateServiceInput, CreateServiceOutput]):
    """Create a new service for a business."""

    def __init__(
        self,
        services: ServiceRepository,
        uow: UnitOfWork,
    ) -> None:
        self._services = services
        self._uow = uow

    async def execute(self, input_data: CreateServiceInput) -> CreateServiceOutput:
        self._validate_input(input_data)
        tenant = get_current_tenant()

        async with self._uow:
            # Create service
            service = Service.create(
                tenant_id=tenant.tenant_id,
                business_id=input_data.business_id,
                name=input_data.name,
                duration_minutes=input_data.duration_minutes,
                description=input_data.description,
                price=input_data.price,
            )

            await self._services.add(service)
            await self._uow.commit()

        return CreateServiceOutput(
            service_id=service.id,
            name=service.name,
            duration_minutes=service.duration_minutes,
        )

    def _validate_input(self, data: CreateServiceInput) -> None:
        if not data.name.strip():
            raise ValidationError("Service name is required")
        if data.duration_minutes < 1:
            raise ValidationError("Service duration must be at least 1 minute")
        if data.price is not None and data.price < 0:
            raise ValidationError("Service price cannot be negative")
