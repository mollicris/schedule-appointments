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
    async def get_active_for_client_at(
        self,
        client_id: UUID,
        service_id: UUID,
        scheduled_at: datetime,
    ) -> Appointment | None:
        """The client's active appointment for that exact service and start time.

        Used to make booking idempotent: a client confirming twice, or an agent
        re-issuing the same call in a later turn, must not end up with two seats
        in the same class.
        """
        ...

    @abstractmethod
    async def count_active_for_service_at(
        self,
        service_id: UUID,
        scheduled_at: datetime,
    ) -> int:
        """Count active appointments of a service at an exact start time.

        Used to enforce group-class capacity: a class is full when this count
        reaches ``Service.capacity``.
        """
        ...

    @abstractmethod
    async def add(self, appointment: Appointment) -> None: ...

    @abstractmethod
    async def update(self, appointment: Appointment) -> None: ...
