"""question_table

Revision ID: 005_question
Revises: 004_question_sequence
Create Date: 2026-01-30 00:01:00.000000

Question Progression Protocol - Question entity migration.
Creates the questions table for individual questions within sequences.
Supports validation status tracking and immutability guarantees.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_question'
down_revision: Union[str, None] = '004_question_sequence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create Question table for Question Progression Protocol (Spec 006).

    Table Structure:
    - question_id: UUID primary key
    - sequence_id: UUID foreign key to question_sequences
    - order: Integer (1-indexed sequential order)
    - question_text: String (10-200 chars, validated)
    - mode: Enum (HOST_DEFINED | AUTO_GENERATED)
    - validation_status: Enum (VALID | REJECTED | PENDING)
    - created_at: Timestamp
    - immutable_since: Timestamp (set when round starts, enforces immutability)
    """

    # Create question_mode enum (reuses sequence_mode values)
    question_mode_enum = postgresql.ENUM(
        'HOST_DEFINED', 'AUTO_GENERATED',
        name='question_mode',
        create_type=True
    )
    question_mode_enum.create(op.get_bind(), checkfirst=True)

    # Create validation_status enum
    validation_status_enum = postgresql.ENUM(
        'VALID', 'REJECTED', 'PENDING',
        name='validation_status',
        create_type=True
    )
    validation_status_enum.create(op.get_bind(), checkfirst=True)

    # Create questions table
    op.create_table(
        'questions',
        sa.Column('question_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('sequence_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.String(200), nullable=False),
        sa.Column('mode', question_mode_enum, nullable=False),
        sa.Column('validation_status', validation_status_enum, nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('immutable_since', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['sequence_id'], ['question_sequences.sequence_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('question_id'),
        sa.CheckConstraint('order >= 1', name='ck_questions_order_positive'),
        sa.CheckConstraint(
            'char_length(question_text) BETWEEN 10 AND 200',
            name='ck_questions_text_length'
        ),
        comment='Individual questions within sequences with validation and immutability tracking'
    )

    # Create unique composite index on (sequence_id, order)
    op.create_index(
        'uq_questions_sequence_order',
        'questions',
        ['sequence_id', 'order'],
        unique=True
    )

    # Create index on question_id for round assignment lookups
    op.create_index(
        'ix_questions_question_id',
        'questions',
        ['question_id']
    )


def downgrade() -> None:
    """
    Drop Question table and related enums.
    """
    # Drop indexes
    op.drop_index('ix_questions_question_id', table_name='questions')
    op.drop_index('uq_questions_sequence_order', table_name='questions')

    # Drop table
    op.drop_table('questions')

    # Drop enums
    validation_status_enum = postgresql.ENUM(
        'VALID', 'REJECTED', 'PENDING',
        name='validation_status'
    )
    validation_status_enum.drop(op.get_bind(), checkfirst=True)

    question_mode_enum = postgresql.ENUM(
        'HOST_DEFINED', 'AUTO_GENERATED',
        name='question_mode'
    )
    question_mode_enum.drop(op.get_bind(), checkfirst=True)
