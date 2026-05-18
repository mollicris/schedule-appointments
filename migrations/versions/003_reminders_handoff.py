"""Reminders and human handoff support

Adds:
  - appointments.reminder_sent_at  — timestamp when the 24h reminder was sent
  - businesses.owner_whatsapp      — owner's personal WhatsApp for escalation alerts
  - human_transfers table          — tracks escalated conversations

Revision ID: 003
Revises: 002
Create Date: 2026-05-16

"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "003"
down_revision: str | Sequence[str] | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "businesses",
        sa.Column("owner_whatsapp", sa.String(20), nullable=True),
    )

    op.create_table(
        "human_transfers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "business_id",
            UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "client_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clients.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("context_snapshot", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_human_transfers_status", "human_transfers", ["status"])


def downgrade() -> None:
    op.drop_index("ix_human_transfers_status", table_name="human_transfers")
    op.drop_table("human_transfers")
    op.drop_column("businesses", "owner_whatsapp")
    op.drop_column("appointments", "reminder_sent_at")
