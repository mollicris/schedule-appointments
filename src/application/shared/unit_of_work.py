from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


class UnitOfWork(ABC):
    """Transactional boundary for a use case.

    A use case typically modifies multiple aggregates; the UnitOfWork
    ensures they are committed atomically. Domain events accumulated by
    aggregates are dispatched on successful commit.

    Usage:

        async with uow:
            tenant = await uow.tenants.get_by_id(tenant_id)
            tenant.complete_onboarding()
            await uow.tenants.update(tenant)
            await uow.commit()
    """

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
