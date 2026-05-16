from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.client.client import Client


class ClientRepository(ABC):
    @abstractmethod
    async def get_by_id(self, client_id: UUID) -> Client | None: ...

    @abstractmethod
    async def get_by_whatsapp(self, whatsapp_number: str) -> Client | None: ...

    @abstractmethod
    async def add(self, client: Client) -> None: ...

    @abstractmethod
    async def update(self, client: Client) -> None: ...
