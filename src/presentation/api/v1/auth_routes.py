from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, EmailStr

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    tenant_id: UUID
    user_id: UUID


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(payload: LoginRequest) -> TokenResponse:
    raise NotImplementedError("Wire AuthenticateUserUseCase here")


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh() -> TokenResponse:
    raise NotImplementedError


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    raise NotImplementedError
