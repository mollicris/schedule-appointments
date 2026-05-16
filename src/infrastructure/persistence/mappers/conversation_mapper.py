from __future__ import annotations

from src.domain.conversation.conversation import Conversation, Message
from src.domain.conversation.value_objects import ConversationState
from src.infrastructure.persistence.models.conversation import ConversationModel, MessageModel


class ConversationMapper:
    @staticmethod
    def to_model(conversation: Conversation) -> ConversationModel:
        return ConversationModel(
            id=conversation.id,
            tenant_id=conversation.tenant_id,
            business_id=conversation.business_id,
            client_id=conversation.client_id,
            current_state=conversation.current_state.value,
            collected_data=conversation.collected_data,
            message_count=conversation.message_count,
            is_escalated=conversation.is_escalated,
            escalated_at=conversation.escalated_at,
            last_message_at=conversation.last_message_at,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    @staticmethod
    def to_domain(model: ConversationModel) -> Conversation:
        return Conversation(
            id=model.id,
            tenant_id=model.tenant_id,
            business_id=model.business_id,
            client_id=model.client_id,
            current_state=ConversationState(model.current_state),
            collected_data=model.collected_data or {},
            message_count=model.message_count,
            is_escalated=model.is_escalated,
            escalated_at=model.escalated_at,
            last_message_at=model.last_message_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class MessageMapper:
    @staticmethod
    def to_model(message: Message) -> MessageModel:
        return MessageModel(
            id=message.id,
            tenant_id=message.tenant_id,
            conversation_id=message.conversation_id,
            sender=message.sender,
            message_type=message.message_type,
            content=message.content,
            extra_data=message.extra_data,
            whatsapp_message_id=message.whatsapp_message_id,
            created_at=message.created_at,
        )

    @staticmethod
    def to_domain(model: MessageModel) -> Message:
        return Message(
            id=model.id,
            tenant_id=model.tenant_id,
            conversation_id=model.conversation_id,
            sender=model.sender,
            message_type=model.message_type,
            content=model.content,
            extra_data=model.extra_data,
            whatsapp_message_id=model.whatsapp_message_id,
            created_at=model.created_at,
        )
