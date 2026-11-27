"""shop prepayment

A shop can ask customers to pay online when they book (no-show protection). Off for every existing shop.

Revision ID: a4c6e8b0d2f1
Revises: e1a7c42f9d05
Create Date: 2026-11-28 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4c6e8b0d2f1"
down_revision: Union[str, Sequence[str], None] = "e1a7c42f9d05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shop_schedule_settings",
        sa.Column("require_prepayment", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("shop_schedule_settings", "require_prepayment")
