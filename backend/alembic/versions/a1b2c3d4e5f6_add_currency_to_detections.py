"""add_currency_to_detections

Revision ID: a1b2c3d4e5f6
Revises: 3c85f5c111e0
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3c85f5c111e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add a currency column to the precomputed detection tables."""
    op.add_column(
        'detected_subscriptions',
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
    )
    op.add_column(
        'flagged_anomalies',
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
    )


def downgrade() -> None:
    """Drop the currency column from the detection tables."""
    op.drop_column('flagged_anomalies', 'currency')
    op.drop_column('detected_subscriptions', 'currency')
