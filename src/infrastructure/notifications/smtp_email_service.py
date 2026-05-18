from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.application.notifications.email_service import EmailDeliveryError, EmailMessage

logger = logging.getLogger(__name__)


class SmtpEmailService:
    """Email service using a standard SMTP relay.

    Compatible with Gmail, Outlook, Brevo, Mailgun SMTP, Postfix, etc.

    Required settings:
        SMTP_HOST      — e.g. "smtp.gmail.com"
        SMTP_PORT      — e.g. 587 (STARTTLS) or 465 (SSL)
        SMTP_USER      — sender login / address
        SMTP_PASSWORD  — sender password or app password
        EMAIL_FROM     — display name + address, e.g. "Agente Citas <noreply@yourdomain.com>"
        SMTP_USE_TLS   — true for port 587 STARTTLS (default), false for plain/SSL
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_address: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._from = from_address
        self._use_tls = use_tls

    async def send(self, message: EmailMessage) -> None:
        # smtplib is synchronous — run in a thread to avoid blocking the event loop
        await asyncio.get_event_loop().run_in_executor(None, self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        msg = MIMEMultipart("alternative")
        msg["From"] = self._from
        msg["To"] = message.to
        msg["Subject"] = message.subject
        if message.reply_to:
            msg["Reply-To"] = message.reply_to

        if message.text_body:
            msg.attach(MIMEText(message.text_body, "plain", "utf-8"))
        msg.attach(MIMEText(message.html_body, "html", "utf-8"))

        try:
            if self._use_tls:
                with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.login(self._user, self._password)
                    smtp.sendmail(self._from, [message.to], msg.as_string())
            else:
                with smtplib.SMTP_SSL(self._host, self._port, timeout=10) as smtp:
                    smtp.login(self._user, self._password)
                    smtp.sendmail(self._from, [message.to], msg.as_string())
        except smtplib.SMTPException as exc:
            logger.error("SMTP error sending to %s: %s", message.to, exc)
            raise EmailDeliveryError(str(exc)) from exc

        logger.info("Email sent via SMTP to %s (subject: %s)", message.to, message.subject)
