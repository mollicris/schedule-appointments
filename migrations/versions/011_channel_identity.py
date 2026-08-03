"""Add channel identity to clients, conversations and messages

Prepares the data model for Messenger and Instagram alongside WhatsApp:

  - clients.channel + clients.external_id — identity is now (channel,
    external_id): the phone number on WhatsApp, the page-scoped id (PSID/IGSID)
    on Meta's social inboxes. Existing rows are backfilled with
    channel='whatsapp' and external_id=whatsapp_number, so nothing changes for
    them, and a unique index enforces one client per identity per tenant (the
    constraint that until now only existed as a comment in the ORM model).
  - clients.whatsapp_number becomes nullable: a client who writes from
    Instagram has no phone number until they give one.
  - conversations.channel — for filtering and reporting.
  - messages.whatsapp_message_id renamed to external_message_id: Messenger's
    `mid` plays the same role as WhatsApp's `wamid` for idempotency. The unique
    index is preserved (Meta redelivers webhooks).

Revision ID: 011
Revises: 010
Create Date: 2026-07-31

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str | Sequence[str] | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── clients ─────────────────────────────────────────────────────────────
    op.add_column(
        "clients",
        sa.Column("channel", sa.String(20), nullable=False, server_default="whatsapp"),
    )
    op.add_column("clients", sa.Column("external_id", sa.String(64), nullable=True))

    # Backfill before adding the NOT NULL and the unique index
    op.execute("UPDATE clients SET external_id = whatsapp_number WHERE external_id IS NULL")

    op.alter_column("clients", "external_id", nullable=False)
    op.alter_column("clients", "whatsapp_number", existing_type=sa.String(20), nullable=True)

    op.create_index("ix_clients_external_id", "clients", ["external_id"])
    op.create_unique_constraint(
        "uq_clients_tenant_channel_external",
        "clients",
        ["tenant_id", "channel", "external_id"],
    )

    # ── conversations ───────────────────────────────────────────────────────
    op.add_column(
        "conversations",
        sa.Column("channel", sa.String(20), nullable=False, server_default="whatsapp"),
    )

    # ── messages ────────────────────────────────────────────────────────────
    op.alter_column("messages", "whatsapp_message_id", new_column_name="external_message_id")


def downgrade() -> None:
    op.alter_column("messages", "external_message_id", new_column_name="whatsapp_message_id")

    op.drop_column("conversations", "channel")

    op.drop_constraint("uq_clients_tenant_channel_external", "clients", type_="unique")
    op.drop_index("ix_clients_external_id", table_name="clients")
    # Social clients have no phone number, so they would violate NOT NULL.
    op.execute("DELETE FROM clients WHERE channel <> 'whatsapp'")
    op.execute("UPDATE clients SET whatsapp_number = '' WHERE whatsapp_number IS NULL")
    op.alter_column("clients", "whatsapp_number", existing_type=sa.String(20), nullable=False)
    op.drop_column("clients", "external_id")
    op.drop_column("clients", "channel")
