"""Add capacity to services (group classes)

Adds one column needed to support group classes (gyms, workshops):
  - services.capacity (INTEGER, NOT NULL, default 1)
    How many clients can book the same start time for this service.

capacity = 1 (the default) reproduces the current behaviour exactly: any
overlapping appointment blocks the slot. capacity > 1 turns the service into a
group class: the slot stays open while booked < capacity.

Revision ID: 008
Revises: 007
Create Date: 2026-07-31

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | Sequence[str] | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("services", "capacity")
