from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.membership.repository import MembershipPlanRepository
from src.domain.membership.value_objects import BillingPeriod


@dataclass(frozen=True)
class ListMembershipPlansInput:
    business_id: UUID
    include_inactive: bool = False
    page: int = 1
    page_size: int = 10


@dataclass(frozen=True)
class MembershipPlanSummary:
    membership_plan_id: UUID
    name: str
    description: str | None
    price: int
    billing_period: BillingPeriod
    is_active: bool
    service_ids: list[UUID] = field(default_factory=list)   # empty = all services


@dataclass(frozen=True)
class ListMembershipPlansOutput:
    plans: list[MembershipPlanSummary]
    total: int
    page: int
    page_size: int


class ListMembershipPlansUseCase(UseCase[ListMembershipPlansInput, ListMembershipPlansOutput]):
    """List membership plans of a business (paginated)."""

    def __init__(self, plans: MembershipPlanRepository) -> None:
        self._plans = plans

    async def execute(self, input_data: ListMembershipPlansInput) -> ListMembershipPlansOutput:
        page = max(1, input_data.page)
        page_size = max(1, min(100, input_data.page_size))
        offset = (page - 1) * page_size

        plans = await self._plans.list_by_business(
            input_data.business_id,
            include_inactive=input_data.include_inactive,
            limit=page_size,
            offset=offset,
        )
        total = await self._plans.count_by_business(
            input_data.business_id,
            include_inactive=input_data.include_inactive,
        )

        summaries = []
        for plan in plans:
            service_ids = await self._plans.list_service_ids(plan.id)
            summaries.append(
                MembershipPlanSummary(
                    membership_plan_id=plan.id,
                    name=plan.name,
                    description=plan.description,
                    price=plan.price,
                    billing_period=plan.billing_period,
                    is_active=plan.is_active,
                    service_ids=service_ids,
                )
            )

        return ListMembershipPlansOutput(
            plans=summaries,
            total=total,
            page=page,
            page_size=page_size,
        )
