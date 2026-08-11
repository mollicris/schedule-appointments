from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True)
class SummaryReport:
    """High-level KPIs for a business in a date range."""
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
    # Comparison with the previous equivalent period
    previous_total_appointments: int = 0
    previous_revenue_cents: int = 0
    appointments_change_pct: float = 0.0
    revenue_change_pct: float = 0.0


@dataclass(frozen=True)
class TrendPoint:
    day: date
    total: int
    completed: int
    cancelled: int
    no_show: int


@dataclass(frozen=True)
class TrendReport:
    points: list[TrendPoint] = field(default_factory=list)


@dataclass(frozen=True)
class TopServiceItem:
    service_id: UUID
    service_name: str
    count: int
    revenue_cents: int


@dataclass(frozen=True)
class TopServicesReport:
    items: list[TopServiceItem] = field(default_factory=list)


@dataclass(frozen=True)
class TopClientItem:
    client_id: UUID
    client_name: str
    whatsapp_number: str
    appointments_count: int
    revenue_cents: int
    last_appointment_at: datetime | None


@dataclass(frozen=True)
class TopClientsReport:
    items: list[TopClientItem] = field(default_factory=list)


@dataclass(frozen=True)
class ProfessionalPerformanceItem:
    # None agrupa las citas sin profesional asignado, que antes quedaban fuera
    # del reporte por completo.
    professional_id: UUID | None
    professional_name: str
    total: int
    completed: int
    cancelled: int
    no_show: int
    revenue_cents: int


@dataclass(frozen=True)
class ProfessionalPerformanceReport:
    items: list[ProfessionalPerformanceItem] = field(default_factory=list)


@dataclass(frozen=True)
class HeatmapCell:
    day_of_week: int  # 0 = Monday, 6 = Sunday
    hour: int  # 0–23
    count: int


@dataclass(frozen=True)
class HeatmapReport:
    cells: list[HeatmapCell] = field(default_factory=list)


@dataclass(frozen=True)
class StatusBucket:
    status: str
    count: int


@dataclass(frozen=True)
class StatusDistributionReport:
    buckets: list[StatusBucket] = field(default_factory=list)
