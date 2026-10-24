"""accepted terms version on users

Revision ID: 5b2e7c9a1f04
Revises: d26373d2513f
Create Date: 2026-10-23 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b2e7c9a1f04"
down_revision: Union[str, Sequence[str], None] = "d26373d2513f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Accounts created before this have accepted no recorded version (NULL): the app asks them again.
    op.add_column("users", sa.Column("accepted_terms_version", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("accepted_terms_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "accepted_terms_at")
    op.drop_column("users", "accepted_terms_version")
