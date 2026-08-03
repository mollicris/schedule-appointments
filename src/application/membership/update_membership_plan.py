from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.membership.repository import MembershipPlanRepository
from src.domain.membership.value_objects import BillingPeriod
from src.domain.shared.errors import NotFoundError, ValidationError


@dataclass(frozen=True)
class UpdateMembershipPlanInput:
    membership_plan_id: UUID
    name: str | None = None
    description: str | None = None
    price: int | None = None
    billing_period: BillingPeriod | None = None
    service_ids: list[UUID] | None = None   # None = leave as is, [] = all services
    is_active: bool | None = None


@dataclass(frozen=True)
class UpdateMembershipPlanOutput:
    membership_plan_id: UUID
    name: str
    price: int
    billing_period: BillingPeriod
    is_active: bool
    service_ids: list[UUID]


class UpdateMembershipPlanUseCase(
    UseCase[UpdateMembershipPlanInput, UpdateMembershipPlanOutput]
):
    """Update a membership plan.

    Memberships already granted keep their own snapshot of period and price, so
    editing a plan never changes what a member already bought.
    """

    def __init__(self, plans: MembershipPlanRepository, uow: UnitOfWork) -> None:
        self._plans = plans
        self._uow = uow

    async def execute(self, input_data: UpdateMembershipPlanInput) -> UpdateMembershipPlanOutput:
        self._validate_input(input_data)

        async with self._uow:
            plan = await self._plans.get_by_id(input_data.membership_plan_id)
            if not plan:
                raise NotFoundError(
                    f"Membership plan {input_data.membership_plan_id} not found"
                )

            plan.update(
                name=input_data.name,
                description=input_data.description,
                price=input_data.price,
                billing_period=input_data.billing_period,
            )

            if input_data.is_active is True:
                plan.activate()
            elif input_data.is_active is False:
                plan.deactivate()

            await self._plans.update(plan)

            if input_data.service_ids is not None:
                await self._plans.set_services(plan.id, input_data.service_ids)

            await self._uow.commit()

        service_ids = await self._plans.list_service_ids(plan.id)
        return UpdateMembershipPlanOutput(
            membership_plan_id=plan.id,
            name=plan.name,
            price=plan.price,
            billing_period=plan.billing_period,
            is_active=plan.is_active,
            service_ids=service_ids,
        )

    def _validate_input(self, data: UpdateMembershipPlanInput) -> None:
        if data.name is not None and not data.name.strip():
            raise ValidationError("Membership plan name cannot be empty")
        if data.price is not None and data.price < 0:
            raise ValidationError("Membership plan price cannot be negative")
