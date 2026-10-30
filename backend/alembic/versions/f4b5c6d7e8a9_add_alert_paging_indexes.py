"""index the paged alert inbox and its per-area filter

Revision ID: f4b5c6d7e8a9
Revises: e2f3a4b5c6d7
Create Date: 2026-10-26 12:00:00.000000

The alerts listing is now paged newest-first and can be filtered to one
analysis. ``ix_alerts_user_read`` only covered the equality on is_read, so an
unread inbox still sorted the matches; the new composite carries the order.
The result index serves the join that scopes alerts to a single area.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f4b5c6d7e8a9'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index('ix_alerts_user_read', table_name='alerts')
    op.create_index(
        'ix_alerts_user_read_created',
        'alerts',
        ['user_id', 'is_read', 'created_at'],
        unique=False,
    )
    op.create_index(
        'ix_alerts_user_result',
        'alerts',
        ['user_id', 'analysis_result_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_alerts_user_result', table_name='alerts')
    op.drop_index('ix_alerts_user_read_created', table_name='alerts')
    op.create_index(
        'ix_alerts_user_read', 'alerts', ['user_id', 'is_read'], unique=False
    )
