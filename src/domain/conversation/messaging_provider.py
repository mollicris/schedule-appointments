from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.shared.channel import Channel


@runtime_checkable
class MessagingProvider(Protocol):
    """Port for sending messages back to a client, whatever the channel.

    Implemented by ``WhatsAppClient`` (Cloud API) and ``MetaMessagingClient``
    (Messenger and Instagram via the Graph API). The conversation flow depends
    on this instead of a concrete client, so adding a channel does not touch the
    agent or the use case.

    Deliberately small: only what every channel can do. WhatsApp templates stay
    on ``WhatsAppClient`` because no other channel has them — Messenger and
    Instagram use message tags instead, with different rules.

    Implementations never raise: they log and return False, so a delivery
    failure cannot lose the conversation.
    """

    @property
    def channel(self) -> Channel:
        """Which channel this provider talks to."""
        ...

    async def send_text(self, *, to: str, body: str) -> bool:
        """Send plain text. ``to`` is the channel id: phone, PSID or IGSID."""
        ...

    async def send_buttons(self, *, to: str, body: str, buttons: list[dict]) -> bool:
        """Send text with quick replies. Each button: {"id": ..., "title": ...}.

        Providers truncate to their own limit (WhatsApp allows 3).
        """
        ...
