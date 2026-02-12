"""Add performance indexes for submission_metadata table

Revision ID: 010_add_submission_indexes
Revises: 009_add_dropout_count
Create Date: 2026-02-01

Adds indexes for:
1. idx_submission_metadata_participant_round: Composite index on (participant_id, round_id)
   - Optimizes queries that fetch all submissions for a participant in a specific round
   - Used by: GET /api/v1/submissions/participant/{participant_id}/round/{round_id}
   - Query pattern: WHERE participant_id = X AND round_id = Y ORDER BY timestamp DESC

2. idx_submission_metadata_counted: Index on counted field
   - Optimizes queries that filter by counted status
   - Used by: Aggregation queries for "last-approved-wins" logic
   - Query pattern: WHERE counted = TRUE

Performance Impact (T084):
- Reduces query time for submission history retrieval from O(n) to O(log n)
- Enables efficient filtering of counted submissions for flow calculations
- Critical for concurrent submission handling at scale (100+ participants)

Constitutional Compliance:
- Temporal Transparency: Fast queries enable real-time participant history access
- Parallel-First: Independent participant queries don't block each other
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '010_add_submission_indexes'
down_revision = '009_add_dropout_count'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create performance indexes on submission_metadata table.

    Index 1: Composite index on (participant_id, round_id)
    - Accelerates participant submission history queries
    - Enables efficient rate limit checks
    - Supports ORDER BY timestamp DESC without additional sort

    Index 2: Index on counted field
    - Accelerates filtering of counted vs uncounted submissions
    - Critical for "last-approved-wins" query performance
    - Supports fast aggregation queries for Sankey flow calculations
    """
    # Create composite index for participant + round queries
    # Note: Order matters! participant_id first enables partial index usage
    op.create_index(
        'idx_submission_metadata_participant_round',
        'submission_metadata',
        ['participant_id', 'round_id', 'timestamp'],  # Include timestamp for covering index
        unique=False
    )

    # Create index for counted field
    # Partial index: only index counted = TRUE rows (smaller, faster)
    op.execute("""
        CREATE INDEX idx_submission_metadata_counted
        ON submission_metadata (counted)
        WHERE counted = TRUE
    """)


def downgrade() -> None:
    """Remove performance indexes."""
    op.drop_index('idx_submission_metadata_counted', table_name='submission_metadata')
    op.drop_index('idx_submission_metadata_participant_round', table_name='submission_metadata')
