from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.membership.repository import MembershipPlanRepository, MembershipRepository
from src.domain.membership.value_objects import BillingPeriod, MembershipStatus


@dataclass(frozen=True)
class GetClientMembershipInput:
    client_id: UUID
    business_id: UUID


@dataclass(frozen=True)
class GetClientMembershipOutput:
    """Everything the agent (or the API) needs to talk about a membership.

    ``warning`` is a short Spanish sentence ready to send over WhatsApp when the
    membership does not entitle the client to attend. It never blocks a booking:
    the agent mentions it and offers to renew.
    """

    has_membership: bool
    membership_id: UUID | None = None
    plan_name: str | None = None
    status: MembershipStatus | None = None
    billing_period: BillingPeriod | None = None
    price_paid: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    days_remaining: int | None = None
    is_current: bool = False
    included_service_ids: list[UUID] = field(default_factory=list)   # empty = all
    warning: str | None = None


class GetClientMembershipUseCase(
    UseCase[GetClientMembershipInput, GetClientMembershipOutput]
):
    """Read the membership status of a client at a business.

    Read-only on purpose: an expired membership is reported as EXPIRED through
    ``effective_status`` without persisting anything, so GET requests and the
    agent never write.
    """

    def __init__(
        self,
        memberships: MembershipRepository,
        plans: MembershipPlanRepository,
    ) -> None:
        self._memberships = memberships
        self._plans = plans

    async def execute(self, input_data: GetClientMembershipInput) -> GetClientMembershipOutput:
        membership = await self._memberships.get_current_for_client(
            input_data.client_id, input_data.business_id
        )

        if membership is None:
            # Fall back to the latest historical membership, so the agent can say
            # "tu plan venció el 5 de julio" instead of "no tienes membresía".
            history = await self._memberships.list_by_client(input_data.client_id, limit=1)
            membership = history[0] if history else None

        if membership is None:
            return GetClientMembershipOutput(
                has_membership=False,
                warning="El cliente no tiene una membresía registrada.",
            )

        plan = await self._plans.get_by_id(membership.membership_plan_id)
        service_ids = await self._plans.list_service_ids(membership.membership_plan_id)
        status = membership.effective_status()
        is_current = membership.is_current()

        return GetClientMembershipOutput(
            has_membership=True,
            membership_id=membership.id,
            plan_name=plan.name if plan else None,
            status=status,
            billing_period=membership.billing_period,
            price_paid=membership.price_paid,
            starts_at=membership.starts_at,
            ends_at=membership.ends_at,
            days_remaining=membership.days_remaining(),
            is_current=is_current,
            included_service_ids=service_ids,
            warning=None if is_current else _warning_for(status, membership.ends_at),
        )


def _warning_for(status: MembershipStatus, ends_at: datetime | None) -> str:
    """Short, WhatsApp-ready reason why the membership is not usable right now."""
    when = ends_at.strftime("%d/%m/%Y") if ends_at else "una fecha anterior"
    if status == MembershipStatus.EXPIRED:
        return f"La membresía venció el {when}."
    if status == MembershipStatus.FROZEN:
        return "La membresía está congelada."
    if status == MembershipStatus.CANCELLED:
        return "La membresía fue cancelada."
    return "La membresía aún no está vigente."
