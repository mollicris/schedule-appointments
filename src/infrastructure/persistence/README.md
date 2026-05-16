# Infrastructure: Persistence

## Multitenancy strategy

**Shared database, shared schema, with PostgreSQL Row-Level Security (RLS)**.

Every multitenant table includes a non-nullable `tenant_id UUID` column with a foreign key to `tenants.id`. RLS policies on each table enforce:

```sql
CREATE POLICY tenant_isolation ON appointments
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

The session-level setting `app.current_tenant_id` is set by the FastAPI dependency `set_tenant_context` after authenticating the request. **Even if application code forgets to filter by tenant_id, the database refuses to return rows from another tenant.**

This gives us:
- Low operational overhead (single DB to back up, patch, scale)
- Fast cross-tenant aggregate analytics (admin views can bypass RLS with the `app_admin` role)
- Strong defense-in-depth: app bugs cannot leak data across tenants

## Layout

- `database.py` — SQLAlchemy engine + session factory
- `models/` — SQLAlchemy ORM models (one file per aggregate)
- `repositories/` — Concrete implementations of domain repository interfaces
- `mappers.py` — Functions translating between domain entities and ORM models
- `tenant_session.py` — Helper to set `app.current_tenant_id` on a session

## Why separate domain entities from ORM models?

Pure DDD: domain entities stay free of SQLAlchemy concerns. The mapper layer absorbs schema evolution, lazy loading, and ORM-specific quirks. Cost is small (write 2x classes per aggregate), benefit is enormous (testable, refactorable domain).

## Migrations

Alembic, in `backend/migrations/`. First migration creates:
1. `tenants` table (no RLS — root of multitenancy)
2. All tenant-scoped tables with `tenant_id`
3. RLS policies enabled on each
4. pgvector extension for embeddings
