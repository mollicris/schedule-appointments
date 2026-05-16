from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tenant.repository import TenantRepository
from src.domain.tenant.tenant import Tenant
from src.domain.tenant.value_objects import TenantSlug
from src.infrastructure.persistence.mappers.tenant_mapper import TenantMapper
from src.infrastructure.persistence.models import TenantModel


class TenantRepositoryImpl(TenantRepository):
    """SQLAlchemy implementation of TenantRepository.

    Operations on the Tenant aggregate are NOT scoped to a single tenant
    because the Tenant IS the root of multitenancy. This repository only
    uses TenantModel directly (not subject to RLS).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.id == tenant_id)
        row = await self._session.scalar(stmt)
        return TenantMapper.toPersistence(row) if row else None

    async def get_by_slug(self, slug: TenantSlug) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.slug == slug.value)
        row = await self._session.scalar(stmt)
        return TenantMapper.toPersistence(row) if row else None

    async def get_by_admin_email(self, email: str) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.admin_email == email.lower())
        row = await self._session.scalar(stmt)
        return TenantMapper.toPersistence(row) if row else None

    async def slug_exists(self, slug: TenantSlug) -> bool:
        stmt = select(1).select_from(TenantModel).where(TenantModel.slug == slug.value)
        result = await self._session.scalar(stmt)
        return result is not None

    async def email_exists(self, email: str) -> bool:
        stmt = select(1).select_from(TenantModel).where(TenantModel.admin_email == email.lower())
        result = await self._session.scalar(stmt)
        return result is not None

    async def add(self, tenant: Tenant) -> None:
        model = TenantMapper.fromPersistence(tenant)
        self._session.add(model)
        await self._session.flush()

    async def update(self, tenant: Tenant) -> None:
        model = TenantMapper.fromPersistence(tenant)
        await self._session.merge(model)
