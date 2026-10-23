"""dispute outcome and refunded amount

Revision ID: d58a1f3c6e72
Revises: 2e1de9055a8e
Create Date: 2026-10-23 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd58a1f3c6e72'
down_revision: Union[str, Sequence[str], None] = '2e1de9055a8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('disputes', sa.Column('outcome', sa.String(length=20), nullable=True))
    op.add_column('disputes', sa.Column('refund_amount_cents', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('disputes', 'refund_amount_cents')
    op.drop_column('disputes', 'outcome')
