from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.professional.repository import ProfessionalRepository


@dataclass(frozen=True)
class ListProfessionalsInput:
    business_id: UUID
    page: int = 1
    page_size: int = 10


@dataclass(frozen=True)
class ProfessionalSummary:
    professional_id: UUID
    user_id: UUID
    name: str
    phone: str | None
    is_active: bool


@dataclass(frozen=True)
class ListProfessionalsOutput:
    professionals: list[ProfessionalSummary]
    total: int
    page: int
    page_size: int


class ListProfessionalsUseCase(UseCase[ListProfessionalsInput, ListProfessionalsOutput]):
    """List all professionals for a specific business (paginated)."""

    def __init__(self, professionals: ProfessionalRepository) -> None:
        self._professionals = professionals

    async def execute(self, input_data: ListProfessionalsInput) -> ListProfessionalsOutput:
        page = max(1, input_data.page)
        page_size = max(1, min(100, input_data.page_size))
        offset = (page - 1) * page_size

        professionals = await self._professionals.list_by_business(
            business_id=input_data.business_id,
            limit=page_size,
            offset=offset,
        )
        total = await self._professionals.count_by_business(business_id=input_data.business_id)

        return ListProfessionalsOutput(
            professionals=[
                ProfessionalSummary(
                    professional_id=p.id,
                    user_id=p.user_id,
                    name=p.name,
                    phone=p.phone,
                    is_active=p.is_active,
                )
                for p in professionals
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
