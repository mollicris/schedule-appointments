from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.application.shared.unit_of_work import UnitOfWork
from src.application.shared.use_case import UseCase
from src.domain.shared.errors import ConflictError, ValidationError
from src.domain.tenant.repository import TenantRepository
from src.domain.tenant.tenant import Tenant
from src.domain.tenant.value_objects import TenantSlug


@runtime_checkable
class PasswordHasher(Protocol):
    """Port — implemented in infrastructure (argon2/bcrypt)."""

    def hash(self, plaintext: str) -> str: ...
    def verify(self, plaintext: str, hashed: str) -> bool: ...


@runtime_checkable
class VerificationTokenService(Protocol):
    """Port — issues and validates email/phone verification tokens."""

    async def issue_for(self, tenant_id: UUID) -> str: ...
    async def consume(self, token: str) -> UUID | None: ...


@runtime_checkable
class UserFactory(Protocol):
    """Port — creates the initial admin user in the identity context."""

    async def create_admin_user(
        self, *, tenant_id: UUID, email: str, password_hash: str
    ) -> UUID: ...


@dataclass(frozen=True)
class RegisterTenantInput:
    name: str
    admin_email: str
    admin_password: str
    industry: str
    desired_slug: str | None = None  # If None, generated from name


@dataclass(frozen=True)
class RegisterTenantOutput:
    tenant_id: UUID
    slug: str
    verification_token: str


class RegisterTenantUseCase(UseCase[RegisterTenantInput, RegisterTenantOutput]):
    """Public auto-onboarding entry point.

    Creates a new Tenant in PENDING_VERIFICATION status and emits a
    ``TenantRegistered`` event. Downstream subscribers handle:
      - Sending verification email (with the verification_token)
      - Provisioning default services for the industry (template)
      - Starting the trial timer

    Idempotency: rejects duplicate admin emails. Slug collisions auto-resolve
    by appending a numeric suffix.
    """

    def __init__(
        self,
        tenants: TenantRepository,
        uow: UnitOfWork,
        password_hasher: PasswordHasher,
        verification_token_service: VerificationTokenService,
        user_factory: UserFactory,
    ) -> None:
        self._tenants = tenants
        self._uow = uow
        self._hasher = password_hasher
        self._tokens = verification_token_service
        self._user_factory = user_factory

    async def execute(self, input_data: RegisterTenantInput) -> RegisterTenantOutput:
        self._validate_input(input_data)

        async with self._uow:
            if await self._tenants.email_exists(input_data.admin_email):
                raise ConflictError(
                    f"An account already exists for {input_data.admin_email}"
                )

            slug = await self._resolve_slug(input_data.desired_slug or input_data.name)

            tenant = Tenant.register(
                name=input_data.name,
                slug=slug,
                admin_email=input_data.admin_email,
                industry=input_data.industry,
            )

            password_hash = self._hasher.hash(input_data.admin_password)
            await self._user_factory.create_admin_user(
                tenant_id=tenant.id,
                email=input_data.admin_email,
                password_hash=password_hash,
            )

            await self._tenants.add(tenant)
            verification_token = await self._tokens.issue_for(tenant.id)

            await self._uow.commit()

        return RegisterTenantOutput(
            tenant_id=tenant.id,
            slug=slug.value,
            verification_token=verification_token,
        )

    def _validate_input(self, data: RegisterTenantInput) -> None:
        if len(data.admin_password) < 8:
            raise ValidationError("Password must be at least 8 characters")
        if not data.name.strip():
            raise ValidationError("Tenant name is required")
        if not data.industry:
            raise ValidationError("Industry is required for auto-provisioning")

    async def _resolve_slug(self, candidate: str) -> TenantSlug:
        base = _slugify(candidate)
        slug = TenantSlug(value=base)
        suffix = 1
        while await self._tenants.slug_exists(slug):
            suffix += 1
            slug = TenantSlug(value=f"{base}-{suffix}")
            if suffix > 1000:
                raise ConflictError("Unable to generate a unique slug")
        return slug


def _slugify(text: str) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    lowered = normalized.lower().strip()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")[:48] or "tenant"
