"""Membership lifecycle rules: validity, renewal, freezing and cancellation."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.membership.membership import Membership
from src.domain.membership.membership_plan import MembershipPlan
from src.domain.membership.value_objects import BillingPeriod, MembershipStatus
from src.domain.shared.errors import BusinessRuleViolationError

TENANT_ID = uuid4()
BUSINESS_ID = uuid4()
CLIENT_ID = uuid4()
START = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def _plan(period: BillingPeriod = BillingPeriod.MONTHLY, price: int = 5000) -> MembershipPlan:
    return MembershipPlan.create(
        tenant_id=TENANT_ID,
        business_id=BUSINESS_ID,
        name="Premium",
        price=price,
        billing_period=period,
    )


def _membership(period: BillingPeriod = BillingPeriod.MONTHLY) -> Membership:
    return Membership.grant(
        tenant_id=TENANT_ID,
        business_id=BUSINESS_ID,
        client_id=CLIENT_ID,
        plan=_plan(period),
        starts_at=START,
    )


# ── Granting ─────────────────────────────────────────────────────────────────


def test_grant_sets_the_end_date_from_the_billing_period():
    monthly = _membership(BillingPeriod.MONTHLY)
    annual = _membership(BillingPeriod.ANNUAL)

    assert monthly.ends_at == START + timedelta(days=30)
    assert annual.ends_at == START + timedelta(days=365)
    assert monthly.status == MembershipStatus.ACTIVE


def test_grant_snapshots_period_and_price_so_plan_edits_do_not_rewrite_history():
    plan = _plan(price=5000)
    membership = Membership.grant(
        tenant_id=TENANT_ID,
        business_id=BUSINESS_ID,
        client_id=CLIENT_ID,
        plan=plan,
        starts_at=START,
    )

    plan.update(price=9900, billing_period=BillingPeriod.ANNUAL)

    assert membership.price_paid == 5000
    assert membership.billing_period == BillingPeriod.MONTHLY


def test_grant_rejects_a_naive_start_date():
    with pytest.raises(BusinessRuleViolationError) as exc_info:
        Membership.grant(
            tenant_id=TENANT_ID,
            business_id=BUSINESS_ID,
            client_id=CLIENT_ID,
            plan=_plan(),
            starts_at=datetime(2026, 7, 1, 12, 0),   # no tzinfo
        )

    assert "timezone-aware" in str(exc_info.value)


# ── Validity boundaries ──────────────────────────────────────────────────────


def test_is_current_at_the_boundaries_of_the_validity_window():
    membership = _membership()

    assert membership.is_current(START) is True
    assert membership.is_current(START - timedelta(seconds=1)) is False
    assert membership.is_current(membership.ends_at - timedelta(seconds=1)) is True
    assert membership.is_current(membership.ends_at) is False   # end date is exclusive


def test_effective_status_reports_expired_without_persisting_it():
    membership = _membership()
    after_expiry = membership.ends_at + timedelta(days=1)

    assert membership.effective_status(after_expiry) == MembershipStatus.EXPIRED
    assert membership.status == MembershipStatus.ACTIVE   # nothing was written


def test_expire_if_due_persists_the_status_once_due():
    membership = _membership()

    assert membership.expire_if_due(now=membership.ends_at - timedelta(days=1)) is False
    assert membership.expire_if_due(now=membership.ends_at) is True
    assert membership.status == MembershipStatus.EXPIRED


def test_days_remaining_rounds_up_and_floors_at_zero():
    membership = _membership()

    assert membership.days_remaining(membership.ends_at - timedelta(hours=1)) == 1
    assert membership.days_remaining(membership.ends_at) == 0
    assert membership.days_remaining(membership.ends_at + timedelta(days=5)) == 0


# ── Renewal ──────────────────────────────────────────────────────────────────


def test_renewing_early_extends_from_the_current_end_date():
    membership = _membership()
    original_end = membership.ends_at

    membership.renew(at=original_end - timedelta(days=5))

    assert membership.ends_at == original_end + timedelta(days=30)
    assert membership.renewal_count == 1


def test_renewing_after_expiry_extends_from_the_renewal_date():
    membership = _membership()
    late = membership.ends_at + timedelta(days=10)

    membership.renew(at=late)

    assert membership.ends_at == late + timedelta(days=30)
    assert membership.status == MembershipStatus.ACTIVE


def test_renewing_can_switch_the_period_and_updates_the_snapshot():
    membership = _membership()

    membership.renew(at=START, period=BillingPeriod.ANNUAL)

    assert membership.billing_period == BillingPeriod.ANNUAL
    assert membership.ends_at == START + timedelta(days=30) + timedelta(days=365)


def test_a_cancelled_membership_cannot_be_renewed():
    membership = _membership()
    membership.cancel(at=START, reason="mudanza")

    with pytest.raises(BusinessRuleViolationError):
        membership.renew(at=START)


def test_a_frozen_membership_must_be_unfrozen_before_renewing():
    membership = _membership()
    membership.freeze(at=START)

    with pytest.raises(BusinessRuleViolationError) as exc_info:
        membership.renew(at=START)

    assert "Unfreeze" in str(exc_info.value)


# ── Freezing ─────────────────────────────────────────────────────────────────


def test_unfreezing_pushes_the_end_date_by_the_frozen_days():
    membership = _membership()
    original_end = membership.ends_at

    membership.freeze(at=START + timedelta(days=2))
    membership.unfreeze(at=START + timedelta(days=9))

    assert membership.status == MembershipStatus.ACTIVE
    assert membership.frozen_days_used == 7
    assert membership.ends_at == original_end + timedelta(days=7)
    assert membership.frozen_at is None


def test_a_frozen_membership_is_not_current():
    membership = _membership()
    membership.freeze(at=START)

    assert membership.is_current(START + timedelta(days=1)) is False
    assert membership.effective_status(START + timedelta(days=1)) == MembershipStatus.FROZEN


def test_freezing_twice_is_rejected():
    membership = _membership()
    membership.freeze(at=START)

    with pytest.raises(BusinessRuleViolationError):
        membership.freeze(at=START + timedelta(days=1))


def test_unfreezing_an_active_membership_is_rejected():
    membership = _membership()

    with pytest.raises(BusinessRuleViolationError):
        membership.unfreeze(at=START)


# ── Cancellation ─────────────────────────────────────────────────────────────


def test_cancelling_records_the_reason_and_is_idempotent():
    membership = _membership()

    membership.cancel(at=START, reason="se mudó de ciudad")
    first_cancelled_at = membership.cancelled_at
    membership.cancel(at=START + timedelta(days=1), reason="otra razón")

    assert membership.status == MembershipStatus.CANCELLED
    assert membership.cancelled_reason == "se mudó de ciudad"
    assert membership.cancelled_at == first_cancelled_at


# ── Plan invariants ──────────────────────────────────────────────────────────


def test_plan_rejects_an_empty_name_and_a_negative_price():
    with pytest.raises(BusinessRuleViolationError):
        MembershipPlan.create(
            tenant_id=TENANT_ID, business_id=BUSINESS_ID, name="   ", price=100
        )

    with pytest.raises(BusinessRuleViolationError):
        MembershipPlan.create(
            tenant_id=TENANT_ID, business_id=BUSINESS_ID, name="Premium", price=-1
        )
