from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.onboarding.register_tenant import (
    PasswordHasher,
    UserFactory,
    VerificationTokenService,
)
from src.application.shared.unit_of_work import UnitOfWork
from src.domain.business.repository import BusinessRepository
from src.domain.service.repository import ServiceRepository
from src.domain.tenant.repository import TenantRepository
from src.infrastructure.adapters.password_hasher import Argon2PasswordHasher
from src.infrastructure.adapters.user_factory import UserFactoryImpl
from src.infrastructure.adapters.verification_token_service import InMemoryVerificationTokenService
from src.infrastructure.persistence.database import get_session_factory
from src.infrastructure.persistence.repositories.business_repository import BusinessRepositoryImpl
from src.infrastructure.persistence.repositories.service_repository import ServiceRepositoryImpl
from src.infrastructure.persistence.repositories.tenant_repository import TenantRepositoryImpl

_verification_token_service: InMemoryVerificationTokenService | None = None


def _get_verification_token_service() -> InMemoryVerificationTokenService:
    global _verification_token_service
    if _verification_token_service is None:
        _verification_token_service = InMemoryVerificationTokenService()
    return _verification_token_service


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Inject a database session into request handlers."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_password_hasher() -> PasswordHasher:
    """DI: PasswordHasher."""
    return Argon2PasswordHasher()


async def get_verification_token_service() -> VerificationTokenService:
    """DI: VerificationTokenService."""
    return _get_verification_token_service()


async def get_tenant_repository(session: DbSession) -> TenantRepository:
    """DI: TenantRepository."""
    return TenantRepositoryImpl(session)


async def get_user_factory(session: DbSession) -> UserFactory:
    """DI: UserFactory."""
    return UserFactoryImpl(session)


def get_business_repository(session: DbSession) -> BusinessRepository:
    """DI: BusinessRepository."""
    return BusinessRepositoryImpl(session)


def get_service_repository(session: DbSession) -> ServiceRepository:
    """DI: ServiceRepository."""
    return ServiceRepositoryImpl(session)


async def get_unit_of_work(session: DbSession) -> UnitOfWork:
    """DI: UnitOfWork."""
    class SimpleUnitOfWork(UnitOfWork):
        async def __aenter__(self) -> UnitOfWork:
            return self

        async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
            if exc_type is None:
                await session.commit()
            else:
                await session.rollback()

        async def commit(self) -> None:
            await session.commit()

        async def rollback(self) -> None:
            await session.rollback()

    return SimpleUnitOfWork()
