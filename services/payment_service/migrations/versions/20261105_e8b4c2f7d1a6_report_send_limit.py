"""report send limit

How many times today an owner pressed "send me this report now": each can be a paid WhatsApp message.

Revision ID: e8b4c2f7d1a6
Revises: a4d2e6b8c1f7
Create Date: 2026-11-05 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8b4c2f7d1a6"
down_revision: Union[str, Sequence[str], None] = "a4d2e6b8c1f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shop_report_preferences", sa.Column("sent_on", sa.Date(), nullable=True))
    op.add_column("shop_report_preferences", sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("shop_report_preferences", "sent_count")
    op.drop_column("shop_report_preferences", "sent_on")
