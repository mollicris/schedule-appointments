"""Booking enforces group-class capacity and still rejects double bookings.

Hand-written mocks, like tests/test_verify_email.py: no database involved.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.application.appointment.book_appointment import (
    BookAppointmentInput,
    BookAppointmentUseCase,
)
from src.application.shared.tenant_context import TenantContext, set_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.appointment.appointment import Appointment
from src.domain.client.client import Client
from src.domain.service.service import Service
from src.domain.shared.errors import ConflictError

TENANT_ID = uuid4()
BUSINESS_ID = uuid4()
# Relative to today on purpose: Appointment.create refuses a slot in the past,
# so a hard-coded date turns green tests red the moment it goes by.
SLOT = (datetime.now(timezone.utc) + timedelta(days=7)).replace(
    hour=18, minute=0, second=0, microsecond=0
)


class MockUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


class MockServiceRepository:
    """Tracks whether the row lock was taken before capacity was counted."""

    def __init__(self, service: Service) -> None:
        self._service = service
        self.locked_before_listing = False
        self._locked = False

    async def get_by_id(self, service_id: UUID) -> Service | None:
        return self._service if service_id == self._service.id else None

    async def lock_for_update(self, service_id: UUID) -> Service | None:
        self._locked = True
        return self._service if service_id == self._service.id else None

    async def get_capacity_map(self, service_ids: list[UUID]) -> dict[UUID, int]:
        self.locked_before_listing = self._locked
        return {self._service.id: self._service.capacity}

    async def list_professional_ids(self, service_id: UUID) -> list[UUID]:
        return []


class MockAppointmentRepository:
    def __init__(self, existing: list[Appointment] | None = None) -> None:
        self.appointments = list(existing or [])

    async def list_active_in_range(
        self, business_id: UUID, start: datetime, end: datetime, professional_id=None
    ) -> list[Appointment]:
        return [
            a
            for a in self.appointments
            if start < a.ends_at and end > a.scheduled_at
        ]

    async def get_active_for_client_at(
        self, client_id: UUID, service_id: UUID, scheduled_at: datetime
    ) -> Appointment | None:
        for a in self.appointments:
            if (
                a.client_id == client_id
                and a.service_id == service_id
                and a.scheduled_at == scheduled_at
            ):
                return a
        return None

    async def add(self, appointment: Appointment) -> None:
        self.appointments.append(appointment)

    async def update(self, appointment: Appointment) -> None:
        pass


class MockClientRepository:
    def __init__(self) -> None:
        self.clients: dict[str, Client] = {}

    async def get_by_whatsapp(self, whatsapp: str) -> Client | None:
        return self.clients.get(whatsapp)

    async def add(self, client: Client) -> None:
        self.clients[client.whatsapp_number] = client

    async def update(self, client: Client) -> None:
        self.clients[client.whatsapp_number] = client


def _service(capacity: int) -> Service:
    return Service.create(
        tenant_id=TENANT_ID,
        business_id=BUSINESS_ID,
        name="Yoga" if capacity > 1 else "Masaje",
        duration_minutes=60,
        capacity=capacity,
    )


def _use_case(service: Service, existing: list[Appointment] | None = None):
    services = MockServiceRepository(service)
    appointments = MockAppointmentRepository(existing)
    clients = MockClientRepository()
    uow = MockUnitOfWork()
    use_case = BookAppointmentUseCase(
        appointments=appointments,
        services=services,
        clients=clients,
        uow=uow,
    )
    return use_case, services, appointments, uow


@pytest.fixture(autouse=True)
def _tenant_context():
    set_current_tenant(TenantContext(tenant_id=TENANT_ID))


# ── Group classes ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_group_class_fills_up_and_then_rejects():
    service = _service(capacity=3)
    use_case, _, _, uow = _use_case(service)

    remaining = []
    for seat in range(3):
        output = await use_case.execute(
            BookAppointmentInput(
                business_id=BUSINESS_ID,
                service_id=service.id,
                scheduled_at=SLOT,
                client_name=f"Socio {seat}",
                client_whatsapp=f"5917000000{seat}",
            )
        )
        remaining.append(output.spots_left)

    assert remaining == [2, 1, 0]
    assert uow.committed is True

    with pytest.raises(ConflictError) as exc_info:
        await use_case.execute(
            BookAppointmentInput(
                business_id=BUSINESS_ID,
                service_id=service.id,
                scheduled_at=SLOT,
                client_name="Socio 4",
                client_whatsapp="59170000009",
            )
        )

    assert "full" in str(exc_info.value)


@pytest.mark.asyncio
async def test_booking_the_same_seat_twice_is_idempotent():
    """A client confirming twice must not take two seats in the same class.

    The agent re-issues book_appointment across turns, so without this the same
    person ends up occupying several places in one session.
    """
    service = _service(capacity=10)
    use_case, _, appointments, _ = _use_case(service)

    payload = BookAppointmentInput(
        business_id=BUSINESS_ID,
        service_id=service.id,
        scheduled_at=SLOT,
        client_name="Cris",
        client_whatsapp="59179559800",
    )

    first = await use_case.execute(payload)
    second = await use_case.execute(payload)

    assert second.appointment_id == first.appointment_id
    assert second.already_booked is True
    assert first.already_booked is False
    assert len(appointments.appointments) == 1


@pytest.mark.asyncio
async def test_capacity_is_counted_after_taking_the_row_lock():
    """The lock must come first, otherwise two concurrent bookings see stale counts."""
    service = _service(capacity=5)
    use_case, services, _, _ = _use_case(service)

    await use_case.execute(
        BookAppointmentInput(
            business_id=BUSINESS_ID,
            service_id=service.id,
            scheduled_at=SLOT,
            client_name="Socia",
            client_whatsapp="59171111111",
        )
    )

    assert services.locked_before_listing is True


@pytest.mark.asyncio
async def test_a_misaligned_session_of_the_same_class_is_rejected():
    service = _service(capacity=10)
    existing = Appointment.book(
        tenant_id=TENANT_ID,
        business_id=BUSINESS_ID,
        service_id=service.id,
        client_id=uuid4(),
        professional_id=None,
        scheduled_at=SLOT + timedelta(minutes=30),
        duration_minutes=60,
    )
    use_case, _, _, _ = _use_case(service, [existing])

    with pytest.raises(ConflictError) as exc_info:
        await use_case.execute(
            BookAppointmentInput(
                business_id=BUSINESS_ID,
                service_id=service.id,
                scheduled_at=SLOT,
                client_name="Socio",
                client_whatsapp="59172222222",
            )
        )

    assert "no longer available" in str(exc_info.value)


# ── One-to-one services: regression ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_one_to_one_service_rejects_an_overlapping_booking():
    """This used to slip through: the availability check was wrapped in a bare except."""
    service = _service(capacity=1)
    existing = Appointment.book(
        tenant_id=TENANT_ID,
        business_id=BUSINESS_ID,
        service_id=service.id,
        client_id=uuid4(),
        professional_id=None,
        scheduled_at=SLOT + timedelta(minutes=15),
        duration_minutes=60,
    )
    use_case, _, _, _ = _use_case(service, [existing])

    with pytest.raises(ConflictError):
        await use_case.execute(
            BookAppointmentInput(
                business_id=BUSINESS_ID,
                service_id=service.id,
                scheduled_at=SLOT,
                client_name="Socio",
                client_whatsapp="59173333333",
            )
        )


@pytest.mark.asyncio
async def test_one_to_one_booking_reports_no_spots_left():
    service = _service(capacity=1)
    use_case, _, appointments, _ = _use_case(service)

    output = await use_case.execute(
        BookAppointmentInput(
            business_id=BUSINESS_ID,
            service_id=service.id,
            scheduled_at=SLOT,
            client_name="Socio",
            client_whatsapp="59174444444",
        )
    )

    assert output.spots_left is None       # capacity semantics do not apply
    assert len(appointments.appointments) == 1
