"""services are filed under their shop's type of work, for browsing by type

Revision ID: 7e4b1c9a2f60
Revises: 5d2c8e1a7b90
Create Date: 2026-11-03 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7e4b1c9a2f60'
down_revision: Union[str, Sequence[str], None] = '5d2c8e1a7b90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Filled in for existing services by shop_service's regular listing sync.
    op.add_column('service_listings', sa.Column('shop_category', sa.String(), nullable=True))
    op.create_index(op.f('ix_service_listings_shop_category'), 'service_listings', ['shop_category'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_service_listings_shop_category'), table_name='service_listings')
    op.drop_column('service_listings', 'shop_category')
