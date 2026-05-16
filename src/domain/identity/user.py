from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.domain.identity.value_objects import UserRole, UserStatus


@dataclass(frozen=True)
class User:
    id: UUID
    tenant_id: UUID
    email: str
    password_hash: str
    role: UserRole
    status: UserStatus
    is_active: bool
