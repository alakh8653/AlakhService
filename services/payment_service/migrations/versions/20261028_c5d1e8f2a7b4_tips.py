"""tips

Payments say what they are for (a booking, or a tip added once it is completed), so a booking is paid
for once and tipped at most once; shop earnings record which staff member a tip is for.

Revision ID: c5d1e8f2a7b4
Revises: b7e4c2a91d30
Create Date: 2026-10-28 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d1e8f2a7b4"
down_revision: Union[str, Sequence[str], None] = "b7e4c2a91d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COMPLETED = sa.text("status = 'COMPLETED'")


def upgrade() -> None:
    op.add_column("payments", sa.Column("purpose", sa.String(length=10), server_default="BOOKING", nullable=False))
    op.add_column("shop_earnings", sa.Column("provider_id", sa.String(), nullable=True))
    op.drop_index("uq_payments_booking_completed", table_name="payments")
    op.create_index(
        "uq_payments_booking_purpose_completed",
        "payments",
        ["booking_id", "purpose"],
        unique=True,
        sqlite_where=COMPLETED,
        postgresql_where=COMPLETED,
    )


def downgrade() -> None:
    # Tips are money customers paid: refusing beats deleting them, or mixing them up with bookings.
    tips = op.get_bind().execute(sa.text("SELECT count(*) FROM payments WHERE purpose = 'TIP'")).scalar()
    if tips:
        raise RuntimeError(f"{tips} tip payment(s) exist; settle and archive them before downgrading")
    op.drop_index("uq_payments_booking_purpose_completed", table_name="payments")
    op.create_index(
        "uq_payments_booking_completed",
        "payments",
        ["booking_id"],
        unique=True,
        sqlite_where=COMPLETED,
        postgresql_where=COMPLETED,
    )
    op.drop_column("shop_earnings", "provider_id")
    op.drop_column("payments", "purpose")
