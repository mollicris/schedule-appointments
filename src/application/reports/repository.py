from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.application.reports.dtos import (
    HeatmapReport,
    ProfessionalPerformanceReport,
    StatusDistributionReport,
    SummaryReport,
    TopClientsReport,
    TopServicesReport,
    TrendReport,
)


class ReportsRepository(ABC):
    """Read-only port for analytical queries.

    All implementations MUST enforce tenant isolation via the current
    TenantContext. Methods return DTOs, not domain aggregates, because
    these are query projections, not transactional entities.
    """

    @abstractmethod
    async def get_summary(
        self, business_id: UUID, period_start: datetime, period_end: datetime
    ) -> SummaryReport: ...

    @abstractmethod
    async def get_trend(
        self, business_id: UUID, period_start: datetime, period_end: datetime
    ) -> TrendReport: ...

    @abstractmethod
    async def get_top_services(
        self, business_id: UUID, period_start: datetime, period_end: datetime, limit: int = 10
    ) -> TopServicesReport: ...

    @abstractmethod
    async def get_top_clients(
        self, business_id: UUID, period_start: datetime, period_end: datetime, limit: int = 10
    ) -> TopClientsReport: ...

    @abstractmethod
    async def get_professional_performance(
        self, business_id: UUID, period_start: datetime, period_end: datetime
    ) -> ProfessionalPerformanceReport: ...

    @abstractmethod
    async def get_heatmap(
        self, business_id: UUID, period_start: datetime, period_end: datetime
    ) -> HeatmapReport: ...

    @abstractmethod
    async def get_status_distribution(
        self, business_id: UUID, period_start: datetime, period_end: datetime
    ) -> StatusDistributionReport: ...
