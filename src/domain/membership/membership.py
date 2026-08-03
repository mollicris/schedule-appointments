from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.membership.membership_plan import MembershipPlan
from src.domain.membership.value_objects import BillingPeriod, MembershipStatus
from src.domain.shared.entity import TenantAwareEntity
from src.domain.shared.errors import BusinessRuleViolationError


@dataclass(eq=False)
class Membership(TenantAwareEntity):
    """A client's membership at a business.

    ``billing_period`` and ``price_paid`` are snapshots taken when the membership
    was granted: changing the plan's price later must not rewrite what a member
    already bought.

    All datetimes are timezone-aware UTC (``datetime.now(timezone.utc)``), since
    validity is compared against the current time.

    Lifecycle:
        ACTIVE → FROZEN → ACTIVE     (freeze pauses and extends the end date)
        ACTIVE → EXPIRED             (end date reached)
        ACTIVE | FROZEN → CANCELLED  (terminal)
    """

    business_id: UUID = UUID(int=0)
    client_id: UUID = UUID(int=0)
    membership_plan_id: UUID = UUID(int=0)
    status: MembershipStatus = MembershipStatus.ACTIVE
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    billing_period: BillingPeriod = BillingPeriod.MONTHLY   # snapshot
    price_paid: int = 0                                    # snapshot, in cents
    frozen_at: datetime | None = None
    frozen_days_used: int = 0
    renewal_count: int = 0
    cancelled_at: datetime | None = None
    cancelled_reason: str | None = None
    notes: str | None = None

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def grant(
        cls,
        *,
        tenant_id: UUID,
        business_id: UUID,
        client_id: UUID,
        plan: MembershipPlan,
        starts_at: datetime | None = None,
        notes: str | None = None,
    ) -> Membership:
        """Grant a membership to a client based on a plan."""
        now = datetime.now(timezone.utc)
        start = starts_at or now
        if start.tzinfo is None:
            raise BusinessRuleViolationError("starts_at must be timezone-aware (UTC)")

        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            client_id=client_id,
            membership_plan_id=plan.id,
            status=MembershipStatus.ACTIVE,
            starts_at=start,
            ends_at=plan.billing_period.add_to(start),
            billing_period=plan.billing_period,
            price_paid=plan.price,
            notes=notes,
            created_at=now,
            updated_at=now,
        )

    # ── Queries (never write) ─────────────────────────────────────────────────

    def effective_status(self, now: datetime | None = None) -> MembershipStatus:
        """Status as the client experiences it, without persisting anything.

        An ACTIVE membership past its end date reads as EXPIRED, so a read path
        (the WhatsApp agent, a GET endpoint) never reports stale information.
        """
        moment = now or datetime.now(timezone.utc)
        if self.status == MembershipStatus.ACTIVE and self.ends_at and moment >= self.ends_at:
            return MembershipStatus.EXPIRED
        return self.status

    def is_current(self, now: datetime | None = None) -> bool:
        """True when the membership entitles the client to attend right now.

        FROZEN is deliberately not current: pausing is the whole point.
        """
        moment = now or datetime.now(timezone.utc)
        if self.effective_status(moment) != MembershipStatus.ACTIVE:
            return False
        return bool(self.starts_at and self.starts_at <= moment and self.ends_at and moment < self.ends_at)

    def days_remaining(self, now: datetime | None = None) -> int:
        """Whole days left before expiry (0 once expired)."""
        moment = now or datetime.now(timezone.utc)
        if not self.ends_at or moment >= self.ends_at:
            return 0
        return math.ceil((self.ends_at - moment).total_seconds() / 86400)

    # ── Commands ──────────────────────────────────────────────────────────────

    def renew(self, *, at: datetime | None = None, period: BillingPeriod | None = None) -> None:
        """Extend the membership by one period.

        Renewing early extends from the current end date (the member does not
        lose the days already paid); renewing after expiry starts from ``at``.
        """
        if self.status == MembershipStatus.CANCELLED:
            raise BusinessRuleViolationError("Cannot renew a cancelled membership")
        if self.status == MembershipStatus.FROZEN:
            raise BusinessRuleViolationError("Unfreeze the membership before renewing it")

        moment = at or datetime.now(timezone.utc)
        applied = period or self.billing_period
        base = self.ends_at if self.ends_at and self.ends_at > moment else moment

        self.ends_at = applied.add_to(base)
        self.billing_period = applied
        self.status = MembershipStatus.ACTIVE
        self.renewal_count += 1
        self.updated_at = moment

    def freeze(self, *, at: datetime | None = None) -> None:
        """Pause the membership (holidays, injury). Extends on unfreeze."""
        if self.status != MembershipStatus.ACTIVE:
            raise BusinessRuleViolationError(f"Cannot freeze a membership in status '{self.status}'")

        moment = at or datetime.now(timezone.utc)
        self.status = MembershipStatus.FROZEN
        self.frozen_at = moment
        self.updated_at = moment

    def unfreeze(self, *, at: datetime | None = None) -> None:
        """Resume a frozen membership, pushing the end date by the frozen days."""
        if self.status != MembershipStatus.FROZEN:
            raise BusinessRuleViolationError(
                f"Cannot unfreeze a membership in status '{self.status}'"
            )

        moment = at or datetime.now(timezone.utc)
        frozen_days = 0
        if self.frozen_at:
            frozen_days = max(0, math.ceil((moment - self.frozen_at).total_seconds() / 86400))

        if self.ends_at and frozen_days:
            from datetime import timedelta

            self.ends_at = self.ends_at + timedelta(days=frozen_days)

        self.frozen_days_used += frozen_days
        self.frozen_at = None
        self.status = MembershipStatus.ACTIVE
        self.updated_at = moment

    def expire_if_due(self, *, now: datetime | None = None) -> bool:
        """Persist the EXPIRED status when the end date has passed."""
        moment = now or datetime.now(timezone.utc)
        if self.status == MembershipStatus.ACTIVE and self.ends_at and moment >= self.ends_at:
            self.status = MembershipStatus.EXPIRED
            self.updated_at = moment
            return True
        return False

    def cancel(self, *, at: datetime | None = None, reason: str | None = None) -> None:
        """Terminate the membership (no refunds modelled here)."""
        if self.status == MembershipStatus.CANCELLED:
            return

        moment = at or datetime.now(timezone.utc)
        self.status = MembershipStatus.CANCELLED
        self.cancelled_at = moment
        self.cancelled_reason = reason
        self.updated_at = moment
