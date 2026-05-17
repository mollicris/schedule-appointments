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
from src.domain.appointment.repository import AppointmentRepository
from src.domain.business.repository import BusinessRepository
from src.domain.conversation.human_transfer_repository import HumanTransferRepository
from src.domain.conversation.repository import ConversationRepository
from src.domain.business_hours.repository import BusinessHourRepository
from src.domain.client.repository import ClientRepository
from src.domain.identity.repository import UserRepository
from src.domain.professional.repository import ProfessionalRepository
from src.domain.service.repository import ServiceRepository
from src.domain.tenant.repository import TenantRepository
from src.infrastructure.adapters.jwt_service import JWTService
from src.infrastructure.adapters.password_hasher import Argon2PasswordHasher
from src.infrastructure.adapters.user_factory import UserFactoryImpl
from src.infrastructure.adapters.verification_token_service import InMemoryVerificationTokenService
from src.infrastructure.config.settings import get_settings
from src.infrastructure.persistence.database import get_session_factory
from src.infrastructure.persistence.repositories.appointment_repository import AppointmentRepositoryImpl
from src.infrastructure.persistence.repositories.business_hour_repository import BusinessHourRepositoryImpl
from src.infrastructure.persistence.repositories.business_repository import BusinessRepositoryImpl
from src.infrastructure.persistence.repositories.client_repository import ClientRepositoryImpl
from src.infrastructure.persistence.repositories.conversation_repository import ConversationRepositoryImpl
from src.infrastructure.persistence.repositories.human_transfer_repository import HumanTransferRepositoryImpl
from src.infrastructure.persistence.repositories.professional_repository import ProfessionalRepositoryImpl
from src.infrastructure.persistence.repositories.service_repository import ServiceRepositoryImpl
from src.infrastructure.persistence.repositories.tenant_repository import TenantRepositoryImpl
from src.infrastructure.persistence.repositories.user_repository import UserRepositoryImpl

_verification_token_service: InMemoryVerificationTokenService | None = None
_jwt_service: JWTService | None = None


def _get_verification_token_service() -> InMemoryVerificationTokenService:
    global _verification_token_service
    if _verification_token_service is None:
        _verification_token_service = InMemoryVerificationTokenService()
    return _verification_token_service


def _get_jwt_service() -> JWTService:
    global _jwt_service
    if _jwt_service is None:
        s = get_settings()
        _jwt_service = JWTService(
            secret_key=s.jwt_secret_key,
            algorithm=s.jwt_algorithm,
            access_token_expire_minutes=s.jwt_access_token_expire_minutes,
        )
    return _jwt_service


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Inject a database session into request handlers."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_password_hasher() -> Argon2PasswordHasher:
    """DI: PasswordHasher."""
    return Argon2PasswordHasher()


def get_verification_token_service() -> VerificationTokenService:
    """DI: VerificationTokenService."""
    return _get_verification_token_service()


def get_jwt_service() -> JWTService:
    """DI: JWTService."""
    return _get_jwt_service()


def get_tenant_repository(session: DbSession) -> TenantRepository:
    """DI: TenantRepository."""
    return TenantRepositoryImpl(session)


def get_user_repository(session: DbSession) -> UserRepository:
    """DI: UserRepository."""
    return UserRepositoryImpl(session)


def get_user_factory(session: DbSession) -> UserFactory:
    """DI: UserFactory."""
    return UserFactoryImpl(session)


def get_business_repository(session: DbSession) -> BusinessRepository:
    """DI: BusinessRepository."""
    return BusinessRepositoryImpl(session)


def get_service_repository(session: DbSession) -> ServiceRepository:
    """DI: ServiceRepository."""
    return ServiceRepositoryImpl(session)


def get_professional_repository(session: DbSession) -> ProfessionalRepository:
    """DI: ProfessionalRepository."""
    return ProfessionalRepositoryImpl(session)


def get_business_hours_repository(session: DbSession) -> BusinessHourRepository:
    """DI: BusinessHourRepository."""
    return BusinessHourRepositoryImpl(session)


def get_appointment_repository(session: DbSession) -> AppointmentRepository:
    """DI: AppointmentRepository."""
    return AppointmentRepositoryImpl(session)


def get_client_repository(session: DbSession) -> ClientRepository:
    """DI: ClientRepository."""
    return ClientRepositoryImpl(session)


def get_conversation_repository(session: DbSession) -> ConversationRepository:
    """DI: ConversationRepository."""
    return ConversationRepositoryImpl(session)


def get_human_transfer_repository(session: DbSession) -> HumanTransferRepository:
    """DI: HumanTransferRepository."""
    return HumanTransferRepositoryImpl(session)


def get_unit_of_work(session: DbSession) -> UnitOfWork:
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
