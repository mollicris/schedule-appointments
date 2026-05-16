from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.repository import UserRepository
from src.domain.identity.user import User
from src.domain.identity.value_objects import UserRole, UserStatus
from src.infrastructure.persistence.models.identity import UserModel


class UserRepositoryImpl(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(
                UserModel.email == email,
                UserModel.is_active == True,  # noqa: E712
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _to_domain(model)

    async def update_last_login(self, user_id: UUID) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        tenant_id=model.tenant_id,
        email=model.email,
        password_hash=model.password_hash,
        role=UserRole(model.role),
        status=UserStatus.ACTIVE if model.is_active else UserStatus.INACTIVE,
        is_active=model.is_active,
    )
