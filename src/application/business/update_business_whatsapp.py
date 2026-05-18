from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.business.repository import BusinessRepository
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class UpdateBusinessWhatsappInput:
    business_id: UUID
    phone_number_id: str | None = None
    app_secret: str | None = None
    owner_whatsapp: str | None = None


@dataclass(frozen=True)
class UpdateBusinessWhatsappOutput:
    business_id: UUID
    whatsapp_phone_number_id: str | None
    owner_whatsapp: str | None
    has_whatsapp_app_secret: bool


class UpdateBusinessWhatsappUseCase(UseCase[UpdateBusinessWhatsappInput, UpdateBusinessWhatsappOutput]):
    """Configure WhatsApp integration credentials for a business."""

    def __init__(self, businesses: BusinessRepository, uow: UnitOfWork) -> None:
        self._businesses = businesses
        self._uow = uow

    async def execute(self, input_data: UpdateBusinessWhatsappInput) -> UpdateBusinessWhatsappOutput:
        async with self._uow:
            business = await self._businesses.get_by_id(input_data.business_id)
            if not business:
                raise NotFoundError(f"Business {input_data.business_id} not found")

            business.configure_whatsapp(
                phone_number_id=input_data.phone_number_id,
                app_secret=input_data.app_secret,
                owner_whatsapp=input_data.owner_whatsapp,
            )
            await self._businesses.update(business)
            await self._uow.commit()

        return UpdateBusinessWhatsappOutput(
            business_id=business.id,
            whatsapp_phone_number_id=business.whatsapp_phone_number_id,
            owner_whatsapp=business.owner_whatsapp,
            has_whatsapp_app_secret=bool(business.whatsapp_app_secret),
        )
