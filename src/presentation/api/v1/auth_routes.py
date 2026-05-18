from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from src.application.identity.authenticate_user import (
    AuthenticateUserInput,
    AuthenticateUserUseCase,
)
from src.application.identity.logout import LogoutInput, LogoutUseCase
from src.application.identity.refresh_token import RefreshTokenInput, RefreshTokenUseCase
from src.application.shared.tenant_context import get_current_tenant
from src.domain.identity.repository import UserRepository
from src.domain.tenant.repository import TenantRepository
from src.infrastructure.adapters.jwt_service import JWTService
from src.infrastructure.adapters.password_hasher import Argon2PasswordHasher
from src.presentation.dependencies import (
    get_jwt_service,
    get_password_hasher,
    get_tenant_repository,
    get_user_repository,
)

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    email: str
    role: str
    tenant_status: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime
    tenant_id: UUID
    user_id: UUID


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    summary="Obtain JWT access + refresh tokens",
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials"},
    },
)
async def login(
    payload: LoginRequest,
    users: Annotated[UserRepository, Depends(get_user_repository)],
    password_hasher: Annotated[Argon2PasswordHasher, Depends(get_password_hasher)],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> TokenResponse:
    use_case = AuthenticateUserUseCase(
        users=users,
        password_hasher=password_hasher,
        jwt_service=jwt_service,
    )
    output = await use_case.execute(AuthenticateUserInput(
        email=payload.email,
        password=payload.password,
    ))
    return TokenResponse(
        access_token=output.access_token,
        refresh_token=output.refresh_token,
        token_type=output.token_type,
        expires_at=output.expires_at,
        tenant_id=output.tenant_id,
        user_id=output.user_id,
    )


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and get new access token",
    responses={
        200: {"description": "Token refreshed"},
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh(
    payload: RefreshRequest,
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> TokenResponse:
    use_case = RefreshTokenUseCase(jwt_service=jwt_service)
    output = await use_case.execute(RefreshTokenInput(refresh_token=payload.refresh_token))
    return TokenResponse(
        access_token=output.access_token,
        refresh_token=output.refresh_token,
        token_type=output.token_type,
        expires_at=output.expires_at,
        tenant_id=output.tenant_id,
        user_id=output.user_id,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke refresh token",
)
async def logout(payload: LogoutRequest) -> None:
    use_case = LogoutUseCase()
    await use_case.execute(LogoutInput(refresh_token=payload.refresh_token))


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user",
)
async def me(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    tenants: Annotated[TenantRepository, Depends(get_tenant_repository)],
) -> MeResponse:
    ctx = get_current_tenant()
    if ctx.user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = await users.get_by_id(ctx.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    tenant = await tenants.get_by_id(ctx.tenant_id)
    tenant_status = tenant.status.value if tenant else "unknown"
    return MeResponse(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role.value,
        tenant_status=tenant_status,
    )
