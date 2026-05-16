from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.domain.shared.events import DomainEvent
from src.domain.tenant.value_objects import SubscriptionPlan, TenantStatus


@dataclass(frozen=True, kw_only=True)
class TenantRegistered(DomainEvent):
    """Emitted when a new tenant signs up. Triggers the auto-onboarding pipeline:
    send verification email, create default resources, start trial timer.
    """

    tenant_name: str
    admin_email: str
    industry: str


@dataclass(frozen=True, kw_only=True)
class TenantVerified(DomainEvent):
    """Email/phone verification completed. Tenant can proceed to onboarding wizard."""


@dataclass(frozen=True, kw_only=True)
class TenantOnboardingCompleted(DomainEvent):
    """Tenant has finished the setup wizard and the bot is ready to receive messages."""


@dataclass(frozen=True, kw_only=True)
class TenantPlanChanged(DomainEvent):
    previous_plan: SubscriptionPlan
    new_plan: SubscriptionPlan


@dataclass(frozen=True, kw_only=True)
class TenantStatusChanged(DomainEvent):
    previous_status: TenantStatus
    new_status: TenantStatus
    reason: str | None = None
