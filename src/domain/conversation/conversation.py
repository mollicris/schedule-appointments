from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from src.domain.conversation.value_objects import ConversationState
from src.domain.shared.entity import TenantAwareEntity


@dataclass(eq=False)
class Message:
    """An individual message within a conversation. Immutable after creation."""

    id: UUID
    tenant_id: UUID
    conversation_id: UUID
    sender: str          # "client" | "bot"
    message_type: str    # "text" | "audio" | "image" | "interactive"
    content: str
    whatsapp_message_id: str | None = None
    extra_data: dict | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_client(
        cls,
        *,
        tenant_id: UUID,
        conversation_id: UUID,
        content: str,
        message_type: str = "text",
        whatsapp_message_id: str | None = None,
        extra_data: dict | None = None,
    ) -> Message:
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            sender="client",
            message_type=message_type,
            content=content,
            whatsapp_message_id=whatsapp_message_id,
            extra_data=extra_data,
            created_at=datetime.utcnow(),
        )

    @classmethod
    def from_bot(
        cls,
        *,
        tenant_id: UUID,
        conversation_id: UUID,
        content: str,
        message_type: str = "text",
        extra_data: dict | None = None,
    ) -> Message:
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            sender="bot",
            message_type=message_type,
            content=content,
            extra_data=extra_data,
            created_at=datetime.utcnow(),
        )


@dataclass(eq=False)
class Conversation(TenantAwareEntity):
    """Conversation aggregate root.

    Tracks the WhatsApp dialogue between a client and the bot for a specific
    business. Carries the current state machine position and the entities
    collected so far (service, date, time, etc.).
    """

    business_id: UUID = UUID(int=0)
    client_id: UUID = UUID(int=0)
    current_state: ConversationState = ConversationState.IDLE
    collected_data: dict = field(default_factory=dict)
    message_count: int = 0
    is_escalated: bool = False
    escalated_at: datetime | None = None
    last_message_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def start(
        cls,
        *,
        tenant_id: UUID,
        business_id: UUID,
        client_id: UUID,
    ) -> Conversation:
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            client_id=client_id,
            current_state=ConversationState.IDLE,
            collected_data={},
            message_count=0,
            is_escalated=False,
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )

    def transition_to(self, new_state: ConversationState) -> None:
        self.current_state = new_state
        self.updated_at = datetime.utcnow()

    def record_message(self) -> None:
        self.message_count += 1
        self.last_message_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def update_collected_data(self, updates: dict) -> None:
        self.collected_data = {**self.collected_data, **updates}
        self.updated_at = datetime.utcnow()

    def escalate(self) -> None:
        self.is_escalated = True
        self.escalated_at = datetime.utcnow()
        self.current_state = ConversationState.HUMAN_HANDOVER
        self.updated_at = datetime.utcnow()
