from __future__ import annotations

import httpx
import structlog

from src.infrastructure.config.settings import get_settings

log = structlog.get_logger(__name__)


class WhatsAppClient:
    """HTTP client for the WhatsApp Cloud API (Meta).

    Sends text messages and interactive button messages on behalf of a
    WhatsApp Business Number. Each business uses its own access_token
    and phone_number_id configured during onboarding.
    """

    def __init__(
        self,
        phone_number_id: str,
        access_token: str,
        api_version: str | None = None,
    ) -> None:
        settings = get_settings()
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._base_url = (
            f"https://graph.facebook.com/{api_version or settings.whatsapp_api_version}"
        )

    async def send_text(self, *, to: str, body: str) -> bool:
        """Send a plain text message. Returns True on success."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        return await self._post(payload)

    async def send_interactive_buttons(
        self,
        *,
        to: str,
        body: str,
        buttons: list[dict],
    ) -> bool:
        """Send an interactive message with up to 3 quick-reply buttons.

        Each button: {"id": "btn_confirm", "title": "Confirmar"}
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                        for b in buttons[:3]
                    ]
                },
            },
        }
        return await self._post(payload)

    async def _post(self, payload: dict) -> bool:
        url = f"{self._base_url}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code not in (200, 201):
                    log.warning(
                        "whatsapp_send_failed",
                        status=response.status_code,
                        body=response.text[:200],
                    )
                    return False
                return True
            except httpx.HTTPError as exc:
                log.error("whatsapp_send_error", error=str(exc))
                return False


def whatsapp_client_for_business(
    *,
    phone_number_id: str,
    access_token: str,
) -> WhatsAppClient:
    """Factory used by the webhook handler to build a per-business client."""
    settings = get_settings()
    return WhatsAppClient(
        phone_number_id=phone_number_id,
        access_token=access_token,
        api_version=settings.whatsapp_api_version,
    )
