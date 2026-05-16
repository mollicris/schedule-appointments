from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.shared.errors import AuthenticationError
from src.infrastructure.adapters.jwt_service import JWTService
from src.infrastructure.cache.redis_client import get_redis

_REFRESH_TOKEN_TTL = 7 * 24 * 3600  # 7 days


@dataclass(frozen=True)
class RefreshTokenInput:
    refresh_token: str


@dataclass(frozen=True)
class RefreshTokenOutput:
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime
    tenant_id: UUID
    user_id: UUID


class RefreshTokenUseCase(UseCase[RefreshTokenInput, RefreshTokenOutput]):
    def __init__(self, jwt_service: JWTService) -> None:
        self._jwt = jwt_service

    async def execute(self, input_data: RefreshTokenInput) -> RefreshTokenOutput:
        redis = await get_redis()
        redis_key = f"refresh:{input_data.refresh_token}"
        stored = await redis.get(redis_key)

        if not stored:
            raise AuthenticationError("Invalid or expired refresh token")

        parts = stored.decode().split(":")
        if len(parts) != 3:
            raise AuthenticationError("Malformed refresh token data")

        user_id = UUID(parts[0])
        tenant_id = UUID(parts[1])
        role = parts[2]

        # Rotate: delete old token, issue new one
        await redis.delete(redis_key)

        access_token, expires_at = self._jwt.create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
        )
        new_refresh_token = self._jwt.generate_refresh_token()
        await redis.setex(
            f"refresh:{new_refresh_token}",
            _REFRESH_TOKEN_TTL,
            f"{user_id}:{tenant_id}:{role}",
        )

        return RefreshTokenOutput(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_at=expires_at,
            tenant_id=tenant_id,
            user_id=user_id,
        )
