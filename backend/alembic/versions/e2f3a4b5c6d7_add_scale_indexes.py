"""add composite indexes for listings, roll-ups and the monitoring scheduler

Revision ID: e2f3a4b5c6d7
Revises: 3b7e9f1c2d5a
Create Date: 2026-10-18 09:30:00.000000

Scaling the read side: the analysis list, the account roll-up, monitoring
history and the alert inbox all filter by owner and order or filter by a
second column. Each of those was a sequential scan of the whole table plus a
sort. These are plain b-tree indexes (no expression or GiST components), so
they apply identically on PostGIS and on the SQLite schema demo mode builds
from the models.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = '3b7e9f1c2d5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES = (
    ('ix_analyses_user_created', 'analyses', ('user_id', 'created_at')),
    ('ix_analyses_user_status', 'analyses', ('user_id', 'status')),
    ('ix_analyses_next_check_at', 'analyses', ('next_check_at',)),
    ('ix_analysis_results_analysis_created', 'analysis_results', ('analysis_id', 'created_at')),
    ('ix_alerts_user_created', 'alerts', ('user_id', 'created_at')),
    ('ix_alerts_user_read', 'alerts', ('user_id', 'is_read')),
)


def upgrade() -> None:
    """Upgrade schema."""
    for name, table, columns in INDEXES:
        op.create_index(name, table, list(columns), unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
