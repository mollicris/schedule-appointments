from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.conversation.conversation import Conversation, Message
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import ConversationState
from src.infrastructure.persistence.mappers.conversation_mapper import ConversationMapper, MessageMapper
from src.infrastructure.persistence.models.conversation import ConversationModel, MessageModel

# States that represent an open conversation (bot still active)
_ACTIVE_STATES = {s.value for s in ConversationState} - {
    ConversationState.HUMAN_HANDOVER.value,
}


class ConversationRepositoryImpl(ConversationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_by_client_and_business(
        self,
        client_id: UUID,
        business_id: UUID,
    ) -> Conversation | None:
        row = await self._session.scalar(
            select(ConversationModel)
            .where(
                ConversationModel.client_id == client_id,
                ConversationModel.business_id == business_id,
                ConversationModel.is_escalated.is_(False),
                ConversationModel.current_state.in_(_ACTIVE_STATES),
            )
            .order_by(ConversationModel.last_message_at.desc())
            .limit(1)
        )
        return ConversationMapper.to_domain(row) if row else None

    async def add(self, conversation: Conversation) -> None:
        self._session.add(ConversationMapper.to_model(conversation))
        await self._session.flush()

    async def update(self, conversation: Conversation) -> None:
        await self._session.merge(ConversationMapper.to_model(conversation))
        await self._session.flush()

    async def add_message(self, message: Message) -> None:
        self._session.add(MessageMapper.to_model(message))
        await self._session.flush()

    async def message_exists(self, whatsapp_message_id: str) -> bool:
        row = await self._session.scalar(
            select(MessageModel.id).where(
                MessageModel.whatsapp_message_id == whatsapp_message_id
            ).limit(1)
        )
        return row is not None

    async def get_recent_messages(
        self,
        conversation_id: UUID,
        limit: int = 20,
    ) -> list[Message]:
        rows = await self._session.scalars(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.desc())
            .limit(limit)
        )
        return [MessageMapper.to_domain(r) for r in reversed(list(rows))]
