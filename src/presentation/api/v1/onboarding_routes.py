from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, EmailStr, Field

router = APIRouter()


class RegisterTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)
    industry: str = Field(min_length=2, max_length=40)
    desired_slug: str | None = Field(default=None, max_length=48)


class RegisterTenantResponse(BaseModel):
    tenant_id: UUID
    slug: str
    verification_sent_to: str


@router.post(
    "/register",
    response_model=RegisterTenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Public self-service tenant signup",
    description=(
        "Creates a new tenant account in pending-verification status. "
        "A verification email is sent to the admin email. "
        "After verification, the tenant proceeds through the auto-onboarding wizard."
    ),
)
async def register_tenant(payload: RegisterTenantRequest) -> RegisterTenantResponse:
    # TODO: wire RegisterTenantUseCase via FastAPI Depends
    raise NotImplementedError("Wire RegisterTenantUseCase here")


@router.post(
    "/verify/{token}",
    status_code=status.HTTP_200_OK,
    summary="Confirm email verification token",
)
async def verify_email(token: str) -> dict[str, str]:
    raise NotImplementedError


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
