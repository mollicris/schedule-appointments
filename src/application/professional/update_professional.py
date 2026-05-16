from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.professional.repository import ProfessionalRepository
from src.domain.shared.errors import NotFoundError, ValidationError


@dataclass(frozen=True)
class UpdateProfessionalInput:
    professional_id: UUID
    name: str | None = None
    phone: str | None = None


@dataclass(frozen=True)
class UpdateProfessionalOutput:
    professional_id: UUID
    name: str
    phone: str | None


class UpdateProfessionalUseCase(UseCase[UpdateProfessionalInput, UpdateProfessionalOutput]):
    """Update an existing professional's details."""

    def __init__(self, professionals: ProfessionalRepository, uow: UnitOfWork) -> None:
        self._professionals = professionals
        self._uow = uow

    async def execute(self, input_data: UpdateProfessionalInput) -> UpdateProfessionalOutput:
        self._validate_input(input_data)

        async with self._uow:
            professional = await self._professionals.get_by_id(input_data.professional_id)
            if not professional:
                raise NotFoundError(f"Professional {input_data.professional_id} not found")

            professional.update(
                name=input_data.name,
                phone=input_data.phone,
            )

            await self._professionals.update(professional)
            await self._uow.commit()

        return UpdateProfessionalOutput(
            professional_id=professional.id,
            name=professional.name,
            phone=professional.phone,
        )

    def _validate_input(self, data: UpdateProfessionalInput) -> None:
        if data.name is not None and not data.name.strip():
            raise ValidationError("Professional name cannot be empty")
