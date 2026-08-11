from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, case, cast, func, literal_column, select
from sqlalchemy.dialects.postgresql import INTEGER
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reports.dtos import (
    HeatmapCell,
    HeatmapReport,
    ProfessionalPerformanceItem,
    ProfessionalPerformanceReport,
    StatusBucket,
    StatusDistributionReport,
    SummaryReport,
    TopClientItem,
    TopClientsReport,
    TopServiceItem,
    TopServicesReport,
    TrendPoint,
    TrendReport,
)
from src.application.reports.repository import ReportsRepository
from src.application.shared.tenant_context import get_current_tenant
from src.domain.appointment.value_objects import AppointmentStatus
from src.infrastructure.persistence.models.appointment import AppointmentModel
from src.infrastructure.persistence.models.business import ProfessionalModel, ServiceModel
from src.infrastructure.persistence.models.client import ClientModel


def _revenue() -> object:
    """SUM of what was actually collected, over completed appointments.

    Reads ``appointments.amount_charged`` — the figure the staff recorded when
    closing the appointment — and never ``services.price``. The service price is
    mutable: sourcing revenue from it meant that raising a price rewrote months
    already closed, and that a discount or a longer job was invisible.

    Appointments that are not completed contribute zero, so an open agenda never
    shows as income.
    """
    return func.coalesce(
        func.sum(
            case(
                (
                    and_(
                        AppointmentModel.status == AppointmentStatus.COMPLETED.value,
                        AppointmentModel.amount_charged.isnot(None),
                    ),
                    AppointmentModel.amount_charged,
                ),
                else_=0,
            )
        ),
        0,
    )


class ReportsRepositoryImpl(ReportsRepository):
    """SQL-based implementation of the analytical reports port.

    All queries scope by the current tenant and the provided business_id.
    Revenue is SUM(appointments.amount_charged) over completed appointments,
    in cents. See _revenue() for why it is not the service price.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Summary ──────────────────────────────────────────────────────────────

    async def get_summary(
        self, business_id: UUID, period_start: datetime, period_end: datetime
    ) -> SummaryReport:
        current = await self._summary_block(business_id, period_start, period_end)

        # Compare with the equivalent previous period
        delta = period_end - period_start
        prev_start = period_start - delta
        prev_end = period_start
        previous = await self._summary_block(business_id, prev_start, prev_end)

        def pct(curr: int, prev: int) -> float:
            if prev == 0:
                return 100.0 if curr > 0 else 0.0
            return round(((curr - prev) / prev) * 100, 1)

        new_clients, returning_clients = await self._count_new_vs_returning(
            business_id, period_start, period_end
        )

        total = current["total"]
        no_show_rate = (current["no_show"] / total * 100) if total else 0.0
        cancellation_rate = (current["cancelled"] / total * 100) if total else 0.0

        return SummaryReport(
            total_appointments=total,
            completed_count=current["completed"],
            pending_count=current["pending"],
            confirmed_count=current["confirmed"],
            cancelled_count=current["cancelled"],
            no_show_count=current["no_show"],
            revenue_cents=current["revenue"],
            new_clients=new_clients,
            returning_clients=returning_clients,
            no_show_rate=round(no_show_rate, 1),
            cancellation_rate=round(cancellation_rate, 1),
            previous_total_appointments=previous["total"],
            previous_revenue_cents=previous["revenue"],
            appointments_change_pct=pct(total, previous["total"]),
            revenue_change_pct=pct(current["revenue"], previous["revenue"]),
        )

    async def _summary_block(
        self, business_id: UUID, start: datetime, end: datetime
    ) -> dict[str, int]:
        tenant = get_current_tenant()
        revenue_expr = _revenue()

        def status_count(status: AppointmentStatus):
            return func.coalesce(
                func.sum(
                    case(
                        (AppointmentModel.status == status.value, 1),
                        else_=0,
                    )
                ),
                0,
            )

        stmt = (
            select(
                func.count(AppointmentModel.id).label("total"),
                status_count(AppointmentStatus.PENDING).label("pending"),
                status_count(AppointmentStatus.CONFIRMED).label("confirmed"),
                status_count(AppointmentStatus.COMPLETED).label("completed"),
                status_count(AppointmentStatus.CANCELLED).label("cancelled"),
                status_count(AppointmentStatus.NO_SHOW).label("no_show"),
                revenue_expr.label("revenue"),
            )
            .select_from(AppointmentModel)
            .join(ServiceModel, ServiceModel.id == AppointmentModel.service_id, isouter=True)
            .where(
                AppointmentModel.tenant_id == tenant.tenant_id,
                AppointmentModel.business_id == business_id,
                AppointmentModel.scheduled_at >= start,
                AppointmentModel.scheduled_at < end,
            )
        )
        row = (await self._session.execute(stmt)).one()
        return {
            "total": int(row.total or 0),
            "pending": int(row.pending or 0),
            "confirmed": int(row.confirmed or 0),
            "completed": int(row.completed or 0),
            "cancelled": int(row.cancelled or 0),
            "no_show": int(row.no_show or 0),
            "revenue": int(row.revenue or 0),
        }

    async def _count_new_vs_returning(
        self, business_id: UUID, start: datetime, end: datetime
    ) -> tuple[int, int]:
        tenant = get_current_tenant()
        # New = client.created_at within the period
        new_stmt = (
            select(func.count(func.distinct(ClientModel.id)))
            .select_from(ClientModel)
            .join(AppointmentModel, AppointmentModel.client_id == ClientModel.id)
            .where(
                ClientModel.tenant_id == tenant.tenant_id,
                AppointmentModel.business_id == business_id,
                AppointmentModel.scheduled_at >= start,
                AppointmentModel.scheduled_at < end,
                ClientModel.created_at >= start,
                ClientModel.created_at < end,
            )
        )
        new_count = await self._session.scalar(new_stmt) or 0

        # Returning = had an appointment in the period AND was created before the period started
        returning_stmt = (
            select(func.count(func.distinct(ClientModel.id)))
            .select_from(ClientModel)
            .join(AppointmentModel, AppointmentModel.client_id == ClientModel.id)
            .where(
                ClientModel.tenant_id == tenant.tenant_id,
                AppointmentModel.business_id == business_id,
                AppointmentModel.scheduled_at >= start,
                AppointmentModel.scheduled_at < end,
                ClientModel.created_at < start,
            )
        )
        returning_count = await self._session.scalar(returning_stmt) or 0
        return int(new_count), int(returning_count)

    # ── Trend ────────────────────────────────────────────────────────────────

    async def get_trend(
        self, business_id: UUID, period_start: datetime, period_end: datetime
    ) -> TrendReport:
        tenant = get_current_tenant()
        day_expr = func.date_trunc("day", AppointmentModel.scheduled_at).label("day")

        stmt = (
            select(
                day_expr,
                func.count(AppointmentModel.id).label("total"),
                func.coalesce(
                    func.sum(
                        case(
                            (AppointmentModel.status == AppointmentStatus.COMPLETED.value, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("completed"),
                func.coalesce(
                    func.sum(
                        case(
                            (AppointmentModel.status == AppointmentStatus.CANCELLED.value, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("cancelled"),
                func.coalesce(
                    func.sum(
                        case(
                            (AppointmentModel.status == AppointmentStatus.NO_SHOW.value, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("no_show"),
            )
            .where(
                AppointmentModel.tenant_id == tenant.tenant_id,
                AppointmentModel.business_id == business_id,
                AppointmentModel.scheduled_at >= period_start,
                AppointmentModel.scheduled_at < period_end,
            )
            .group_by(day_expr)
            .order_by(day_expr)
        )
        rows = (await self._session.execute(stmt)).all()
        points = [
            TrendPoint(
                day=r.day.date() if hasattr(r.day, "date") else r.day,
                total=int(r.total or 0),
                completed=int(r.completed or 0),
                cancelled=int(r.cancelled or 0),
                no_show=int(r.no_show or 0),
            )
            for r in rows
        ]
        return TrendReport(points=points)

    # ── Top services ─────────────────────────────────────────────────────────

    async def get_top_services(
        self, business_id: UUID, period_start: datetime, period_end: datetime, limit: int = 10
    ) -> TopServicesReport:
        tenant = get_current_tenant()
        revenue_expr = _revenue()
        stmt = (
            select(
                ServiceModel.id.label("service_id"),
                ServiceModel.name.label("service_name"),
                func.count(AppointmentModel.id).label("count"),
                revenue_expr.label("revenue"),
            )
            .select_from(AppointmentModel)
            .join(ServiceModel, ServiceModel.id == AppointmentModel.service_id)
            .where(
                AppointmentModel.tenant_id == tenant.tenant_id,
                AppointmentModel.business_id == business_id,
                AppointmentModel.scheduled_at >= period_start,
                AppointmentModel.scheduled_at < period_end,
            )
            .group_by(ServiceModel.id, ServiceModel.name)
            .order_by(func.count(AppointmentModel.id).desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        items = [
            TopServiceItem(
                service_id=r.service_id,
                service_name=r.service_name,
                count=int(r.count),
                revenue_cents=int(r.revenue or 0),
            )
            for r in rows
        ]
        return TopServicesReport(items=items)

    # ── Top clients ──────────────────────────────────────────────────────────

    async def get_top_clients(
        self, business_id: UUID, period_start: datetime, period_end: datetime, limit: int = 10
    ) -> TopClientsReport:
        tenant = get_current_tenant()
        revenue_expr = _revenue()
        stmt = (
            select(
                ClientModel.id.label("client_id"),
                ClientModel.name.label("client_name"),
                ClientModel.whatsapp_number.label("whatsapp_number"),
                func.count(AppointmentModel.id).label("count"),
                revenue_expr.label("revenue"),
                func.max(AppointmentModel.scheduled_at).label("last_at"),
            )
            .select_from(AppointmentModel)
            .join(ClientModel, ClientModel.id == AppointmentModel.client_id)
            .join(ServiceModel, ServiceModel.id == AppointmentModel.service_id, isouter=True)
            .where(
                AppointmentModel.tenant_id == tenant.tenant_id,
                AppointmentModel.business_id == business_id,
                AppointmentModel.scheduled_at >= period_start,
                AppointmentModel.scheduled_at < period_end,
            )
            .group_by(ClientModel.id, ClientModel.name, ClientModel.whatsapp_number)
            .order_by(func.count(AppointmentModel.id).desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        items = [
            TopClientItem(
                client_id=r.client_id,
                client_name=r.client_name or "Sin nombre",
                whatsapp_number=r.whatsapp_number or "",
                appointments_count=int(r.count),
                revenue_cents=int(r.revenue or 0),
                last_appointment_at=r.last_at,
            )
            for r in rows
        ]
        return TopClientsReport(items=items)

    # ── Professional performance ─────────────────────────────────────────────

    async def get_professional_performance(
        self, business_id: UUID, period_start: datetime, period_end: datetime
    ) -> ProfessionalPerformanceReport:
        tenant = get_current_tenant()
        revenue_expr = _revenue()

        def status_count(status: AppointmentStatus):
            return func.coalesce(
                func.sum(
                    case(
                        (AppointmentModel.status == status.value, 1),
                        else_=0,
                    )
                ),
                0,
            )

        stmt = (
            select(
                ProfessionalModel.id.label("professional_id"),
                ProfessionalModel.name.label("professional_name"),
                func.count(AppointmentModel.id).label("total"),
                status_count(AppointmentStatus.COMPLETED).label("completed"),
                status_count(AppointmentStatus.CANCELLED).label("cancelled"),
                status_count(AppointmentStatus.NO_SHOW).label("no_show"),
                revenue_expr.label("revenue"),
            )
            .select_from(AppointmentModel)
            # Outer join a propósito: con el join interno, toda cita sin
            # profesional asignado desaparecía del reporte sin dejar rastro —
            # en un gimnasio con clases grupales, eso es casi todo. Ahora caen
            # en un grupo propio con professional_id nulo.
            .join(
                ProfessionalModel,
                ProfessionalModel.id == AppointmentModel.professional_id,
                isouter=True,
            )
            .join(ServiceModel, ServiceModel.id == AppointmentModel.service_id, isouter=True)
            .where(
                AppointmentModel.tenant_id == tenant.tenant_id,
                AppointmentModel.business_id == business_id,
                AppointmentModel.scheduled_at >= period_start,
                AppointmentModel.scheduled_at < period_end,
            )
            .group_by(ProfessionalModel.id, ProfessionalModel.name)
            .order_by(func.count(AppointmentModel.id).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        items = [
            ProfessionalPerformanceItem(
                professional_id=r.professional_id,
                professional_name=r.professional_name or "Sin profesional asignado",
                total=int(r.total),
                completed=int(r.completed),
                cancelled=int(r.cancelled),
                no_show=int(r.no_show),
                revenue_cents=int(r.revenue or 0),
            )
            for r in rows
        ]
        return ProfessionalPerformanceReport(items=items)

    # ── Heatmap ──────────────────────────────────────────────────────────────

    async def get_heatmap(
        self, business_id: UUID, period_start: datetime, period_end: datetime
    ) -> HeatmapReport:
        tenant = get_current_tenant()
        # PostgreSQL: EXTRACT(DOW FROM ...) returns 0=Sunday..6=Saturday
        # We normalize to 0=Monday..6=Sunday
        raw_dow = func.extract("dow", AppointmentModel.scheduled_at)
        dow_expr = cast(((raw_dow + 6) % 7), INTEGER).label("dow")
        hour_expr = cast(func.extract("hour", AppointmentModel.scheduled_at), INTEGER).label("hour")

        stmt = (
            select(
                dow_expr,
                hour_expr,
                func.count(AppointmentModel.id).label("count"),
            )
            .where(
                AppointmentModel.tenant_id == tenant.tenant_id,
                AppointmentModel.business_id == business_id,
                AppointmentModel.scheduled_at >= period_start,
                AppointmentModel.scheduled_at < period_end,
            )
            .group_by(literal_column("dow"), literal_column("hour"))
            .order_by(literal_column("dow"), literal_column("hour"))
        )
        rows = (await self._session.execute(stmt)).all()
        cells = [
            HeatmapCell(day_of_week=int(r.dow), hour=int(r.hour), count=int(r.count))
            for r in rows
        ]
        return HeatmapReport(cells=cells)

    # ── Status distribution ──────────────────────────────────────────────────

    async def get_status_distribution(
        self, business_id: UUID, period_start: datetime, period_end: datetime
    ) -> StatusDistributionReport:
        tenant = get_current_tenant()
        stmt = (
            select(
                AppointmentModel.status.label("status"),
                func.count(AppointmentModel.id).label("count"),
            )
            .where(
                AppointmentModel.tenant_id == tenant.tenant_id,
                AppointmentModel.business_id == business_id,
                AppointmentModel.scheduled_at >= period_start,
                AppointmentModel.scheduled_at < period_end,
            )
            .group_by(AppointmentModel.status)
            .order_by(func.count(AppointmentModel.id).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        buckets = [StatusBucket(status=r.status, count=int(r.count)) for r in rows]
        return StatusDistributionReport(buckets=buckets)
