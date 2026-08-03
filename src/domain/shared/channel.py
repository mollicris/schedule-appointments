from enum import Enum


class Channel(str, Enum):
    """Messaging channel a client contacts the business through.

    Lives in ``shared`` because three bounded contexts need it — client
    (identity), conversation (where the dialogue happens) and business (which
    credentials to send with) — and contexts must not import each other.

    Each channel identifies people differently: WhatsApp by phone number,
    Messenger and Instagram by an opaque page-scoped id (PSID / IGSID). Those
    ids cannot be correlated, so the same person writing from two channels is
    two clients.
    """

    WHATSAPP = "whatsapp"
    MESSENGER = "messenger"
    INSTAGRAM = "instagram"

    @property
    def is_social(self) -> bool:
        """True for Meta's social inboxes, where the bot is read-only."""
        return self in (Channel.MESSENGER, Channel.INSTAGRAM)

    @property
    def label_es(self) -> str:
        return {
            Channel.WHATSAPP: "WhatsApp",
            Channel.MESSENGER: "Messenger",
            Channel.INSTAGRAM: "Instagram",
        }[self]
