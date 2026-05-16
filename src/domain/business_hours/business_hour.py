from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import IntEnum
from uuid import UUID, uuid4

from src.domain.shared.entity import TenantAwareEntity
from src.domain.shared.errors import BusinessRuleViolationError


class DayOfWeek(IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


@dataclass(eq=False)
class BusinessHour(TenantAwareEntity):
    """BusinessHour aggregate root.

    Defines the operating schedule for one day of the week at a business.
    A business has at most 7 BusinessHour records (one per day).

    When is_closed=True, open_at/close_at are stored but ignored for
    availability calculations.
    """

    business_id: UUID = UUID(int=0)
    day_of_week: int = 0        # DayOfWeek value (0=Monday … 6=Sunday)
    open_at: time = time(9, 0)
    close_at: time = time(18, 0)
    is_closed: bool = False

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        business_id: UUID,
        day_of_week: int,
        open_at: time,
        close_at: time,
        is_closed: bool = False,
    ) -> BusinessHour:
        """Factory for creating a new business hour entry."""
        _validate_day(day_of_week)
        if not is_closed:
            _validate_times(open_at, close_at)

        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            day_of_week=day_of_week,
            open_at=open_at,
            close_at=close_at,
            is_closed=is_closed,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        open_at: time | None = None,
        close_at: time | None = None,
        is_closed: bool | None = None,
    ) -> None:
        """Update schedule for this day."""
        new_open = open_at if open_at is not None else self.open_at
        new_close = close_at if close_at is not None else self.close_at
        new_closed = is_closed if is_closed is not None else self.is_closed

        if not new_closed:
            _validate_times(new_open, new_close)

        self.open_at = new_open
        self.close_at = new_close
        self.is_closed = new_closed
        self.updated_at = datetime.utcnow()


def _validate_day(day_of_week: int) -> None:
    if day_of_week not in range(7):
        raise BusinessRuleViolationError(
            f"day_of_week must be 0–6 (Mon–Sun), got {day_of_week}"
        )


def _validate_times(open_at: time, close_at: time) -> None:
    if close_at <= open_at:
        raise BusinessRuleViolationError(
            f"close_at ({close_at}) must be after open_at ({open_at})"
        )
