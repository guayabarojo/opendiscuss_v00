"""Add dropout_count field to rounds table

Revision ID: 009_add_dropout_count
Revises: 008_add_question_indexes
Create Date: 2026-02-01

T068: Implement dropout analytics by adding dropout_count field to Round model
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_add_dropout_count'
down_revision = '008_add_question_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """Add dropout_count column to rounds table."""
    op.add_column(
        'rounds',
        sa.Column(
            'dropout_count',
            sa.Integer(),
            nullable=True,
            comment='Number of participants who dropped out before this round (NULL for round 1)'
        )
    )


def downgrade():
    """Remove dropout_count column from rounds table."""
    op.drop_column('rounds', 'dropout_count')
