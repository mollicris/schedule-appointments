"""Add Messenger / Instagram credentials and lead kind

  - businesses.facebook_page_id, facebook_page_access_token,
    instagram_account_id, meta_app_secret — one Facebook Page serves both
    Messenger and Instagram Direct, so they share the page token. The two ids
    are indexed because inbound webhooks resolve the business by them.
  - human_transfers.kind — the same queue now holds two things: 'escalation'
    (the bot handed the conversation over and went quiet) and 'lead' (someone
    on social left their details; the bot keeps chatting).

Revision ID: 012
Revises: 011
Create Date: 2026-07-31

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str | Sequence[str] | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("businesses", sa.Column("facebook_page_id", sa.String(64), nullable=True))
    op.add_column(
        "businesses", sa.Column("facebook_page_access_token", sa.String(512), nullable=True)
    )
    op.add_column("businesses", sa.Column("instagram_account_id", sa.String(64), nullable=True))
    op.add_column("businesses", sa.Column("meta_app_secret", sa.String(255), nullable=True))

    op.create_index("ix_businesses_facebook_page_id", "businesses", ["facebook_page_id"])
    op.create_index("ix_businesses_instagram_account_id", "businesses", ["instagram_account_id"])

    op.add_column(
        "human_transfers",
        sa.Column("kind", sa.String(20), nullable=False, server_default="escalation"),
    )
    op.create_index("ix_human_transfers_kind", "human_transfers", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_human_transfers_kind", table_name="human_transfers")
    op.drop_column("human_transfers", "kind")

    op.drop_index("ix_businesses_instagram_account_id", table_name="businesses")
    op.drop_index("ix_businesses_facebook_page_id", table_name="businesses")
    op.drop_column("businesses", "meta_app_secret")
    op.drop_column("businesses", "instagram_account_id")
    op.drop_column("businesses", "facebook_page_access_token")
    op.drop_column("businesses", "facebook_page_id")
