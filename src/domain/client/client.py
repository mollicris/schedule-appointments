from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from src.domain.shared.entity import TenantAwareEntity


@dataclass(eq=False)
class Client(TenantAwareEntity):
    """Client aggregate root.

    Represents a customer who books appointments via WhatsApp or admin UI.
    whatsapp_number is the primary identifier for bot-initiated flows (E.164).
    """

    whatsapp_number: str = ""
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
        whatsapp_number: str,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        notes: str | None = None,
    ) -> Client:
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            whatsapp_number=whatsapp_number.strip(),
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
