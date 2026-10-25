"""booking idempotency key

Revision ID: 1607721714ca
Revises: cd4216b31ff9
Create Date: 2026-10-17 05:16:17.292104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1607721714ca'
down_revision: Union[str, Sequence[str], None] = 'cd4216b31ff9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Batch mode so the constraint can also be added on SQLite (it recreates the table there).
    with op.batch_alter_table('bookings') as batch:
        batch.add_column(sa.Column('idempotency_key', sa.String(length=128), nullable=True))
        batch.add_column(sa.Column('request_hash', sa.String(length=32), nullable=True))
        batch.create_unique_constraint('uq_bookings_customer_idempotency_key', ['customer_id', 'idempotency_key'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('bookings') as batch:
        batch.drop_constraint('uq_bookings_customer_idempotency_key', type_='unique')
        batch.drop_column('request_hash')
        batch.drop_column('idempotency_key')
