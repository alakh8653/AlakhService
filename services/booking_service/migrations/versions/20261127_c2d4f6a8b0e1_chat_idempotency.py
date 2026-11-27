"""chat idempotency

An Idempotency-Key on a chat message, so an app sending it again after being offline does not post it
twice.

Revision ID: c2d4f6a8b0e1
Revises: a7c3e5f9b1d2
Create Date: 2026-11-27 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d4f6a8b0e1"
down_revision: Union[str, Sequence[str], None] = "a7c3e5f9b1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("booking_messages") as batch:
        batch.add_column(sa.Column("client_key", sa.String(length=64), nullable=True))
        batch.create_unique_constraint(
            "uq_booking_messages_sender_client_key", ["booking_id", "sender_id", "client_key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("booking_messages") as batch:
        batch.drop_constraint("uq_booking_messages_sender_client_key", type_="unique")
        batch.drop_column("client_key")
