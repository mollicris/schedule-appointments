from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.service.repository import ServiceRepository
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class DeleteServiceInput:
    service_id: UUID


@dataclass(frozen=True)
class DeleteServiceOutput:
    service_id: UUID
    deleted: bool


class DeleteServiceUseCase(UseCase[DeleteServiceInput, DeleteServiceOutput]):
    """Soft-delete a service (marks it as inactive)."""

    def __init__(self, services: ServiceRepository, uow: UnitOfWork) -> None:
        self._services = services
        self._uow = uow

    async def execute(self, input_data: DeleteServiceInput) -> DeleteServiceOutput:
        async with self._uow:
            deleted = await self._services.delete(input_data.service_id)
            if not deleted:
                raise NotFoundError(f"Service {input_data.service_id} not found")

            await self._uow.commit()

        return DeleteServiceOutput(
            service_id=input_data.service_id,
            deleted=True,
        )
