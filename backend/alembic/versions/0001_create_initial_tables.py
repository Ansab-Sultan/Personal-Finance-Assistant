"""create initial tables

Revision ID: 0001
Revises: None
Create Date: 2026-06-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Create users, transactions, and monthly_category_rollups tables."""
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clerk_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_clerk_id', 'users', ['clerk_id'], unique=True)

    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('merchant', sa.String(), nullable=False),
        sa.Column('raw_description', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_transactions_user_date', 'transactions', ['user_id', 'date'], unique=False)
    op.create_index('idx_transactions_user_category_date', 'transactions', ['user_id', 'category', 'date'], unique=False)
    op.create_index('idx_transactions_user_hash', 'transactions', ['user_id', 'hash'], unique=True)

    op.create_table(
        'monthly_category_rollups',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('month', sa.String(length=7), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('txn_count', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_rollups_user_month_category', 'monthly_category_rollups', ['user_id', 'month', 'category'], unique=True)

def downgrade() -> None:
    """Drop users, transactions, and monthly_category_rollups tables."""
    op.drop_table('monthly_category_rollups')
    op.drop_table('transactions')
    op.drop_table('users')
