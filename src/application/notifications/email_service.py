from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html_body: str
    text_body: str = ""
    reply_to: str | None = None
    tags: list[str] = field(default_factory=list)


@runtime_checkable
class EmailService(Protocol):
    """Port — send transactional emails through any provider.

    Implementations:
        ConsoleEmailService  — logs to stdout (development)
        ResendEmailService   — Resend API (production default)
        SmtpEmailService     — SMTP relay (self-hosted / alternative)

    To add a new channel, implement this Protocol and register it
    in get_email_service() inside dependencies.py.
    """

    async def send(self, message: EmailMessage) -> None:
        """Send a single transactional email.

        Raises:
            EmailDeliveryError: if the provider rejects the message.
        """
        ...


class EmailDeliveryError(Exception):
    """Raised when a provider fails to accept the message."""
