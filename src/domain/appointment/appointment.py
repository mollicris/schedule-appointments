from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from src.domain.appointment.value_objects import AppointmentStatus
from src.domain.shared.entity import TenantAwareEntity
from src.domain.shared.errors import BusinessRuleViolationError


@dataclass(eq=False)
class Appointment(TenantAwareEntity):
    """Appointment aggregate root.

    Represents a booked service slot at a business. The lifecycle is:
        PENDING | CONFIRMED | RESCHEDULED → COMPLETED | NO_SHOW
        PENDING | CONFIRMED → CANCELLED
        PENDING | CONFIRMED → RESCHEDULED (moved in place, same row)

    Closing it with ``complete()`` records what was actually collected, which is
    what the revenue reports read — not the service's current price.
    """

    business_id: UUID = UUID(int=0)
    service_id: UUID = UUID(int=0)
    client_id: UUID = UUID(int=0)
    scheduled_at: datetime = datetime.utcnow
    duration_minutes: int = 30
    status: AppointmentStatus = AppointmentStatus.PENDING
    professional_id: UUID | None = None
    notes: str | None = None
    cancelled_reason: str | None = None
    cancelled_at: datetime | None = None
    reminder_sent_at: datetime | None = None
    amount_charged: int | None = None    # in cents, written when it is closed
    completed_at: datetime | None = None

    @classmethod
    def book(
        cls,
        *,
        tenant_id: UUID,
        business_id: UUID,
        service_id: UUID,
        client_id: UUID,
        scheduled_at: datetime,
        duration_minutes: int,
        professional_id: UUID | None = None,
        notes: str | None = None,
    ) -> Appointment:
        if duration_minutes < 1:
            raise BusinessRuleViolationError("Duration must be at least 1 minute")
        if scheduled_at <= datetime.now(timezone.utc):
            raise BusinessRuleViolationError("Appointment must be scheduled in the future")

        now = datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            service_id=service_id,
            client_id=client_id,
            professional_id=professional_id,
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            status=AppointmentStatus.PENDING,
            notes=notes,
            created_at=now,
            updated_at=now,
        )

    @property
    def ends_at(self) -> datetime:
        return self.scheduled_at + timedelta(minutes=self.duration_minutes)

    @property
    def is_active(self) -> bool:
        return self.status in (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED)

    def confirm(self) -> None:
        if self.status != AppointmentStatus.PENDING:
            raise BusinessRuleViolationError(
                f"Cannot confirm appointment in status '{self.status}'"
            )
        self.status = AppointmentStatus.CONFIRMED
        self.updated_at = datetime.now(timezone.utc)

    def cancel(self, reason: str | None = None) -> None:
        if self.status in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED):
            raise BusinessRuleViolationError(
                f"Cannot cancel appointment in status '{self.status}'"
            )
        self.status = AppointmentStatus.CANCELLED
        self.cancelled_reason = reason
        self.cancelled_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def reschedule(
        self,
        new_scheduled_at: datetime,
        new_duration_minutes: int | None = None,
    ) -> None:
        if self.status in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED):
            raise BusinessRuleViolationError(
                f"Cannot reschedule appointment in status '{self.status}'"
            )
        if new_scheduled_at <= datetime.now(timezone.utc):
            raise BusinessRuleViolationError("New time must be in the future")

        self.scheduled_at = new_scheduled_at
        if new_duration_minutes is not None:
            if new_duration_minutes < 1:
                raise BusinessRuleViolationError("Duration must be at least 1 minute")
            self.duration_minutes = new_duration_minutes
        self.status = AppointmentStatus.RESCHEDULED
        self.updated_at = datetime.now(timezone.utc)

    # A booking only leaves PENDING if the client taps the reminder button, and
    # rescheduling parks it in RESCHEDULED. Requiring CONFIRMED here would reject
    # almost every real appointment, so anything not already closed can be closed.
    _CLOSEABLE = (
        AppointmentStatus.PENDING,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.RESCHEDULED,
    )

    def complete(self, amount_charged: int) -> None:
        """Close the appointment with what was actually collected.

        The amount is required rather than defaulting to the service price: zero
        means "no charge" and saying so is a deliberate act. A silent null is a
        number nobody can justify when the report is audited months later.
        """
        if self.status not in self._CLOSEABLE:
            raise BusinessRuleViolationError(
                f"Cannot complete appointment in status '{self.status}'"
            )
        if amount_charged < 0:
            raise BusinessRuleViolationError("Amount charged cannot be negative")

        now = datetime.now(timezone.utc)
        self.status = AppointmentStatus.COMPLETED
        self.amount_charged = amount_charged
        self.completed_at = now
        self.updated_at = now

    def mark_no_show(self) -> None:
        if self.status not in self._CLOSEABLE:
            raise BusinessRuleViolationError(
                f"Cannot mark no-show for appointment in status '{self.status}'"
            )
        self.status = AppointmentStatus.NO_SHOW
        self.updated_at = datetime.now(timezone.utc)

    def mark_reminder_sent(self) -> None:
        self.reminder_sent_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
