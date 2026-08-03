from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.domain.membership.membership import Membership
from src.domain.membership.membership_plan import MembershipPlan
from src.domain.membership.value_objects import MembershipStatus


class MembershipPlanRepository(ABC):
    """Repository port for the MembershipPlan aggregate.

    All queries are scoped to the current tenant by the implementation.
    """

    @abstractmethod
    async def get_by_id(self, plan_id: UUID) -> MembershipPlan | None: ...

    @abstractmethod
    async def list_by_business(
        self,
        business_id: UUID,
        *,
        include_inactive: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MembershipPlan]: ...

    @abstractmethod
    async def count_by_business(
        self,
        business_id: UUID,
        *,
        include_inactive: bool = False,
    ) -> int: ...

    @abstractmethod
    async def add(self, plan: MembershipPlan) -> None: ...

    @abstractmethod
    async def update(self, plan: MembershipPlan) -> None: ...

    @abstractmethod
    async def list_service_ids(self, plan_id: UUID) -> list[UUID]:
        """Services included in the plan. Empty list = every service."""
        ...

    @abstractmethod
    async def set_services(self, plan_id: UUID, service_ids: list[UUID]) -> None:
        """Replace the set of services included in the plan."""
        ...


class MembershipRepository(ABC):
    """Repository port for the Membership aggregate."""

    @abstractmethod
    async def get_by_id(self, membership_id: UUID) -> Membership | None: ...

    @abstractmethod
    async def get_current_for_client(
        self,
        client_id: UUID,
        business_id: UUID,
    ) -> Membership | None:
        """Latest non-terminal membership (ACTIVE or FROZEN) of a client."""
        ...

    @abstractmethod
    async def list_by_client(
        self,
        client_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Membership]: ...

    @abstractmethod
    async def list_by_business(
        self,
        business_id: UUID,
        *,
        status: MembershipStatus | None = None,
        expiring_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Membership]: ...

    @abstractmethod
    async def count_by_business(
        self,
        business_id: UUID,
        *,
        status: MembershipStatus | None = None,
        expiring_before: datetime | None = None,
    ) -> int: ...

    @abstractmethod
    async def add(self, membership: Membership) -> None: ...

    @abstractmethod
    async def update(self, membership: Membership) -> None: ...
