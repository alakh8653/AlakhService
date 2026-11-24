"""a shop can do more than one type of work

Revision ID: e1a7c42f9d05
Revises: f3a9c1e7b2d4
Create Date: 2026-11-24 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1a7c42f9d05'
down_revision: Union[str, Sequence[str], None] = 'f3a9c1e7b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('shops', sa.Column('extra_categories', sa.String(length=500), server_default='', nullable=False))


def downgrade() -> None:
    op.drop_column('shops', 'extra_categories')
