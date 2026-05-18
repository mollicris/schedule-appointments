"""Make professional user_id optional

Allows creating professionals from the dashboard without a linked user account.

Revision ID: 005
Revises: 004
Create Date: 2026-05-17

"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | Sequence[str] | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("professionals", "user_id", nullable=True)


def downgrade() -> None:
    # Set NULLs to a sentinel before re-adding NOT NULL (data may be lost)
    op.execute(
        "DELETE FROM professionals WHERE user_id IS NULL"
    )
    op.alter_column("professionals", "user_id", nullable=False)
