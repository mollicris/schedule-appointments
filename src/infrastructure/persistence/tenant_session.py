from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def bind_tenant_to_session(session: AsyncSession, tenant_id: UUID) -> None:
    """Activate Row-Level Security context for this session.

    PostgreSQL RLS policies on tenant-scoped tables check
    ``current_setting('app.current_tenant_id')`` to filter rows.
    Calling this once at the start of a request ensures every subsequent
    query within the same session/transaction is automatically scoped.

    NOTE: The setting is session-local; reusing a session across requests
    would leak context, so we ALWAYS use one session per request.
    """
    await session.execute(
        text("SET LOCAL app.current_tenant_id = :tid"),
        {"tid": str(tenant_id)},
    )


async def clear_tenant_from_session(session: AsyncSession) -> None:
    """Reset to admin/cross-tenant mode. Use ONLY in trusted admin endpoints
    and background jobs that legitimately operate across tenants."""
    await session.execute(text("RESET app.current_tenant_id"))
