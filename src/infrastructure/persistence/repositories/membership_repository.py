from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.shared.tenant_context import get_current_tenant
from src.domain.membership.membership import Membership
from src.domain.membership.membership_plan import MembershipPlan
from src.domain.membership.repository import MembershipPlanRepository, MembershipRepository
from src.domain.membership.value_objects import MembershipStatus
from src.domain.shared.errors import TenantIsolationError
from src.infrastructure.persistence.mappers.membership_mapper import (
    MembershipMapper,
    MembershipPlanMapper,
)
from src.infrastructure.persistence.models import (
    MembershipModel,
    MembershipPlanModel,
    MembershipPlanServiceModel,
)

_LIVE_STATUSES = (MembershipStatus.ACTIVE.value, MembershipStatus.FROZEN.value)


class MembershipPlanRepositoryImpl(MembershipPlanRepository):
    """SQLAlchemy implementation of MembershipPlanRepository.

    Every query filters by the current tenant (defence in depth on top of RLS).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, plan_id: UUID) -> MembershipPlan | None:
        tenant = get_current_tenant()
        row = await self._session.scalar(
            select(MembershipPlanModel).where(
                and_(
                    MembershipPlanModel.id == plan_id,
                    MembershipPlanModel.tenant_id == tenant.tenant_id,
                )
            )
        )
        return MembershipPlanMapper.to_domain(row) if row else None

    async def list_by_business(
        self,
        business_id: UUID,
        *,
        include_inactive: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MembershipPlan]:
        tenant = get_current_tenant()
        conditions = [
            MembershipPlanModel.tenant_id == tenant.tenant_id,
            MembershipPlanModel.business_id == business_id,
        ]
        if not include_inactive:
            conditions.append(MembershipPlanModel.is_active.is_(True))

        rows = await self._session.scalars(
            select(MembershipPlanModel)
            .where(and_(*conditions))
            .order_by(MembershipPlanModel.price)
            .limit(limit)
            .offset(offset)
        )
        return [MembershipPlanMapper.to_domain(row) for row in rows]

    async def count_by_business(
        self,
        business_id: UUID,
        *,
        include_inactive: bool = False,
    ) -> int:
        tenant = get_current_tenant()
        conditions = [
            MembershipPlanModel.tenant_id == tenant.tenant_id,
            MembershipPlanModel.business_id == business_id,
        ]
        if not include_inactive:
            conditions.append(MembershipPlanModel.is_active.is_(True))

        count = await self._session.scalar(
            select(func.count(MembershipPlanModel.id)).where(and_(*conditions))
        )
        return count or 0

    async def add(self, plan: MembershipPlan) -> None:
        tenant = get_current_tenant()
        if plan.tenant_id != tenant.tenant_id:
            raise TenantIsolationError(
                f"Cannot add membership plan for tenant {plan.tenant_id}; "
                f"current tenant is {tenant.tenant_id}"
            )
        self._session.add(MembershipPlanMapper.to_model(plan))
        await self._session.flush()

    async def update(self, plan: MembershipPlan) -> None:
        tenant = get_current_tenant()
        if plan.tenant_id != tenant.tenant_id:
            raise TenantIsolationError(
                f"Cannot update membership plan of tenant {plan.tenant_id}; "
                f"current tenant is {tenant.tenant_id}"
            )
        await self._session.merge(MembershipPlanMapper.to_model(plan))
        await self._session.flush()

    async def list_service_ids(self, plan_id: UUID) -> list[UUID]:
        tenant = get_current_tenant()
        rows = await self._session.scalars(
            select(MembershipPlanServiceModel.service_id).where(
                and_(
                    MembershipPlanServiceModel.membership_plan_id == plan_id,
                    MembershipPlanServiceModel.tenant_id == tenant.tenant_id,
                )
            )
        )
        return list(rows)

    async def set_services(self, plan_id: UUID, service_ids: list[UUID]) -> None:
        tenant = get_current_tenant()
        await self._session.execute(
            sa_delete(MembershipPlanServiceModel).where(
                and_(
                    MembershipPlanServiceModel.membership_plan_id == plan_id,
                    MembershipPlanServiceModel.tenant_id == tenant.tenant_id,
                )
            )
        )
        for service_id in dict.fromkeys(service_ids):   # de-duplicate, keep order
            self._session.add(
                MembershipPlanServiceModel(
                    id=uuid4(),
                    tenant_id=tenant.tenant_id,
                    membership_plan_id=plan_id,
                    service_id=service_id,
                )
            )
        await self._session.flush()


class MembershipRepositoryImpl(MembershipRepository):
    """SQLAlchemy implementation of MembershipRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, membership_id: UUID) -> Membership | None:
        tenant = get_current_tenant()
        row = await self._session.scalar(
            select(MembershipModel).where(
                and_(
                    MembershipModel.id == membership_id,
                    MembershipModel.tenant_id == tenant.tenant_id,
                )
            )
        )
        return MembershipMapper.to_domain(row) if row else None

    async def get_current_for_client(
        self,
        client_id: UUID,
        business_id: UUID,
    ) -> Membership | None:
        tenant = get_current_tenant()
        row = await self._session.scalar(
            select(MembershipModel)
            .where(
                and_(
                    MembershipModel.tenant_id == tenant.tenant_id,
                    MembershipModel.business_id == business_id,
                    MembershipModel.client_id == client_id,
                    MembershipModel.status.in_(_LIVE_STATUSES),
                )
            )
            .order_by(MembershipModel.ends_at.desc())
        )
        return MembershipMapper.to_domain(row) if row else None

    async def list_by_client(
        self,
        client_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Membership]:
        tenant = get_current_tenant()
        rows = await self._session.scalars(
            select(MembershipModel)
            .where(
                and_(
                    MembershipModel.tenant_id == tenant.tenant_id,
                    MembershipModel.client_id == client_id,
                )
            )
            .order_by(MembershipModel.ends_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [MembershipMapper.to_domain(row) for row in rows]

    async def list_by_business(
        self,
        business_id: UUID,
        *,
        status: MembershipStatus | None = None,
        expiring_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Membership]:
        rows = await self._session.scalars(
            select(MembershipModel)
            .where(and_(*self._filters(business_id, status, expiring_before)))
            .order_by(MembershipModel.ends_at)
            .limit(limit)
            .offset(offset)
        )
        return [MembershipMapper.to_domain(row) for row in rows]

    async def count_by_business(
        self,
        business_id: UUID,
        *,
        status: MembershipStatus | None = None,
        expiring_before: datetime | None = None,
    ) -> int:
        count = await self._session.scalar(
            select(func.count(MembershipModel.id)).where(
                and_(*self._filters(business_id, status, expiring_before))
            )
        )
        return count or 0

    async def add(self, membership: Membership) -> None:
        tenant = get_current_tenant()
        if membership.tenant_id != tenant.tenant_id:
            raise TenantIsolationError(
                f"Cannot add membership for tenant {membership.tenant_id}; "
                f"current tenant is {tenant.tenant_id}"
            )
        self._session.add(MembershipMapper.to_model(membership))
        await self._session.flush()

    async def update(self, membership: Membership) -> None:
        tenant = get_current_tenant()
        if membership.tenant_id != tenant.tenant_id:
            raise TenantIsolationError(
                f"Cannot update membership of tenant {membership.tenant_id}; "
                f"current tenant is {tenant.tenant_id}"
            )
        await self._session.merge(MembershipMapper.to_model(membership))
        await self._session.flush()

    def _filters(
        self,
        business_id: UUID,
        status: MembershipStatus | None,
        expiring_before: datetime | None,
    ) -> list:
        tenant = get_current_tenant()
        conditions = [
            MembershipModel.tenant_id == tenant.tenant_id,
            MembershipModel.business_id == business_id,
        ]
        if status is not None:
            conditions.append(MembershipModel.status == status.value)
        if expiring_before is not None:
            conditions.append(MembershipModel.ends_at <= expiring_before)
        return conditions
