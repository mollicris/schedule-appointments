from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Pure occupancy rules shared by availability and booking.
#
# Both GetAvailableSlotsUseCase and BookAppointmentUseCase evaluate a slot with
# `evaluate_slot`, so the agent can never offer a start time that then fails to
# book. No I/O here on purpose: this module is unit-testable without a database.


@dataclass(frozen=True)
class SlotEvaluation:
    """How a candidate start time looks for one service."""

    start: datetime
    capacity: int
    remaining: int      # free places in this session (0 when blocked)
    blocked: bool       # occupied by an exclusive service or a misaligned session

    @property
    def is_bookable(self) -> bool:
        return not self.blocked and self.remaining > 0


def evaluate_slot(
    *,
    slot_start: datetime,
    slot_end: datetime,
    service_id: UUID,
    capacity: int,
    booked: Sequence,
    capacity_by_service: Mapping[UUID, int] | None = None,
    exclude_appointment_id: UUID | None = None,
) -> SlotEvaluation:
    """Evaluate one candidate start time against the appointments already booked.

    ``booked`` are active appointments already narrowed to the relevant window
    (and to a professional, when the caller asked for one).

    One-to-one services (``capacity == 1``) keep the historical rule untouched:
    any overlapping appointment blocks the slot.

    Group classes (``capacity > 1``) apply, per overlapping appointment:
      * the other service is exclusive (its capacity is 1) → blocked. A personal
        session occupies the venue and the staff, so the class cannot run.
      * same service, same start time → consumes one place (it is the same
        session); the class stays open while ``taken < capacity``.
      * same service, different start time → blocked. Two sessions of one class
        cannot overlap; the session key is (service_id, scheduled_at).
      * another group class → ignored. Different classes may run in parallel
        (separate rooms/instructors). Narrow this by passing a professional_id
        when the same instructor cannot be in two places at once.

    ``capacity_by_service`` maps service_id → capacity for the booked
    appointments; a missing id defaults to 1 (exclusive), which is the safe
    assumption — it never relaxes a block.
    """
    caps = capacity_by_service or {}
    overlapping = [
        apt
        for apt in booked
        if apt.id != exclude_appointment_id and slot_start < apt.ends_at and slot_end > apt.scheduled_at
    ]

    if capacity <= 1:
        return SlotEvaluation(
            start=slot_start,
            capacity=1,
            remaining=0 if overlapping else 1,
            blocked=bool(overlapping),
        )

    taken = 0
    for apt in overlapping:
        other_capacity = caps.get(apt.service_id, 1)
        if other_capacity <= 1:
            return _blocked(slot_start, capacity)
        if apt.service_id == service_id:
            if apt.scheduled_at == slot_start:
                taken += 1
            else:
                return _blocked(slot_start, capacity)
        # else: a different group class — runs in parallel, ignored.

    return SlotEvaluation(
        start=slot_start,
        capacity=capacity,
        remaining=max(0, capacity - taken),
        blocked=False,
    )


def _blocked(slot_start: datetime, capacity: int) -> SlotEvaluation:
    return SlotEvaluation(start=slot_start, capacity=capacity, remaining=0, blocked=True)
