"""add_question_indexes

Revision ID: 008_add_question_indexes
Revises: 007_round_question_fk
Create Date: 2026-01-31 00:00:00.000000

Phase 11: Performance optimization indexes for Question Progression Protocol.
Adds composite indexes for efficient question retrieval and provenance lookups.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '008_add_question_indexes'
down_revision: Union[str, None] = '007_round_question_fk'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add performance optimization indexes for Question Progression Protocol.

    T099: Add composite index on questions(sequence_id, question_order)
    - Optimizes sequential question fetch in get_next_question()
    - Already exists as unique constraint (uq_questions_sequence_order), adding note

    T100: Add index on question_provenance(question_id)
    - Unique constraint already exists (question_id is unique FK)
    - Add index on generation_timestamp for time-series queries
    """

    # T099: questions(sequence_id, question_order) already has unique index
    # Created in migration 005_question as 'uq_questions_sequence_order'
    # No action needed - already optimized

    # T100: Add index on question_provenance(generation_timestamp) for time-series queries
    # Note: question_id already has unique constraint, so it's indexed
    op.create_index(
        'ix_question_provenance_generation_timestamp',
        'question_provenance',
        ['generation_timestamp'],
        unique=False,
        comment='Time-series queries for provenance metrics'
    )

    # Additional optimization: Add composite index for common query pattern
    # Query pattern: Find recent provenance records with high retry counts
    op.create_index(
        'ix_question_provenance_timestamp_retry',
        'question_provenance',
        ['generation_timestamp', 'retry_count'],
        unique=False,
        comment='Optimizes queries for failed generation analysis'
    )


def downgrade() -> None:
    """
    Drop performance optimization indexes.
    """
    op.drop_index('ix_question_provenance_timestamp_retry', table_name='question_provenance')
    op.drop_index('ix_question_provenance_generation_timestamp', table_name='question_provenance')
