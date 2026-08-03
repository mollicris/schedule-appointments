from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.business.repository import BusinessRepository
from src.domain.shared.errors import NotFoundError


@dataclass(frozen=True)
class UpdateBusinessChannelsInput:
    business_id: UUID
    facebook_page_id: str | None = None
    facebook_page_access_token: str | None = None
    instagram_account_id: str | None = None
    meta_app_secret: str | None = None


@dataclass(frozen=True)
class UpdateBusinessChannelsOutput:
    business_id: UUID
    facebook_page_id: str | None
    instagram_account_id: str | None
    messenger_connected: bool
    instagram_connected: bool
    has_page_access_token: bool
    has_meta_app_secret: bool


class UpdateBusinessChannelsUseCase(
    UseCase[UpdateBusinessChannelsInput, UpdateBusinessChannelsOutput]
):
    """Configure the Messenger / Instagram credentials of a business.

    Manual counterpart of the WhatsApp Embedded Signup: the operator pastes the
    Page ID, the page access token and the Instagram account id taken from the
    Meta dashboard. Secrets are never echoed back, only whether they are set.
    """

    def __init__(self, businesses: BusinessRepository, uow: UnitOfWork) -> None:
        self._businesses = businesses
        self._uow = uow

    async def execute(
        self, input_data: UpdateBusinessChannelsInput
    ) -> UpdateBusinessChannelsOutput:
        async with self._uow:
            business = await self._businesses.get_by_id(input_data.business_id)
            if not business:
                raise NotFoundError(f"Business {input_data.business_id} not found")

            business.configure_social_channels(
                facebook_page_id=input_data.facebook_page_id,
                facebook_page_access_token=input_data.facebook_page_access_token,
                instagram_account_id=input_data.instagram_account_id,
                meta_app_secret=input_data.meta_app_secret,
            )

            await self._businesses.update(business)
            await self._uow.commit()

        return UpdateBusinessChannelsOutput(
            business_id=business.id,
            facebook_page_id=business.facebook_page_id,
            instagram_account_id=business.instagram_account_id,
            messenger_connected=business.has_messenger,
            instagram_connected=business.has_instagram,
            has_page_access_token=bool(business.facebook_page_access_token),
            has_meta_app_secret=bool(business.meta_app_secret),
        )
