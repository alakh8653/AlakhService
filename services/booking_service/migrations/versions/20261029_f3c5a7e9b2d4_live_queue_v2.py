"""live queue v2

Walk-ins, VIPs, check-in and manual order on bookings; who serves them and when it began (one customer
at a time per team member); per-shop queue settings, learnt service durations, team status and an
audit log of changes to the line.

Revision ID: f3c5a7e9b2d4
Revises: e6b2d8f4a1c7
Create Date: 2026-10-29 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f3c5a7e9b2d4'
down_revision: Union[str, Sequence[str], None] = 'e6b2d8f4a1c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IN_SERVICE = sa.text("status = 'IN_PROGRESS' AND served_by_staff_id IS NOT NULL")


def upgrade() -> None:
    op.add_column('bookings', sa.Column('source', sa.String(10), server_default='BOOKED', nullable=False))
    op.add_column('bookings', sa.Column('priority', sa.Integer(), server_default='1', nullable=False))
    op.add_column('bookings', sa.Column('checked_in_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bookings', sa.Column('queue_rank', sa.Float(), nullable=True))
    op.add_column('bookings', sa.Column('served_by_staff_id', sa.String(), nullable=True))
    op.add_column('bookings', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bookings', sa.Column('walk_in_name', sa.String(80), nullable=True))
    op.add_column('bookings', sa.Column('queue_notice_state', sa.Text(), nullable=True))
    op.create_index(
        'uq_bookings_one_in_service_per_staff',
        'bookings',
        ['shop_id', 'served_by_staff_id'],
        unique=True,
        postgresql_where=IN_SERVICE,
    )
    # Today's line at a shop is read on every look: by shop and time.
    op.create_index('ix_bookings_shop_scheduled', 'bookings', ['shop_id', 'scheduled_at'])
    op.create_table(
        'queue_settings',
        sa.Column('shop_id', sa.String(), primary_key=True),
        sa.Column('buffer_pct', sa.Float(), server_default='0', nullable=False),
        sa.Column('alpha', sa.Float(), server_default='0.2', nullable=False),
        sa.Column('grace_minutes', sa.Integer(), server_default='10', nullable=False),
        sa.Column('aging_minutes', sa.Integer(), server_default='20', nullable=False),
        sa.Column('check_in_required', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('vip_per_day', sa.Integer(), server_default='5', nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'duration_stats',
        sa.Column('shop_id', sa.String(), primary_key=True),
        sa.Column('service_id', sa.String(), primary_key=True),
        sa.Column('staff_id', sa.String(), primary_key=True),
        sa.Column('mean', sa.Float(), nullable=False),
        sa.Column('var', sa.Float(), nullable=False),
        sa.Column('n', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'worker_status',
        sa.Column('shop_id', sa.String(), primary_key=True),
        sa.Column('staff_id', sa.String(), primary_key=True),
        sa.Column('status', sa.String(10), nullable=False),
        sa.Column('until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'queue_audit',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('shop_id', sa.String(), nullable=False),
        sa.Column('booking_id', sa.String(), nullable=True),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('actor_id', sa.String(), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_queue_audit_shop_id', 'queue_audit', ['shop_id'])


def downgrade() -> None:
    op.drop_index('ix_queue_audit_shop_id', table_name='queue_audit')
    op.drop_table('queue_audit')
    op.drop_table('worker_status')
    op.drop_table('duration_stats')
    op.drop_table('queue_settings')
    op.drop_index('ix_bookings_shop_scheduled', table_name='bookings')
    op.drop_index('uq_bookings_one_in_service_per_staff', table_name='bookings')
    for column in (
        'queue_notice_state',
        'walk_in_name',
        'started_at',
        'served_by_staff_id',
        'queue_rank',
        'checked_in_at',
        'priority',
        'source',
    ):
        op.drop_column('bookings', column)
