from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.shared.tenant_context import get_current_tenant
from src.domain.service.service import Service
from src.domain.service.repository import ServiceRepository
from src.domain.shared.errors import TenantIsolationError
from src.infrastructure.persistence.mappers.service_mapper import ServiceMapper
from src.infrastructure.persistence.models import ServiceModel, ServiceProfessionalModel


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

    async def list_professional_ids(self, service_id: UUID) -> list[UUID]:
        tenant = get_current_tenant()
        stmt = select(ServiceProfessionalModel.professional_id).where(
            and_(
                ServiceProfessionalModel.service_id == service_id,
                ServiceProfessionalModel.tenant_id == tenant.tenant_id,
            )
        )
        rows = await self._session.scalars(stmt)
        return list(rows)

    async def set_professionals(self, service_id: UUID, professional_ids: list[UUID]) -> None:
        tenant = get_current_tenant()

        # Delete existing assignments for this service
        await self._session.execute(
            sa_delete(ServiceProfessionalModel).where(
                and_(
                    ServiceProfessionalModel.service_id == service_id,
                    ServiceProfessionalModel.tenant_id == tenant.tenant_id,
                )
            )
        )

        # Insert the new set (deduplicate)
        for pid in set(professional_ids):
            self._session.add(
                ServiceProfessionalModel(
                    tenant_id=tenant.tenant_id,
                    service_id=service_id,
                    professional_id=pid,
                )
            )
        await self._session.flush()
