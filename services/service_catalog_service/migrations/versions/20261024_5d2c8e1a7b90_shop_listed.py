"""services of shops awaiting approval are kept out of browsing and search

Revision ID: 5d2c8e1a7b90
Revises: bdf07de16c0b
Create Date: 2026-10-24 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5d2c8e1a7b90'
down_revision: Union[str, Sequence[str], None] = 'bdf07de16c0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing shops were all migrated to APPROVED in shop_service, so their services stay listed.
    op.add_column('service_listings', sa.Column('shop_listed', sa.Boolean(), server_default=sa.true(), nullable=False))
    op.create_index(op.f('ix_service_listings_shop_listed'), 'service_listings', ['shop_listed'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_service_listings_shop_listed'), table_name='service_listings')
    op.drop_column('service_listings', 'shop_listed')
