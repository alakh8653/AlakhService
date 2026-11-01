"""service packages

Shops sell prepaid packages of visits; customers book each visit with one, and the shop earns each
visit's share of the price when it is completed.

Revision ID: f7c3d2b1a9e8
Revises: e2a9b4c7d6f1
Create Date: 2026-10-28 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f7c3d2b1a9e8'
down_revision: Union[str, Sequence[str], None] = 'e2a9b4c7d6f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('service_packages',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('shop_id', sa.String(), nullable=False),
    sa.Column('service_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('visits', sa.Integer(), nullable=False),
    sa.Column('price_cents', sa.Integer(), nullable=False),
    sa.Column('valid_days', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_service_packages_service_id'), 'service_packages', ['service_id'], unique=False)
    op.create_index(op.f('ix_service_packages_shop_id'), 'service_packages', ['shop_id'], unique=False)
    op.create_table('package_purchases',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('package_id', sa.String(), nullable=False),
    sa.Column('customer_id', sa.String(), nullable=False),
    sa.Column('shop_id', sa.String(), nullable=False),
    sa.Column('service_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('visits_total', sa.Integer(), nullable=False),
    sa.Column('visits_left', sa.Integer(), nullable=False),
    sa.Column('price_cents', sa.Integer(), nullable=False),
    sa.Column('valid_days', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('payment_id', sa.String(), nullable=True),
    sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['package_id'], ['service_packages.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_package_purchases_customer_id'), 'package_purchases', ['customer_id'], unique=False)
    op.create_index(op.f('ix_package_purchases_package_id'), 'package_purchases', ['package_id'], unique=False)
    op.create_index(op.f('ix_package_purchases_shop_id'), 'package_purchases', ['shop_id'], unique=False)
    op.create_table('package_redemptions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('purchase_id', sa.String(), nullable=False),
    sa.Column('booking_id', sa.String(), nullable=False),
    sa.Column('visit_value_cents', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['purchase_id'], ['package_purchases.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('booking_id')
    )
    op.create_index(op.f('ix_package_redemptions_purchase_id'), 'package_redemptions', ['purchase_id'], unique=False)


def downgrade() -> None:
    # Packages are money customers paid: refusing beats deleting them.
    bought = op.get_bind().execute(sa.text("SELECT count(*) FROM package_purchases WHERE status != 'PENDING'")).scalar()
    if bought:
        raise RuntimeError(f"{bought} package purchase(s) exist; settle and archive them before downgrading")
    op.drop_index(op.f('ix_package_redemptions_purchase_id'), table_name='package_redemptions')
    op.drop_table('package_redemptions')
    op.drop_index(op.f('ix_package_purchases_shop_id'), table_name='package_purchases')
    op.drop_index(op.f('ix_package_purchases_package_id'), table_name='package_purchases')
    op.drop_index(op.f('ix_package_purchases_customer_id'), table_name='package_purchases')
    op.drop_table('package_purchases')
    op.drop_index(op.f('ix_service_packages_shop_id'), table_name='service_packages')
    op.drop_index(op.f('ix_service_packages_service_id'), table_name='service_packages')
    op.drop_table('service_packages')
