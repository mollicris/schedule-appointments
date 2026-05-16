from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.shared.tenant_context import get_current_tenant
from src.domain.business.business import Business
from src.domain.business.repository import BusinessRepository
from src.domain.shared.errors import TenantIsolationError
from src.infrastructure.persistence.mappers.business_mapper import BusinessMapper
from src.infrastructure.persistence.models import BusinessModel


class BusinessRepositoryImpl(BusinessRepository):
    """SQLAlchemy implementation of BusinessRepository.

    All operations are scoped to the current tenant via TenantContext.
    Queries enforce tenant isolation at the repository level.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, business_id: UUID) -> Business | None:
        tenant = get_current_tenant()
        stmt = select(BusinessModel).where(
            and_(
                BusinessModel.id == business_id,
                BusinessModel.tenant_id == tenant.tenant_id,
            )
        )
        row = await self._session.scalar(stmt)
        return BusinessMapper.toPersistence(row) if row else None

    async def get_by_slug(self, slug: str) -> Business | None:
        tenant = get_current_tenant()
        stmt = select(BusinessModel).where(
            and_(
                BusinessModel.slug == slug,
                BusinessModel.tenant_id == tenant.tenant_id,
            )
        )
        row = await self._session.scalar(stmt)
        return BusinessMapper.toPersistence(row) if row else None

    async def list_active(self, limit: int = 50, offset: int = 0) -> list[Business]:
        tenant = get_current_tenant()
        stmt = (
            select(BusinessModel)
            .where(
                and_(
                    BusinessModel.tenant_id == tenant.tenant_id,
                    BusinessModel.is_active.is_(True),
                )
            )
            .limit(limit)
            .offset(offset)
        )
        rows = await self._session.scalars(stmt)
        return [BusinessMapper.toPersistence(row) for row in rows if row]

    async def count_active(self) -> int:
        tenant = get_current_tenant()
        stmt = select(1).select_from(BusinessModel).where(
            and_(
                BusinessModel.tenant_id == tenant.tenant_id,
                BusinessModel.is_active.is_(True),
            )
        )
        result = await self._session.scalar(select(select(stmt).scalars().__len__()))
        # Better approach using count
        from sqlalchemy import func

        count_stmt = select(func.count(BusinessModel.id)).where(
            and_(
                BusinessModel.tenant_id == tenant.tenant_id,
                BusinessModel.is_active.is_(True),
            )
        )
        count = await self._session.scalar(count_stmt)
        return count or 0

    async def slug_exists(self, slug: str) -> bool:
        tenant = get_current_tenant()
        stmt = select(1).select_from(BusinessModel).where(
            and_(
                BusinessModel.slug == slug,
                BusinessModel.tenant_id == tenant.tenant_id,
            )
        )
        result = await self._session.scalar(stmt)
        return result is not None

    async def add(self, business: Business) -> None:
        tenant = get_current_tenant()
        # Verify that the business being added belongs to the current tenant
        if business.tenant_id != tenant.tenant_id:
            raise TenantIsolationError(
                f"Cannot add business for tenant {business.tenant_id}; "
                f"current tenant is {tenant.tenant_id}"
            )

        model = BusinessMapper.fromPersistence(business)
        self._session.add(model)
        await self._session.flush()

    async def update(self, business: Business) -> None:
        tenant = get_current_tenant()
        # Verify that the business being updated belongs to the current tenant
        if business.tenant_id != tenant.tenant_id:
            raise TenantIsolationError(
                f"Cannot update business for tenant {business.tenant_id}; "
                f"current tenant is {tenant.tenant_id}"
            )

        model = BusinessMapper.fromPersistence(business)
        await self._session.merge(model)

    async def delete(self, business_id: UUID) -> bool:
        tenant = get_current_tenant()
        stmt = select(BusinessModel).where(
            and_(
                BusinessModel.id == business_id,
                BusinessModel.tenant_id == tenant.tenant_id,
            )
        )
        row = await self._session.scalar(stmt)
        if not row:
            return False

        row.is_active = False
        await self._session.flush()
        return True
