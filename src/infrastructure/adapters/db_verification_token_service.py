from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.models.identity import UserModel

TOKEN_TTL_HOURS = 24


class DatabaseVerificationTokenService:
    """Persists verification tokens in the users table.

    Unlike the in-memory implementation, tokens survive server restarts,
    hot-reloads, and multi-worker deployments.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def issue_for(self, tenant_id: UUID) -> str:
        token = secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)

        # Flush any pending ORM inserts (e.g. the new user) before running
        # a Core UPDATE so they are visible within the same transaction.
        await self._session.flush()

        await self._session.execute(
            update(UserModel)
            .where(
                UserModel.tenant_id == tenant_id,
                UserModel.role == "admin",
                UserModel.is_active == True,  # noqa: E712
            )
            .values(
                verification_token=token,
                verification_token_expires_at=expiry,
            )
        )
        return token

    async def consume(self, token: str) -> UUID | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.verification_token == token)
        )
        user = result.scalar_one_or_none()

        if user is None:
            return None

        if user.verification_token_expires_at is None:
            return None

        expiry = user.verification_token_expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expiry:
            return None

        # Clear token so it can only be used once
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user.id)
            .values(
                verification_token=None,
                verification_token_expires_at=None,
                email_verified=True,
            )
        )
        await self._session.flush()

        return user.tenant_id
