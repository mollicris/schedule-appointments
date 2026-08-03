from __future__ import annotations

import httpx
import structlog

from src.domain.shared.channel import Channel
from src.infrastructure.config.settings import get_settings

log = structlog.get_logger(__name__)

# Meta allows 13 quick replies; keeping it lower matches the prompt rule of
# never showing more than three options at a time.
_MAX_QUICK_REPLIES = 3


class MetaMessagingClient:
    """Send messages through Messenger and Instagram Direct (Meta Graph API).

    Both channels share one endpoint, ``POST /{page_id}/messages``, and one
    credential: the **Page access token**. Instagram Direct is served by the
    Facebook Page the professional account is linked to, so the only practical
    difference is the recipient id (PSID vs IGSID) and the reply-window rules.

    ``to`` is that page-scoped id, never a phone number: it only makes sense for
    the page that received the message.

    Implements the ``MessagingProvider`` port. Like ``WhatsAppClient`` it never
    raises — it logs and returns False.
    """

    BASE_URL = "https://graph.facebook.com"

    def __init__(
        self,
        *,
        page_id: str,
        page_access_token: str,
        channel: Channel = Channel.MESSENGER,
        api_version: str | None = None,
    ) -> None:
        settings = get_settings()
        self._page_id = page_id
        self._access_token = page_access_token
        self._channel = channel
        self._base_url = f"{self.BASE_URL}/{api_version or settings.whatsapp_api_version}"

    @property
    def channel(self) -> Channel:
        return self._channel

    async def send_text(self, *, to: str, body: str) -> bool:
        return await self._post(
            {
                "recipient": {"id": to},
                "messaging_type": "RESPONSE",
                "message": {"text": body},
            }
        )

    async def send_buttons(self, *, to: str, body: str, buttons: list[dict]) -> bool:
        """Send text with quick replies.

        Meta's quick replies are the closest equivalent to WhatsApp's reply
        buttons: the payload comes back in ``message.quick_reply.payload``,
        which the webhook maps to the same ``button_id`` the flow already uses.
        """
        quick_replies = [
            {
                "content_type": "text",
                "title": b["title"][:20],   # Meta truncates at 20 chars
                "payload": b["id"],
            }
            for b in buttons[:_MAX_QUICK_REPLIES]
        ]
        return await self._post(
            {
                "recipient": {"id": to},
                "messaging_type": "RESPONSE",
                "message": {"text": body, "quick_replies": quick_replies},
            }
        )

    async def _post(self, payload: dict) -> bool:
        url = f"{self._base_url}/{self._page_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code not in (200, 201):
                    hint = ""
                    if response.status_code == 401:
                        hint = (
                            "Token de página rechazado. Regeneralo en Meta → Messenger → "
                            "Settings → Access Tokens y actualizá "
                            "businesses.facebook_page_access_token."
                        )
                    elif response.status_code == 400 and "outside" in response.text.lower():
                        hint = (
                            "Fuera de la ventana de respuesta de Meta (24 h en Messenger, "
                            "7 días con etiqueta de agente humano en Instagram)."
                        )
                    log.warning(
                        "meta_send_failed",
                        channel=self._channel.value,
                        status=response.status_code,
                        body=response.text[:300],
                        hint=hint,
                    )
                    return False
                return True
            except httpx.HTTPError as exc:
                log.error("meta_send_error", channel=self._channel.value, error=str(exc))
                return False


def meta_client_for_business(
    *,
    page_id: str,
    page_access_token: str,
    channel: Channel,
) -> MetaMessagingClient:
    """Factory used by the webhook handler to build a per-business client."""
    settings = get_settings()
    return MetaMessagingClient(
        page_id=page_id,
        page_access_token=page_access_token,
        channel=channel,
        api_version=settings.whatsapp_api_version,
    )
