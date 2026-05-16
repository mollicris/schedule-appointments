from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.shared.tenant_context import get_current_tenant
from src.domain.business_hours.business_hour import BusinessHour
from src.domain.business_hours.repository import BusinessHourRepository
from src.infrastructure.persistence.mappers.business_hour_mapper import BusinessHourMapper
from src.infrastructure.persistence.models import BusinessHourModel


class BusinessHourRepositoryImpl(BusinessHourRepository):
    """SQLAlchemy implementation of BusinessHourRepository.

    Upsert uses PostgreSQL INSERT … ON CONFLICT DO UPDATE so that setting
    a day's schedule is idempotent regardless of whether it existed before.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_business(self, business_id: UUID) -> list[BusinessHour]:
        tenant = get_current_tenant()
        stmt = select(BusinessHourModel).where(
            and_(
                BusinessHourModel.business_id == business_id,
                BusinessHourModel.tenant_id == tenant.tenant_id,
            )
        )
        rows = await self._session.scalars(stmt)
        return [BusinessHourMapper.toPersistence(row) for row in rows if row]

    async def get_by_business_and_day(self, business_id: UUID, day_of_week: int) -> BusinessHour | None:
        tenant = get_current_tenant()
        stmt = select(BusinessHourModel).where(
            and_(
                BusinessHourModel.business_id == business_id,
                BusinessHourModel.tenant_id == tenant.tenant_id,
                BusinessHourModel.day_of_week == str(day_of_week),
            )
        )
        row = await self._session.scalar(stmt)
        return BusinessHourMapper.toPersistence(row) if row else None

    async def upsert(self, business_hour: BusinessHour) -> None:
        await self._upsert_one(business_hour)
        await self._session.flush()

    async def upsert_many(self, business_hours: list[BusinessHour]) -> None:
        for bh in business_hours:
            await self._upsert_one(bh)
        await self._session.flush()

    async def _upsert_one(self, bh: BusinessHour) -> None:
        """PostgreSQL upsert on (business_id, day_of_week) uniqueness."""
        values = {
            "id": bh.id,
            "tenant_id": bh.tenant_id,
            "business_id": bh.business_id,
            "day_of_week": str(bh.day_of_week),
            "open_at": bh.open_at,
            "close_at": bh.close_at,
            "is_closed": bh.is_closed,
            "created_at": bh.created_at,
            "updated_at": bh.updated_at,
        }
        stmt = (
            pg_insert(BusinessHourModel)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["business_id", "day_of_week"],
                set_={
                    "open_at": bh.open_at,
                    "close_at": bh.close_at,
                    "is_closed": bh.is_closed,
                    "updated_at": bh.updated_at,
                },
            )
        )
        await self._session.execute(stmt)
