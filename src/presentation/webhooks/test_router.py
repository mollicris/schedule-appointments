from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.application.conversation.process_inbound_message import (
    InboundMessage,
    ProcessInboundMessageInput,
    ProcessInboundMessageUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.infrastructure.ai.booking_agent import BookingAgent
from src.domain.shared.channel import Channel
from src.infrastructure.config.settings import get_settings
from src.infrastructure.persistence.database import get_session_factory
from src.infrastructure.persistence.repositories.appointment_repository import AppointmentRepositoryImpl
from src.infrastructure.persistence.repositories.business_hour_repository import BusinessHourRepositoryImpl
from src.infrastructure.persistence.repositories.business_repository import BusinessRepositoryImpl
from src.infrastructure.persistence.repositories.client_repository import ClientRepositoryImpl
from src.infrastructure.persistence.repositories.conversation_repository import ConversationRepositoryImpl
from src.infrastructure.persistence.repositories.human_transfer_repository import HumanTransferRepositoryImpl
from src.infrastructure.persistence.repositories.membership_repository import (
    MembershipPlanRepositoryImpl,
    MembershipRepositoryImpl,
)
from src.infrastructure.persistence.repositories.professional_repository import ProfessionalRepositoryImpl
from src.infrastructure.persistence.repositories.service_repository import ServiceRepositoryImpl

log = structlog.get_logger(__name__)

test_router = APIRouter(prefix="/test", tags=["dev-testing"])

_booking_agent: BookingAgent | None = None


def _get_booking_agent() -> BookingAgent:
    global _booking_agent
    if _booking_agent is None:
        _booking_agent = BookingAgent()
    return _booking_agent


class _NullMessagingProvider:
    """Dev-only provider that logs instead of sending anywhere.

    Implements the MessagingProvider port directly instead of subclassing the
    WhatsApp client, so it can stand in for any channel.
    """

    def __init__(self, channel: Channel = Channel.WHATSAPP) -> None:
        self._channel = channel

    @property
    def channel(self) -> Channel:
        return self._channel

    async def send_text(self, *, to: str, body: str) -> bool:
        log.info("null_send_text", channel=self._channel.value, to=to, body=body)
        return True

    async def send_buttons(self, *, to: str, body: str, buttons: list[dict]) -> bool:
        log.info("null_send_buttons", channel=self._channel.value, to=to, buttons=buttons)
        return True

    async def send_interactive_buttons(self, *, to: str, body: str, buttons: list[dict]) -> bool:
        return await self.send_buttons(to=to, body=body, buttons=buttons)


class SimulateMessageRequest(BaseModel):
    phone_number_id: str
    from_number: str = "+59171000001"
    sender_name: str = "Test User"
    message: str
    channel: Channel = Channel.WHATSAPP
    external_id: str | None = Field(
        default=None,
        description=(
            "Channel id of the sender. Defaults to from_number. For Messenger or "
            "Instagram use a fake PSID such as 'psid_test_1'."
        ),
    )


class SimulateMessageResponse(BaseModel):
    reply: str
    conversation_id: str
    reply_sent: bool


@test_router.post(
    "/simulate-message",
    response_model=SimulateMessageResponse,
    summary="[DEV] Simulate an inbound WhatsApp message",
    description=(
        "Only available in non-production environments. "
        "Bypasses HMAC verification and WhatsApp sending. "
        "Use `phone_number_id` matching a business in the DB."
    ),
)
async def simulate_message(body: SimulateMessageRequest) -> SimulateMessageResponse:
    settings = get_settings()

    if settings.is_production:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    factory = get_session_factory()
    reply_text = "(no reply)"

    async with factory() as session:
        business_repo = BusinessRepositoryImpl(session)
        business = await business_repo.get_by_whatsapp_phone_number_id(body.phone_number_id)

        if business is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No business found with phone_number_id='{body.phone_number_id}'. "
                       f"Run: UPDATE businesses SET whatsapp_phone_number_id = '{body.phone_number_id}' "
                       f"WHERE slug = 'clinica-demo';",
            )

        conversation_repo = ConversationRepositoryImpl(session)
        client_repo = ClientRepositoryImpl(session)
        service_repo = ServiceRepositoryImpl(session)
        appointment_repo = AppointmentRepositoryImpl(session)
        professional_repo = ProfessionalRepositoryImpl(session)
        business_hour_repo = BusinessHourRepositoryImpl(session)
        human_transfer_repo = HumanTransferRepositoryImpl(session)
        membership_plan_repo = MembershipPlanRepositoryImpl(session)
        membership_repo = MembershipRepositoryImpl(session)

        services = await service_repo.list_by_business(business.id)

        class _SessionUoW(UnitOfWork):
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    await session.commit()
                else:
                    await session.rollback()
            async def commit(self): await session.commit()
            async def rollback(self): await session.rollback()

        uow = _SessionUoW()

        import uuid

        null_client = _NullMessagingProvider(body.channel)
        inbound = InboundMessage(
            external_message_id=f"test_{uuid.uuid4().hex[:12]}",
            from_number=body.external_id or body.from_number,
            sender_name=body.sender_name,
            content=body.message,
            message_type="text",
            channel=body.channel,
        )

        use_case = ProcessInboundMessageUseCase(
            conversations=conversation_repo,
            clients=client_repo,
            services=service_repo,
            appointments=appointment_repo,
            professionals=professional_repo,
            business_hours=business_hour_repo,
            human_transfers=human_transfer_repo,
            agent=_get_booking_agent(),
            uow=uow,
            membership_plans=membership_plan_repo,
            memberships=membership_repo,
        )

        output = await use_case.execute(
            ProcessInboundMessageInput(
                tenant_id=business.tenant_id,
                business_id=business.id,
                message=inbound,
                messaging=null_client,
                staff_notifier=null_client,
                business=business,
                services=services,
            )
        )

        # Read the last bot message for the response
        last_messages = await conversation_repo.get_recent_messages(
            conversation_id=output.conversation_id, limit=1
        )
        if last_messages:
            reply_text = last_messages[-1].content

    return SimulateMessageResponse(
        reply=reply_text,
        conversation_id=str(output.conversation_id),
        reply_sent=output.reply_sent,
    )
