"""extra charges

What a provider asks for on top of a booking's price after seeing the job, and the customer's answer.

Revision ID: b9e1c4d7a2f3
Revises: f3c5a7e9b2d4
Create Date: 2026-11-04 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9e1c4d7a2f3"
down_revision: Union[str, Sequence[str], None] = "f3c5a7e9b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("extra_amount", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bookings", sa.Column("pending_extra_id", sa.String(), nullable=True))
    op.add_column("bookings", sa.Column("pending_extra_amount", sa.Integer(), nullable=True))
    op.add_column("bookings", sa.Column("pending_extra_reason", sa.Text(), nullable=True))
    op.create_table(
        "booking_extra_charges",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("booking_id", sa.String(), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_booking_extra_charges_booking_id", "booking_extra_charges", ["booking_id"])


def downgrade() -> None:
    op.drop_index("ix_booking_extra_charges_booking_id", table_name="booking_extra_charges")
    op.drop_table("booking_extra_charges")
    op.drop_column("bookings", "pending_extra_reason")
    op.drop_column("bookings", "pending_extra_amount")
    op.drop_column("bookings", "pending_extra_id")
    op.drop_column("bookings", "extra_amount")
