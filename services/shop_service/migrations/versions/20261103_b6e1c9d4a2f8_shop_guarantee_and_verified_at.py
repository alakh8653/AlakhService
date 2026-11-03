"""shop guarantee and verified_at

The free-fix period a shop promises after a completed booking (guarantee_days, 0-90, 7 by default),
and when the shop was approved (verified_at, for the "Verified" badge). Shops approved before this get
their review time as verified_at.

Revision ID: b6e1c9d4a2f8
Revises: 9a4d2e6f1b73
Create Date: 2026-11-03 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b6e1c9d4a2f8'
down_revision: Union[str, Sequence[str], None] = '9a4d2e6f1b73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('shops', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('shops', sa.Column('guarantee_days', sa.Integer(), server_default='7', nullable=False))
    op.execute(
        "UPDATE shops SET verified_at = COALESCE(reviewed_at, created_at) WHERE verification_status = 'APPROVED'"
    )


def downgrade() -> None:
    op.drop_column('shops', 'guarantee_days')
    op.drop_column('shops', 'verified_at')
