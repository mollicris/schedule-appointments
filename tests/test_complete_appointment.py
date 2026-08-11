"""Cerrar una cita con lo que se cobró.

Es la pieza que faltaba para que los reportes de ingreso dejaran de dar cero:
`complete()` existía en el dominio pero nadie lo llamaba, y la cita no guardaba
ningún importe.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.application.appointment.complete_appointment import (
    CompleteAppointmentInput,
    CompleteAppointmentUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.appointment.appointment import Appointment
from src.domain.appointment.value_objects import AppointmentStatus
from src.domain.shared.errors import (
    BusinessRuleViolationError,
    ConflictError,
    NotFoundError,
)

TENANT_ID = uuid4()
BUSINESS_ID = uuid4()
FUTURE = datetime.now(timezone.utc) + timedelta(days=1)


def _appointment(status: AppointmentStatus = AppointmentStatus.PENDING) -> Appointment:
    apt = Appointment.book(
        tenant_id=TENANT_ID,
        business_id=BUSINESS_ID,
        service_id=uuid4(),
        client_id=uuid4(),
        scheduled_at=FUTURE,
        duration_minutes=45,
        professional_id=uuid4(),
    )
    apt.status = status
    return apt


class MockUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None


class MockAppointmentRepository:
    def __init__(self, apt: Appointment | None) -> None:
        self.apt = apt
        self.updated: Appointment | None = None

    async def get_by_id(self, appointment_id: UUID) -> Appointment | None:
        return self.apt

    async def update(self, apt: Appointment) -> None:
        self.updated = apt


# ── El agregado ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "status",
    [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED, AppointmentStatus.RESCHEDULED],
)
def test_any_open_appointment_can_be_closed(status):
    """Antes exigía CONFIRMED, y las citas nacen PENDING: con esa regla no se
    podía cerrar casi ninguna."""
    apt = _appointment(status)

    apt.complete(amount_charged=28000)

    assert apt.status == AppointmentStatus.COMPLETED
    assert apt.amount_charged == 28000
    assert apt.completed_at is not None
    assert apt.completed_at.tzinfo is not None, "debe ser aware, o el timestamp se desplaza"


@pytest.mark.parametrize(
    "status", [AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW]
)
def test_a_closed_appointment_cannot_be_completed(status):
    apt = _appointment(status)

    with pytest.raises(BusinessRuleViolationError):
        apt.complete(amount_charged=1000)


def test_a_courtesy_service_is_closed_with_zero():
    """Cero es un cobro válido; lo que no se acepta es un importe ausente."""
    apt = _appointment()

    apt.complete(amount_charged=0)

    assert apt.status == AppointmentStatus.COMPLETED
    assert apt.amount_charged == 0


def test_a_negative_amount_is_rejected():
    apt = _appointment()

    with pytest.raises(BusinessRuleViolationError):
        apt.complete(amount_charged=-1)


def test_no_show_also_accepts_a_pending_appointment():
    apt = _appointment(AppointmentStatus.PENDING)

    apt.mark_no_show()

    assert apt.status == AppointmentStatus.NO_SHOW
    assert apt.amount_charged is None, "no vino: no hay nada cobrado"


# ── El caso de uso ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_completing_records_the_amount_and_commits():
    apt = _appointment()
    repo = MockAppointmentRepository(apt)
    uow = MockUnitOfWork()

    out = await CompleteAppointmentUseCase(appointments=repo, uow=uow).execute(
        CompleteAppointmentInput(appointment_id=apt.id, amount_charged=45000)
    )

    assert out.status == AppointmentStatus.COMPLETED
    assert out.amount_charged == 45000
    assert repo.updated is apt
    assert uow.committed


@pytest.mark.asyncio
async def test_completing_twice_reports_a_conflict_not_a_rule_violation():
    """Dos pestañas o un doble clic deben leerse como «alguien llegó primero»,
    no como un fallo: el panel muestra un aviso, no un error."""
    apt = _appointment(AppointmentStatus.COMPLETED)
    repo = MockAppointmentRepository(apt)

    with pytest.raises(ConflictError):
        await CompleteAppointmentUseCase(appointments=repo, uow=MockUnitOfWork()).execute(
            CompleteAppointmentInput(appointment_id=apt.id, amount_charged=1000)
        )


@pytest.mark.asyncio
async def test_completing_a_missing_appointment_is_not_found():
    repo = MockAppointmentRepository(None)

    with pytest.raises(NotFoundError):
        await CompleteAppointmentUseCase(appointments=repo, uow=MockUnitOfWork()).execute(
            CompleteAppointmentInput(appointment_id=uuid4(), amount_charged=1000)
        )


@pytest.mark.asyncio
async def test_the_note_is_appended_without_losing_the_existing_one():
    apt = _appointment()
    apt.notes = "Alergia al amoníaco"
    repo = MockAppointmentRepository(apt)

    await CompleteAppointmentUseCase(appointments=repo, uow=MockUnitOfWork()).execute(
        CompleteAppointmentInput(
            appointment_id=apt.id, amount_charged=25000, note="pagó con tarjeta"
        )
    )

    assert "Alergia al amoníaco" in apt.notes
    assert "pagó con tarjeta" in apt.notes
