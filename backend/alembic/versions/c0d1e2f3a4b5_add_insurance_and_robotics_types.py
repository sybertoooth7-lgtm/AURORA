"""add insurance_index and robotics_inspection analysis types

Revision ID: c0d1e2f3a4b5
Revises: b5c6d7e8f9a0
Create Date: 2026-09-11 12:00:00.000000

Extends the `analysistype` Postgres enum with the two analysis types the
insurance-index and robotics-inspection pipelines register (AURORA-2).
Follows the established pattern: ALTER TYPE ... ADD VALUE IF NOT EXISTS,
enum members left in place on downgrade, existing rows untouched.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c0d1e2f3a4b5'
down_revision: Union[str, Sequence[str], None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_ANALYSIS_TYPES = (
    'INSURANCE_INDEX',
    'ROBOTICS_INSPECTION',
)


def upgrade() -> None:
    """Upgrade schema."""
    for value in _NEW_ANALYSIS_TYPES:
        op.execute(f"ALTER TYPE analysistype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema."""
    # Enum members intentionally left in place (see a1b2c3d4e5f6).
    pass