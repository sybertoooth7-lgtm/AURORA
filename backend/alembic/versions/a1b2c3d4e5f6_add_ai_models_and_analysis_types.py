"""add ai model registry and new analysis types

Revision ID: a1b2c3d4e5f6
Revises: db5c3b1b933e
Create Date: 2026-09-11 09:00:00.000000

Extends the `analysistype` Postgres enum with the three analysis types the
AI pipeline registry adds (infrastructure_monitoring, environmental_monitoring,
anomaly_detection) and creates the `ai_models` model-metadata table.

Postgres note: ALTER TYPE ... ADD VALUE IF NOT EXISTS is used rather than a
create/drop of the whole type, because a downgrade that removes a value only
works while no row uses it (and DROP VALUE is PG 15+ anyway). Existing
rows are never touched here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'db5c3b1b933e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_ANALYSIS_TYPES = (
    'INFRASTRUCTURE_MONITORING',
    'ENVIRONMENTAL_MONITORING',
    'ANOMALY_DETECTION',
)


def upgrade() -> None:
    """Upgrade schema."""
    for value in _NEW_ANALYSIS_TYPES:
        op.execute(f"ALTER TYPE analysistype ADD VALUE IF NOT EXISTS '{value}'")

    op.create_table('ai_models',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('framework', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('parameters', sa.Text(), nullable=True),
    sa.Column('metrics', sa.Text(), nullable=True),
    sa.Column('artifact_uri', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_models_id'), 'ai_models', ['id'], unique=False)
    op.create_index(op.f('ix_ai_models_name'), 'ai_models', ['name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Enum members are intentionally left in place: PG can only DROP a value
    # once no row uses it, so a safe downgrade can't be guaranteed generically.
    op.drop_index(op.f('ix_ai_models_name'), table_name='ai_models')
    op.drop_index(op.f('ix_ai_models_id'), table_name='ai_models')
    op.drop_table('ai_models')