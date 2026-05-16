from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.domain.tenant.tenant import Tenant
from src.domain.tenant.value_objects import SubscriptionPlan, TenantSlug, TenantStatus
from src.infrastructure.persistence.models import TenantModel


class TenantMapper:
    """Map between domain Tenant aggregate and ORM TenantModel."""

    @staticmethod
    def fromPersistence(tenant: Tenant) -> TenantModel:
        """Domain → ORM."""
        return TenantModel(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug.value if tenant.slug else "",
            admin_email=tenant.admin_email,
            industry=tenant.industry,
            status=tenant.status.value,
            plan=tenant.plan.value,
            trial_ends_at=tenant.trial_ends_at,
            verified_at=tenant.verified_at,
            onboarded_at=tenant.onboarded_at,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )

    @staticmethod
    def toPersistence(model: TenantModel | None) -> Tenant | None:
        """ORM → Domain."""
        if not model:
            return None

        tenant = Tenant(
            id=model.id,
            name=model.name,
            slug=TenantSlug(value=model.slug),
            admin_email=model.admin_email,
            industry=model.industry,
            status=TenantStatus(model.status),
            plan=SubscriptionPlan(model.plan),
            trial_ends_at=model.trial_ends_at,
            verified_at=model.verified_at,
            onboarded_at=model.onboarded_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
        # Domain events are NOT persisted in this initial version;
        # they would be stored in an event table in a full event sourcing setup
        return tenant
