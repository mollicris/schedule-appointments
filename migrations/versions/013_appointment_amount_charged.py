"""Record what an appointment actually collected

  - appointments.amount_charged — in cents, like every other amount in the
    system (services.price, memberships.price_paid). Written when the staff
    closes the appointment. Nullable because rows created before this migration
    were never closed; from here on every completed appointment carries one.
  - appointments.completed_at — when it was actually attended, which is neither
    scheduled_at nor updated_at.

Until now the revenue reports summed services.price, the *current* price: a
price change rewrote months already closed. Reading the amount off the
appointment freezes it.

Also creates two indexes the model declares but 001 never created. Every report
filters by (business_id, scheduled_at), and the per-professional one groups by
professional_id.

Revision ID: 013
Revises: 012
Create Date: 2026-08-08

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | Sequence[str] | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("amount_charged", sa.Integer(), nullable=True))
    op.add_column(
        "appointments",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # IF NOT EXISTS on purpose: a database built from the migrations lacks both
    # indexes, but one built from sql/001_schema_completo.sql (which was dumped
    # from the models, where they are declared) already has the per-column ones.
    # The migration has to land on either without failing.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_appointments_business_scheduled "
        "ON appointments (business_id, scheduled_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_appointments_professional_id "
        "ON appointments (professional_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_appointments_professional_id")
    op.execute("DROP INDEX IF EXISTS ix_appointments_business_scheduled")
    op.drop_column("appointments", "completed_at")
    op.drop_column("appointments", "amount_charged")
