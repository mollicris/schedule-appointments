from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.membership.membership_plan import MembershipPlan
from src.domain.membership.repository import MembershipPlanRepository
from src.domain.membership.value_objects import BillingPeriod
from src.domain.shared.errors import ValidationError


@dataclass(frozen=True)
class CreateMembershipPlanInput:
    business_id: UUID
    name: str
    price: int                                    # in cents
    billing_period: BillingPeriod = BillingPeriod.MONTHLY
    description: str | None = None
    service_ids: list[UUID] = field(default_factory=list)   # empty = all services


@dataclass(frozen=True)
class CreateMembershipPlanOutput:
    membership_plan_id: UUID
    name: str
    price: int
    billing_period: BillingPeriod
    service_ids: list[UUID]


class CreateMembershipPlanUseCase(
    UseCase[CreateMembershipPlanInput, CreateMembershipPlanOutput]
):
    """Create a membership plan for a business."""

    def __init__(self, plans: MembershipPlanRepository, uow: UnitOfWork) -> None:
        self._plans = plans
        self._uow = uow

    async def execute(self, input_data: CreateMembershipPlanInput) -> CreateMembershipPlanOutput:
        self._validate_input(input_data)
        tenant = get_current_tenant()

        async with self._uow:
            plan = MembershipPlan.create(
                tenant_id=tenant.tenant_id,
                business_id=input_data.business_id,
                name=input_data.name,
                price=input_data.price,
                billing_period=input_data.billing_period,
                description=input_data.description,
            )
            await self._plans.add(plan)

            if input_data.service_ids:
                await self._plans.set_services(plan.id, input_data.service_ids)

            await self._uow.commit()

        return CreateMembershipPlanOutput(
            membership_plan_id=plan.id,
            name=plan.name,
            price=plan.price,
            billing_period=plan.billing_period,
            service_ids=list(input_data.service_ids),
        )

    def _validate_input(self, data: CreateMembershipPlanInput) -> None:
        if not data.name.strip():
            raise ValidationError("Membership plan name is required")
        if data.price < 0:
            raise ValidationError("Membership plan price cannot be negative")
