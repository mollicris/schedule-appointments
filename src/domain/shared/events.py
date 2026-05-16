from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, kw_only=True)
class DomainEvent(ABC):
    """Base for all domain events.

    Events are immutable facts about something that happened in the domain.
    They carry the ``tenant_id`` so that subscribers (handlers, projections,
    analytics) can route events to the correct tenant context without
    relying on ambient state.
    """

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    tenant_id: UUID
