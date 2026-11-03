"""shop reports

The expenses and outside income an owner writes down, where their reports go, and which were sent.

Revision ID: a4d2e6b8c1f7
Revises: f7c3d2b1a9e8
Create Date: 2026-11-03 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4d2e6b8c1f7"
down_revision: Union[str, Sequence[str], None] = "f7c3d2b1a9e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_cash_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("shop_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("on_date", sa.Date(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_shop_cash_entries_shop_date", "shop_cash_entries", ["shop_id", "on_date"])
    op.create_index("ix_shop_cash_entries_on_date", "shop_cash_entries", ["on_date"])
    op.create_table(
        "shop_report_preferences",
        sa.Column("shop_id", sa.String(), primary_key=True),
        sa.Column("daily", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("weekly", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("monthly", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("yearly", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("whatsapp", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("whatsapp_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
    )
    op.create_table(
        "shop_report_deliveries",
        sa.Column("shop_id", sa.String(), primary_key=True),
        sa.Column("period", sa.String(length=10), primary_key=True),
        sa.Column("period_start", sa.Date(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_shop_earnings_completed_at", "shop_earnings", ["completed_at"])


def downgrade() -> None:
    op.drop_index("ix_shop_earnings_completed_at", table_name="shop_earnings")
    op.drop_table("shop_report_deliveries")
    op.drop_table("shop_report_preferences")
    op.drop_index("ix_shop_cash_entries_on_date", table_name="shop_cash_entries")
    op.drop_index("ix_shop_cash_entries_shop_date", table_name="shop_cash_entries")
    op.drop_table("shop_cash_entries")
