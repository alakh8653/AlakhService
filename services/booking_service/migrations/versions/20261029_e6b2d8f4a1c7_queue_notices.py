"""queue notices

On the day, customers are told once when their turn is near and once if the shop is running late.

Revision ID: e6b2d8f4a1c7
Revises: d4a7c9e2f1b5
Create Date: 2026-10-29 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e6b2d8f4a1c7'
down_revision: Union[str, Sequence[str], None] = 'd4a7c9e2f1b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('turn_soon_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bookings', sa.Column('running_late_sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('bookings', 'running_late_sent_at')
    op.drop_column('bookings', 'turn_soon_sent_at')
