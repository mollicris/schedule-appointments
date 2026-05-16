from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr

from src.application.identity.authenticate_user import (
    AuthenticateUserInput,
    AuthenticateUserUseCase,
)
from src.application.identity.logout import LogoutInput, LogoutUseCase
from src.application.identity.refresh_token import RefreshTokenInput, RefreshTokenUseCase
from src.domain.identity.repository import UserRepository
from src.infrastructure.adapters.jwt_service import JWTService
from src.infrastructure.adapters.password_hasher import Argon2PasswordHasher
from src.presentation.dependencies import (
    get_jwt_service,
    get_password_hasher,
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
