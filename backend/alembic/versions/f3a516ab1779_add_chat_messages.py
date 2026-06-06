"""add_chat_messages

Revision ID: f3a516ab1779
Revises: 146c269ce0aa
Create Date: 2026-06-06 22:32:02.472850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f3a516ab1779'
down_revision: Union[str, Sequence[str], None] = '146c269ce0aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create message_role enum and chat_messages table with indexes."""
    op.execute("CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system')")

    op.create_table(
        'chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', postgresql.ENUM('user', 'assistant', 'system', name='message_role', create_type=False), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_summarized', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_chat_messages_user_created', 'chat_messages', ['user_id', 'created_at'])
    op.create_index('idx_chat_messages_user_summarized', 'chat_messages', ['user_id', 'is_summarized'])


def downgrade() -> None:
    """Drop index, table, and enum type."""
    op.drop_index('idx_chat_messages_user_summarized', table_name='chat_messages')
    op.drop_index('idx_chat_messages_user_created', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.execute("DROP TYPE message_role")
