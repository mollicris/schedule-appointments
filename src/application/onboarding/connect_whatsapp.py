from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.business.repository import BusinessRepository
from src.domain.shared.errors import NotFoundError, ValidationError
from src.infrastructure.whatsapp.meta_graph_client import MetaGraphClient, WabaInfo


@dataclass(frozen=True)
class ConnectWhatsAppInput:
    """Auth code returned by Facebook Embedded Signup popup."""
    code: str
    redirect_uri: str = ""


@dataclass(frozen=True)
class ConnectWhatsAppOutput:
    business_id: UUID
    waba_id: str
    phone_number_id: str
    phone_display: str
    connected: bool = True


class ConnectWhatsAppUseCase(UseCase[ConnectWhatsAppInput, ConnectWhatsAppOutput]):
    """Completes the WhatsApp Embedded Signup OAuth flow for a tenant.

    Flow:
        1. Exchange short-lived auth code → user access token (Graph API)
        2. Extend to long-lived token (60 days)
        3. Discover WABA ID and phone_number_id
        4. Subscribe WABA to this app's webhooks
        5. Persist credentials on the tenant's Business aggregate
    """

    def __init__(
        self,
        businesses: BusinessRepository,
        meta_client: MetaGraphClient,
        uow: UnitOfWork,
    ) -> None:
        self._businesses = businesses
        self._meta = meta_client
        self._uow = uow

    async def execute(self, input_data: ConnectWhatsAppInput) -> ConnectWhatsAppOutput:
        if not input_data.code.strip():
            raise ValidationError("Auth code is required")

        ctx = get_current_tenant()

        businesses = await self._businesses.list_active(limit=1)
        if not businesses:
            raise NotFoundError("No active business found for this tenant. Complete the setup wizard first.")
        business = businesses[0]

        short_token = await self._meta.exchange_code_for_token(
            code=input_data.code,
            redirect_uri=input_data.redirect_uri,
        )
        long_token = await self._meta.get_long_lived_token(short_token)

        waba_info: WabaInfo = await self._meta.get_waba_and_phone(long_token)

        await self._meta.subscribe_waba_to_app(waba_info.waba_id, long_token)

        business.connect_via_embedded_signup(
            waba_id=waba_info.waba_id,
            phone_number_id=waba_info.phone_number_id,
            access_token=waba_info.access_token,
            phone_display=waba_info.phone_display,
        )

        async with self._uow:
            await self._businesses.update(business)
            await self._uow.commit()

        return ConnectWhatsAppOutput(
            business_id=business.id,
            waba_id=waba_info.waba_id,
            phone_number_id=waba_info.phone_number_id,
            phone_display=waba_info.phone_display,
        )
