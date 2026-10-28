"""loyalty points and referrals

Customers earn points on completed bookings, spend them on new ones (the platform pays: the shop
earns the full price) and get a bonus for inviting friends.

Revision ID: e2a9b4c7d6f1
Revises: c5d1e8f2a7b4
Create Date: 2026-10-28 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e2a9b4c7d6f1'
down_revision: Union[str, Sequence[str], None] = 'c5d1e8f2a7b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('loyalty_entries',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('points', sa.Integer(), nullable=False),
    sa.Column('booking_id', sa.String(), nullable=True),
    sa.Column('note', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'kind', 'booking_id', name='uq_loyalty_user_kind_booking')
    )
    op.create_index(op.f('ix_loyalty_entries_booking_id'), 'loyalty_entries', ['booking_id'], unique=False)
    op.create_index(op.f('ix_loyalty_entries_user_id'), 'loyalty_entries', ['user_id'], unique=False)
    op.create_table('referral_codes',
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('code', sa.String(length=12), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('referrals',
    sa.Column('referee_id', sa.String(), nullable=False),
    sa.Column('referrer_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('rewarded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rewarded_booking_id', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('referee_id')
    )
    op.create_index(op.f('ix_referrals_referrer_id'), 'referrals', ['referrer_id'], unique=False)
    op.add_column('shop_earnings', sa.Column('platform_discount_cents', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('shop_earnings', 'platform_discount_cents')
    op.drop_index(op.f('ix_referrals_referrer_id'), table_name='referrals')
    op.drop_table('referrals')
    op.drop_table('referral_codes')
    op.drop_index(op.f('ix_loyalty_entries_user_id'), table_name='loyalty_entries')
    op.drop_index(op.f('ix_loyalty_entries_booking_id'), table_name='loyalty_entries')
    op.drop_table('loyalty_entries')
