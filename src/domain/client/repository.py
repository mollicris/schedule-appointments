from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.client.client import Client
from src.domain.shared.channel import Channel


class ClientRepository(ABC):
    @abstractmethod
    async def get_by_id(self, client_id: UUID) -> Client | None: ...

    @abstractmethod
    async def get_by_whatsapp(self, whatsapp_number: str) -> Client | None:
        """Find a WhatsApp client by phone number.

        Kept as the entry point for phone-based flows (booking from the admin
        UI, granting a membership at the counter).
        """
        ...

    @abstractmethod
    async def get_by_channel_id(self, channel: Channel, external_id: str) -> Client | None:
        """Find a client by the id its channel assigns (phone, PSID or IGSID)."""
        ...

    @abstractmethod
    async def add(self, client: Client) -> None: ...

    @abstractmethod
    async def update(self, client: Client) -> None: ...
