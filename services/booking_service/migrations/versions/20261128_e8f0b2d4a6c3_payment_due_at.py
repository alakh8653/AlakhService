"""payment due at

At a shop that asks customers to pay when they book, when an unpaid booking is released.

Revision ID: e8f0b2d4a6c3
Revises: d5e7a9c1b3f2
Create Date: 2026-11-28 10:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f0b2d4a6c3"
down_revision: Union[str, Sequence[str], None] = "d5e7a9c1b3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("payment_due_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "payment_due_at")
