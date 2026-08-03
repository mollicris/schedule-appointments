from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum


class BillingPeriod(str, Enum):
    """How long a membership lasts once granted or renewed.

    Durations are counted in days on purpose: month arithmetic would need an
    extra dependency and creates end-of-month edge cases ("31 de enero + 1 mes")
    that a gym counter has to explain to the client.
    """

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"

    @property
    def days(self) -> int:
        return {
            BillingPeriod.MONTHLY: 30,
            BillingPeriod.QUARTERLY: 90,
            BillingPeriod.ANNUAL: 365,
        }[self]

    def add_to(self, moment: datetime) -> datetime:
        return moment + timedelta(days=self.days)

    @property
    def label_es(self) -> str:
        return {
            BillingPeriod.MONTHLY: "mensual",
            BillingPeriod.QUARTERLY: "trimestral",
            BillingPeriod.ANNUAL: "anual",
        }[self]


class MembershipStatus(str, Enum):
    """Lifecycle of a client's membership.

    ACTIVE → FROZEN → ACTIVE (freeze pauses and extends the end date)
    ACTIVE → EXPIRED (end date reached; renewing issues/extends)
    ACTIVE | FROZEN → CANCELLED (terminal)
    """

    ACTIVE = "active"
    FROZEN = "frozen"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (MembershipStatus.EXPIRED, MembershipStatus.CANCELLED)
