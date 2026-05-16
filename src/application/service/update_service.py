from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.service.repository import ServiceRepository
from src.domain.shared.errors import NotFoundError, ValidationError


@dataclass(frozen=True)
class UpdateServiceInput:
    service_id: UUID
    name: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    price: int | None = None


@dataclass(frozen=True)
class UpdateServiceOutput:
    service_id: UUID
    name: str
    duration_minutes: int
    price: int | None


class UpdateServiceUseCase(UseCase[UpdateServiceInput, UpdateServiceOutput]):
    """Update an existing service."""

    def __init__(self, services: ServiceRepository, uow: UnitOfWork) -> None:
        self._services = services
        self._uow = uow

    async def execute(self, input_data: UpdateServiceInput) -> UpdateServiceOutput:
        self._validate_input(input_data)

        async with self._uow:
            service = await self._services.get_by_id(input_data.service_id)
            if not service:
                raise NotFoundError(f"Service {input_data.service_id} not found")

            service.update(
                name=input_data.name,
                description=input_data.description,
                duration_minutes=input_data.duration_minutes,
                price=input_data.price,
            )

            await self._services.update(service)
            await self._uow.commit()

        return UpdateServiceOutput(
            service_id=service.id,
            name=service.name,
            duration_minutes=service.duration_minutes,
            price=service.price,
        )

    def _validate_input(self, data: UpdateServiceInput) -> None:
        if data.name is not None and not data.name.strip():
            raise ValidationError("Service name cannot be empty")
        if data.duration_minutes is not None and data.duration_minutes < 1:
            raise ValidationError("Service duration must be at least 1 minute")
        if data.price is not None and data.price < 0:
            raise ValidationError("Service price cannot be negative")
