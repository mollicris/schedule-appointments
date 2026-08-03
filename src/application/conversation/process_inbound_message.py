from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog

from src.application.membership.get_client_membership import (
    GetClientMembershipInput,
    GetClientMembershipOutput,
    GetClientMembershipUseCase,
)
from src.application.shared.tenant_context import TenantContext, set_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.appointment.repository import AppointmentRepository
from src.domain.business.business import Business
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.client.client import Client
from src.domain.client.repository import ClientRepository
from src.domain.conversation.conversation import Conversation, Message
from src.domain.conversation.human_transfer import HumanTransfer
from src.domain.conversation.human_transfer_repository import HumanTransferRepository
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import ConversationState
from src.domain.membership.repository import MembershipPlanRepository, MembershipRepository
from src.domain.professional.repository import ProfessionalRepository
from src.domain.service.repository import ServiceRepository
from src.domain.service.service import Service
from src.domain.conversation.messaging_provider import MessagingProvider
from src.domain.shared.channel import Channel
from src.infrastructure.ai.agent_tools import ToolContext
from src.infrastructure.config.settings import get_settings
from src.infrastructure.ai.booking_agent import AgentInput, BookingAgent, _FALLBACK_REPLY

log = structlog.get_logger(__name__)

_HISTORY_LIMIT = 20


@dataclass(frozen=True)
class InboundMessage:
    """One inbound message, already parsed by the channel's webhook."""

    external_message_id: str
    # Channel id of the sender: E.164 on WhatsApp, PSID/IGSID on Meta's social
    # inboxes. Also the address replies are sent back to.
    from_number: str
    sender_name: str
    content: str
    message_type: str         # "text" | "audio" | "image" | "interactive"
    extra_data: dict | None = None
    channel: Channel = Channel.WHATSAPP


@dataclass(frozen=True)
class ProcessInboundMessageInput:
    tenant_id: UUID
    business_id: UUID
    message: InboundMessage
    messaging: MessagingProvider
    business: Business
    services: list[Service]
    industry: str = ""
    # Owner alerts always go out over WhatsApp, whatever the inbound channel:
    # the "owner" of a Facebook page is not someone the page can message.
    staff_notifier: MessagingProvider | None = None


@dataclass(frozen=True)
class ProcessInboundMessageOutput:
    conversation_id: UUID
    reply_sent: bool


class ProcessInboundMessageUseCase:
    """Handle one inbound WhatsApp message end-to-end.

    Flow:
      1. Idempotency check — skip duplicate external_message_id.
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
        human_transfers: HumanTransferRepository,
        agent: BookingAgent,
        uow: UnitOfWork,
        membership_plans: MembershipPlanRepository | None = None,
        memberships: MembershipRepository | None = None,
    ) -> None:
        self._conversations = conversations
        self._clients = clients
        self._services = services
        self._appointments = appointments
        self._professionals = professionals
        self._business_hours = business_hours
        self._human_transfers = human_transfers
        self._agent = agent
        self._uow = uow
        # Optional: businesses without memberships (a salon, a garage) work
        # exactly as before when these are not provided.
        self._membership_plans = membership_plans
        self._memberships = memberships

    async def execute(
        self, input_data: ProcessInboundMessageInput
    ) -> ProcessInboundMessageOutput:
        # Set tenant context so tenant-scoped repos work correctly
        set_current_tenant(TenantContext(tenant_id=input_data.tenant_id))

        async with self._uow:
            # 1. Idempotency — skip if already processed
            already_processed = await self._conversations.message_exists(
                input_data.message.external_message_id
            )
            if already_processed:
                log.info(
                    "whatsapp_duplicate_message",
                    wamid=input_data.message.external_message_id,
                )
                await self._uow.rollback()
                return ProcessInboundMessageOutput(
                    conversation_id=UUID(int=0),
                    reply_sent=False,
                )

            # 2. Find or create client — identity is (channel, external_id)
            channel = input_data.message.channel
            client = await self._clients.get_by_channel_id(
                channel, input_data.message.from_number
            )
            if client is None:
                client = Client.create(
                    tenant_id=input_data.tenant_id,
                    # Only WhatsApp ids are phone numbers; a PSID is not.
                    whatsapp_number=(
                        input_data.message.from_number if channel == Channel.WHATSAPP else ""
                    ),
                    channel=channel,
                    external_id=input_data.message.from_number,
                    name=input_data.message.sender_name,
                )
                await self._clients.add(client)
            else:
                # Keeps last_interaction_at fresh, which is what inactivity
                # segmentation (win-back campaigns) reads.
                client.record_interaction()
                await self._clients.update(client)

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
                    channel=channel,
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
                external_message_id=input_data.message.external_message_id,
                extra_data=input_data.message.extra_data,
            )
            await self._conversations.add_message(inbound)
            conversation.record_message()

            # 6. If escalated, the bot stays quiet — unless the handover has been
            # sitting unattended longer than the configured grace period.
            if conversation.is_escalated and self._should_resume(conversation):
                conversation.is_escalated = False
                conversation.escalated_at = None
                conversation.transition_to(ConversationState.IDLE)
                log.info(
                    "conversation_auto_resumed",
                    conversation_id=str(conversation.id),
                    after_minutes=get_settings().escalation_auto_resume_minutes,
                )

            if conversation.is_escalated:
                await self._conversations.update(conversation)
                await self._uow.commit()
                log.info(
                    "conversation_muted_escalated",
                    conversation_id=str(conversation.id),
                    hint="Resuelve la transferencia (PUT /api/v1/transfers/{id}/resolve) para que el bot vuelva a responder.",
                )
                return ProcessInboundMessageOutput(
                    conversation_id=conversation.id,
                    reply_sent=False,
                )

            # 7. Build ToolContext with the now-resolved client_id
            tool_ctx = ToolContext(
                tenant_id=input_data.tenant_id,
                business_id=input_data.business_id,
                client_id=client.id,
                client_name=client.name,
                client_whatsapp=client.whatsapp_number or client.external_id,
                conversation_id=conversation.id,
                business_timezone=input_data.business.timezone,
                business_name=input_data.business.name,
                channel=channel,
                services=self._services,
                appointments=self._appointments,
                professionals=self._professionals,
                business_hours=self._business_hours,
                clients=self._clients,
                human_transfers=self._human_transfers,
                uow=self._uow,
                membership_plans=self._membership_plans,
                memberships=self._memberships,
                # Staff alerts go over WhatsApp even from a social conversation.
                staff_notifier=input_data.staff_notifier,
                owner_whatsapp=input_data.business.owner_whatsapp,
            )

            # 8. Run the Claude agent (may call tools, do multiple iterations).
            # On social channels it gets a read-only toolset: see tools_for_channel.
            is_returning = client.appointment_count > 0
            membership = (
                None if channel.is_social
                else await self._load_membership(client.id, input_data.business_id)
            )
            agent_input = AgentInput(
                business=input_data.business,
                services=input_data.services,
                client_name=client.name,
                is_returning_client=is_returning,
                history=history,
                user_message=input_data.message.content,
                tool_ctx=tool_ctx,
                industry=input_data.industry,
                membership=membership,
                channel=channel,
            )
            try:
                reply_text = await self._agent.run(agent_input)
            except Exception:
                log.exception(
                    "agent_error",
                    conversation_id=str(conversation.id),
                    client_id=str(client.id),
                )
                reply_text = _FALLBACK_REPLY

            # 9. Escalate if tool triggered it or agent hit max retries
            should_escalate = tool_ctx.escalation_triggered or reply_text == _FALLBACK_REPLY
            if should_escalate:
                conversation.escalate()
                transfer = HumanTransfer.create(
                    tenant_id=input_data.tenant_id,
                    business_id=input_data.business_id,
                    conversation_id=conversation.id,
                    client_id=client.id,
                    reason=tool_ctx.escalation_reason or "Límite de iteraciones del agente alcanzado",
                    context_snapshot=[
                        {"sender": m.sender, "content": m.content}
                        for m in history[-5:]
                    ],
                )
                await self._human_transfers.add(transfer)
                log.info(
                    "conversation_escalated",
                    conversation_id=str(conversation.id),
                    reason=transfer.reason,
                )
                # Notify owner over WhatsApp (never over the inbound channel:
                # a page cannot message its own owner).
                notifier = input_data.staff_notifier
                if input_data.business.owner_whatsapp and notifier is not None:
                    await _notify_owner(
                        wa_client=notifier,
                        owner_number=input_data.business.owner_whatsapp,
                        business_name=input_data.business.name,
                        client_name=client.name,
                        client_number=client.whatsapp_number or client.external_id,
                        channel=channel,
                        reason=transfer.reason,
                        context=transfer.context_snapshot,
                    )

            # 10. Persist bot reply
            bot_msg = Message.from_bot(
                tenant_id=input_data.tenant_id,
                conversation_id=conversation.id,
                content=reply_text,
            )
            await self._conversations.add_message(bot_msg)
            conversation.record_message()

            # 11. Update conversation
            await self._conversations.update(conversation)
            await self._uow.commit()

        # Send reply through the same channel it came from (outside the
        # transaction — network call)
        reply_sent = await input_data.messaging.send_text(
            to=input_data.message.from_number,
            body=reply_text,
        )
        if not reply_sent:
            log.warning(
                "reply_send_failed",
                channel=input_data.message.channel.value,
                to=input_data.message.from_number,
                conversation_id=str(conversation.id),
            )

        return ProcessInboundMessageOutput(
            conversation_id=conversation.id,
            reply_sent=reply_sent,
        )

    def _should_resume(self, conversation: Conversation) -> bool:
        """True when an unattended handover has aged past the grace period.

        Without this, one escalation leaves the client talking to a wall until
        somebody resolves the transfer by hand — which is exactly what happens
        while testing, where no one is watching the queue.
        """
        minutes = get_settings().escalation_auto_resume_minutes
        if minutes <= 0 or conversation.escalated_at is None:
            return False

        escalated_at = conversation.escalated_at
        if escalated_at.tzinfo is None:
            escalated_at = escalated_at.replace(tzinfo=timezone.utc)

        return datetime.now(timezone.utc) - escalated_at >= timedelta(minutes=minutes)

    async def _load_membership(
        self,
        client_id: UUID,
        business_id: UUID,
    ) -> GetClientMembershipOutput | None:
        """Membership status injected into the prompt, or None when not applicable.

        A failure here must never cost the client their reply, so it degrades to
        None and the agent simply talks without membership context.
        """
        if self._memberships is None or self._membership_plans is None:
            return None

        try:
            use_case = GetClientMembershipUseCase(
                memberships=self._memberships,
                plans=self._membership_plans,
            )
            return await use_case.execute(
                GetClientMembershipInput(client_id=client_id, business_id=business_id)
            )
        except Exception:
            log.exception("membership_lookup_failed", client_id=str(client_id))
            return None


async def _notify_owner(
    *,
    wa_client: MessagingProvider,
    owner_number: str,
    business_name: str,
    client_name: str,
    client_number: str,
    reason: str | None,
    context: list[dict],
    channel: Channel = Channel.WHATSAPP,
) -> None:
    sender_icon = {"client": "👤", "bot": "🤖"}
    context_lines = "\n".join(
        f"{sender_icon.get(m['sender'], '•')} {m['content'][:120]}"
        for m in context[-5:]
    )
    # On social channels the id is a PSID, not something staff can dial, so the
    # closing line tells them where to reply instead.
    if channel == Channel.WHATSAPP:
        contact_line = f"Escríbele directamente a {client_number}"
    else:
        contact_line = f"Respondé desde la bandeja de {channel.label_es}"

    body = (
        f"🚨 *Nuevo escalamiento — {business_name}*\n\n"
        f"*Canal:* {channel.label_es}\n"
        f"*Cliente:* {client_name}\n"
        f"*Contacto:* {client_number}\n"
        f"*Motivo:* {reason or 'No especificado'}\n\n"
        f"*Últimos mensajes:*\n{context_lines}\n\n"
        f"{contact_line}"
    )
    try:
        await wa_client.send_text(to=owner_number, body=body)
    except Exception:
        log.exception("owner_notification_failed", owner=owner_number)
