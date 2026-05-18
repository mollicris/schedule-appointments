from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.shared.tenant_context import get_current_tenant
from src.domain.professional.professional import Professional
from src.domain.professional.repository import ProfessionalRepository
from src.domain.shared.errors import TenantIsolationError
from src.infrastructure.persistence.mappers.professional_mapper import ProfessionalMapper
from src.infrastructure.persistence.models import ProfessionalModel, ServiceProfessionalModel


class ProfessionalRepositoryImpl(ProfessionalRepository):
    """SQLAlchemy implementation of ProfessionalRepository.

    All operations are scoped to the current tenant via TenantContext.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, professional_id: UUID) -> Professional | None:
        tenant = get_current_tenant()
        stmt = select(ProfessionalModel).where(
            and_(
                ProfessionalModel.id == professional_id,
                ProfessionalModel.tenant_id == tenant.tenant_id,
            )
        )
        row = await self._session.scalar(stmt)
        return ProfessionalMapper.toPersistence(row) if row else None

    async def get_by_user_and_business(self, user_id: UUID, business_id: UUID) -> Professional | None:
        tenant = get_current_tenant()
        stmt = select(ProfessionalModel).where(
            and_(
                ProfessionalModel.user_id == user_id,
                ProfessionalModel.business_id == business_id,
                ProfessionalModel.tenant_id == tenant.tenant_id,
            )
        )
        row = await self._session.scalar(stmt)
        return ProfessionalMapper.toPersistence(row) if row else None

    async def list_by_business(self, business_id: UUID, limit: int = 50, offset: int = 0) -> list[Professional]:
        tenant = get_current_tenant()
        stmt = (
            select(ProfessionalModel)
            .where(
                and_(
                    ProfessionalModel.tenant_id == tenant.tenant_id,
                    ProfessionalModel.business_id == business_id,
                    ProfessionalModel.is_active.is_(True),
                )
            )
            .limit(limit)
            .offset(offset)
        )
        rows = await self._session.scalars(stmt)
        return [ProfessionalMapper.toPersistence(row) for row in rows if row]

    async def count_by_business(self, business_id: UUID) -> int:
        tenant = get_current_tenant()
        count_stmt = select(func.count(ProfessionalModel.id)).where(
            and_(
                ProfessionalModel.tenant_id == tenant.tenant_id,
                ProfessionalModel.business_id == business_id,
                ProfessionalModel.is_active.is_(True),
            )
        )
        count = await self._session.scalar(count_stmt)
        return count or 0

    async def user_in_business_exists(self, user_id: UUID, business_id: UUID) -> bool:
        tenant = get_current_tenant()
        stmt = select(1).select_from(ProfessionalModel).where(
            and_(
                ProfessionalModel.user_id == user_id,
                ProfessionalModel.business_id == business_id,
                ProfessionalModel.tenant_id == tenant.tenant_id,
            )
        )
        result = await self._session.scalar(stmt)
        return result is not None

    async def add(self, professional: Professional) -> None:
        tenant = get_current_tenant()
        if professional.tenant_id != tenant.tenant_id:
            raise TenantIsolationError(
                f"Cannot add professional for tenant {professional.tenant_id}; "
                f"current tenant is {tenant.tenant_id}"
            )
        model = ProfessionalMapper.fromPersistence(professional)
        self._session.add(model)
        await self._session.flush()

    async def update(self, professional: Professional) -> None:
        tenant = get_current_tenant()
        if professional.tenant_id != tenant.tenant_id:
            raise TenantIsolationError(
                f"Cannot update professional for tenant {professional.tenant_id}; "
                f"current tenant is {tenant.tenant_id}"
            )
        model = ProfessionalMapper.fromPersistence(professional)
        await self._session.merge(model)

    async def delete(self, professional_id: UUID) -> bool:
        tenant = get_current_tenant()
        stmt = select(ProfessionalModel).where(
            and_(
                ProfessionalModel.id == professional_id,
                ProfessionalModel.tenant_id == tenant.tenant_id,
            )
        )
        row = await self._session.scalar(stmt)
        if not row:
            return False

        row.is_active = False
        await self._session.flush()
        return True

    async def list_by_service(self, service_id: UUID) -> list[Professional]:
        tenant = get_current_tenant()
        stmt = (
            select(ProfessionalModel)
            .join(
                ServiceProfessionalModel,
                ServiceProfessionalModel.professional_id == ProfessionalModel.id,
            )
            .where(
                and_(
                    ServiceProfessionalModel.service_id == service_id,
                    ProfessionalModel.tenant_id == tenant.tenant_id,
                    ProfessionalModel.is_active.is_(True),
                )
            )
        )
        rows = await self._session.scalars(stmt)
        return [ProfessionalMapper.toPersistence(row) for row in rows if row]
