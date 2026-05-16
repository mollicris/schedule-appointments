from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt


@dataclass(frozen=True)
class TokenPayload:
    user_id: UUID
    tenant_id: UUID
    role: str


class JWTService:
    def __init__(
        self,
        secret_key: str,
        algorithm: str,
        access_token_expire_minutes: int,
    ) -> None:
        self._secret = secret_key
        self._algorithm = algorithm
        self._access_expire = access_token_expire_minutes

    def create_access_token(
        self,
        user_id: UUID,
        tenant_id: UUID,
        role: str,
    ) -> tuple[str, datetime]:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self._access_expire)
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": role,
            "type": "access",
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, expires_at

    def decode_access_token(self, token: str) -> TokenPayload:
        """Decode and validate a JWT access token. Raises JWTError on failure."""
        payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        if payload.get("type") != "access":
            raise JWTError("Not an access token")
        return TokenPayload(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tenant_id"]),
            role=payload["role"],
        )

    @staticmethod
    def generate_refresh_token() -> str:
        return secrets.token_urlsafe(32)
