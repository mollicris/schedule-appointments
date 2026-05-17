from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.domain.conversation.human_transfer_repository import HumanTransferRepository
from src.domain.conversation.repository import ConversationRepository
from src.domain.identity.repository import UserRepository
from src.presentation.dependencies import (
    get_conversation_repository,
    get_human_transfer_repository,
    get_user_repository,
)
from src.presentation.schemas import PaginatedResponse, SuccessResponse, paginated_response, success_response
from src.application.shared.tenant_context import get_current_tenant

router = APIRouter()


class TransferResponse(BaseModel):
    transfer_id: UUID
    conversation_id: UUID
    client_id: UUID
    reason: str | None
    status: str
    context_snapshot: list
    created_at: datetime
    resolved_at: datetime | None


@router.get(
    "/businesses/{business_id}/transfers",
    status_code=status.HTTP_200_OK,
    summary="List human transfers for a business",
    tags=["transfers"],
)
async def list_transfers(
    business_id: UUID,
    transfer_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    transfers: Annotated[HumanTransferRepository, Depends(get_human_transfer_repository)] = ...,
) -> PaginatedResponse:
    offset = (page - 1) * page_size
    items = await transfers.list_by_business(
        business_id, status=transfer_status, limit=page_size, offset=offset
    )
    total = await transfers.count_by_business(business_id, status=transfer_status)
    return paginated_response(
        data=[
            TransferResponse(
                transfer_id=t.id,
                conversation_id=t.conversation_id,
                client_id=t.client_id,
                reason=t.reason,
                status=t.status,
                context_snapshot=t.context_snapshot,
                created_at=t.created_at,
                resolved_at=t.resolved_at,
            )
            for t in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/transfers/{transfer_id}/resolve",
    status_code=status.HTTP_200_OK,
    summary="Resolve a human transfer (re-activates the bot)",
    tags=["transfers"],
)
async def resolve_transfer(
    transfer_id: UUID,
    transfers: Annotated[HumanTransferRepository, Depends(get_human_transfer_repository)],
    conversations: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> SuccessResponse:
    ctx = get_current_tenant()
    transfer = await transfers.get_by_id(transfer_id)
    if transfer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found")
    if transfer.status == "resolved":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already resolved")

    transfer.resolve(resolved_by_id=ctx.user_id)
    await transfers.update(transfer)

    # Re-activate the conversation so the bot responds again
    conv = await conversations.get_by_id(transfer.conversation_id)
    if conv is not None:
        from src.domain.conversation.value_objects import ConversationState
        conv.is_escalated = False
        conv.escalated_at = None
        conv.transition_to(ConversationState.IDLE)
        await conversations.update(conv)

    return success_response(
        message="Transfer resolved. Bot re-activated.",
        code="TRANSFER_RESOLVED",
        data={"transfer_id": str(transfer_id)},
    )
