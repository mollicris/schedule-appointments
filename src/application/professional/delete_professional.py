from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.professional.repository import ProfessionalRepository
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class DeleteProfessionalInput:
    professional_id: UUID


@dataclass(frozen=True)
class DeleteProfessionalOutput:
    professional_id: UUID
    deleted: bool


class DeleteProfessionalUseCase(UseCase[DeleteProfessionalInput, DeleteProfessionalOutput]):
    """Soft-delete a professional (marks them as inactive)."""

    def __init__(self, professionals: ProfessionalRepository, uow: UnitOfWork) -> None:
        self._professionals = professionals
        self._uow = uow

    async def execute(self, input_data: DeleteProfessionalInput) -> DeleteProfessionalOutput:
        async with self._uow:
            deleted = await self._professionals.delete(input_data.professional_id)
            if not deleted:
                raise NotFoundError(f"Professional {input_data.professional_id} not found")

            await self._uow.commit()

        return DeleteProfessionalOutput(
            professional_id=input_data.professional_id,
            deleted=True,
        )
