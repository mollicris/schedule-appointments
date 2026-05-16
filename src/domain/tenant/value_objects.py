from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.domain.shared.entity import ValueObject
from src.domain.shared.errors import ValidationError


class SubscriptionPlan(str, Enum):
    TRIAL = "trial"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class TenantStatus(str, Enum):
    """Lifecycle of a tenant from signup to potential suspension."""

    PENDING_VERIFICATION = "pending_verification"  # Signed up, email not verified
    ONBOARDING = "onboarding"  # Verified, completing setup wizard
    ACTIVE = "active"  # Fully onboarded, bot live
    TRIAL_EXPIRED = "trial_expired"  # Needs to pick a paid plan
    SUSPENDED = "suspended"  # Payment issue / admin action
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class TenantSlug(ValueObject):
    """URL-safe identifier for a tenant (e.g. 'salon-maria-lopez').

    Used in subdomains, public booking links, and as a human-readable
    fallback to the UUID id.
    """

    value: str

    _PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,46}[a-z0-9])?$")

    def _validate(self) -> None:
        if not self._PATTERN.match(self.value):
            raise ValidationError(
                f"Invalid tenant slug '{self.value}': must be 1-48 chars, "
                "lowercase alphanumerics and dashes, no leading/trailing dash"
            )
