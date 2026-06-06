"""add_enums_and_budgets

Revision ID: cb63873c2c7d
Revises: 0001
Create Date: 2026-06-06 21:48:57.173681

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'cb63873c2c7d'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate columns to enums, add check constraint, and create budgets table."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("UPDATE transactions SET category = 'restaurants' WHERE category = 'food'")
    op.execute("UPDATE transactions SET category = 'groceries' WHERE category = 'grocery'")
    op.execute("UPDATE transactions SET category = 'rent' WHERE category = 'housing'")
    op.execute("UPDATE transactions SET category = 'transport' WHERE category = 'transportation'")
    op.execute("UPDATE transactions SET category = 'health' WHERE category = 'healthcare'")
    op.execute(
        "UPDATE transactions SET category = 'uncategorized' WHERE category NOT IN ("
        "'groceries', 'restaurants', 'transport', 'fuel', 'utilities', 'rent', "
        "'health', 'entertainment', 'shopping', 'subscriptions', 'travel', "
        "'education', 'income', 'transfer', 'uncategorized')"
    )

    op.execute("DELETE FROM monthly_category_rollups")

    op.execute("CREATE TYPE transaction_source AS ENUM ('csv', 'bank_api', 'manual', 'receipt')")
    op.execute(
        "CREATE TYPE transaction_category AS ENUM ("
        "'groceries', 'restaurants', 'transport', 'fuel', 'utilities', 'rent', "
        "'health', 'entertainment', 'shopping', 'subscriptions', 'travel', "
        "'education', 'income', 'transfer', 'uncategorized')"
    )
    op.execute("CREATE TYPE budget_period AS ENUM ('monthly', 'yearly')")

    op.execute("ALTER TABLE transactions ALTER COLUMN source TYPE transaction_source USING source::transaction_source")
    op.execute("ALTER TABLE transactions ALTER COLUMN category TYPE transaction_category USING category::transaction_category")
    op.execute("ALTER TABLE monthly_category_rollups ALTER COLUMN category TYPE transaction_category USING category::transaction_category")

    op.execute(
        "INSERT INTO monthly_category_rollups (id, user_id, month, category, total_amount, txn_count, updated_at) "
        "SELECT gen_random_uuid(), user_id, to_char(date, 'YYYY-MM'), category, SUM(amount), COUNT(id), NOW() "
        "FROM transactions "
        "GROUP BY user_id, to_char(date, 'YYYY-MM'), category"
    )

    op.create_check_constraint(
        "ck_transactions_currency_format",
        "transactions",
        "currency ~ '^[A-Z]{3}$'"
    )

    op.create_table(
        'budgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category', postgresql.ENUM(name='transaction_category', create_type=False), nullable=False),
        sa.Column('limit_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('period', postgresql.ENUM('monthly', 'yearly', name='budget_period', create_type=False), server_default='monthly', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_budgets_user_category_period', 'budgets', ['user_id', 'category', 'period'], unique=True)


def downgrade() -> None:
    """Drop budgets table, constraints, and revert columns to varchar, dropping enums."""
    op.drop_index('idx_budgets_user_category_period', table_name='budgets')
    op.drop_table('budgets')

    op.drop_constraint('ck_transactions_currency_format', 'transactions', type_='check')

    op.execute("ALTER TABLE transactions ALTER COLUMN source TYPE VARCHAR USING source::varchar")
    op.execute("ALTER TABLE transactions ALTER COLUMN category TYPE VARCHAR USING category::varchar")
    op.execute("ALTER TABLE monthly_category_rollups ALTER COLUMN category TYPE VARCHAR USING category::varchar")

    op.execute("DROP TYPE budget_period")
    op.execute("DROP TYPE transaction_category")
    op.execute("DROP TYPE transaction_source")
