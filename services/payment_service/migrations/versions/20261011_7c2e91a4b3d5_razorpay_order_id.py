"""razorpay order id on payments

Revision ID: 7c2e91a4b3d5
Revises: da31f4d875d8
Create Date: 2026-10-11 14:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7c2e91a4b3d5'
down_revision: Union[str, Sequence[str], None] = 'da31f4d875d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payments', sa.Column('provider_order_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_payments_provider_order_id'), 'payments', ['provider_order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_provider_order_id'), table_name='payments')
    op.drop_column('payments', 'provider_order_id')
