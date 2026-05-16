from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from src.domain.shared.entity import Entity
from src.domain.shared.errors import BusinessRuleViolationError
from src.domain.tenant.events import (
    TenantOnboardingCompleted,
    TenantPlanChanged,
    TenantRegistered,
    TenantStatusChanged,
    TenantVerified,
)
from src.domain.tenant.value_objects import SubscriptionPlan, TenantSlug, TenantStatus

TRIAL_DURATION = timedelta(days=14)


@dataclass(eq=False)
class Tenant(Entity):
    """Tenant aggregate root.

    A Tenant represents a customer organization that has signed up to the
    platform. It owns one or more Businesses (multi-location support) and
    all other resources (clients, appointments, conversations) belong to
    exactly one tenant.

    The Tenant is the **only** aggregate that does NOT extend
    ``TenantAwareEntity`` — it IS the tenant.

    Lifecycle:
        PENDING_VERIFICATION  → register()
        ONBOARDING            → verify()
        ACTIVE                → complete_onboarding()
        TRIAL_EXPIRED         → automatic (cron)
        SUSPENDED / CANCELLED → admin actions
    """

    name: str = ""
    slug: TenantSlug | None = None
    admin_email: str = ""
    industry: str = ""  # 'hair_salon', 'veterinary', 'mechanic', etc.
    status: TenantStatus = TenantStatus.PENDING_VERIFICATION
    plan: SubscriptionPlan = SubscriptionPlan.TRIAL
    trial_ends_at: datetime | None = None
    verified_at: datetime | None = None
    onboarded_at: datetime | None = None

    @classmethod
    def register(
        cls,
        *,
        name: str,
        slug: TenantSlug,
        admin_email: str,
        industry: str,
    ) -> Tenant:
        """Factory for new tenant signup. Emits ``TenantRegistered``
        to trigger the auto-onboarding pipeline."""
        if not name.strip():
            raise BusinessRuleViolationError("Tenant name cannot be empty")
        if "@" not in admin_email:
            raise BusinessRuleViolationError("Invalid admin email")

        tenant_id = uuid4()
        now = datetime.utcnow()
        tenant = cls(
            id=tenant_id,
            name=name.strip(),
            slug=slug,
            admin_email=admin_email.lower().strip(),
            industry=industry,
            status=TenantStatus.PENDING_VERIFICATION,
            plan=SubscriptionPlan.TRIAL,
            trial_ends_at=now + TRIAL_DURATION,
            created_at=now,
            updated_at=now,
        )
        tenant.record_event(
            TenantRegistered(
                tenant_id=tenant_id,
                tenant_name=name,
                admin_email=admin_email,
                industry=industry,
            )
        )
        return tenant

    def verify(self) -> None:
        """Mark verification (email/phone) as complete and move into onboarding."""
        if self.status != TenantStatus.PENDING_VERIFICATION:
            raise BusinessRuleViolationError(
                f"Cannot verify tenant in status '{self.status.value}'"
            )
        previous = self.status
        self.status = TenantStatus.ONBOARDING
        self.verified_at = datetime.utcnow()
        self.updated_at = self.verified_at
        self.record_event(TenantVerified(tenant_id=self.id))
        self.record_event(
            TenantStatusChanged(
                tenant_id=self.id,
                previous_status=previous,
                new_status=self.status,
            )
        )

    def complete_onboarding(self) -> None:
        """Finalize the setup wizard and activate the bot."""
        if self.status != TenantStatus.ONBOARDING:
            raise BusinessRuleViolationError(
                f"Cannot complete onboarding from status '{self.status.value}'"
            )
        previous = self.status
        self.status = TenantStatus.ACTIVE
        self.onboarded_at = datetime.utcnow()
        self.updated_at = self.onboarded_at
        self.record_event(TenantOnboardingCompleted(tenant_id=self.id))
        self.record_event(
            TenantStatusChanged(
                tenant_id=self.id,
                previous_status=previous,
                new_status=self.status,
            )
        )

    def change_plan(self, new_plan: SubscriptionPlan) -> None:
        if new_plan == self.plan:
            return
        previous = self.plan
        self.plan = new_plan
        self.updated_at = datetime.utcnow()
        if self.status == TenantStatus.TRIAL_EXPIRED and new_plan != SubscriptionPlan.TRIAL:
            self._transition_status(TenantStatus.ACTIVE, "Paid plan selected")
        self.record_event(
            TenantPlanChanged(tenant_id=self.id, previous_plan=previous, new_plan=new_plan)
        )

    def suspend(self, reason: str) -> None:
        self._transition_status(TenantStatus.SUSPENDED, reason)

    def cancel(self, reason: str) -> None:
        self._transition_status(TenantStatus.CANCELLED, reason)

    def mark_trial_expired(self) -> None:
        if self.plan != SubscriptionPlan.TRIAL:
            return
        if self.trial_ends_at and datetime.utcnow() < self.trial_ends_at:
            return
        self._transition_status(TenantStatus.TRIAL_EXPIRED, "Trial period ended")

    def is_active(self) -> bool:
        return self.status == TenantStatus.ACTIVE

    def can_send_messages(self) -> bool:
        return self.status in (TenantStatus.ACTIVE, TenantStatus.ONBOARDING)

    def _transition_status(self, new_status: TenantStatus, reason: str) -> None:
        if new_status == self.status:
            return
        previous = self.status
        self.status = new_status
        self.updated_at = datetime.utcnow()
        self.record_event(
            TenantStatusChanged(
                tenant_id=self.id,
                previous_status=previous,
                new_status=new_status,
                reason=reason,
            )
        )
