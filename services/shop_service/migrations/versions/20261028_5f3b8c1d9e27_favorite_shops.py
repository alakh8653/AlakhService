"""favorite shops

Customers save shops they like, to find and book them again quickly.

Revision ID: 5f3b8c1d9e27
Revises: 7c1e5a9b2d44
Create Date: 2026-10-28 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f3b8c1d9e27'
down_revision: Union[str, Sequence[str], None] = '7c1e5a9b2d44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('favorite_shops',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('shop_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['shop_id'], ['shops.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'shop_id', name='uq_favorite_shops_user_shop')
    )
    op.create_index(op.f('ix_favorite_shops_shop_id'), 'favorite_shops', ['shop_id'], unique=False)
    op.create_index(op.f('ix_favorite_shops_user_id'), 'favorite_shops', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_favorite_shops_user_id'), table_name='favorite_shops')
    op.drop_index(op.f('ix_favorite_shops_shop_id'), table_name='favorite_shops')
    op.drop_table('favorite_shops')
