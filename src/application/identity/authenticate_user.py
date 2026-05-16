from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.shared.use_case import UseCase
from src.domain.identity.repository import UserRepository
from src.domain.shared.errors import AuthenticationError
from src.infrastructure.adapters.jwt_service import JWTService
from src.infrastructure.adapters.password_hasher import Argon2PasswordHasher
from src.infrastructure.cache.redis_client import get_redis

_REFRESH_TOKEN_TTL = 7 * 24 * 3600  # 7 days


@dataclass(frozen=True)
class AuthenticateUserInput:
    email: str
    password: str


@dataclass(frozen=True)
class AuthenticateUserOutput:
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime
    tenant_id: UUID
    user_id: UUID


class AuthenticateUserUseCase(UseCase[AuthenticateUserInput, AuthenticateUserOutput]):
    def __init__(
        self,
        users: UserRepository,
        password_hasher: Argon2PasswordHasher,
        jwt_service: JWTService,
    ) -> None:
        self._users = users
        self._hasher = password_hasher
        self._jwt = jwt_service

    async def execute(self, input_data: AuthenticateUserInput) -> AuthenticateUserOutput:
        user = await self._users.get_by_email(input_data.email)
        if not user or not user.is_active:
            raise AuthenticationError("Invalid email or password")

        if not self._hasher.verify(input_data.password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        await self._users.update_last_login(user.id)

        access_token, expires_at = self._jwt.create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role.value,
        )

        refresh_token = self._jwt.generate_refresh_token()
        redis = await get_redis()
        await redis.setex(
            f"refresh:{refresh_token}",
            _REFRESH_TOKEN_TTL,
            f"{user.id}:{user.tenant_id}:{user.role.value}",
        )

        return AuthenticateUserOutput(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_at=expires_at,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
