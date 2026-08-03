from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.membership.repository import MembershipRepository
from src.domain.membership.value_objects import BillingPeriod, MembershipStatus


@dataclass(frozen=True)
class ListMembershipsInput:
    business_id: UUID
    status: MembershipStatus | None = None
    expiring_in_days: int | None = None   # e.g. 7 → memberships ending this week
    page: int = 1
    page_size: int = 10


@dataclass(frozen=True)
class MembershipSummary:
    membership_id: UUID
    client_id: UUID
    membership_plan_id: UUID
    status: MembershipStatus          # effective status (expiry applied)
    starts_at: datetime
    ends_at: datetime
    days_remaining: int
    billing_period: BillingPeriod
    price_paid: int


@dataclass(frozen=True)
class ListMembershipsOutput:
    memberships: list[MembershipSummary]
    total: int
    page: int
    page_size: int


class ListMembershipsUseCase(UseCase[ListMembershipsInput, ListMembershipsOutput]):
    """List memberships of a business, optionally by status or upcoming expiry.

    ``expiring_in_days`` is what the reception desk (and later the campaign job)
    uses to find members to call before their plan lapses.
    """

    def __init__(self, memberships: MembershipRepository) -> None:
        self._memberships = memberships

    async def execute(self, input_data: ListMembershipsInput) -> ListMembershipsOutput:
        page = max(1, input_data.page)
        page_size = max(1, min(100, input_data.page_size))
        offset = (page - 1) * page_size

        expiring_before = None
        if input_data.expiring_in_days is not None:
            expiring_before = datetime.now(timezone.utc) + timedelta(
                days=max(0, input_data.expiring_in_days)
            )

        memberships = await self._memberships.list_by_business(
            input_data.business_id,
            status=input_data.status,
            expiring_before=expiring_before,
            limit=page_size,
            offset=offset,
        )
        total = await self._memberships.count_by_business(
            input_data.business_id,
            status=input_data.status,
            expiring_before=expiring_before,
        )

        return ListMembershipsOutput(
            memberships=[
                MembershipSummary(
                    membership_id=m.id,
                    client_id=m.client_id,
                    membership_plan_id=m.membership_plan_id,
                    status=m.effective_status(),
                    starts_at=m.starts_at,
                    ends_at=m.ends_at,
                    days_remaining=m.days_remaining(),
                    billing_period=m.billing_period,
                    price_paid=m.price_paid,
                )
                for m in memberships
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
