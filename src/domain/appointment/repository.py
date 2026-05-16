from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from uuid import UUID

from src.domain.appointment.appointment import Appointment


class AppointmentRepository(ABC):
    @abstractmethod
    async def get_by_id(self, appointment_id: UUID) -> Appointment | None: ...

    @abstractmethod
    async def list_by_business(
        self,
        business_id: UUID,
        *,
        on_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Appointment]: ...

    @abstractmethod
    async def count_by_business(
        self,
        business_id: UUID,
        on_date: date | None = None,
    ) -> int: ...

    @abstractmethod
    async def list_active_in_range(
        self,
        business_id: UUID,
        start: datetime,
        end: datetime,
        professional_id: UUID | None = None,
    ) -> list[Appointment]: ...

    @abstractmethod
    async def add(self, appointment: Appointment) -> None: ...

    @abstractmethod
    async def update(self, appointment: Appointment) -> None: ...
