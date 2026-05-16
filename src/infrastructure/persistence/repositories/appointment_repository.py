from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.shared.tenant_context import get_current_tenant
from src.domain.appointment.appointment import Appointment
from src.domain.appointment.repository import AppointmentRepository
from src.domain.appointment.value_objects import AppointmentStatus
from src.infrastructure.persistence.mappers.appointment_mapper import AppointmentMapper
from src.infrastructure.persistence.models.appointment import AppointmentModel


class AppointmentRepositoryImpl(AppointmentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, appointment_id: UUID) -> Appointment | None:
        tenant = get_current_tenant()
        row = await self._session.scalar(
            select(AppointmentModel).where(
                AppointmentModel.id == appointment_id,
                AppointmentModel.tenant_id == tenant.tenant_id,
            )
        )
        return AppointmentMapper.to_domain(row) if row else None

    async def list_by_business(
        self,
        business_id: UUID,
        *,
        on_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Appointment]:
        tenant = get_current_tenant()
        conditions = [
            AppointmentModel.business_id == business_id,
            AppointmentModel.tenant_id == tenant.tenant_id,
        ]
        if on_date is not None:
            day_start = datetime(on_date.year, on_date.month, on_date.day, tzinfo=timezone.utc)
            day_end = datetime(on_date.year, on_date.month, on_date.day, 23, 59, 59, tzinfo=timezone.utc)
            conditions.append(AppointmentModel.scheduled_at >= day_start)
            conditions.append(AppointmentModel.scheduled_at <= day_end)

        rows = await self._session.scalars(
            select(AppointmentModel)
            .where(and_(*conditions))
            .order_by(AppointmentModel.scheduled_at)
            .limit(limit)
            .offset(offset)
        )
        return [AppointmentMapper.to_domain(r) for r in rows]

    async def count_by_business(
        self,
        business_id: UUID,
        on_date: date | None = None,
    ) -> int:
        tenant = get_current_tenant()
        conditions = [
            AppointmentModel.business_id == business_id,
            AppointmentModel.tenant_id == tenant.tenant_id,
        ]
        if on_date is not None:
            day_start = datetime(on_date.year, on_date.month, on_date.day, tzinfo=timezone.utc)
            day_end = datetime(on_date.year, on_date.month, on_date.day, 23, 59, 59, tzinfo=timezone.utc)
            conditions.append(AppointmentModel.scheduled_at >= day_start)
            conditions.append(AppointmentModel.scheduled_at <= day_end)

        count = await self._session.scalar(
            select(func.count(AppointmentModel.id)).where(and_(*conditions))
        )
        return count or 0

    async def list_active_in_range(
        self,
        business_id: UUID,
        start: datetime,
        end: datetime,
        professional_id: UUID | None = None,
    ) -> list[Appointment]:
        """Return active appointments that overlap with [start, end)."""
        tenant = get_current_tenant()
        active_statuses = [
            AppointmentStatus.PENDING.value,
            AppointmentStatus.CONFIRMED.value,
            AppointmentStatus.RESCHEDULED.value,
        ]
        conditions = [
            AppointmentModel.business_id == business_id,
            AppointmentModel.tenant_id == tenant.tenant_id,
            AppointmentModel.status.in_(active_statuses),
            AppointmentModel.scheduled_at < end,
        ]
        if professional_id is not None:
            conditions.append(AppointmentModel.professional_id == professional_id)

        rows = await self._session.scalars(
            select(AppointmentModel).where(and_(*conditions))
        )
        # Filter by end time in Python (scheduled_at + duration > start)
        result = []
        for r in rows:
            apt_end = datetime(
                r.scheduled_at.year,
                r.scheduled_at.month,
                r.scheduled_at.day,
                r.scheduled_at.hour,
                r.scheduled_at.minute,
                r.scheduled_at.second,
                tzinfo=r.scheduled_at.tzinfo,
            )
            from datetime import timedelta
            apt_end = r.scheduled_at + timedelta(minutes=r.duration_minutes)
            if apt_end > start:
                result.append(AppointmentMapper.to_domain(r))
        return result

    async def add(self, appointment: Appointment) -> None:
        self._session.add(AppointmentMapper.to_model(appointment))
        await self._session.flush()

    async def update(self, appointment: Appointment) -> None:
        await self._session.merge(AppointmentMapper.to_model(appointment))
        await self._session.flush()
