from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from src.domain.shared.errors import TenantIsolationError


@dataclass(frozen=True)
class TenantContext:
    """Immutable per-request tenant context.

    Injected by the presentation layer (via FastAPI dependency) after
    resolving the tenant from the JWT, subdomain, or API key. Carried
    through the request via ContextVar so application services can
    access it without explicit parameter threading.

    Repositories use this to enforce isolation; cross-tenant access
    raises ``TenantIsolationError``.
    """

    tenant_id: UUID
    user_id: UUID | None = None
    roles: frozenset[str] = frozenset()

    def assert_owns(self, other_tenant_id: UUID) -> None:
        """Raise if attempting to operate on a resource from another tenant."""
        if other_tenant_id != self.tenant_id:
            raise TenantIsolationError(
                f"Cross-tenant access denied: current tenant {self.tenant_id} "
                f"cannot access resources of tenant {other_tenant_id}"
            )

    def has_role(self, role: str) -> bool:
        return role in self.roles


_current_tenant: ContextVar[TenantContext | None] = ContextVar(
    "current_tenant", default=None
)


def set_current_tenant(context: TenantContext) -> None:
    _current_tenant.set(context)


def get_current_tenant() -> TenantContext:
    ctx = _current_tenant.get()
    if ctx is None:
        raise RuntimeError(
            "No tenant context set. Ensure the request passes through "
            "the tenant resolution dependency."
        )
    return ctx


def try_get_current_tenant() -> TenantContext | None:
    return _current_tenant.get()
