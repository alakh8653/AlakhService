"""staff working hours

Each team member's own week; null keeps them on the shop's opening hours.

Revision ID: 9a4d2e6f1b73
Revises: 5f3b8c1d9e27
Create Date: 2026-10-30 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9a4d2e6f1b73'
down_revision: Union[str, Sequence[str], None] = '5f3b8c1d9e27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('staff_members', sa.Column('working_hours', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('staff_members', 'working_hours')
