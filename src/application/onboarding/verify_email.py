from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.shared.errors import ValidationError
from src.domain.tenant.repository import TenantRepository


@dataclass(frozen=True)
class VerifyEmailInput:
    token: str


@dataclass(frozen=True)
class VerifyEmailOutput:
    tenant_id: UUID
    slug: str
    admin_email: str


class VerifyEmailUseCase(UseCase[VerifyEmailInput, VerifyEmailOutput]):
    """Verify tenant's admin email and transition to onboarding.

    After registration, the admin receives a verification email with a token.
    This use case validates the token and moves the tenant from
    PENDING_VERIFICATION → ONBOARDING status, unlocking the onboarding wizard.

    Errors:
        ValidationError: If token is invalid or expired
    """

    def __init__(
        self,
        tenants: TenantRepository,
        uow: UnitOfWork,
        verification_token_service,
    ) -> None:
        self._tenants = tenants
        self._uow = uow
        self._tokens = verification_token_service

    async def execute(self, input_data: VerifyEmailInput) -> VerifyEmailOutput:
        # Consume token (retrieves tenant_id if valid, None if expired/invalid)
        tenant_id = await self._tokens.consume(input_data.token)

        if not tenant_id:
            raise ValidationError("Invalid or expired verification token")

        async with self._uow:
            # Fetch tenant
            tenant = await self._tenants.get_by_id(tenant_id)
            if not tenant:
                raise ValidationError("Tenant not found")

            # Transition to ONBOARDING
            tenant.verify()

            # Persist state change
            await self._tenants.update(tenant)

            await self._uow.commit()

        return VerifyEmailOutput(
            tenant_id=tenant.id,
            slug=tenant.slug.value,
            admin_email=tenant.admin_email,
        )
