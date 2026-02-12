"""question_sequence_table

Revision ID: 004_question_sequence
Revises: 003_user_story_2
Create Date: 2026-01-30 00:00:00.000000

Question Progression Protocol - QuestionSequence entity migration.
Creates the question_sequences table for tracking ordered collections of questions
for discussions. Supports both HOST_DEFINED and AUTO_GENERATED modes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_question_sequence'
down_revision: Union[str, None] = '003_user_story_2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create QuestionSequence table for Question Progression Protocol (Spec 006).

    Table Structure:
    - sequence_id: UUID primary key
    - discussion_id: UUID foreign key to discussions (one-to-one)
    - mode: Enum (HOST_DEFINED | AUTO_GENERATED)
    - total_questions: Integer (1-10 for HOST_DEFINED, NULL for AUTO_GENERATED)
    - current_index: Integer (0-based index of current question)
    - completion_status: Enum (IN_PROGRESS | COMPLETED | TERMINATED)
    - created_at: Timestamp
    """

    # Create sequence_mode enum
    sequence_mode_enum = postgresql.ENUM(
        'HOST_DEFINED', 'AUTO_GENERATED',
        name='sequence_mode',
        create_type=True
    )
    sequence_mode_enum.create(op.get_bind(), checkfirst=True)

    # Create completion_status enum
    completion_status_enum = postgresql.ENUM(
        'IN_PROGRESS', 'COMPLETED', 'TERMINATED',
        name='completion_status',
        create_type=True
    )
    completion_status_enum.create(op.get_bind(), checkfirst=True)

    # Create question_sequences table
    op.create_table(
        'question_sequences',
        sa.Column('sequence_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('discussion_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mode', sequence_mode_enum, nullable=False),
        sa.Column('total_questions', sa.Integer(), nullable=True),
        sa.Column('current_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_status', completion_status_enum, nullable=False, server_default='IN_PROGRESS'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['discussion_id'], ['discussions.discussion_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('sequence_id'),
        sa.CheckConstraint('current_index >= 0', name='ck_question_sequences_index_non_negative'),
        sa.CheckConstraint(
            "(mode = 'HOST_DEFINED' AND total_questions BETWEEN 1 AND 10) OR (mode = 'AUTO_GENERATED' AND total_questions IS NULL)",
            name='ck_question_sequences_total_questions_by_mode'
        ),
        comment='Ordered collections of questions for discussions with dual-mode support'
    )

    # Create unique index on discussion_id (one sequence per discussion)
    op.create_index(
        'uq_question_sequences_discussion',
        'question_sequences',
        ['discussion_id'],
        unique=True
    )


def downgrade() -> None:
    """
    Drop QuestionSequence table and related enums.
    """
    # Drop index
    op.drop_index('uq_question_sequences_discussion', table_name='question_sequences')

    # Drop table
    op.drop_table('question_sequences')

    # Drop enums
    completion_status_enum = postgresql.ENUM(
        'IN_PROGRESS', 'COMPLETED', 'TERMINATED',
        name='completion_status'
    )
    completion_status_enum.drop(op.get_bind(), checkfirst=True)

    sequence_mode_enum = postgresql.ENUM(
        'HOST_DEFINED', 'AUTO_GENERATED',
        name='sequence_mode'
    )
    sequence_mode_enum.drop(op.get_bind(), checkfirst=True)
