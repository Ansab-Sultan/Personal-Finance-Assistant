"""add_user_preferences

Revision ID: 146c269ce0aa
Revises: cb63873c2c7d
Create Date: 2026-06-06 22:05:38.993458

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '146c269ce0aa'
down_revision: Union[str, Sequence[str], None] = 'cb63873c2c7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_preferences table with CHECK constraint on key values."""
    op.create_table(
        'user_preferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "key IN ('pay_date', 'exclude_from_food', 'currency_display', 'pay_cycle_start')",
            name="ck_user_preferences_key_values"
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_preferences_user_key', 'user_preferences', ['user_id', 'key'], unique=True)


def downgrade() -> None:
    """Drop user_preferences table and index."""
    op.drop_index('idx_user_preferences_user_key', table_name='user_preferences')
    op.drop_table('user_preferences')
