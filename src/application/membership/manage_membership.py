from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.membership.repository import MembershipRepository
from src.domain.membership.value_objects import BillingPeriod, MembershipStatus
from src.domain.shared.errors import NotFoundError

# Lifecycle commands on an existing membership. They share one Output because
# every one of them answers the same question: "how does the membership look
# now?" — which is what both the API and the WhatsApp agent need to reply.


@dataclass(frozen=True)
class MembershipActionInput:
    membership_id: UUID
    period: BillingPeriod | None = None   # renew only; defaults to the snapshot
    reason: str | None = None             # cancel only


@dataclass(frozen=True)
class MembershipActionOutput:
    membership_id: UUID
    client_id: UUID
    status: MembershipStatus
    starts_at: datetime
    ends_at: datetime
    days_remaining: int
    renewal_count: int
    frozen_days_used: int


def _to_output(membership) -> MembershipActionOutput:
    return MembershipActionOutput(
        membership_id=membership.id,
        client_id=membership.client_id,
        status=membership.effective_status(),
        starts_at=membership.starts_at,
        ends_at=membership.ends_at,
        days_remaining=membership.days_remaining(),
        renewal_count=membership.renewal_count,
        frozen_days_used=membership.frozen_days_used,
    )


class _MembershipCommandUseCase(UseCase[MembershipActionInput, MembershipActionOutput]):
    """Shared plumbing: load, mutate, persist, commit."""

    def __init__(self, memberships: MembershipRepository, uow: UnitOfWork) -> None:
        self._memberships = memberships
        self._uow = uow

    async def execute(self, input_data: MembershipActionInput) -> MembershipActionOutput:
        async with self._uow:
            membership = await self._memberships.get_by_id(input_data.membership_id)
            if not membership:
                raise NotFoundError(f"Membership {input_data.membership_id} not found")

            self._apply(membership, input_data)

            await self._memberships.update(membership)
            await self._uow.commit()

        return _to_output(membership)

    def _apply(self, membership, input_data: MembershipActionInput) -> None:
        raise NotImplementedError


class RenewMembershipUseCase(_MembershipCommandUseCase):
    """Extend a membership by one period (early renewals keep the paid days)."""

    def _apply(self, membership, input_data: MembershipActionInput) -> None:
        membership.renew(period=input_data.period)


class FreezeMembershipUseCase(_MembershipCommandUseCase):
    """Pause a membership; unfreezing pushes the end date by the frozen days."""

    def _apply(self, membership, input_data: MembershipActionInput) -> None:
        membership.freeze()


class UnfreezeMembershipUseCase(_MembershipCommandUseCase):
    """Resume a frozen membership."""

    def _apply(self, membership, input_data: MembershipActionInput) -> None:
        membership.unfreeze()


class CancelMembershipUseCase(_MembershipCommandUseCase):
    """Terminate a membership."""

    def _apply(self, membership, input_data: MembershipActionInput) -> None:
        membership.cancel(reason=input_data.reason)
