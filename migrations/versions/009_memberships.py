"""Add membership plans and client memberships

Three tables for the gym module:
  - membership_plans          What the business sells (name, price, period).
  - membership_plan_services  Which services a plan includes. No rows for a
                              plan = the plan includes every service (same
                              convention as service_professionals).
  - memberships               A client's membership: validity window, snapshot
                              of the period and price paid, freeze bookkeeping.

Named membership_* on purpose: tenants.plan is the SaaS plan the business pays
us, a different concept.

A partial unique index guarantees a client cannot hold two live memberships at
the same business; renewing extends the existing one instead.

RLS is enabled with the same four tenant_isolation_* policies as 001/006.

Revision ID: 009
Revises: 008
Create Date: 2026-07-31

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: str | Sequence[str] | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_TABLES = ("membership_plans", "membership_plan_services", "memberships")


def upgrade() -> None:
    op.create_table(
        "membership_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(127), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billing_period", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_membership_plans_tenant", "membership_plans", ["tenant_id"])
    op.create_index("ix_membership_plans_business", "membership_plans", ["business_id"])

    op.create_table(
        "membership_plan_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_plan_id"], ["membership_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "membership_plan_id", "service_id", name="uq_membership_plan_services_plan_service"
        ),
    )
    op.create_index("ix_membership_plan_services_tenant", "membership_plan_services", ["tenant_id"])
    op.create_index("ix_membership_plan_services_plan", "membership_plan_services", ["membership_plan_id"])
    op.create_index("ix_membership_plan_services_service", "membership_plan_services", ["service_id"])

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("billing_period", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("price_paid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("frozen_days_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("renewal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["membership_plan_id"], ["membership_plans.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memberships_tenant", "memberships", ["tenant_id"])
    op.create_index("ix_memberships_business", "memberships", ["business_id"])
    op.create_index("ix_memberships_client", "memberships", ["client_id"])
    op.create_index("ix_memberships_ends_at", "memberships", ["ends_at"])
    # One live membership per client and business; renewals extend it.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_memberships_one_live_per_client
        ON memberships (tenant_id, business_id, client_id)
        WHERE status IN ('active', 'frozen')
        """
    )

    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_select ON {table}
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_insert ON {table}
            FOR INSERT
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_update ON {table}
            FOR UPDATE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_delete ON {table}
            FOR DELETE
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            """
        )


def downgrade() -> None:
    for table in _RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_delete ON {table}")

    op.execute("DROP INDEX IF EXISTS uq_memberships_one_live_per_client")
    op.drop_index("ix_memberships_ends_at", "memberships")
    op.drop_index("ix_memberships_client", "memberships")
    op.drop_index("ix_memberships_business", "memberships")
    op.drop_index("ix_memberships_tenant", "memberships")
    op.drop_table("memberships")

    op.drop_index("ix_membership_plan_services_service", "membership_plan_services")
    op.drop_index("ix_membership_plan_services_plan", "membership_plan_services")
    op.drop_index("ix_membership_plan_services_tenant", "membership_plan_services")
    op.drop_table("membership_plan_services")

    op.drop_index("ix_membership_plans_business", "membership_plans")
    op.drop_index("ix_membership_plans_tenant", "membership_plans")
    op.drop_table("membership_plans")
