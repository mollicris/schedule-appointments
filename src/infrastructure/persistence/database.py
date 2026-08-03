from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase

from src.infrastructure.config.settings import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models.

    ORM models live in ``infrastructure/persistence/models/`` and are
    intentionally separate from domain entities. Mapper functions in
    ``infrastructure/persistence/mappers.py`` translate between the two.
    """


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _is_transaction_pooler(url: str) -> bool:
    """True when the URL points at PgBouncer in transaction mode.

    Supabase serves that pooler on port 6543 (the session pooler and the direct
    connection both use 5432).
    """
    return ":6543/" in url or "pgbouncer=true" in url


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        kwargs: dict = {
            "echo": settings.app_debug,
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
        }

        if _is_transaction_pooler(url):
            # asyncpg prepares every statement and reuses it by name; PgBouncer in
            # transaction mode hands each transaction a different backend, so the
            # name is not there any more and queries fail with
            # DuplicatePreparedStatementError / InvalidSQLStatementName.
            # Disabling both caches is what makes asyncpg work through the pooler.
            # Pooling is PgBouncer's job here, so NullPool avoids pooling twice.
            kwargs["poolclass"] = NullPool
            kwargs.pop("pool_size")
            kwargs.pop("max_overflow")
            kwargs["connect_args"] = {
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
            }

        _engine = create_async_engine(url, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async context manager yielding a transactional session.

    Use inside background jobs and tests. In FastAPI handlers, prefer
    the ``Depends(get_db_session)`` injection in ``presentation/dependencies.py``.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
