from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.application.onboarding.register_tenant import VerificationTokenService as VerificationTokenServicePort


class InMemoryVerificationTokenService:
    """In-memory implementation of VerificationTokenService for development.

    Tokens are stored in memory with a 24-hour expiry.
    Suitable for development/testing. Use RedisVerificationTokenService for production.
    """

    TOKEN_EXPIRY_SECONDS = 86400  # 24 hours

    def __init__(self) -> None:
        self._tokens: dict[str, tuple[UUID, datetime]] = {}

    async def issue_for(self, tenant_id: UUID) -> str:
        """Generate a secure token and store it in memory."""
        token = secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc) + timedelta(seconds=self.TOKEN_EXPIRY_SECONDS)
        self._tokens[token] = (tenant_id, expiry)
        return token

    async def consume(self, token: str) -> UUID | None:
        """Retrieve and delete a token. Returns tenant_id or None if expired/invalid."""
        if token not in self._tokens:
            return None

        tenant_id, expiry = self._tokens.pop(token)

        if datetime.now(timezone.utc) > expiry:
            return None

        return tenant_id
