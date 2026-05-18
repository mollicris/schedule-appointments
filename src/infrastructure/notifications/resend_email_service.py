from __future__ import annotations

import logging

import httpx

from src.application.notifications.email_service import EmailDeliveryError, EmailMessage

logger = logging.getLogger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailService:
    """Production email service using the Resend API (https://resend.com).

    Required settings:
        RESEND_API_KEY  — API key from the Resend dashboard
        EMAIL_FROM      — verified sender address, e.g. "Agente Citas <noreply@yourdomain.com>"

    Resend has a generous free tier (3 000 emails/mo) and supports custom domains,
    HTML, tags, and webhooks out of the box.
    """

    def __init__(self, api_key: str, from_address: str) -> None:
        self._api_key = api_key
        self._from = from_address

    async def send(self, message: EmailMessage) -> None:
        payload: dict = {
            "from": self._from,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html_body,
        }
        if message.text_body:
            payload["text"] = message.text_body
        if message.reply_to:
            payload["reply_to"] = message.reply_to
        if message.tags:
            payload["tags"] = [{"name": t} for t in message.tags]

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                _RESEND_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code not in (200, 201):
            body = response.text
            logger.error("Resend API error %s: %s", response.status_code, body)
            raise EmailDeliveryError(f"Resend returned {response.status_code}: {body}")

        logger.info("Email sent via Resend to %s (subject: %s)", message.to, message.subject)
