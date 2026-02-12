"""Add performance indexes to summaries table

Revision ID: 012_summary_indexes
Revises: 011_create_summaries
Create Date: 2026-02-01

Tasks T104-T105: Database optimization for summary queries
- T104: Composite index for (participant_id, round_id, status) queries
- T105: Index for (approved_at) for last-approved-wins queries
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012_summary_indexes'
down_revision = '011_create_summaries'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance indexes to summaries table."""
    # T104: Composite index for common query pattern:
    # SELECT * FROM summaries WHERE participant_id = ? AND round_id = ? AND status = ?
    op.create_index(
        'idx_summaries_participant_round_status',
        'summaries',
        ['participant_id', 'round_id', 'status'],
        unique=False,
    )

    # T105: Index for last-approved-wins queries:
    # SELECT * FROM summaries WHERE status = 'approved' ORDER BY approved_at DESC
    # Note: approved_at already has individual index from model, this ensures it's optimized
    # for sorted queries (B-tree index)
    op.create_index(
        'idx_summaries_approved_at_desc',
        'summaries',
        [sa.text('approved_at DESC')],
        unique=False,
        postgresql_where=sa.text("status = 'approved'"),  # Partial index for approved only
    )

    # Additional index for status + approved_at combined queries
    op.create_index(
        'idx_summaries_status_approved_at',
        'summaries',
        ['status', 'approved_at'],
        unique=False,
    )


def downgrade() -> None:
    """Remove performance indexes from summaries table."""
    op.drop_index('idx_summaries_status_approved_at', table_name='summaries')
    op.drop_index('idx_summaries_approved_at_desc', table_name='summaries')
    op.drop_index('idx_summaries_participant_round_status', table_name='summaries')
