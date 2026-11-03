"""each service has its own type of work, for a shop that does more than one

Revision ID: c3f18a6d2b47
Revises: 7e4b1c9a2f60
Create Date: 2026-11-03 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3f18a6d2b47'
down_revision: Union[str, Sequence[str], None] = '7e4b1c9a2f60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Null on existing services: they stay under their shop's main type.
    op.add_column('service_listings', sa.Column('service_type', sa.String(), nullable=True))
    op.create_index(op.f('ix_service_listings_service_type'), 'service_listings', ['service_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_service_listings_service_type'), table_name='service_listings')
    op.drop_column('service_listings', 'service_type')
