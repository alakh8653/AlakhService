"""photo moderation

Customers report work photos, and admins hide or remove them.

Revision ID: d7a3b5e1f9c2
Revises: c2f8a1d6e4b9
Create Date: 2026-11-04 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7a3b5e1f9c2"
down_revision: Union[str, Sequence[str], None] = "c2f8a1d6e4b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shop_work_photos", sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("shop_work_photos", sa.Column("report_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "work_photo_reports",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("photo_id", sa.String(), sa.ForeignKey("shop_work_photos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("photo_id", "reporter_id", name="uq_work_photo_reports_photo_reporter"),
    )
    op.create_index("ix_work_photo_reports_photo_id", "work_photo_reports", ["photo_id"])


def downgrade() -> None:
    op.drop_index("ix_work_photo_reports_photo_id", table_name="work_photo_reports")
    op.drop_table("work_photo_reports")
    op.drop_column("shop_work_photos", "report_count")
    op.drop_column("shop_work_photos", "is_hidden")
