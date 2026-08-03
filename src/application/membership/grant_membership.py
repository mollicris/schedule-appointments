from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from src.application.shared.tenant_context import get_current_tenant
from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.client.client import Client
from src.domain.client.repository import ClientRepository
from src.domain.membership.membership import Membership
from src.domain.membership.repository import MembershipPlanRepository, MembershipRepository
from src.domain.membership.value_objects import BillingPeriod, MembershipStatus
from src.domain.shared.errors import ConflictError, NotFoundError, ValidationError


@dataclass(frozen=True)
class GrantMembershipInput:
    business_id: UUID
    membership_plan_id: UUID
    client_id: UUID | None = None
    client_whatsapp: str | None = None    # find-or-create, for the gym counter
    client_name: str | None = None
    starts_at: datetime | None = None     # default: now (UTC)
    notes: str | None = None


@dataclass(frozen=True)
class GrantMembershipOutput:
    membership_id: UUID
    client_id: UUID
    membership_plan_id: UUID
    plan_name: str
    status: MembershipStatus
    starts_at: datetime
    ends_at: datetime
    billing_period: BillingPeriod
    price_paid: int


class GrantMembershipUseCase(UseCase[GrantMembershipInput, GrantMembershipOutput]):
    """Grant a membership to a client.

    Flow:
      1. Load and validate the plan (active, belongs to the business).
      2. Resolve the client by id, or find-or-create by WhatsApp number.
      3. Reject if the client already holds a live membership (renew instead).
      4. Persist the membership with a snapshot of period and price.
    """

    def __init__(
        self,
        memberships: MembershipRepository,
        plans: MembershipPlanRepository,
        clients: ClientRepository,
        uow: UnitOfWork,
    ) -> None:
        self._memberships = memberships
        self._plans = plans
        self._clients = clients
        self._uow = uow

    async def execute(self, input_data: GrantMembershipInput) -> GrantMembershipOutput:
        self._validate_input(input_data)
        tenant = get_current_tenant()

        async with self._uow:
            plan = await self._plans.get_by_id(input_data.membership_plan_id)
            if not plan:
                raise NotFoundError(
                    f"Membership plan {input_data.membership_plan_id} not found"
                )
            if not plan.is_active:
                raise ValidationError("This membership plan is no longer offered")
            if plan.business_id != input_data.business_id:
                raise ValidationError("Membership plan does not belong to this business")

            client = await self._resolve_client(input_data, tenant.tenant_id)

            existing = await self._memberships.get_current_for_client(
                client.id, input_data.business_id
            )
            if existing is not None:
                raise ConflictError(
                    "This client already has a live membership. Renew it instead."
                )

            membership = Membership.grant(
                tenant_id=tenant.tenant_id,
                business_id=input_data.business_id,
                client_id=client.id,
                plan=plan,
                starts_at=input_data.starts_at,
                notes=input_data.notes,
            )
            await self._memberships.add(membership)
            await self._uow.commit()

        return GrantMembershipOutput(
            membership_id=membership.id,
            client_id=membership.client_id,
            membership_plan_id=plan.id,
            plan_name=plan.name,
            status=membership.status,
            starts_at=membership.starts_at,
            ends_at=membership.ends_at,
            billing_period=membership.billing_period,
            price_paid=membership.price_paid,
        )

    async def _resolve_client(self, input_data: GrantMembershipInput, tenant_id: UUID) -> Client:
        if input_data.client_id is not None:
            client = await self._clients.get_by_id(input_data.client_id)
            if not client:
                raise NotFoundError(f"Client {input_data.client_id} not found")
            return client

        whatsapp = (input_data.client_whatsapp or "").strip()
        client = await self._clients.get_by_whatsapp(whatsapp)
        if client is None:
            client = Client.create(
                tenant_id=tenant_id,
                whatsapp_number=whatsapp,
                name=(input_data.client_name or "").strip(),
            )
            await self._clients.add(client)
        return client

    def _validate_input(self, data: GrantMembershipInput) -> None:
        if data.client_id is None and not (data.client_whatsapp or "").strip():
            raise ValidationError("Either client_id or client_whatsapp is required")
        if data.starts_at is not None and data.starts_at.tzinfo is None:
            raise ValidationError("starts_at must be timezone-aware (UTC)")
        if data.starts_at is not None and data.starts_at > datetime.now(timezone.utc).replace(
            year=datetime.now(timezone.utc).year + 5
        ):
            raise ValidationError("starts_at is unrealistically far in the future")
