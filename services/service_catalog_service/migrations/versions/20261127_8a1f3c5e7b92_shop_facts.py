"""where each service's shop is and how it is rated, for filters and sorting

Revision ID: 8a1f3c5e7b92
Revises: 7e4b1c9a2f60
Create Date: 2026-11-27 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8a1f3c5e7b92'
down_revision: Union[str, Sequence[str], None] = '7e4b1c9a2f60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Filled in for existing services by shop_service's regular listing sync.
    op.add_column('service_listings', sa.Column('shop_latitude', sa.Float(), nullable=True))
    op.add_column('service_listings', sa.Column('shop_longitude', sa.Float(), nullable=True))
    op.add_column('service_listings', sa.Column('shop_rating', sa.Float(), server_default='0', nullable=False))
    op.add_column('service_listings', sa.Column('shop_rating_count', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('service_listings', 'shop_rating_count')
    op.drop_column('service_listings', 'shop_rating')
    op.drop_column('service_listings', 'shop_longitude')
    op.drop_column('service_listings', 'shop_latitude')
