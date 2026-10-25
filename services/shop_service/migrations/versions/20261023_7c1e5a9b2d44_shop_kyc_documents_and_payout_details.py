"""shop kyc, documents and payout details

Shops get a verification status (new shops wait for an admin's review; the shops that already exist
are approved, so nothing customers see changes), the legal name, address and GSTIN for invoices, the
uploaded KYC documents' file details, and where their payouts go.

Revision ID: 7c1e5a9b2d44
Revises: db0035b6a1b9
Create Date: 2026-10-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1e5a9b2d44'
down_revision: Union[str, Sequence[str], None] = 'db0035b6a1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing shops are live already: they start APPROVED (and verified); new rows default to review.
    op.add_column(
        'shops', sa.Column('verification_status', sa.String(length=20), server_default='APPROVED', nullable=False)
    )
    op.alter_column('shops', 'verification_status', server_default='PENDING_REVIEW')
    op.execute("UPDATE shops SET is_verified = true")
    op.create_index(op.f('ix_shops_verification_status'), 'shops', ['verification_status'], unique=False)
    op.add_column('shops', sa.Column('rejection_reason', sa.Text(), nullable=True))
    op.add_column('shops', sa.Column('legal_name', sa.String(length=200), nullable=True))
    op.add_column('shops', sa.Column('legal_address', sa.Text(), nullable=True))
    op.add_column('shops', sa.Column('gstin', sa.String(length=15), nullable=True))
    op.add_column('shops', sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('shops', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('shops', sa.Column('reviewed_by', sa.String(), nullable=True))

    op.add_column('shop_documents', sa.Column('storage_key', sa.String(), nullable=True))
    op.add_column('shop_documents', sa.Column('file_name', sa.String(length=255), nullable=True))
    op.add_column('shop_documents', sa.Column('content_type', sa.String(length=100), nullable=True))
    op.add_column('shop_documents', sa.Column('size_bytes', sa.Integer(), nullable=True))
    op.add_column('shop_documents', sa.Column('uploaded_by', sa.String(), nullable=True))
    op.add_column(
        'shop_documents',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )

    op.create_table('shop_payout_details',
    sa.Column('shop_id', sa.String(), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('account_name', sa.String(length=200), nullable=True),
    sa.Column('account_number', sa.String(length=18), nullable=True),
    sa.Column('ifsc', sa.String(length=11), nullable=True),
    sa.Column('upi_id', sa.String(length=255), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_by', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['shop_id'], ['shops.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('shop_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('shop_payout_details')
    for column in ('created_at', 'uploaded_by', 'size_bytes', 'content_type', 'file_name', 'storage_key'):
        op.drop_column('shop_documents', column)
    for column in ('reviewed_by', 'reviewed_at', 'submitted_at', 'gstin', 'legal_address', 'legal_name',
                   'rejection_reason'):
        op.drop_column('shops', column)
    op.drop_index(op.f('ix_shops_verification_status'), table_name='shops')
    op.drop_column('shops', 'verification_status')
