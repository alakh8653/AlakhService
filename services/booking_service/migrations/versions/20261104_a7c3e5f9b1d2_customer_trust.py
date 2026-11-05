"""customer trust

Start codes for home visits and pickups (with a count of wrong tries), free fixes (rework) within
the shop's guarantee, shared visit links and SOS alerts.

Open home visits and pickups made before this get a start code, so they too start only with one.

Revision ID: a7c3e5f9b1d2
Revises: b9e1c4d7a2f3
Create Date: 2026-11-04 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c3e5f9b1d2'
down_revision: Union[str, Sequence[str], None] = 'b9e1c4d7a2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('start_code', sa.String(length=4), nullable=True))
    op.add_column('bookings', sa.Column('start_code_tries', sa.Integer(), server_default='0', nullable=False))
    op.add_column('bookings', sa.Column('start_code_tries_since', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bookings', sa.Column('guarantee_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bookings', sa.Column('rework_of', sa.String(), nullable=True))
    op.add_column('bookings', sa.Column('rework_booking_id', sa.String(), nullable=True))
    op.create_unique_constraint('uq_bookings_rework_of', 'bookings', ['rework_of'])
    op.execute(
        "UPDATE bookings SET start_code = lpad(floor(random() * 10000)::int::text, 4, '0') "
        "WHERE service_mode IN ('AT_HOME', 'PICKUP_DROP') "
        "AND status IN ('PENDING', 'CONFIRMED', 'ASSIGNED', 'PROVIDER_EN_ROUTE')"
    )

    op.create_table('booking_shares',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('booking_id', sa.String(), nullable=False),
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('created_by', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('booking_id'),
    sa.UniqueConstraint('token')
    )

    op.create_table('sos_alerts',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('booking_id', sa.String(), nullable=False),
    sa.Column('raised_by', sa.String(), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('lat', sa.Float(), nullable=True),
    sa.Column('lng', sa.Float(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sos_alerts_booking_created', 'sos_alerts', ['booking_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_sos_alerts_booking_created', table_name='sos_alerts')
    op.drop_table('sos_alerts')
    op.drop_table('booking_shares')
    op.drop_constraint('uq_bookings_rework_of', 'bookings', type_='unique')
    op.drop_column('bookings', 'rework_booking_id')
    op.drop_column('bookings', 'rework_of')
    op.drop_column('bookings', 'guarantee_until')
    op.drop_column('bookings', 'start_code_tries_since')
    op.drop_column('bookings', 'start_code_tries')
    op.drop_column('bookings', 'start_code')
