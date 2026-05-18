"""Add service_professionals many-to-many table

Allows restricting which professionals can perform each service.

Revision ID: 006
Revises: 005
Create Date: 2026-05-17

"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: str | Sequence[str] | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_professionals",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["professional_id"], ["professionals.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("service_id", "professional_id"),
    )
    op.create_index(
        "ix_service_professionals_professional",
        "service_professionals",
        ["professional_id"],
    )
    op.create_index(
        "ix_service_professionals_tenant",
        "service_professionals",
        ["tenant_id"],
    )

    op.execute("ALTER TABLE service_professionals ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_select ON service_professionals
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_insert ON service_professionals
        FOR INSERT
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_update ON service_professionals
        FOR UPDATE
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_delete ON service_professionals
        FOR DELETE
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON service_professionals")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_insert ON service_professionals")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_update ON service_professionals")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_delete ON service_professionals")
    op.drop_index("ix_service_professionals_professional", "service_professionals")
    op.drop_index("ix_service_professionals_tenant", "service_professionals")
    op.drop_table("service_professionals")
