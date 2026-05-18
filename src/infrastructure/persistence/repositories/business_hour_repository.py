from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.shared.tenant_context import get_current_tenant
from src.domain.business_hours.business_hour import BusinessHour
from src.domain.business_hours.repository import BusinessHourRepository
from src.infrastructure.persistence.mappers.business_hour_mapper import BusinessHourMapper
from src.infrastructure.persistence.models import BusinessHourModel

logger = logging.getLogger(__name__)


class BusinessHourRepositoryImpl(BusinessHourRepository):
    """SQLAlchemy implementation of BusinessHourRepository.

    Supports multiple time ranges per day (e.g., lunch break).
    When upserting multiple ranges for the same day, deletes old entries
    and inserts new ones with proper sequence numbers.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_business(self, business_id: UUID) -> list[BusinessHour]:
        tenant = get_current_tenant()
        logger.info(f"get_by_business: business_id={business_id}, tenant_id={tenant.tenant_id}")

        stmt = select(BusinessHourModel).where(
            and_(
                BusinessHourModel.business_id == business_id,
                BusinessHourModel.tenant_id == tenant.tenant_id,
            )
        ).order_by(BusinessHourModel.day_of_week, BusinessHourModel.sequence)

        rows = await self._session.scalars(stmt)
        result = [BusinessHourMapper.toPersistence(row) for row in rows if row]

        logger.info(f"get_by_business: Retrieved {len(result)} total records")
        for r in result:
            logger.info(f"  - day {r.day_of_week}: {r.open_at}-{r.close_at}, is_closed={r.is_closed}")

        return result

    async def get_by_business_and_day(self, business_id: UUID, day_of_week: int) -> list[BusinessHour]:
        tenant = get_current_tenant()
        query_day_str = str(day_of_week)
        logger.info(f"get_by_business_and_day QUERY: business_id={business_id}, day_of_week={day_of_week} (as string: '{query_day_str}'), tenant_id={tenant.tenant_id}")

        stmt = select(BusinessHourModel).where(
            and_(
                BusinessHourModel.business_id == business_id,
                BusinessHourModel.tenant_id == tenant.tenant_id,
                BusinessHourModel.day_of_week == query_day_str,
            )
        ).order_by(BusinessHourModel.sequence)

        rows = await self._session.scalars(stmt)
        result = [BusinessHourMapper.toPersistence(row) for row in rows if row]

        logger.info(f"get_by_business_and_day RESULT: Found {len(result)} records for day {day_of_week}")
        for r in result:
            logger.info(f"  - {r.open_at}-{r.close_at}, is_closed={r.is_closed}, day_of_week={r.day_of_week}")

        return result

    async def upsert(self, business_hour: BusinessHour) -> None:
        await self._upsert_one(business_hour)
        await self._session.flush()

    async def upsert_many(self, business_hours: list[BusinessHour]) -> None:
        """Replace all hours for affected days with new entries.

        Supports multiple time ranges per day (e.g., lunch break).
        Groups by (business_id, day_of_week) and deletes old entries before inserting new ones.
        """
        if not business_hours:
            return

        tenant = get_current_tenant()
        logger.info(f"upsert_many: tenant_id={tenant.tenant_id}")
        logger.info(f"upsert_many: Received {len(business_hours)} business hour records")

        # Group by (business_id, day_of_week) manually since input may not be sorted
        from collections import defaultdict

        groups: dict[tuple[UUID, int], list[BusinessHour]] = defaultdict(list)
        for bh in business_hours:
            groups[(bh.business_id, bh.day_of_week)].append(bh)

        logger.info(f"upsert_many: Grouped into {len(groups)} day groups")

        for (bid, dow), items in groups.items():
            logger.info(f"upsert_many: Processing business_id={bid}, day_of_week={dow} with {len(items)} ranges")

            # Delete existing entries for this (business_id, day_of_week)
            stmt = delete(BusinessHourModel).where(
                and_(
                    BusinessHourModel.business_id == bid,
                    BusinessHourModel.day_of_week == str(dow),
                    BusinessHourModel.tenant_id == tenant.tenant_id,
                )
            )
            result = await self._session.execute(stmt)
            logger.info(f"upsert_many: Deleted {result.rowcount} existing records for day {dow}")

            # Sort items by open_at time before assigning sequence numbers
            sorted_items = sorted(items, key=lambda x: x.open_at)
            logger.info(f"upsert_many: Sorted items: {[(item.open_at, item.close_at, item.is_closed) for item in sorted_items]}")

            # Insert new entries with proper sequence
            for seq, bh in enumerate(sorted_items, start=1):
                values = {
                    "id": bh.id,
                    "tenant_id": bh.tenant_id,
                    "business_id": bh.business_id,
                    "day_of_week": str(bh.day_of_week),
                    "sequence": seq,
                    "open_at": bh.open_at,
                    "close_at": bh.close_at,
                    "is_closed": bh.is_closed,
                    "created_at": bh.created_at,
                    "updated_at": bh.updated_at,
                }
                logger.info(f"upsert_many: Inserting day {dow} seq {seq}: {bh.open_at}-{bh.close_at}, is_closed={bh.is_closed}")
                stmt = pg_insert(BusinessHourModel).values(**values)
                await self._session.execute(stmt)

        await self._session.flush()
        logger.info(f"upsert_many: Flush complete")
