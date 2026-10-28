"""waitlist

Customers wait for a fully booked day at a shop and are told when a time there opens up.

Revision ID: d4a7c9e2f1b5
Revises: b8e1f4a2c6d3
Create Date: 2026-10-29 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4a7c9e2f1b5'
down_revision: Union[str, Sequence[str], None] = 'b8e1f4a2c6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('waitlist_entries',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('customer_id', sa.String(), nullable=False),
    sa.Column('service_id', sa.String(), nullable=False),
    sa.Column('shop_id', sa.String(), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('customer_id', 'service_id', 'day', name='uq_waitlist_customer_service_day')
    )
    op.create_index(op.f('ix_waitlist_entries_customer_id'), 'waitlist_entries', ['customer_id'], unique=False)
    op.create_index('ix_waitlist_entries_shop_day', 'waitlist_entries', ['shop_id', 'day'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_waitlist_entries_shop_day', table_name='waitlist_entries')
    op.drop_index(op.f('ix_waitlist_entries_customer_id'), table_name='waitlist_entries')
    op.drop_table('waitlist_entries')
