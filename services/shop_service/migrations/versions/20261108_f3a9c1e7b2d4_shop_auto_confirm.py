"""shop auto confirm

A shop can have each booking confirmed at once while a place is free. Off for every existing shop.

Revision ID: f3a9c1e7b2d4
Revises: b6e1c9d4a2f8
Create Date: 2026-11-08 21:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c1e7b2d4"
down_revision: Union[str, Sequence[str], None] = "b6e1c9d4a2f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shop_schedule_settings",
        sa.Column("auto_confirm", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("shop_schedule_settings", "auto_confirm")
