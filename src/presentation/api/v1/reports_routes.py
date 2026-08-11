from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.application.reports.repository import ReportsRepository
from src.domain.business.repository import BusinessRepository
from src.presentation.dependencies import get_business_repository, get_reports_repository

router = APIRouter(prefix="/reports", tags=["reports"])


# ── Pydantic response schemas ────────────────────────────────────────────────


class SummaryResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_appointments: int
    completed_count: int
    pending_count: int
    confirmed_count: int
    cancelled_count: int
    no_show_count: int
    revenue_cents: int
    new_clients: int
    returning_clients: int
    no_show_rate: float
    cancellation_rate: float
    previous_total_appointments: int
    previous_revenue_cents: int
    appointments_change_pct: float
    revenue_change_pct: float


class TrendPointResponse(BaseModel):
    day: date
    total: int
    completed: int
    cancelled: int
    no_show: int


class TrendResponse(BaseModel):
    points: list[TrendPointResponse]


class TopServiceResponse(BaseModel):
    service_id: UUID
    service_name: str
    count: int
    revenue_cents: int


class TopServicesResponse(BaseModel):
    items: list[TopServiceResponse]


class TopClientResponse(BaseModel):
    client_id: UUID
    client_name: str
    whatsapp_number: str
    appointments_count: int
    revenue_cents: int
    last_appointment_at: datetime | None


class TopClientsResponse(BaseModel):
    items: list[TopClientResponse]


class ProfessionalPerformanceResponse(BaseModel):
    professional_id: UUID | None
    professional_name: str
    total: int
    completed: int
    cancelled: int
    no_show: int
    revenue_cents: int


class ProfessionalPerformanceListResponse(BaseModel):
    items: list[ProfessionalPerformanceResponse]


class HeatmapCellResponse(BaseModel):
    day_of_week: int
    hour: int
    count: int


class HeatmapResponse(BaseModel):
    cells: list[HeatmapCellResponse]


class StatusBucketResponse(BaseModel):
    status: str
    count: int


class StatusDistributionResponse(BaseModel):
    buckets: list[StatusBucketResponse]


# ── Date range helper ────────────────────────────────────────────────────────


async def _business_tz(businesses: BusinessRepository, business_id: UUID) -> ZoneInfo:
    """The business's own clock, falling back to UTC."""
    business = await businesses.get_by_id(business_id)
    try:
        return ZoneInfo(business.timezone) if business and business.timezone else timezone.utc
    except ZoneInfoNotFoundError:
        return timezone.utc


async def _resolve_range(
    businesses: BusinessRepository,
    business_id: UUID,
    from_date: date | None,
    to_date: date | None,
) -> tuple[datetime, datetime]:
    """Default: last 30 days through the end of today, in the business's timezone.

    Resolving the range in UTC shifted every day boundary: for a salon in
    La Paz (UTC−4) the report's day started at 20:00 the previous evening, so
    anything attended after that hour landed in the following day. A production
    report that moves work between days is one nobody trusts.
    """
    tz = await _business_tz(businesses, business_id)
    today = datetime.now(tz).date()
    if to_date is None:
        to_date = today
    if from_date is None:
        from_date = to_date - timedelta(days=29)
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="'from' must be earlier than 'to'")

    # Local midnight to local midnight, then let the driver hand UTC to Postgres.
    start = datetime.combine(from_date, time.min, tzinfo=tz)
    end = datetime.combine(to_date, time.min, tzinfo=tz) + timedelta(days=1)
    return start, end


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=SummaryResponse, summary="High-level KPIs")
async def get_summary(
    business_id: Annotated[UUID, Query(description="Target business")],
    reports: Annotated[ReportsRepository, Depends(get_reports_repository)],
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> SummaryResponse:
    start, end = await _resolve_range(businesses, business_id, from_date, to_date)
    r = await reports.get_summary(business_id, start, end)
    return SummaryResponse(
        period_start=start,
        period_end=end,
        total_appointments=r.total_appointments,
        completed_count=r.completed_count,
        pending_count=r.pending_count,
        confirmed_count=r.confirmed_count,
        cancelled_count=r.cancelled_count,
        no_show_count=r.no_show_count,
        revenue_cents=r.revenue_cents,
        new_clients=r.new_clients,
        returning_clients=r.returning_clients,
        no_show_rate=r.no_show_rate,
        cancellation_rate=r.cancellation_rate,
        previous_total_appointments=r.previous_total_appointments,
        previous_revenue_cents=r.previous_revenue_cents,
        appointments_change_pct=r.appointments_change_pct,
        revenue_change_pct=r.revenue_change_pct,
    )


@router.get("/trend", response_model=TrendResponse, summary="Daily appointment trend")
async def get_trend(
    business_id: Annotated[UUID, Query()],
    reports: Annotated[ReportsRepository, Depends(get_reports_repository)],
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> TrendResponse:
    start, end = await _resolve_range(businesses, business_id, from_date, to_date)
    r = await reports.get_trend(business_id, start, end)
    return TrendResponse(
        points=[
            TrendPointResponse(
                day=p.day, total=p.total, completed=p.completed,
                cancelled=p.cancelled, no_show=p.no_show,
            )
            for p in r.points
        ]
    )


@router.get("/top-services", response_model=TopServicesResponse)
async def get_top_services(
    business_id: Annotated[UUID, Query()],
    reports: Annotated[ReportsRepository, Depends(get_reports_repository)],
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> TopServicesResponse:
    start, end = await _resolve_range(businesses, business_id, from_date, to_date)
    r = await reports.get_top_services(business_id, start, end, limit=limit)
    return TopServicesResponse(
        items=[
            TopServiceResponse(
                service_id=i.service_id, service_name=i.service_name,
                count=i.count, revenue_cents=i.revenue_cents,
            )
            for i in r.items
        ]
    )


@router.get("/top-clients", response_model=TopClientsResponse)
async def get_top_clients(
    business_id: Annotated[UUID, Query()],
    reports: Annotated[ReportsRepository, Depends(get_reports_repository)],
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> TopClientsResponse:
    start, end = await _resolve_range(businesses, business_id, from_date, to_date)
    r = await reports.get_top_clients(business_id, start, end, limit=limit)
    return TopClientsResponse(
        items=[
            TopClientResponse(
                client_id=i.client_id, client_name=i.client_name,
                whatsapp_number=i.whatsapp_number,
                appointments_count=i.appointments_count,
                revenue_cents=i.revenue_cents,
                last_appointment_at=i.last_appointment_at,
            )
            for i in r.items
        ]
    )


@router.get("/professional-performance", response_model=ProfessionalPerformanceListResponse)
async def get_professional_performance(
    business_id: Annotated[UUID, Query()],
    reports: Annotated[ReportsRepository, Depends(get_reports_repository)],
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> ProfessionalPerformanceListResponse:
    start, end = await _resolve_range(businesses, business_id, from_date, to_date)
    r = await reports.get_professional_performance(business_id, start, end)
    return ProfessionalPerformanceListResponse(
        items=[
            ProfessionalPerformanceResponse(
                professional_id=i.professional_id,
                professional_name=i.professional_name,
                total=i.total, completed=i.completed,
                cancelled=i.cancelled, no_show=i.no_show,
                revenue_cents=i.revenue_cents,
            )
            for i in r.items
        ]
    )


@router.get("/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    business_id: Annotated[UUID, Query()],
    reports: Annotated[ReportsRepository, Depends(get_reports_repository)],
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> HeatmapResponse:
    start, end = await _resolve_range(businesses, business_id, from_date, to_date)
    r = await reports.get_heatmap(business_id, start, end)
    return HeatmapResponse(
        cells=[
            HeatmapCellResponse(day_of_week=c.day_of_week, hour=c.hour, count=c.count)
            for c in r.cells
        ]
    )


@router.get("/status-distribution", response_model=StatusDistributionResponse)
async def get_status_distribution(
    business_id: Annotated[UUID, Query()],
    reports: Annotated[ReportsRepository, Depends(get_reports_repository)],
    businesses: Annotated[BusinessRepository, Depends(get_business_repository)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> StatusDistributionResponse:
    start, end = await _resolve_range(businesses, business_id, from_date, to_date)
    r = await reports.get_status_distribution(business_id, start, end)
    return StatusDistributionResponse(
        buckets=[
            StatusBucketResponse(status=b.status, count=b.count) for b in r.buckets
        ]
    )
