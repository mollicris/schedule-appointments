from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.shared.tenant_context import get_current_tenant
from src.domain.conversation.human_transfer import HumanTransfer
from src.domain.conversation.human_transfer_repository import HumanTransferRepository
from src.infrastructure.persistence.models.conversation import HumanTransferModel


def _to_domain(m: HumanTransferModel) -> HumanTransfer:
    return HumanTransfer(
        id=m.id,
        tenant_id=m.tenant_id,
        business_id=m.business_id,
        conversation_id=m.conversation_id,
        client_id=m.client_id,
        reason=m.reason,
        context_snapshot=m.context_snapshot or [],
        status=m.status,
        resolved_at=m.resolved_at,
        resolved_by_id=m.resolved_by_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_model(t: HumanTransfer) -> HumanTransferModel:
    return HumanTransferModel(
        id=t.id,
        tenant_id=t.tenant_id,
        business_id=t.business_id,
        conversation_id=t.conversation_id,
        client_id=t.client_id,
        reason=t.reason,
        context_snapshot=t.context_snapshot,
        status=t.status,
        resolved_at=t.resolved_at,
        resolved_by_id=t.resolved_by_id,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


class HumanTransferRepositoryImpl(HumanTransferRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, transfer: HumanTransfer) -> None:
        self._session.add(_to_model(transfer))
        await self._session.flush()

    async def get_by_id(self, transfer_id: UUID) -> HumanTransfer | None:
        tenant = get_current_tenant()
        row = await self._session.scalar(
            select(HumanTransferModel).where(
                HumanTransferModel.id == transfer_id,
                HumanTransferModel.tenant_id == tenant.tenant_id,
            )
        )
        return _to_domain(row) if row else None

    async def list_by_business(
        self,
        business_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[HumanTransfer]:
        tenant = get_current_tenant()
        conditions = [
            HumanTransferModel.business_id == business_id,
            HumanTransferModel.tenant_id == tenant.tenant_id,
        ]
        if status is not None:
            conditions.append(HumanTransferModel.status == status)
        rows = await self._session.scalars(
            select(HumanTransferModel)
            .where(*conditions)
            .order_by(HumanTransferModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain(r) for r in rows]

    async def count_by_business(self, business_id: UUID, status: str | None = None) -> int:
        tenant = get_current_tenant()
        conditions = [
            HumanTransferModel.business_id == business_id,
            HumanTransferModel.tenant_id == tenant.tenant_id,
        ]
        if status is not None:
            conditions.append(HumanTransferModel.status == status)
        count = await self._session.scalar(
            select(func.count(HumanTransferModel.id)).where(*conditions)
        )
        return count or 0

    async def update(self, transfer: HumanTransfer) -> None:
        await self._session.merge(_to_model(transfer))
        await self._session.flush()
