from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.conversation.conversation import Conversation, Message


class ConversationRepository(ABC):
    @abstractmethod
    async def get_active_by_client_and_business(
        self,
        client_id: UUID,
        business_id: UUID,
    ) -> Conversation | None: ...

    @abstractmethod
    async def add(self, conversation: Conversation) -> None: ...

    @abstractmethod
    async def update(self, conversation: Conversation) -> None: ...

    @abstractmethod
    async def add_message(self, message: Message) -> None: ...

    @abstractmethod
    async def message_exists(self, whatsapp_message_id: str) -> bool: ...

    @abstractmethod
    async def get_recent_messages(
        self,
        conversation_id: UUID,
        limit: int = 20,
    ) -> list[Message]: ...
