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
    async def get_pending_lead(self, conversation_id: UUID) -> HumanTransfer | None:
        """The lead this conversation already left, if reception has not closed it.

        One enquiry is one lead: a retry, a stray attachment or a repeated tool
        call must update that row instead of queueing the same person twice.
        """
        ...

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
