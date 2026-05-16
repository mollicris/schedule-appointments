from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.professional.professional import Professional
from src.domain.professional.repository import ProfessionalRepository
from src.domain.shared.errors import ConflictError, ValidationError


@dataclass(frozen=True)
class CreateProfessionalInput:
    business_id: UUID
    user_id: UUID
    name: str
    phone: str | None = None


@dataclass(frozen=True)
class CreateProfessionalOutput:
    professional_id: UUID
    name: str


class CreateProfessionalUseCase(UseCase[CreateProfessionalInput, CreateProfessionalOutput]):
    """Register a user as a professional in a business."""

    def __init__(self, professionals: ProfessionalRepository, uow: UnitOfWork) -> None:
        self._professionals = professionals
        self._uow = uow

    async def execute(self, input_data: CreateProfessionalInput) -> CreateProfessionalOutput:
        self._validate_input(input_data)
        tenant = get_current_tenant()

        async with self._uow:
            # Prevent duplicates: one user per business
            if await self._professionals.user_in_business_exists(
                user_id=input_data.user_id,
                business_id=input_data.business_id,
            ):
                raise ConflictError(
                    f"User {input_data.user_id} is already a professional in this business"
                )

            professional = Professional.create(
                tenant_id=tenant.tenant_id,
                business_id=input_data.business_id,
                user_id=input_data.user_id,
                name=input_data.name,
                phone=input_data.phone,
            )

            await self._professionals.add(professional)
            await self._uow.commit()

        return CreateProfessionalOutput(
            professional_id=professional.id,
            name=professional.name,
        )

    def _validate_input(self, data: CreateProfessionalInput) -> None:
        if not data.name.strip():
            raise ValidationError("Professional name is required")
