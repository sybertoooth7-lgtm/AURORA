"""add continuous monitoring columns to analyses

Revision ID: 2f4a6b8c0d2a
Revises: 88c46d82cbe3
Create Date: 2026-09-14 12:00:00.000000

Continuous monitoring (scheduled re-checks of areas): a cadence in minutes
and the timestamp of the next scheduled pass. Both nullable; existing rows
are untouched (not monitored until opted in via PATCH /analysis/{id}/monitor).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f4a6b8c0d2a'
down_revision: Union[str, Sequence[str], None] = '88c46d82cbe3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'analyses',
        sa.Column('monitor_interval_minutes', sa.Integer(), nullable=True),
    )
    op.add_column(
        'analyses',
        sa.Column('next_check_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('analyses', 'next_check_at')
    op.drop_column('analyses', 'monitor_interval_minutes')