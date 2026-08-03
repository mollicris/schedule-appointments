from __future__ import annotations

from src.domain.membership.membership import Membership
from src.domain.membership.membership_plan import MembershipPlan
from src.domain.membership.value_objects import BillingPeriod, MembershipStatus
from src.infrastructure.persistence.models import MembershipModel, MembershipPlanModel


class MembershipPlanMapper:
    """Map between the MembershipPlan aggregate and its ORM model."""

    @staticmethod
    def to_model(plan: MembershipPlan) -> MembershipPlanModel:
        return MembershipPlanModel(
            id=plan.id,
            tenant_id=plan.tenant_id,
            business_id=plan.business_id,
            name=plan.name,
            description=plan.description,
            price=plan.price,
            billing_period=plan.billing_period.value,
            is_active=plan.is_active,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )

    @staticmethod
    def to_domain(model: MembershipPlanModel) -> MembershipPlan:
        return MembershipPlan(
            id=model.id,
            tenant_id=model.tenant_id,
            business_id=model.business_id,
            name=model.name,
            description=model.description,
            price=model.price,
            billing_period=BillingPeriod(model.billing_period),
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class MembershipMapper:
    """Map between the Membership aggregate and its ORM model."""

    @staticmethod
    def to_model(membership: Membership) -> MembershipModel:
        return MembershipModel(
            id=membership.id,
            tenant_id=membership.tenant_id,
            business_id=membership.business_id,
            client_id=membership.client_id,
            membership_plan_id=membership.membership_plan_id,
            status=membership.status.value,
            starts_at=membership.starts_at,
            ends_at=membership.ends_at,
            billing_period=membership.billing_period.value,
            price_paid=membership.price_paid,
            frozen_at=membership.frozen_at,
            frozen_days_used=membership.frozen_days_used,
            renewal_count=membership.renewal_count,
            cancelled_at=membership.cancelled_at,
            cancelled_reason=membership.cancelled_reason,
            notes=membership.notes,
            created_at=membership.created_at,
            updated_at=membership.updated_at,
        )

    @staticmethod
    def to_domain(model: MembershipModel) -> Membership:
        return Membership(
            id=model.id,
            tenant_id=model.tenant_id,
            business_id=model.business_id,
            client_id=model.client_id,
            membership_plan_id=model.membership_plan_id,
            status=MembershipStatus(model.status),
            starts_at=model.starts_at,
            ends_at=model.ends_at,
            billing_period=BillingPeriod(model.billing_period),
            price_paid=model.price_paid,
            frozen_at=model.frozen_at,
            frozen_days_used=model.frozen_days_used,
            renewal_count=model.renewal_count,
            cancelled_at=model.cancelled_at,
            cancelled_reason=model.cancelled_reason,
            notes=model.notes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
