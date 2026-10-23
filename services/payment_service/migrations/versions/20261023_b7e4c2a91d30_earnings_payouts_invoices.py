"""shop earnings, commission rates, payouts and invoice numbers

Revision ID: b7e4c2a91d30
Revises: 3cf7a1c27aaa
Create Date: 2026-10-23 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7e4c2a91d30'
down_revision: Union[str, Sequence[str], None] = '3cf7a1c27aaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payments', sa.Column('shop_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_payments_shop_id'), 'payments', ['shop_id'], unique=False)
    op.add_column('payments', sa.Column('invoice_number', sa.String(), nullable=True))
    op.add_column('payments', sa.Column('invoice_issued_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_payments_invoice_number', 'payments', ['invoice_number'])
    op.add_column('refunds', sa.Column('idempotency_key', sa.String(), nullable=True))
    op.create_unique_constraint('uq_refunds_idempotency_key', 'refunds', ['idempotency_key'])

    op.create_table(
        'commission_rates',
        sa.Column('shop_id', sa.String(), nullable=False),
        sa.Column('commission_percent', sa.Numeric(5, 2), nullable=False),
        sa.Column('updated_by', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('shop_id'),
    )
    op.create_table(
        'invoice_sequences',
        sa.Column('series', sa.String(), nullable=False),
        sa.Column('last_number', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('series'),
    )
    op.create_table(
        'payouts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('batch_id', sa.String(), nullable=False),
        sa.Column('shop_id', sa.String(), nullable=False),
        sa.Column('period_from', sa.Date(), nullable=True),
        sa.Column('period_to', sa.Date(), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payouts_batch_id'), 'payouts', ['batch_id'], unique=False)
    op.create_index(op.f('ix_payouts_shop_id'), 'payouts', ['shop_id'], unique=False)
    op.create_table(
        'shop_earnings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('booking_id', sa.String(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('payment_id', sa.String(), nullable=True),
        sa.Column('shop_id', sa.String(), nullable=False),
        sa.Column('collection', sa.String(length=10), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('gross_cents', sa.Integer(), nullable=False),
        sa.Column('commission_percent', sa.Numeric(5, 2), nullable=False),
        sa.Column('gst_percent', sa.Numeric(5, 2), nullable=False),
        sa.Column('commission_cents', sa.Integer(), nullable=False),
        sa.Column('gst_cents', sa.Integer(), nullable=False),
        sa.Column('net_cents', sa.Integer(), nullable=False),
        sa.Column('payout_cents', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('payout_id', sa.String(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['payout_id'], ['payouts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('booking_id', 'kind', name='uq_shop_earnings_booking_kind'),
    )
    op.create_index(op.f('ix_shop_earnings_booking_id'), 'shop_earnings', ['booking_id'], unique=False)
    op.create_index(op.f('ix_shop_earnings_shop_id'), 'shop_earnings', ['shop_id'], unique=False)
    op.create_index(op.f('ix_shop_earnings_payout_id'), 'shop_earnings', ['payout_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_shop_earnings_payout_id'), table_name='shop_earnings')
    op.drop_index(op.f('ix_shop_earnings_shop_id'), table_name='shop_earnings')
    op.drop_index(op.f('ix_shop_earnings_booking_id'), table_name='shop_earnings')
    op.drop_table('shop_earnings')
    op.drop_index(op.f('ix_payouts_shop_id'), table_name='payouts')
    op.drop_index(op.f('ix_payouts_batch_id'), table_name='payouts')
    op.drop_table('payouts')
    op.drop_table('invoice_sequences')
    op.drop_table('commission_rates')
    op.drop_constraint('uq_refunds_idempotency_key', 'refunds', type_='unique')
    op.drop_column('refunds', 'idempotency_key')
    op.drop_constraint('uq_payments_invoice_number', 'payments', type_='unique')
    op.drop_column('payments', 'invoice_issued_at')
    op.drop_column('payments', 'invoice_number')
    op.drop_index(op.f('ix_payments_shop_id'), table_name='payments')
    op.drop_column('payments', 'shop_id')
