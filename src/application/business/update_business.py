from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.business.repository import BusinessRepository
from src.domain.shared.errors import NotFoundError, ValidationError


@dataclass(frozen=True)
class UpdateBusinessInput:
    business_id: UUID
    name: str | None = None
    description: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    timezone: str | None = None


@dataclass(frozen=True)
class UpdateBusinessOutput:
    business_id: UUID
    name: str
    slug: str
    phone: str


class UpdateBusinessUseCase(UseCase[UpdateBusinessInput, UpdateBusinessOutput]):
    """Update an existing business."""

    def __init__(self, businesses: BusinessRepository, uow: UnitOfWork) -> None:
        self._businesses = businesses
        self._uow = uow

    async def execute(self, input_data: UpdateBusinessInput) -> UpdateBusinessOutput:
        self._validate_input(input_data)

        async with self._uow:
            business = await self._businesses.get_by_id(input_data.business_id)
            if not business:
                raise NotFoundError(f"Business {input_data.business_id} not found")

            business.update(
                name=input_data.name,
                description=input_data.description,
                phone=input_data.phone,
                email=input_data.email,
                address=input_data.address,
                timezone=input_data.timezone,
            )

            await self._businesses.update(business)
            await self._uow.commit()

        return UpdateBusinessOutput(
            business_id=business.id,
            name=business.name,
            slug=business.slug,
            phone=business.phone,
        )

    def _validate_input(self, data: UpdateBusinessInput) -> None:
        if data.name is not None and not data.name.strip():
            raise ValidationError("Business name cannot be empty")
        if data.phone is not None and not data.phone.strip():
            raise ValidationError("Phone number cannot be empty")
