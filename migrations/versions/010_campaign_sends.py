"""Add campaign_sends for proactive campaign idempotency

One row per (client, campaign, occurrence). The unique index on
(tenant_id, dedupe_key) is what stops a member from being messaged twice about
the same expiring membership, even if the scheduler restarts mid-cycle or two
instances run at once: the job inserts first and only sends when the insert won.

Revision ID: 010
Revises: 009
Create Date: 2026-07-31

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: str | Sequence[str] | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_sends",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_key", sa.String(50), nullable=False),
        sa.Column("dedupe_key", sa.String(160), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_campaign_sends_tenant_dedupe"),
    )
    op.create_index("ix_campaign_sends_tenant", "campaign_sends", ["tenant_id"])
    op.create_index("ix_campaign_sends_business", "campaign_sends", ["business_id"])
    op.create_index("ix_campaign_sends_client", "campaign_sends", ["client_id"])

    op.execute("ALTER TABLE campaign_sends ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON campaign_sends
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_insert ON campaign_sends
        FOR INSERT
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_update ON campaign_sends
        FOR UPDATE
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_delete ON campaign_sends
        FOR DELETE
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON campaign_sends")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON campaign_sends")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON campaign_sends")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON campaign_sends")
    op.drop_index("ix_campaign_sends_client", "campaign_sends")
    op.drop_index("ix_campaign_sends_business", "campaign_sends")
    op.drop_index("ix_campaign_sends_tenant", "campaign_sends")
    op.drop_table("campaign_sends")
