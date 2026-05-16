from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from src.domain.tenant.tenant import Tenant
from src.domain.tenant.value_objects import TenantSlug


class TenantRepository:
    """Repository for the Tenant aggregate.

    Unlike other repositories, this one is NOT tenant-scoped — it operates
    across all tenants because Tenant is the root of the multitenancy model.
    Only auto-onboarding and admin operations should use it.
    """

    @abstractmethod
    async def get_by_id(self, tenant_id: UUID) -> Tenant | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: TenantSlug) -> Tenant | None: ...

    @abstractmethod
    async def get_by_admin_email(self, email: str) -> Tenant | None: ...

    @abstractmethod
    async def slug_exists(self, slug: TenantSlug) -> bool: ...

    @abstractmethod
    async def email_exists(self, email: str) -> bool: ...

    @abstractmethod
    async def add(self, tenant: Tenant) -> None: ...

    @abstractmethod
    async def update(self, tenant: Tenant) -> None: ...
