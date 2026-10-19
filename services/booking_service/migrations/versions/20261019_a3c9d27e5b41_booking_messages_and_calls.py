"""booking messages and masked calls

Revision ID: a3c9d27e5b41
Revises: 1607721714ca
Create Date: 2026-10-19 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c9d27e5b41'
down_revision: Union[str, Sequence[str], None] = '1607721714ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'booking_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('booking_id', sa.String(), nullable=False),
        sa.Column('sender_id', sa.String(), nullable=False),
        sa.Column('sender_role', sa.String(length=20), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('flagged', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('flag_reasons', sa.String(length=100), nullable=True),
        sa.Column('original_body', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_booking_messages_booking_created', 'booking_messages', ['booking_id', 'created_at'])
    op.create_index('ix_booking_messages_flagged_created', 'booking_messages', ['flagged', 'created_at'])
    op.create_index(op.f('ix_booking_messages_sender_id'), 'booking_messages', ['sender_id'])
    op.create_table(
        'booking_calls',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('booking_id', sa.String(), nullable=False),
        sa.Column('caller_id', sa.String(), nullable=False),
        sa.Column('callee_role', sa.String(length=20), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('provider_call_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_booking_calls_booking_id'), 'booking_calls', ['booking_id'])
    op.create_index(op.f('ix_booking_calls_caller_id'), 'booking_calls', ['caller_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_booking_calls_caller_id'), table_name='booking_calls')
    op.drop_index(op.f('ix_booking_calls_booking_id'), table_name='booking_calls')
    op.drop_table('booking_calls')
    op.drop_index(op.f('ix_booking_messages_sender_id'), table_name='booking_messages')
    op.drop_index('ix_booking_messages_flagged_created', table_name='booking_messages')
    op.drop_index('ix_booking_messages_booking_created', table_name='booking_messages')
    op.drop_table('booking_messages')
