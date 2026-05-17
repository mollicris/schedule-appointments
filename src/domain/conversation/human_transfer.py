from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.shared.entity import TenantAwareEntity


@dataclass(eq=False)
class HumanTransfer(TenantAwareEntity):
    business_id: UUID = UUID(int=0)
    conversation_id: UUID = UUID(int=0)
    client_id: UUID = UUID(int=0)
    reason: str | None = None
    context_snapshot: list = field(default_factory=list)
    status: str = "pending"
    resolved_at: datetime | None = None
    resolved_by_id: UUID | None = None

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        business_id: UUID,
        conversation_id: UUID,
        client_id: UUID,
        reason: str | None = None,
        context_snapshot: list | None = None,
    ) -> HumanTransfer:
        now = datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            business_id=business_id,
            conversation_id=conversation_id,
            client_id=client_id,
            reason=reason,
            context_snapshot=context_snapshot or [],
            status="pending",
            created_at=now,
            updated_at=now,
        )

    def resolve(self, resolved_by_id: UUID) -> None:
        self.status = "resolved"
        self.resolved_at = datetime.now(timezone.utc)
        self.resolved_by_id = resolved_by_id
        self.updated_at = datetime.now(timezone.utc)
