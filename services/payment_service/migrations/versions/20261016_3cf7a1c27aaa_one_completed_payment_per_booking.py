"""one completed payment per booking

Revision ID: 3cf7a1c27aaa
Revises: 7c2e91a4b3d5
Create Date: 2026-10-16 20:18:38.793389

Fails on a database that already has a booking with two COMPLETED payments; refund or
correct those first (e.g. mark the extra one DUPLICATE) and run it again.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3cf7a1c27aaa'
down_revision: Union[str, Sequence[str], None] = '7c2e91a4b3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'uq_payments_booking_completed',
        'payments',
        ['booking_id'],
        unique=True,
        sqlite_where=sa.text("status = 'COMPLETED'"),
        postgresql_where=sa.text("status = 'COMPLETED'"),
    )


def downgrade() -> None:
    op.drop_index('uq_payments_booking_completed', table_name='payments')
