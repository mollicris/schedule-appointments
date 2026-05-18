"""Support multiple time ranges per business day

Allows configuring breaks during operating hours (e.g., 09:00-12:00 lunch 12:00-14:00 14:00-18:00).

Changes:
  - Add sequence column to track range order within a day
  - Replace unique constraint on (business_id, day_of_week) with (business_id, day_of_week, sequence)
  - Update repository to properly handle multiple ranges

Revision ID: 004
Revises: 003
Create Date: 2026-05-17

"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | Sequence[str] | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── business_hours: add sequence for multiple ranges per day ───────────────
    op.add_column(
        "business_hours",
        sa.Column("sequence", sa.Integer, nullable=False, server_default="1"),
    )

    # Drop old unique constraint
    op.drop_constraint(
        "uq_business_hours_business_day",
        "business_hours",
        type_="unique",
    )

    # Add new unique constraint allowing multiple entries per day
    op.create_unique_constraint(
        "uq_business_hours_business_day_sequence",
        "business_hours",
        ["business_id", "day_of_week", "sequence"],
    )


def downgrade() -> None:
    # Drop new constraint
    op.drop_constraint(
        "uq_business_hours_business_day_sequence",
        "business_hours",
        type_="unique",
    )

    # Restore old constraint (will fail if multiple ranges exist for same day)
    op.create_unique_constraint(
        "uq_business_hours_business_day",
        "business_hours",
        ["business_id", "day_of_week"],
    )

    # Remove sequence column
    op.drop_column("business_hours", "sequence")
