from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from src.application.membership.create_membership_plan import (
    CreateMembershipPlanInput,
    CreateMembershipPlanOutput,
    CreateMembershipPlanUseCase,
)
from src.application.membership.get_client_membership import (
    GetClientMembershipInput,
    GetClientMembershipOutput,
    GetClientMembershipUseCase,
)
from src.application.membership.grant_membership import (
    GrantMembershipInput,
    GrantMembershipOutput,
    GrantMembershipUseCase,
)
from src.application.membership.list_membership_plans import (
    ListMembershipPlansInput,
    ListMembershipPlansOutput,
    ListMembershipPlansUseCase,
)
from src.application.membership.list_memberships import (
    ListMembershipsInput,
    ListMembershipsOutput,
    ListMembershipsUseCase,
)
from src.application.membership.manage_membership import (
    CancelMembershipUseCase,
    FreezeMembershipUseCase,
    MembershipActionInput,
    MembershipActionOutput,
    RenewMembershipUseCase,
    UnfreezeMembershipUseCase,
)
from src.application.membership.update_membership_plan import (
    UpdateMembershipPlanInput,
    UpdateMembershipPlanOutput,
    UpdateMembershipPlanUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.client.repository import ClientRepository
from src.domain.membership.repository import MembershipPlanRepository, MembershipRepository
from src.domain.membership.value_objects import BillingPeriod, MembershipStatus
from src.presentation.dependencies import (
    get_client_repository,
    get_membership_plan_repository,
    get_membership_repository,
    get_unit_of_work,
)
from src.presentation.schemas import (
    PaginatedResponse,
    SuccessResponse,
    paginated_response,
    success_response,
)

# Two resources in one module: plans are configuration of a business, while
# memberships belong to clients and are managed by the reception desk.
plans_router = APIRouter(
    prefix="/businesses/{business_id}/membership-plans", tags=["membership-plans"]
)
memberships_router = APIRouter(prefix="/memberships", tags=["memberships"])


# ── Schemas: plans ────────────────────────────────────────────────────────────


class CreateMembershipPlanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=127)
    price: int = Field(ge=0, description="Price in cents")
    billing_period: BillingPeriod = BillingPeriod.MONTHLY
    description: str | None = None
    service_ids: list[UUID] = Field(
        default_factory=list,
        description="Services included in the plan. Empty = every service.",
    )


class UpdateMembershipPlanRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=127)
    price: int | None = Field(default=None, ge=0, description="Price in cents")
    billing_period: BillingPeriod | None = None
    description: str | None = None
    service_ids: list[UUID] | None = None
    is_active: bool | None = None


class MembershipPlanResponse(BaseModel):
    membership_plan_id: UUID
    name: str
    description: str | None = None
    price: int
    billing_period: BillingPeriod
    is_active: bool = True
    service_ids: list[UUID] = []


# ── Schemas: memberships ──────────────────────────────────────────────────────


class GrantMembershipRequest(BaseModel):
    business_id: UUID
    membership_plan_id: UUID
    client_id: UUID | None = None
    client_whatsapp: str | None = Field(default=None, max_length=20)
    client_name: str | None = Field(default=None, max_length=127)
    starts_at: datetime | None = None
    notes: str | None = None


class RenewMembershipRequest(BaseModel):
    period: BillingPeriod | None = Field(
        default=None, description="Defaults to the period the membership was sold with"
    )


class CancelMembershipRequest(BaseModel):
    reason: str | None = None


class MembershipResponse(BaseModel):
    membership_id: UUID
    client_id: UUID
    status: MembershipStatus
    starts_at: datetime
    ends_at: datetime
    days_remaining: int
    renewal_count: int = 0
    frozen_days_used: int = 0


class GrantMembershipResponse(BaseModel):
    membership_id: UUID
    client_id: UUID
    membership_plan_id: UUID
    plan_name: str
    status: MembershipStatus
    starts_at: datetime
    ends_at: datetime
    billing_period: BillingPeriod
    price_paid: int


class MembershipSummaryResponse(BaseModel):
    membership_id: UUID
    client_id: UUID
    membership_plan_id: UUID
    status: MembershipStatus
    starts_at: datetime
    ends_at: datetime
    days_remaining: int
    billing_period: BillingPeriod
    price_paid: int


class ClientMembershipResponse(BaseModel):
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
    included_service_ids: list[UUID] = []
    warning: str | None = None


# ── Plans ─────────────────────────────────────────────────────────────────────


@plans_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a membership plan",
    description="Create a membership plan (what the business sells to its members).",
)
async def create_membership_plan(
    business_id: UUID,
    payload: CreateMembershipPlanRequest,
    plans: Annotated[MembershipPlanRepository, Depends(get_membership_plan_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = CreateMembershipPlanUseCase(plans=plans, uow=uow)
    output: CreateMembershipPlanOutput = await use_case.execute(
        CreateMembershipPlanInput(
            business_id=business_id,
            name=payload.name,
            price=payload.price,
            billing_period=payload.billing_period,
            description=payload.description,
            service_ids=payload.service_ids,
        )
    )
    return success_response(
        message="Membership plan created successfully",
        code="MEMBERSHIP_PLAN_CREATED",
        data=MembershipPlanResponse(
            membership_plan_id=output.membership_plan_id,
            name=output.name,
            description=payload.description,
            price=output.price,
            billing_period=output.billing_period,
            service_ids=output.service_ids,
        ),
    )


@plans_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List membership plans",
    description="Paginated list of the membership plans offered by the business.",
)
async def list_membership_plans(
    business_id: UUID,
    include_inactive: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    plans: Annotated[MembershipPlanRepository, Depends(get_membership_plan_repository)] = ...,
) -> PaginatedResponse:
    use_case = ListMembershipPlansUseCase(plans=plans)
    output: ListMembershipPlansOutput = await use_case.execute(
        ListMembershipPlansInput(
            business_id=business_id,
            include_inactive=include_inactive,
            page=page,
            page_size=page_size,
        )
    )
    return paginated_response(
        data=[
            MembershipPlanResponse(
                membership_plan_id=p.membership_plan_id,
                name=p.name,
                description=p.description,
                price=p.price,
                billing_period=p.billing_period,
                is_active=p.is_active,
                service_ids=p.service_ids,
            )
            for p in output.plans
        ],
        total=output.total,
        page=output.page,
        page_size=output.page_size,
    )


@plans_router.put(
    "/{membership_plan_id}",
    status_code=status.HTTP_200_OK,
    summary="Update a membership plan",
    description=(
        "Update a membership plan. Memberships already granted keep their own "
        "snapshot of period and price, so they are not affected."
    ),
)
async def update_membership_plan(
    business_id: UUID,
    membership_plan_id: UUID,
    payload: UpdateMembershipPlanRequest,
    plans: Annotated[MembershipPlanRepository, Depends(get_membership_plan_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = UpdateMembershipPlanUseCase(plans=plans, uow=uow)
    output: UpdateMembershipPlanOutput = await use_case.execute(
        UpdateMembershipPlanInput(
            membership_plan_id=membership_plan_id,
            name=payload.name,
            description=payload.description,
            price=payload.price,
            billing_period=payload.billing_period,
            service_ids=payload.service_ids,
            is_active=payload.is_active,
        )
    )
    return success_response(
        message="Membership plan updated successfully",
        code="MEMBERSHIP_PLAN_UPDATED",
        data=MembershipPlanResponse(
            membership_plan_id=output.membership_plan_id,
            name=output.name,
            description=payload.description,
            price=output.price,
            billing_period=output.billing_period,
            is_active=output.is_active,
            service_ids=output.service_ids,
        ),
    )


@plans_router.delete(
    "/{membership_plan_id}",
    status_code=status.HTTP_200_OK,
    summary="Stop offering a membership plan",
    description="Soft delete: existing memberships stay valid.",
)
async def delete_membership_plan(
    business_id: UUID,
    membership_plan_id: UUID,
    plans: Annotated[MembershipPlanRepository, Depends(get_membership_plan_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = UpdateMembershipPlanUseCase(plans=plans, uow=uow)
    output: UpdateMembershipPlanOutput = await use_case.execute(
        UpdateMembershipPlanInput(membership_plan_id=membership_plan_id, is_active=False)
    )
    return success_response(
        message="Membership plan is no longer offered",
        code="MEMBERSHIP_PLAN_DELETED",
        data=MembershipPlanResponse(
            membership_plan_id=output.membership_plan_id,
            name=output.name,
            price=output.price,
            billing_period=output.billing_period,
            is_active=output.is_active,
            service_ids=output.service_ids,
        ),
    )


# ── Memberships ───────────────────────────────────────────────────────────────


@memberships_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Grant a membership to a client",
    description=(
        "Grant a membership based on a plan. The client can be identified by id "
        "or by WhatsApp number (created on the fly for the reception desk)."
    ),
    responses={409: {"description": "The client already has a live membership"}},
)
async def grant_membership(
    payload: GrantMembershipRequest,
    memberships: Annotated[MembershipRepository, Depends(get_membership_repository)],
    plans: Annotated[MembershipPlanRepository, Depends(get_membership_plan_repository)],
    clients: Annotated[ClientRepository, Depends(get_client_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = GrantMembershipUseCase(
        memberships=memberships, plans=plans, clients=clients, uow=uow
    )
    output: GrantMembershipOutput = await use_case.execute(
        GrantMembershipInput(
            business_id=payload.business_id,
            membership_plan_id=payload.membership_plan_id,
            client_id=payload.client_id,
            client_whatsapp=payload.client_whatsapp,
            client_name=payload.client_name,
            starts_at=payload.starts_at,
            notes=payload.notes,
        )
    )
    return success_response(
        message="Membership granted successfully",
        code="MEMBERSHIP_GRANTED",
        data=GrantMembershipResponse(
            membership_id=output.membership_id,
            client_id=output.client_id,
            membership_plan_id=output.membership_plan_id,
            plan_name=output.plan_name,
            status=output.status,
            starts_at=output.starts_at,
            ends_at=output.ends_at,
            billing_period=output.billing_period,
            price_paid=output.price_paid,
        ),
    )


@memberships_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List memberships of a business",
    description=(
        "Filter by status or by upcoming expiry (`expiring_in_days=7` returns the "
        "members whose plan lapses within a week)."
    ),
)
async def list_memberships(
    business_id: UUID = Query(...),
    membership_status: MembershipStatus | None = Query(None, alias="status"),
    expiring_in_days: int | None = Query(None, ge=0, le=365),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    memberships: Annotated[MembershipRepository, Depends(get_membership_repository)] = ...,
) -> PaginatedResponse:
    use_case = ListMembershipsUseCase(memberships=memberships)
    output: ListMembershipsOutput = await use_case.execute(
        ListMembershipsInput(
            business_id=business_id,
            status=membership_status,
            expiring_in_days=expiring_in_days,
            page=page,
            page_size=page_size,
        )
    )
    return paginated_response(
        data=[
            MembershipSummaryResponse(
                membership_id=m.membership_id,
                client_id=m.client_id,
                membership_plan_id=m.membership_plan_id,
                status=m.status,
                starts_at=m.starts_at,
                ends_at=m.ends_at,
                days_remaining=m.days_remaining,
                billing_period=m.billing_period,
                price_paid=m.price_paid,
            )
            for m in output.memberships
        ],
        total=output.total,
        page=output.page,
        page_size=output.page_size,
    )


@memberships_router.get(
    "/current",
    status_code=status.HTTP_200_OK,
    summary="Membership status of one client",
    description="Same data the WhatsApp agent reads, including a ready-to-send warning.",
)
async def get_current_membership(
    business_id: UUID = Query(...),
    client_id: UUID = Query(...),
    memberships: Annotated[MembershipRepository, Depends(get_membership_repository)] = ...,
    plans: Annotated[MembershipPlanRepository, Depends(get_membership_plan_repository)] = ...,
) -> SuccessResponse:
    use_case = GetClientMembershipUseCase(memberships=memberships, plans=plans)
    output: GetClientMembershipOutput = await use_case.execute(
        GetClientMembershipInput(client_id=client_id, business_id=business_id)
    )
    return success_response(
        message="Membership status retrieved successfully",
        code="MEMBERSHIP_FOUND" if output.has_membership else "MEMBERSHIP_NOT_FOUND",
        data=ClientMembershipResponse(
            has_membership=output.has_membership,
            membership_id=output.membership_id,
            plan_name=output.plan_name,
            status=output.status,
            billing_period=output.billing_period,
            price_paid=output.price_paid,
            starts_at=output.starts_at,
            ends_at=output.ends_at,
            days_remaining=output.days_remaining,
            is_current=output.is_current,
            included_service_ids=output.included_service_ids,
            warning=output.warning,
        ),
    )


@memberships_router.post(
    "/{membership_id}/renew",
    status_code=status.HTTP_200_OK,
    summary="Renew a membership",
    description="Extends by one period. Renewing early keeps the days already paid.",
)
async def renew_membership(
    membership_id: UUID,
    payload: RenewMembershipRequest,
    memberships: Annotated[MembershipRepository, Depends(get_membership_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = RenewMembershipUseCase(memberships=memberships, uow=uow)
    output: MembershipActionOutput = await use_case.execute(
        MembershipActionInput(membership_id=membership_id, period=payload.period)
    )
    return success_response(
        message="Membership renewed successfully",
        code="MEMBERSHIP_RENEWED",
        data=_to_membership_response(output),
    )


@memberships_router.post(
    "/{membership_id}/freeze",
    status_code=status.HTTP_200_OK,
    summary="Freeze a membership",
    description="Pauses the membership; unfreezing pushes the end date by the frozen days.",
)
async def freeze_membership(
    membership_id: UUID,
    memberships: Annotated[MembershipRepository, Depends(get_membership_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = FreezeMembershipUseCase(memberships=memberships, uow=uow)
    output: MembershipActionOutput = await use_case.execute(
        MembershipActionInput(membership_id=membership_id)
    )
    return success_response(
        message="Membership frozen",
        code="MEMBERSHIP_FROZEN",
        data=_to_membership_response(output),
    )


@memberships_router.post(
    "/{membership_id}/unfreeze",
    status_code=status.HTTP_200_OK,
    summary="Unfreeze a membership",
    description="Resumes a frozen membership and extends its end date.",
)
async def unfreeze_membership(
    membership_id: UUID,
    memberships: Annotated[MembershipRepository, Depends(get_membership_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = UnfreezeMembershipUseCase(memberships=memberships, uow=uow)
    output: MembershipActionOutput = await use_case.execute(
        MembershipActionInput(membership_id=membership_id)
    )
    return success_response(
        message="Membership resumed",
        code="MEMBERSHIP_UNFROZEN",
        data=_to_membership_response(output),
    )


@memberships_router.patch(
    "/{membership_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel a membership",
    description="Terminal state; the client keeps their appointment history.",
)
async def cancel_membership(
    membership_id: UUID,
    payload: CancelMembershipRequest,
    memberships: Annotated[MembershipRepository, Depends(get_membership_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> SuccessResponse:
    use_case = CancelMembershipUseCase(memberships=memberships, uow=uow)
    output: MembershipActionOutput = await use_case.execute(
        MembershipActionInput(membership_id=membership_id, reason=payload.reason)
    )
    return success_response(
        message="Membership cancelled",
        code="MEMBERSHIP_CANCELLED",
        data=_to_membership_response(output),
    )


def _to_membership_response(output: MembershipActionOutput) -> MembershipResponse:
    return MembershipResponse(
        membership_id=output.membership_id,
        client_id=output.client_id,
        status=output.status,
        starts_at=output.starts_at,
        ends_at=output.ends_at,
        days_remaining=output.days_remaining,
        renewal_count=output.renewal_count,
        frozen_days_used=output.frozen_days_used,
    )
