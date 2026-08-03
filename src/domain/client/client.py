from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.shared.channel import Channel
from src.domain.shared.entity import TenantAwareEntity
from src.domain.shared.errors import BusinessRuleViolationError


@dataclass(eq=False)
class Client(TenantAwareEntity):
    """Client aggregate root.

    Represents a customer who contacts the business through a messaging channel
    or is created from the admin UI.

    Identity is the pair (channel, external_id):
      - WhatsApp: external_id is the E.164 number, mirrored in whatsapp_number.
      - Messenger / Instagram: external_id is the page-scoped id Meta assigns
        (PSID / IGSID) and there is no phone number until the client gives one,
        so whatsapp_number stays empty.

    The same person writing from two channels is two clients: Meta gives no way
    to correlate a PSID with a phone number.
    """

    whatsapp_number: str = ""
    channel: Channel = Channel.WHATSAPP
    external_id: str = ""
    name: str = ""
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    is_active: bool = True
    appointment_count: int = 0
    last_appointment_at: datetime | None = None
    last_interaction_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        whatsapp_number: str = "",
        name: str,
        email: str | None = None,
        phone: str | None = None,
        notes: str | None = None,
        channel: Channel = Channel.WHATSAPP,
        external_id: str | None = None,
    ) -> Client:
        """Create a client.

        ``external_id`` defaults to the WhatsApp number, so existing callers keep
        working unchanged; social channels pass the PSID/IGSID explicitly.
        """
        now = datetime.utcnow()
        resolved_external_id = (external_id or whatsapp_number).strip()
        if not resolved_external_id:
            raise BusinessRuleViolationError(
                "A client needs an external_id (WhatsApp number or channel id)"
            )

        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            whatsapp_number=whatsapp_number.strip(),
            channel=channel,
            external_id=resolved_external_id,
            name=name.strip(),
            email=email,
            phone=phone,
            notes=notes,
            is_active=True,
            appointment_count=0,
            created_at=now,
            updated_at=now,
        )

    def increment_appointment_count(self, at: datetime) -> None:
        self.appointment_count += 1
        self.last_appointment_at = at
        self.updated_at = datetime.utcnow()

    def record_contact_details(
        self,
        *,
        name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> None:
        """Store contact details the client handed over during a conversation.

        This is how a social lead becomes reachable: on Messenger and Instagram
        we only know an opaque id until they type their phone number.
        """
        if name and name.strip():
            self.name = name.strip()
        if phone and phone.strip():
            self.phone = phone.strip()
        if email and email.strip():
            self.email = email.strip()
        self.updated_at = datetime.utcnow()

    def record_interaction(self, at: datetime | None = None) -> None:
        """Mark that the client just wrote to us.

        Feeds inactivity segmentation: a win-back campaign needs to know when a
        client last engaged, not only when they last booked.
        """
        moment = at or datetime.now(timezone.utc)
        self.last_interaction_at = moment
        self.updated_at = datetime.utcnow()
