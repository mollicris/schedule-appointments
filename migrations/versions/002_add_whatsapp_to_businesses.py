"""Add WhatsApp fields to businesses; fix missing indices and constraints

Adds:
  - businesses.whatsapp_phone_number_id  (VARCHAR 64, nullable, indexed)
    Used by the webhook to resolve which tenant/business owns an inbound message.
  - businesses.whatsapp_app_secret       (VARCHAR 255, nullable)
    Used to verify the HMAC-SHA256 signature on inbound webhook payloads.

Also fixes two omissions from 001:
  - Index on appointments.professional_id (FK without index hurts JOIN performance)
  - UniqueConstraint on business_hours(business_id, day_of_week) which the
    PostgreSQL upsert (INSERT … ON CONFLICT DO UPDATE) requires to exist.

Revision ID: 002
Revises: 001
Create Date: 2026-05-16

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | Sequence[str] | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── businesses: WhatsApp integration fields ───────────────────────────────
    op.add_column(
        "businesses",
        sa.Column("whatsapp_phone_number_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("whatsapp_app_secret", sa.String(255), nullable=True),
    )
    # Index for fast webhook tenant resolution (global lookup, no tenant scope)
    op.create_index(
        "ix_businesses_whatsapp_phone_number_id",
        "businesses",
        ["whatsapp_phone_number_id"],
    )

    # ── appointments: missing professional_id index ───────────────────────────
    op.create_index(
        "ix_appointments_professional_id",
        "appointments",
        ["professional_id"],
    )

    # ── business_hours: unique constraint required by upsert ──────────────────
    op.create_unique_constraint(
        "uq_business_hours_business_day",
        "business_hours",
        ["business_id", "day_of_week"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_business_hours_business_day", "business_hours", type_="unique")
    op.drop_index("ix_appointments_professional_id", table_name="appointments")
    op.drop_index("ix_businesses_whatsapp_phone_number_id", table_name="businesses")
    op.drop_column("businesses", "whatsapp_app_secret")
    op.drop_column("businesses", "whatsapp_phone_number_id")
