"""add wildfire_risk and flood_monitoring analysis types

Revision ID: b5c6d7e8f9a0
Revises: a1b2c3d4e5f6
Create Date: 2026-09-11 10:00:00.000000

Extends the `analysistype` Postgres enum with the two analysis types the
wildfire and flood pipelines register. Follows the same pattern as
a1b2c3d4e5f6: ALTER TYPE ... ADD VALUE IF NOT EXISTS, enum members left in
place on downgrade, existing rows untouched.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_ANALYSIS_TYPES = (
    'WILDFIRE_RISK',
    'FLOOD_MONITORING',
)


def upgrade() -> None:
    """Upgrade schema."""
    for value in _NEW_ANALYSIS_TYPES:
        op.execute(f"ALTER TYPE analysistype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema."""
    # Enum members intentionally left in place (see a1b2c3d4e5f6).
    pass