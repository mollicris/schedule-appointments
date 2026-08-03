from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.membership.value_objects import BillingPeriod
from src.domain.shared.entity import TenantAwareEntity
from src.domain.shared.errors import BusinessRuleViolationError


@dataclass(eq=False)
class MembershipPlan(TenantAwareEntity):
    """Membership plan aggregate root — what a gym sells to its members.

    Named ``MembershipPlan`` and not ``Plan`` on purpose: ``Tenant.plan``
    (``SubscriptionPlan``) is the SaaS plan the business pays us, a different
    concept entirely.

    The services a plan includes live in a bridge table (see
    ``MembershipPlanRepository.list_service_ids``). An empty set means the plan
    includes every service — the same convention as services without assigned
    professionals meaning "anyone can perform it".

    Lifecycle:
        Created → Active (default) → Inactive (soft delete)
    """

    business_id: UUID = UUID(int=0)
    name: str = ""
    description: str | None = None
    price: int = 0                                       # in cents
    billing_period: BillingPeriod = BillingPeriod.MONTHLY
    is_active: bool = True

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        business_id: UUID,
        name: str,
        price: int,
        billing_period: BillingPeriod = BillingPeriod.MONTHLY,
        description: str | None = None,
    ) -> MembershipPlan:
        """Factory for creating a new membership plan."""
        if not name.strip():
            raise BusinessRuleViolationError("Membership plan name cannot be empty")
        if price < 0:
            raise BusinessRuleViolationError("Membership plan price cannot be negative")

        now = datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            name=name.strip(),
            description=description,
            price=price,
            billing_period=billing_period,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        price: int | None = None,
        billing_period: BillingPeriod | None = None,
    ) -> None:
        """Update plan details.

        Editing a plan never rewrites memberships already granted: each
        membership keeps its own snapshot of period and price paid.
        """
        if name is not None:
            if not name.strip():
                raise BusinessRuleViolationError("Membership plan name cannot be empty")
            self.name = name.strip()

        if price is not None:
            if price < 0:
                raise BusinessRuleViolationError("Membership plan price cannot be negative")
            self.price = price

        if billing_period is not None:
            self.billing_period = billing_period

        if description is not None:
            self.description = description

        self.updated_at = datetime.now(timezone.utc)

    def deactivate(self) -> None:
        """Soft delete: stop offering this plan (existing memberships stay valid)."""
        if not self.is_active:
            return
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)

    def activate(self) -> None:
        """Offer this plan again."""
        if self.is_active:
            return
        self.is_active = True
        self.updated_at = datetime.now(timezone.utc)
