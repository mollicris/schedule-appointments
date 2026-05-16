from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.models import UserModel


class UserFactoryImpl:
    """Adapter: implements UserFactory port.

    Creates the initial admin user during tenant registration.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_admin_user(
        self, *, tenant_id: UUID, email: str, password_hash: str
    ) -> UUID:
        """Create the initial admin user for a tenant."""
        user_id = uuid4()
        user = UserModel(
            id=user_id,
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            role="admin",
            email_verified=False,
            is_active=True,
        )
        self._session.add(user)
        await self._session.flush()
        return user_id
