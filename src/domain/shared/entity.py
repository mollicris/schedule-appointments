from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.domain.shared.events import DomainEvent


@dataclass(eq=False)
class Entity(ABC):
    """Base for all domain entities.

    Identity-based equality: two entities are equal iff their IDs match,
    regardless of attribute differences. Mutable; lifecycle tracked via
    domain events accumulated in ``_pending_events``.
    """

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    _pending_events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))

    def record_event(self, event: DomainEvent) -> None:
        self._pending_events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events


@dataclass(eq=False)
class TenantAwareEntity(Entity):
    """Entity that belongs to a tenant. All entities except ``Tenant`` itself
    must extend this class.

    The ``tenant_id`` is part of the identity model: an entity with the same
    ``id`` but different ``tenant_id`` is conceptually impossible — but we
    keep the field explicit to enforce isolation at the application and
    persistence layers.

    Subclasses that override ``__post_init__`` MUST call ``super().__post_init__()``
    to preserve the tenant_id invariant.
    """

    tenant_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.tenant_id is None:
            raise ValueError(f"{type(self).__name__} requires a tenant_id")


@dataclass(eq=False)
class AggregateRoot(TenantAwareEntity):
    """Marker for aggregate roots — the only entities accessible from outside
    their aggregate boundary. Repositories operate exclusively on aggregate roots.

    Multitenant by default: every aggregate root carries its ``tenant_id``.
    The exception is the ``Tenant`` aggregate itself (see ``domain/tenant``).
    """

    pass


@dataclass(frozen=True)
class ValueObject(ABC):
    """Base for value objects.

    Equality is structural (all attributes compared). Immutable by contract
    (frozen dataclass). Has no identity. Validation runs on construction.
    """

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Override in subclasses to enforce invariants on construction."""
        pass

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)
