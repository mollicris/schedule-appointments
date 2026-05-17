from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.conversation.human_transfer import HumanTransfer


class HumanTransferRepository(ABC):
    @abstractmethod
    async def add(self, transfer: HumanTransfer) -> None: ...

    @abstractmethod
    async def get_by_id(self, transfer_id: UUID) -> HumanTransfer | None: ...

    @abstractmethod
    async def list_by_business(
        self,
        business_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[HumanTransfer]: ...

    @abstractmethod
    async def count_by_business(self, business_id: UUID, status: str | None = None) -> int: ...

    @abstractmethod
    async def update(self, transfer: HumanTransfer) -> None: ...
