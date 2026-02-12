"""round_question_fk

Revision ID: 007_round_question_fk
Revises: 006_question_provenance
Create Date: 2026-01-30 00:03:00.000000

Question Progression Protocol - Extend Round entity with question_id FK.
Adds question_id column to rounds table to link rounds to questions from
the question progression protocol.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007_round_question_fk'
down_revision: Union[str, None] = '006_question_provenance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add question_id foreign key to rounds table.

    Changes:
    - Add question_id column (UUID, nullable, references questions.question_id)
    - Add foreign key constraint with CASCADE delete
    - Add index for efficient joins

    Note: Nullable initially to support existing discussions and gradual migration.
    Will be made NOT NULL after backfill in future migration if needed.
    """

    # Add question_id column to rounds table
    op.add_column(
        'rounds',
        sa.Column('question_id', postgresql.UUID(as_uuid=True), nullable=True)
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_rounds_question_id',
        'rounds',
        'questions',
        ['question_id'],
        ['question_id'],
        ondelete='CASCADE'
    )

    # Create index for efficient round-to-question joins
    op.create_index(
        'ix_rounds_question_id',
        'rounds',
        ['question_id']
    )


def downgrade() -> None:
    """
    Remove question_id foreign key from rounds table.
    """
    # Drop index
    op.drop_index('ix_rounds_question_id', table_name='rounds')

    # Drop foreign key constraint
    op.drop_constraint('fk_rounds_question_id', 'rounds', type_='foreignkey')

    # Drop column
    op.drop_column('rounds', 'question_id')
