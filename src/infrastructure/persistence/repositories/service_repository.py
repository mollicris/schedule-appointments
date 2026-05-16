from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.shared.tenant_context import get_current_tenant
from src.domain.service.service import Service
from src.domain.service.repository import ServiceRepository
from src.domain.shared.errors import TenantIsolationError
from src.infrastructure.persistence.mappers.service_mapper import ServiceMapper
from src.infrastructure.persistence.models import ServiceModel


class ServiceRepositoryImpl(ServiceRepository):
    """SQLAlchemy implementation of ServiceRepository.

    All operations are scoped to the current tenant via TenantContext.
    Queries enforce tenant isolation at the repository level.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, service_id: UUID) -> Service | None:
        tenant = get_current_tenant()
        stmt = select(ServiceModel).where(
            and_(
                ServiceModel.id == service_id,
                ServiceModel.tenant_id == tenant.tenant_id,
            )
        )
        row = await self._session.scalar(stmt)
        return ServiceMapper.toPersistence(row) if row else None

    async def list_by_business(self, business_id: UUID, limit: int = 50, offset: int = 0) -> list[Service]:
        tenant = get_current_tenant()
        stmt = (
            select(ServiceModel)
            .where(
                and_(
                    ServiceModel.tenant_id == tenant.tenant_id,
                    ServiceModel.business_id == business_id,
                    ServiceModel.is_active.is_(True),
                )
            )
            .limit(limit)
            .offset(offset)
        )
        rows = await self._session.scalars(stmt)
        return [ServiceMapper.toPersistence(row) for row in rows if row]

    async def count_by_business(self, business_id: UUID) -> int:
        tenant = get_current_tenant()
        count_stmt = select(func.count(ServiceModel.id)).where(
            and_(
                ServiceModel.tenant_id == tenant.tenant_id,
                ServiceModel.business_id == business_id,
                ServiceModel.is_active.is_(True),
            )
        )
        count = await self._session.scalar(count_stmt)
        return count or 0

    async def add(self, service: Service) -> None:
        tenant = get_current_tenant()
        # Verify that the service being added belongs to the current tenant
        if service.tenant_id != tenant.tenant_id:
            raise TenantIsolationError(
                f"Cannot add service for tenant {service.tenant_id}; "
                f"current tenant is {tenant.tenant_id}"
            )

        model = ServiceMapper.fromPersistence(service)
        self._session.add(model)
        await self._session.flush()

    async def update(self, service: Service) -> None:
        tenant = get_current_tenant()
        # Verify that the service being updated belongs to the current tenant
        if service.tenant_id != tenant.tenant_id:
            raise TenantIsolationError(
                f"Cannot update service for tenant {service.tenant_id}; "
                f"current tenant is {tenant.tenant_id}"
            )

        model = ServiceMapper.fromPersistence(service)
        await self._session.merge(model)

    async def delete(self, service_id: UUID) -> bool:
        tenant = get_current_tenant()
        stmt = select(ServiceModel).where(
            and_(
                ServiceModel.id == service_id,
                ServiceModel.tenant_id == tenant.tenant_id,
            )
        )
        row = await self._session.scalar(stmt)
        if not row:
            return False

        row.is_active = False
        await self._session.flush()
        return True
