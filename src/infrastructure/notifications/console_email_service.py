from __future__ import annotations

import logging

from src.application.notifications.email_service import EmailMessage

logger = logging.getLogger(__name__)


class ConsoleEmailService:
    """Development email service — prints emails to the log instead of sending them.

    Use EMAIL_PROVIDER=console (default) when no real provider is configured.
    """

    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "\n"
            "╔══════════════════════════════════════════════════════╗\n"
            "║              [DEV] EMAIL NOT SENT — PREVIEW           ║\n"
            "╠══════════════════════════════════════════════════════╣\n"
            "║  To      : %s\n"
            "║  Subject : %s\n"
            "╠══════════════════════════════════════════════════════╣\n"
            "%s\n"
            "╚══════════════════════════════════════════════════════╝",
            message.to,
            message.subject,
            message.text_body,
        )
