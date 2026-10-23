"""payment status, reminder flags and the payment outbox

Revision ID: c41d7e9a2b58
Revises: a3c9d27e5b41
Create Date: 2026-10-23 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c41d7e9a2b58'
down_revision: Union[str, Sequence[str], None] = 'a3c9d27e5b41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'bookings', sa.Column('payment_status', sa.String(length=20), server_default='UNPAID', nullable=False)
    )
    op.add_column('bookings', sa.Column('reminder_24h_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bookings', sa.Column('reminder_1h_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        'payment_outbox',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('booking_id', sa.String(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('booking_id', 'kind', name='uq_payment_outbox_booking_kind'),
    )
    op.create_index(op.f('ix_payment_outbox_booking_id'), 'payment_outbox', ['booking_id'], unique=False)
    op.create_index(op.f('ix_payment_outbox_next_attempt_at'), 'payment_outbox', ['next_attempt_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payment_outbox_next_attempt_at'), table_name='payment_outbox')
    op.drop_index(op.f('ix_payment_outbox_booking_id'), table_name='payment_outbox')
    op.drop_table('payment_outbox')
    op.drop_column('bookings', 'reminder_1h_sent_at')
    op.drop_column('bookings', 'reminder_24h_sent_at')
    op.drop_column('bookings', 'payment_status')
