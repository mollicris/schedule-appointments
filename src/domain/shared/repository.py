from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from uuid import UUID

from src.domain.shared.entity import AggregateRoot

TAggregate = TypeVar("TAggregate", bound=AggregateRoot)


class Repository(ABC, Generic[TAggregate]):
    """Base repository interface (port).

    Concrete implementations live in ``infrastructure/persistence/repositories``.
    All operations are **tenant-scoped**: a repository instance is bound to a
    tenant context (injected by the request layer) and never returns rows
    belonging to a different tenant.

    This enforcement is double-layered:
    1. Application layer: this interface receives ``tenant_id`` explicitly
       or pulls it from a ``TenantContext`` injected via DI.
    2. Database layer: PostgreSQL Row-Level Security policies guarantee
       isolation even if application code has a bug.
    """

    @abstractmethod
    async def get_by_id(self, entity_id: UUID, tenant_id: UUID) -> TAggregate | None: ...

    @abstractmethod
    async def add(self, entity: TAggregate) -> None: ...

    @abstractmethod
    async def update(self, entity: TAggregate) -> None: ...

    @abstractmethod
    async def delete(self, entity_id: UUID, tenant_id: UUID) -> None: ...
