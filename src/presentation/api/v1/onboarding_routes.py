from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field

from src.application.onboarding.register_tenant import (
    PasswordHasher,
    RegisterTenantInput,
    RegisterTenantUseCase,
    UserFactory,
    VerificationTokenService,
)
from src.application.onboarding.verify_email import (
    VerifyEmailInput,
    VerifyEmailUseCase,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.tenant.repository import TenantRepository
from src.presentation.schemas import SuccessResponse, success_response
from src.presentation.dependencies import (
    DbSession,
    get_password_hasher,
    get_tenant_repository,
    get_unit_of_work,
    get_user_factory,
    get_verification_token_service,
)

router = APIRouter()


class RegisterTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)
    industry: str = Field(min_length=2, max_length=40)
    desired_slug: str | None = Field(default=None, max_length=48)


class RegisterTenantResponseData(BaseModel):
    tenant_id: UUID
    slug: str
    verification_sent_to: str


class RegisterTenantResponse(BaseModel):
    success: bool = True
    message: str
    code: str
    data: RegisterTenantResponseData


class VerifyEmailResponseData(BaseModel):
    tenant_id: UUID
    slug: str
    admin_email: str


class VerifyEmailResponse(BaseModel):
    success: bool = True
    message: str
    code: str
    data: VerifyEmailResponseData


@router.post(
    "/register",
    response_model=RegisterTenantResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Tenant registered successfully"},
        409: {"description": "Email already exists"},
        422: {"description": "Validation error"},
    },
    summary="Public self-service tenant signup",
    description=(
        "Creates a new tenant account in pending-verification status. "
        "A verification email is sent to the admin email. "
        "After verification, the tenant proceeds through the auto-onboarding wizard."
    ),
)
async def register_tenant(
    payload: RegisterTenantRequest,
    session: DbSession,
    tenants: Annotated[TenantRepository, Depends(get_tenant_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    verification_tokens: Annotated[VerificationTokenService, Depends(get_verification_token_service)],
    user_factory: Annotated[UserFactory, Depends(get_user_factory)],
) -> RegisterTenantResponse:
    use_case = RegisterTenantUseCase(
        tenants=tenants,
        uow=uow,
        password_hasher=password_hasher,
        verification_token_service=verification_tokens,
        user_factory=user_factory,
        session=session,
    )
    output = await use_case.execute(
        RegisterTenantInput(
            name=payload.name,
            admin_email=payload.admin_email,
            admin_password=payload.admin_password,
            industry=payload.industry,
            desired_slug=payload.desired_slug,
        )
    )
    return RegisterTenantResponse(
        success=True,
        message="Tenant registered successfully. A verification email has been sent.",
        code="TENANT_REGISTERED",
        data=RegisterTenantResponseData(
            tenant_id=output.tenant_id,
            slug=output.slug,
            verification_sent_to=payload.admin_email,
        ),
    )


@router.post(
    "/verify/{token}",
    response_model=VerifyEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm email verification token",
    description=(
        "Verifies the tenant's admin email using the token sent to their inbox. "
        "Transitions the tenant from PENDING_VERIFICATION to ONBOARDING status. "
        "The tenant can then proceed with the onboarding wizard."
    ),
    responses={
        200: {"description": "Email verified successfully"},
        422: {"description": "Invalid or expired token"},
    },
)
async def verify_email(
    token: str,
    tenants: Annotated[TenantRepository, Depends(get_tenant_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    verification_tokens: Annotated[VerificationTokenService, Depends(get_verification_token_service)],
) -> VerifyEmailResponse:
    use_case = VerifyEmailUseCase(
        tenants=tenants,
        uow=uow,
        verification_token_service=verification_tokens,
    )
    output = await use_case.execute(VerifyEmailInput(token=token))

    return VerifyEmailResponse(
        success=True,
        message="Email verified successfully. You can now proceed with onboarding.",
        code="EMAIL_VERIFIED",
        data=VerifyEmailResponseData(
            tenant_id=output.tenant_id,
            slug=output.slug,
            admin_email=output.admin_email,
        ),
    )


@router.get(
    "/wizard/state",
    summary="Get current onboarding wizard step for the authenticated tenant",
)
async def get_wizard_state() -> dict[str, object]:
    raise NotImplementedError


@router.post(
    "/wizard/complete",
    status_code=status.HTTP_200_OK,
    summary="Mark onboarding wizard as complete and activate the bot",
)
async def complete_onboarding() -> dict[str, str]:
    raise NotImplementedError
