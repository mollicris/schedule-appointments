from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.identity.user import User


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def update_last_login(self, user_id: UUID) -> None: ...
