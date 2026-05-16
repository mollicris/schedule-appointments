from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.professional.repository import ProfessionalRepository
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class GetProfessionalInput:
    professional_id: UUID


@dataclass(frozen=True)
class GetProfessionalOutput:
    professional_id: UUID
    business_id: UUID
    user_id: UUID
    name: str
    phone: str | None
    is_active: bool


class GetProfessionalUseCase(UseCase[GetProfessionalInput, GetProfessionalOutput]):
    """Get a professional by ID."""

    def __init__(self, professionals: ProfessionalRepository) -> None:
        self._professionals = professionals

    async def execute(self, input_data: GetProfessionalInput) -> GetProfessionalOutput:
        professional = await self._professionals.get_by_id(input_data.professional_id)

        if not professional:
            raise NotFoundError(f"Professional {input_data.professional_id} not found")

        return GetProfessionalOutput(
            professional_id=professional.id,
            business_id=professional.business_id,
            user_id=professional.user_id,
            name=professional.name,
            phone=professional.phone,
            is_active=professional.is_active,
        )
