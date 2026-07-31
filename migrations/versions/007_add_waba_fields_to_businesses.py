"""Add whatsapp_waba_id and whatsapp_access_token to businesses

Adds two columns needed for the WhatsApp Embedded Signup OAuth flow:
  - businesses.whatsapp_waba_id      (VARCHAR 64, nullable, indexed)
    WhatsApp Business Account ID returned by Meta after Embedded Signup.
  - businesses.whatsapp_access_token  (VARCHAR 512, nullable)
    Long-lived user access token (60 days) used to call the Graph API
    on behalf of the tenant. Store encrypted in production.

Revision ID: 007
Revises: 006
Create Date: 2026-05-18

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | Sequence[str] | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("whatsapp_waba_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("whatsapp_access_token", sa.String(512), nullable=True),
    )
    op.create_index(
        "ix_businesses_whatsapp_waba_id",
        "businesses",
        ["whatsapp_waba_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_businesses_whatsapp_waba_id", table_name="businesses")
    op.drop_column("businesses", "whatsapp_access_token")
    op.drop_column("businesses", "whatsapp_waba_id")
