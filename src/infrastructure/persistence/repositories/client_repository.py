from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.shared.tenant_context import get_current_tenant
from src.domain.client.client import Client
from src.domain.client.repository import ClientRepository
from src.infrastructure.persistence.mappers.client_mapper import ClientMapper
from src.infrastructure.persistence.models.client import ClientModel


class ClientRepositoryImpl(ClientRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, client_id: UUID) -> Client | None:
        tenant = get_current_tenant()
        row = await self._session.scalar(
            select(ClientModel).where(
                ClientModel.id == client_id,
                ClientModel.tenant_id == tenant.tenant_id,
            )
        )
        return ClientMapper.to_domain(row) if row else None

    async def get_by_whatsapp(self, whatsapp_number: str) -> Client | None:
        tenant = get_current_tenant()
        row = await self._session.scalar(
            select(ClientModel).where(
                ClientModel.whatsapp_number == whatsapp_number,
                ClientModel.tenant_id == tenant.tenant_id,
                ClientModel.is_active.is_(True),
            )
        )
        return ClientMapper.to_domain(row) if row else None

    async def add(self, client: Client) -> None:
        self._session.add(ClientMapper.to_model(client))
        await self._session.flush()

    async def update(self, client: Client) -> None:
        await self._session.merge(ClientMapper.to_model(client))
        await self._session.flush()
