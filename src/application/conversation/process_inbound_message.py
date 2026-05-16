from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import structlog

from src.application.shared.tenant_context import TenantContext, set_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.appointment.repository import AppointmentRepository
from src.domain.business.business import Business
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.client.client import Client
from src.domain.client.repository import ClientRepository
from src.domain.conversation.conversation import Conversation, Message
from src.domain.conversation.repository import ConversationRepository
from src.domain.professional.repository import ProfessionalRepository
from src.domain.service.repository import ServiceRepository
from src.domain.service.service import Service
from src.infrastructure.ai.agent_tools import ToolContext
from src.infrastructure.ai.booking_agent import AgentInput, BookingAgent
from src.infrastructure.messaging.whatsapp_client import WhatsAppClient

log = structlog.get_logger(__name__)

_HISTORY_LIMIT = 20


@dataclass(frozen=True)
class InboundMessage:
    """Parsed representation of a single WhatsApp inbound message."""

    whatsapp_message_id: str
    from_number: str          # E.164, e.g. "591123456789"
    sender_name: str
    content: str
    message_type: str         # "text" | "audio" | "image" | "interactive"
    extra_data: dict | None = None


@dataclass(frozen=True)
class ProcessInboundMessageInput:
    tenant_id: UUID
    business_id: UUID
    message: InboundMessage
    whatsapp_client: WhatsAppClient
    business: Business
    services: list[Service]


@dataclass(frozen=True)
class ProcessInboundMessageOutput:
    conversation_id: UUID
    reply_sent: bool


class ProcessInboundMessageUseCase:
    """Handle one inbound WhatsApp message end-to-end.

    Flow:
      1. Idempotency check — skip duplicate whatsapp_message_id.
      2. Set tenant context (required by tenant-scoped repositories).
      3. Find or create the client (by WhatsApp number).
      4. Find active conversation or start a new one.
      5. Load recent message history.
      6. Persist inbound message.
      7. Build ToolContext with resolved client_id and run BookingAgent.
      8. Persist bot reply + send via WhatsApp Cloud API.
      9. Persist updated conversation state.
    """

    def __init__(
        self,
        conversations: ConversationRepository,
        clients: ClientRepository,
        services: ServiceRepository,
        appointments: AppointmentRepository,
        professionals: ProfessionalRepository,
        business_hours: BusinessHourRepository,
        agent: BookingAgent,
        uow: UnitOfWork,
    ) -> None:
        self._conversations = conversations
        self._clients = clients
        self._services = services
        self._appointments = appointments
        self._professionals = professionals
        self._business_hours = business_hours
        self._agent = agent
        self._uow = uow

    async def execute(
        self, input_data: ProcessInboundMessageInput
    ) -> ProcessInboundMessageOutput:
        # Set tenant context so tenant-scoped repos work correctly
        set_current_tenant(TenantContext(tenant_id=input_data.tenant_id))

        async with self._uow:
            # 1. Idempotency — skip if already processed
            already_processed = await self._conversations.message_exists(
                input_data.message.whatsapp_message_id
            )
            if already_processed:
                log.info(
                    "whatsapp_duplicate_message",
                    wamid=input_data.message.whatsapp_message_id,
                )
                await self._uow.rollback()
                return ProcessInboundMessageOutput(
                    conversation_id=UUID(int=0),
                    reply_sent=False,
                )

            # 2. Find or create client
            client = await self._clients.get_by_whatsapp(input_data.message.from_number)
            if client is None:
                client = Client.create(
                    tenant_id=input_data.tenant_id,
                    whatsapp_number=input_data.message.from_number,
                    name=input_data.message.sender_name,
                )
                await self._clients.add(client)

            # 3. Find or start conversation
            conversation = await self._conversations.get_active_by_client_and_business(
                client_id=client.id,
                business_id=input_data.business_id,
            )
            if conversation is None:
                conversation = Conversation.start(
                    tenant_id=input_data.tenant_id,
                    business_id=input_data.business_id,
                    client_id=client.id,
                )
                await self._conversations.add(conversation)

            # 4. Load recent history before persisting the new message
            history: list[Message] = await self._conversations.get_recent_messages(
                conversation_id=conversation.id,
                limit=_HISTORY_LIMIT,
            )

            # 5. Persist inbound message
            inbound = Message.from_client(
                tenant_id=input_data.tenant_id,
                conversation_id=conversation.id,
                content=input_data.message.content,
                message_type=input_data.message.message_type,
                whatsapp_message_id=input_data.message.whatsapp_message_id,
                extra_data=input_data.message.extra_data,
            )
            await self._conversations.add_message(inbound)
            conversation.record_message()

            # 6. Build ToolContext with the now-resolved client_id
            tool_ctx = ToolContext(
                tenant_id=input_data.tenant_id,
                business_id=input_data.business_id,
                client_id=client.id,
                client_name=client.name,
                client_whatsapp=client.whatsapp_number,
                services=self._services,
                appointments=self._appointments,
                professionals=self._professionals,
                business_hours=self._business_hours,
                clients=self._clients,
                uow=self._uow,
            )

            # 7. Run the Claude agent (may call tools, do multiple iterations)
            is_returning = client.appointment_count > 0
            agent_input = AgentInput(
                business=input_data.business,
                services=input_data.services,
                client_name=client.name,
                is_returning_client=is_returning,
                history=history,
                user_message=input_data.message.content,
                tool_ctx=tool_ctx,
            )
            try:
                reply_text = await self._agent.run(agent_input)
            except Exception:
                log.exception(
                    "agent_error",
                    conversation_id=str(conversation.id),
                    client_id=str(client.id),
                )
                reply_text = (
                    "Lo siento, hubo un problema procesando tu solicitud. "
                    "Por favor, intenta de nuevo en un momento."
                )

            # 8. Persist bot reply
            bot_msg = Message.from_bot(
                tenant_id=input_data.tenant_id,
                conversation_id=conversation.id,
                content=reply_text,
            )
            await self._conversations.add_message(bot_msg)
            conversation.record_message()

            # 9. Update conversation
            await self._conversations.update(conversation)
            await self._uow.commit()

        # Send reply via WhatsApp (outside the transaction — network call)
        reply_sent = await input_data.whatsapp_client.send_text(
            to=input_data.message.from_number,
            body=reply_text,
        )
        if not reply_sent:
            log.warning(
                "whatsapp_reply_failed",
                to=input_data.message.from_number,
                conversation_id=str(conversation.id),
            )

        return ProcessInboundMessageOutput(
            conversation_id=conversation.id,
            reply_sent=reply_sent,
        )
