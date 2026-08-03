"""Occupancy rules for one-to-one services and group classes.

Pure functions, no database: these are the rules both availability and booking
apply, so a bug here would let the agent offer a class that cannot be booked.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from src.application.appointment.slot_occupancy import evaluate_slot

YOGA = uuid4()
SPINNING = uuid4()
MASSAGE = uuid4()   # one-to-one service

SLOT = datetime(2026, 8, 3, 18, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


@dataclass
class FakeAppointment:
    """Minimal stand-in: evaluate_slot only reads these four attributes."""

    service_id: UUID
    scheduled_at: datetime
    duration: timedelta = HOUR
    id: UUID = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = uuid4()

    @property
    def ends_at(self) -> datetime:
        return self.scheduled_at + self.duration


def _evaluate(capacity: int, booked: list, *, service_id: UUID = YOGA, exclude=None):
    return evaluate_slot(
        slot_start=SLOT,
        slot_end=SLOT + HOUR,
        service_id=service_id,
        capacity=capacity,
        booked=booked,
        capacity_by_service={YOGA: 15, SPINNING: 20, MASSAGE: 1},
        exclude_appointment_id=exclude,
    )


# ── One-to-one services: historical behaviour must not change ────────────────


def test_one_to_one_slot_is_free_when_nothing_overlaps():
    result = _evaluate(1, [], service_id=MASSAGE)

    assert result.is_bookable
    assert result.remaining == 1
    assert result.blocked is False


def test_one_to_one_slot_is_blocked_by_any_overlap():
    booked = [FakeAppointment(service_id=MASSAGE, scheduled_at=SLOT + timedelta(minutes=30))]

    result = _evaluate(1, booked, service_id=MASSAGE)

    assert result.blocked is True
    assert result.is_bookable is False


def test_one_to_one_slot_ignores_appointments_that_end_before_it_starts():
    booked = [FakeAppointment(service_id=MASSAGE, scheduled_at=SLOT - HOUR)]

    result = _evaluate(1, booked, service_id=MASSAGE)

    assert result.is_bookable


# ── Group classes ────────────────────────────────────────────────────────────


def test_group_class_counts_only_same_service_same_start():
    booked = [
        FakeAppointment(service_id=YOGA, scheduled_at=SLOT),
        FakeAppointment(service_id=YOGA, scheduled_at=SLOT),
        FakeAppointment(service_id=YOGA, scheduled_at=SLOT),
    ]

    result = _evaluate(15, booked)

    assert result.remaining == 12
    assert result.capacity == 15
    assert result.is_bookable


def test_group_class_is_full_when_capacity_is_reached():
    booked = [FakeAppointment(service_id=YOGA, scheduled_at=SLOT) for _ in range(3)]

    result = _evaluate(3, booked)

    assert result.remaining == 0
    assert result.blocked is False       # full, not blocked — the caller words it differently
    assert result.is_bookable is False


def test_group_class_is_blocked_by_a_one_to_one_appointment():
    """A personal session occupies the venue and the staff."""
    booked = [FakeAppointment(service_id=MASSAGE, scheduled_at=SLOT)]

    result = _evaluate(15, booked)

    assert result.blocked is True


def test_group_class_is_blocked_by_a_misaligned_session_of_itself():
    """Two sessions of the same class cannot overlap: the session key is (service, start)."""
    booked = [FakeAppointment(service_id=YOGA, scheduled_at=SLOT + timedelta(minutes=30))]

    result = _evaluate(15, booked)

    assert result.blocked is True


def test_group_classes_of_different_services_run_in_parallel():
    """Spinning at 18:00 does not stop yoga at 18:00 (separate rooms)."""
    booked = [FakeAppointment(service_id=SPINNING, scheduled_at=SLOT)]

    result = _evaluate(15, booked)

    assert result.is_bookable
    assert result.remaining == 15


def test_unknown_service_capacity_defaults_to_exclusive():
    """A booked service we cannot resolve is assumed one-to-one — never relax a block."""
    unknown = uuid4()
    booked = [FakeAppointment(service_id=unknown, scheduled_at=SLOT)]

    result = evaluate_slot(
        slot_start=SLOT,
        slot_end=SLOT + HOUR,
        service_id=YOGA,
        capacity=15,
        booked=booked,
        capacity_by_service={YOGA: 15},   # `unknown` deliberately missing
    )

    assert result.blocked is True


def test_excluded_appointment_does_not_consume_its_own_place():
    """Rescheduling a class must not count the appointment being moved."""
    own = FakeAppointment(service_id=YOGA, scheduled_at=SLOT)
    booked = [own, FakeAppointment(service_id=YOGA, scheduled_at=SLOT)]

    result = _evaluate(3, booked, exclude=own.id)

    assert result.remaining == 2
