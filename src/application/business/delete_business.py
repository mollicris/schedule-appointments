from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.business.repository import BusinessRepository
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class DeleteBusinessInput:
    business_id: UUID


@dataclass(frozen=True)
class DeleteBusinessOutput:
    business_id: UUID
    deleted: bool


class DeleteBusinessUseCase(UseCase[DeleteBusinessInput, DeleteBusinessOutput]):
    """Soft-delete a business (marks it as inactive)."""

    def __init__(self, businesses: BusinessRepository, uow: UnitOfWork) -> None:
        self._businesses = businesses
        self._uow = uow

    async def execute(self, input_data: DeleteBusinessInput) -> DeleteBusinessOutput:
        async with self._uow:
            deleted = await self._businesses.delete(input_data.business_id)
            if not deleted:
                raise NotFoundError(f"Business {input_data.business_id} not found")

            await self._uow.commit()

        return DeleteBusinessOutput(
            business_id=input_data.business_id,
            deleted=True,
        )
