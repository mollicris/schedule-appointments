from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.domain.client.repository import ClientRepository
from src.domain.conversation.repository import ConversationRepository
from src.presentation.dependencies import (
    get_client_repository,
    get_conversation_repository,
)
from src.presentation.schemas import PaginatedResponse, SuccessResponse, paginated_response, success_response

router = APIRouter()


class MessageResponse(BaseModel):
    message_id: UUID
    sender: str
    message_type: str
    content: str
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    conversation_id: UUID
    client_id: UUID
    client_name: str
    client_whatsapp: str
    current_state: str
    message_count: int
    is_escalated: bool
    last_message_at: datetime


class ConversationDetailResponse(BaseModel):
    conversation_id: UUID
    client_id: UUID
    client_name: str
    client_whatsapp: str
    current_state: str
    message_count: int
    is_escalated: bool
    last_message_at: datetime
    messages: list[MessageResponse]


@router.get(
    "/businesses/{business_id}/conversations",
    status_code=status.HTTP_200_OK,
    summary="List conversations for a business",
    tags=["conversations"],
)
async def list_conversations(
    business_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conversations: Annotated[ConversationRepository, Depends(get_conversation_repository)] = ...,
    clients: Annotated[ClientRepository, Depends(get_client_repository)] = ...,
) -> PaginatedResponse:
    from src.application.shared.tenant_context import get_current_tenant
    offset = (page - 1) * page_size

    convs = await conversations.list_by_business(business_id, limit=page_size, offset=offset)
    total = await conversations.count_by_business(business_id)

    # Load client info for each conversation
    client_cache: dict[UUID, object] = {}
    items = []
    for conv in convs:
        if conv.client_id not in client_cache:
            client = await clients.get_by_id(conv.client_id)
            client_cache[conv.client_id] = client
        client = client_cache[conv.client_id]
        items.append(ConversationSummaryResponse(
            conversation_id=conv.id,
            client_id=conv.client_id,
            client_name=client.name if client else "Desconocido",
            client_whatsapp=client.whatsapp_number if client else "",
            current_state=conv.current_state.value,
            message_count=conv.message_count,
            is_escalated=conv.is_escalated,
            last_message_at=conv.last_message_at,
        ))

    return paginated_response(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_200_OK,
    summary="Get messages for a conversation",
    tags=["conversations"],
)
async def get_conversation_messages(
    conversation_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    conversations: Annotated[ConversationRepository, Depends(get_conversation_repository)] = ...,
    clients: Annotated[ClientRepository, Depends(get_client_repository)] = ...,
) -> SuccessResponse:
    conv = await conversations.get_by_id(conversation_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    client = await clients.get_by_id(conv.client_id)
    messages = await conversations.get_recent_messages(conversation_id, limit=limit)

    return success_response(
        data=ConversationDetailResponse(
            conversation_id=conv.id,
            client_id=conv.client_id,
            client_name=client.name if client else "Desconocido",
            client_whatsapp=client.whatsapp_number if client else "",
            current_state=conv.current_state.value,
            message_count=conv.message_count,
            is_escalated=conv.is_escalated,
            last_message_at=conv.last_message_at,
            messages=[
                MessageResponse(
                    message_id=m.id,
                    sender=m.sender,
                    message_type=m.message_type,
                    content=m.content,
                    created_at=m.created_at,
                )
                for m in messages
            ],
        ),
    )
