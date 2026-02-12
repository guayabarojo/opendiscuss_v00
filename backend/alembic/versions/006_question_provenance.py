"""question_provenance_table

Revision ID: 006_question_provenance
Revises: 005_question
Create Date: 2026-01-30 00:02:00.000000

Question Progression Protocol - QuestionProvenance entity migration.
Creates the question_provenance table for tracking metadata of auto-generated
questions (generation latency, LLM model, token usage, retry counts, etc).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006_question_provenance'
down_revision: Union[str, None] = '005_question'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create QuestionProvenance table for Question Progression Protocol (Spec 006).

    Table Structure:
    - provenance_id: UUID primary key
    - question_id: UUID foreign key to questions (one-to-one)
    - generation_timestamp: Timestamp when question was generated
    - generation_latency_ms: Float (time from request to completion)
    - input_sankey_hash: String(64) - SHA-256 of Sankey JSON for reproducibility
    - input_round_id: UUID foreign key to rounds (round that triggered generation)
    - llm_model: String(100) - model identifier (e.g., "claude-sonnet-4-5")
    - prompt_tokens: Integer - token count for prompt
    - completion_tokens: Integer - token count for response
    - retry_count: Integer (default 0) - number of API retries
    - validation_attempts: Integer (default 1) - number of validation attempts
    - previous_questions_count: Integer - number of prior questions in context
    """

    # Create question_provenance table
    op.create_table(
        'question_provenance',
        sa.Column('provenance_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('generation_timestamp', sa.DateTime(), nullable=False),
        sa.Column('generation_latency_ms', sa.Float(), nullable=False),
        sa.Column('input_sankey_hash', sa.String(64), nullable=False),
        sa.Column('input_round_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('llm_model', sa.String(100), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('validation_attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('previous_questions_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.question_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['input_round_id'], ['rounds.round_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('provenance_id'),
        sa.CheckConstraint('generation_latency_ms >= 0', name='ck_question_provenance_latency_non_negative'),
        sa.CheckConstraint('prompt_tokens >= 0', name='ck_question_provenance_prompt_tokens_non_negative'),
        sa.CheckConstraint('completion_tokens >= 0', name='ck_question_provenance_completion_tokens_non_negative'),
        sa.CheckConstraint('retry_count >= 0', name='ck_question_provenance_retry_count_non_negative'),
        sa.CheckConstraint('validation_attempts >= 1', name='ck_question_provenance_validation_attempts_positive'),
        sa.CheckConstraint('previous_questions_count >= 0', name='ck_question_provenance_previous_count_non_negative'),
        comment='Provenance metadata for auto-generated questions (audit, debugging, quality monitoring)'
    )

    # Create unique index on question_id (one provenance per question)
    op.create_index(
        'uq_question_provenance_question',
        'question_provenance',
        ['question_id'],
        unique=True
    )

    # Create index on input_round_id for finding questions generated from specific round
    op.create_index(
        'ix_question_provenance_input_round',
        'question_provenance',
        ['input_round_id']
    )

    # Create index on generation_timestamp for time-series queries (monitoring)
    op.create_index(
        'ix_question_provenance_timestamp',
        'question_provenance',
        ['generation_timestamp']
    )


def downgrade() -> None:
    """
    Drop QuestionProvenance table and related indexes.
    """
    # Drop indexes
    op.drop_index('ix_question_provenance_timestamp', table_name='question_provenance')
    op.drop_index('ix_question_provenance_input_round', table_name='question_provenance')
    op.drop_index('uq_question_provenance_question', table_name='question_provenance')

    # Drop table
    op.drop_table('question_provenance')
