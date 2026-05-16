# Bounded Context: Appointment

**Responsibility**: Booking, rescheduling, and cancellation of appointments. Slot availability, conflict detection, business hour rules, professional assignment.

## Aggregates

- **`Appointment`** (root) — A scheduled booking. Owns its lifecycle (pending → confirmed → completed | cancelled | no_show).
- **`AvailabilitySlot`** — Computed, not persisted as aggregate. Represents a free time slot for booking.

## Value Objects

- `TimeRange` — Start/end with invariant: end > start
- `AppointmentStatus` — Enum: PENDING, CONFIRMED, CANCELLED, COMPLETED, NO_SHOW
- `CancellationPolicy` — Rules (e.g. no cancel within 2h)

## Events

- `AppointmentBooked` — Triggers WhatsApp confirmation, calendar sync
- `AppointmentCancelled` — Triggers slot release, optional rebooking suggestion
- `AppointmentRescheduled` — Triggers notification
- `AppointmentNoShow` — Feeds the no-show prediction model

## Invariants

- Cannot book in the past
- Cannot book outside business hours
- Cannot overlap another confirmed appointment for the same professional
- Cannot cancel an already-completed appointment

## Files to create

- `appointment.py` — aggregate
- `value_objects.py` — TimeRange, AppointmentStatus, etc.
- `events.py` — domain events
- `repository.py` — interface
- `availability_service.py` — domain service for slot computation (depends on Business hours + bookings)
