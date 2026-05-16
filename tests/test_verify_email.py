"""Tests for email verification use case."""

import pytest
from uuid import uuid4

from src.application.onboarding.verify_email import (
    VerifyEmailInput,
    VerifyEmailUseCase,
)
from src.domain.shared.errors import ValidationError
from src.domain.tenant.tenant import Tenant
from src.domain.tenant.value_objects import TenantSlug, TenantStatus


class MockVerificationTokenService:
    """Mock in-memory verification token service for testing."""

    def __init__(self):
        self.tokens = {}
        self.consumed_tokens = set()

    async def issue_for(self, tenant_id):
        """Generate a test token."""
        token = f"test-token-{tenant_id}"
        self.tokens[token] = tenant_id
        return token

    async def consume(self, token):
        """Consume a token and return tenant_id."""
        if token in self.consumed_tokens:
            return None  # Already consumed
        if token not in self.tokens:
            return None  # Invalid token
        self.consumed_tokens.add(token)
        return self.tokens[token]


class MockTenantRepository:
    """Mock tenant repository for testing."""

    def __init__(self):
        self.tenants = {}

    async def get_by_id(self, tenant_id):
        return self.tenants.get(tenant_id)

    async def add(self, tenant):
        self.tenants[tenant.id] = tenant

    async def update(self, tenant):
        self.tenants[tenant.id] = tenant


class MockUnitOfWork:
    """Mock unit of work for testing."""

    def __init__(self):
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


@pytest.mark.asyncio
async def test_verify_email_success():
    """Test successful email verification."""
    # Setup
    tenant_id = uuid4()
    tenant = Tenant(
        id=tenant_id,
        name="Test Salon",
        slug=TenantSlug(value="test-salon"),
        admin_email="admin@salon.io",
        industry="hair_salon",
        status=TenantStatus.PENDING_VERIFICATION,
    )

    repo = MockTenantRepository()
    await repo.add(tenant)

    token_service = MockVerificationTokenService()
    token = await token_service.issue_for(tenant_id)

    uow = MockUnitOfWork()

    use_case = VerifyEmailUseCase(
        tenants=repo,
        uow=uow,
        verification_token_service=token_service,
    )

    # Execute
    input_data = VerifyEmailInput(token=token)
    output = await use_case.execute(input_data)

    # Assert
    assert output.tenant_id == tenant_id
    assert output.slug == "test-salon"
    assert output.admin_email == "admin@salon.io"

    # Verify tenant status changed
    updated_tenant = await repo.get_by_id(tenant_id)
    assert updated_tenant.status == TenantStatus.ONBOARDING

    # Verify UoW was committed
    assert uow.committed


@pytest.mark.asyncio
async def test_verify_email_invalid_token():
    """Test verification with invalid token."""
    repo = MockTenantRepository()
    token_service = MockVerificationTokenService()
    uow = MockUnitOfWork()

    use_case = VerifyEmailUseCase(
        tenants=repo,
        uow=uow,
        verification_token_service=token_service,
    )

    # Execute with invalid token
    input_data = VerifyEmailInput(token="invalid-token")

    with pytest.raises(ValidationError) as exc_info:
        await use_case.execute(input_data)

    assert "Invalid or expired verification token" in str(exc_info.value)


@pytest.mark.asyncio
async def test_verify_email_token_already_consumed():
    """Test verification with already-consumed token."""
    # Setup
    tenant_id = uuid4()
    tenant = Tenant(
        id=tenant_id,
        name="Test Salon",
        slug=TenantSlug(value="test-salon"),
        admin_email="admin@salon.io",
        industry="hair_salon",
        status=TenantStatus.PENDING_VERIFICATION,
    )

    repo = MockTenantRepository()
    await repo.add(tenant)

    token_service = MockVerificationTokenService()
    token = await token_service.issue_for(tenant_id)

    # Consume token once
    _ = await token_service.consume(token)

    uow = MockUnitOfWork()

    use_case = VerifyEmailUseCase(
        tenants=repo,
        uow=uow,
        verification_token_service=token_service,
    )

    # Execute with already-consumed token
    input_data = VerifyEmailInput(token=token)

    with pytest.raises(ValidationError) as exc_info:
        await use_case.execute(input_data)

    assert "Invalid or expired verification token" in str(exc_info.value)


@pytest.mark.asyncio
async def test_verify_email_tenant_not_found():
    """Test verification when tenant doesn't exist."""
    fake_tenant_id = uuid4()

    repo = MockTenantRepository()

    token_service = MockVerificationTokenService()
    token = await token_service.issue_for(fake_tenant_id)

    uow = MockUnitOfWork()

    use_case = VerifyEmailUseCase(
        tenants=repo,
        uow=uow,
        verification_token_service=token_service,
    )

    # Execute with non-existent tenant
    input_data = VerifyEmailInput(token=token)

    with pytest.raises(ValidationError) as exc_info:
        await use_case.execute(input_data)

    assert "Tenant not found" in str(exc_info.value)
