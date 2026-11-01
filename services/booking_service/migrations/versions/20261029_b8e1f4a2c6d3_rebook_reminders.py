"""rebook reminders

A few weeks after a completed visit the customer is asked once whether they want to book again.

Revision ID: b8e1f4a2c6d3
Revises: c41d7e9a2b58
Create Date: 2026-10-29 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8e1f4a2c6d3'
down_revision: Union[str, Sequence[str], None] = 'c41d7e9a2b58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('rebook_reminder_sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('bookings', 'rebook_reminder_sent_at')
