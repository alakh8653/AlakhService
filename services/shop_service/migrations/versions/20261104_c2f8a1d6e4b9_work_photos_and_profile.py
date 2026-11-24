"""work photos and profile

What customers see of a business before booking: years of experience, languages and photos of its work.

Revision ID: c2f8a1d6e4b9
Revises: 9a4d2e6f1b73
Create Date: 2026-11-04 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2f8a1d6e4b9"
down_revision: Union[str, Sequence[str], None] = "9a4d2e6f1b73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shops", sa.Column("years_experience", sa.Integer(), nullable=True))
    op.add_column("shops", sa.Column("languages", sa.JSON(), nullable=True))
    op.create_table(
        "shop_work_photos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("shop_id", sa.String(), sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("caption", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_shop_work_photos_shop_id", "shop_work_photos", ["shop_id"])


def downgrade() -> None:
    op.drop_index("ix_shop_work_photos_shop_id", table_name="shop_work_photos")
    op.drop_table("shop_work_photos")
    op.drop_column("shops", "languages")
    op.drop_column("shops", "years_experience")
