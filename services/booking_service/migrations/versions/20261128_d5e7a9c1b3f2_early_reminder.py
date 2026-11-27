"""early reminder

A reminder three days before a visit booked well ahead, alongside the 24-hour and one-hour ones.

Revision ID: d5e7a9c1b3f2
Revises: c2d4f6a8b0e1
Create Date: 2026-11-28 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e7a9c1b3f2"
down_revision: Union[str, Sequence[str], None] = "c2d4f6a8b0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("reminder_3d_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "reminder_3d_sent_at")
