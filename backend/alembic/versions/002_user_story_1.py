"""user_story_1_entities

Revision ID: 002_user_story_1
Revises: 001_foundation
Create Date: 2026-01-29 15:00:00.000000

User Story 1 migration for OpenDiscuss Discussion Protocol.
Creates all entities for discussion lifecycle, rounds, participants, submissions,
approved summaries, thought spaces, and flows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_user_story_1'
down_revision: Union[str, None] = '001_foundation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create User Story 1 schema for OpenDiscuss.

    Tables:
    - discussions: Bounded synchronous deliberation events
    - rounds: Timed phases within discussions
    - participants: User participation tracking across rounds
    - submissions: Ephemeral participant input (TTL-based deletion)
    - approved_summaries: Canonical 1-2 sentence representations
    - thought_spaces: Semantic clusters of approved summaries
    - flows: Participant movement between thought spaces

    Enums:
    - discussion_mode: HOST_DEFINED, AUTO_GENERATED
    - discussion_status: CREATED, ACTIVE, COMPLETED, TERMINATED
    - round_status: PENDING, SUBMISSION_OPEN, SUBMISSION_CLOSED, SUMMARIZING,
                    APPROVING, CLUSTERING, SANKEY_BUILDING, COMPLETE, QUESTION_READY, FAILED
    - dropout_reason: NO_SUBMISSION, NO_APPROVAL, TIMEOUT, EXPLICIT_EXIT
    - submission_modality: TEXT, VOICE
    - summary_status: PENDING, APPROVED, REJECTED, SUPERSEDED, APPROVAL_TIMEOUT
    """

    # Create ENUM types
    discussion_mode_enum = postgresql.ENUM(
        'HOST_DEFINED', 'AUTO_GENERATED',
        name='discussion_mode',
        create_type=True
    )
    discussion_mode_enum.create(op.get_bind(), checkfirst=True)

    discussion_status_enum = postgresql.ENUM(
        'CREATED', 'ACTIVE', 'COMPLETED', 'TERMINATED',
        name='discussion_status',
        create_type=True
    )
    discussion_status_enum.create(op.get_bind(), checkfirst=True)

    round_status_enum = postgresql.ENUM(
        'PENDING', 'SUBMISSION_OPEN', 'SUBMISSION_CLOSED', 'SUMMARIZING',
        'APPROVING', 'CLUSTERING', 'SANKEY_BUILDING', 'COMPLETE',
        'QUESTION_READY', 'FAILED',
        name='round_status',
        create_type=True
    )
    round_status_enum.create(op.get_bind(), checkfirst=True)

    dropout_reason_enum = postgresql.ENUM(
        'NO_SUBMISSION', 'NO_APPROVAL', 'TIMEOUT', 'EXPLICIT_EXIT',
        name='dropout_reason',
        create_type=True
    )
    dropout_reason_enum.create(op.get_bind(), checkfirst=True)

    submission_modality_enum = postgresql.ENUM(
        'TEXT', 'VOICE',
        name='submissionmodality',
        create_type=True
    )
    submission_modality_enum.create(op.get_bind(), checkfirst=True)

    summary_status_enum = postgresql.ENUM(
        'PENDING', 'APPROVED', 'REJECTED', 'SUPERSEDED', 'APPROVAL_TIMEOUT',
        name='summarystatus',
        create_type=True
    )
    summary_status_enum.create(op.get_bind(), checkfirst=True)

    # Create discussions table
    op.create_table(
        'discussions',
        sa.Column('discussion_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('community_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('host_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mode', discussion_mode_enum, nullable=False),
        sa.Column('total_rounds', sa.Integer(), nullable=False),
        sa.Column('current_round_num', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', discussion_status_enum, nullable=False, server_default='CREATED'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('terminated_reason', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('discussion_id'),
        comment='Bounded synchronous deliberation events with lifecycle management'
    )

    # Create indexes for discussions
    op.create_index(
        'ix_discussions_community_created',
        'discussions',
        ['community_id', 'created_at']
    )
    op.create_index(
        'ix_discussions_host_created',
        'discussions',
        ['host_user_id', 'created_at']
    )
    op.create_index(
        'ix_discussions_status',
        'discussions',
        ['status']
    )

    # Create rounds table
    op.create_table(
        'rounds',
        sa.Column('round_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('discussion_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('round_num', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.String(200), nullable=False),
        sa.Column('status', round_status_enum, nullable=False, server_default='PENDING'),
        sa.Column('submission_window_start', sa.DateTime(), nullable=True),
        sa.Column('submission_window_end', sa.DateTime(), nullable=True),
        sa.Column('submission_window_duration_sec', sa.Integer(), nullable=False),
        sa.Column('approval_deadline', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['discussion_id'], ['discussions.discussion_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('round_id'),
        sa.CheckConstraint('submission_window_duration_sec BETWEEN 180 AND 360', name='ck_rounds_window_duration'),
        sa.CheckConstraint('round_num >= 1', name='ck_rounds_num_positive'),
        comment='Timed phases within discussions with state machine coordination'
    )

    # Create indexes for rounds
    op.create_index(
        'ix_rounds_discussion_round_num',
        'rounds',
        ['discussion_id', 'round_num'],
        unique=True
    )
    op.create_index(
        'ix_rounds_status',
        'rounds',
        ['status']
    )
    op.create_index(
        'ix_rounds_approval_deadline',
        'rounds',
        ['approval_deadline']
    )

    # Create participants table
    op.create_table(
        'participants',
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('discussion_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('first_round', sa.Integer(), nullable=False),
        sa.Column('last_round', sa.Integer(), nullable=True),
        sa.Column('dropout_reason', dropout_reason_enum, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['discussion_id'], ['discussions.discussion_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('participant_id'),
        sa.CheckConstraint('first_round >= 1', name='ck_participants_first_round_positive'),
        sa.CheckConstraint(
            'last_round IS NULL OR last_round >= first_round',
            name='ck_participants_last_round_after_first'
        ),
        sa.CheckConstraint(
            '(last_round IS NULL AND dropout_reason IS NULL) OR (last_round IS NOT NULL AND dropout_reason IS NOT NULL)',
            name='ck_participants_dropout_consistency'
        ),
        comment='User participation tracking across rounds with privacy decoupling'
    )

    # Create indexes for participants
    op.create_index(
        'ix_participants_discussion_user',
        'participants',
        ['discussion_id', 'user_id'],
        unique=True
    )
    op.create_index(
        'ix_participants_user',
        'participants',
        ['user_id']
    )

    # Create submissions table
    op.create_table(
        'submissions',
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('round_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('submission_text', sa.Text(), nullable=False),
        sa.Column('modality', submission_modality_enum, nullable=False, server_default='TEXT'),
        sa.Column('submitted_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('summary_status', summary_status_enum, nullable=False, server_default='PENDING'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['participant_id'], ['participants.participant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['round_id'], ['rounds.round_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('submission_id'),
        comment='Ephemeral participant input with TTL-based deletion'
    )

    # Create indexes for submissions
    op.create_index(
        'idx_submission_round_participant_time',
        'submissions',
        ['round_id', 'participant_id', 'submitted_at']
    )
    op.create_index(
        'idx_submission_deleted_at',
        'submissions',
        ['deleted_at']
    )

    # Create approved_summaries table
    op.create_table(
        'approved_summaries',
        sa.Column('summary_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('round_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('summary_text', sa.String(500), nullable=False),
        sa.Column('approved_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('cluster_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['participant_id'], ['participants.participant_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['round_id'], ['rounds.round_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.submission_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('summary_id'),
        comment='Canonical 1-2 sentence representations of submissions with constitutional guarantees'
    )

    # Create indexes for approved_summaries (cluster_id FK will be added after thought_spaces)
    op.create_index(
        'idx_approved_summary_round_participant',
        'approved_summaries',
        ['round_id', 'participant_id'],
        unique=True
    )
    op.create_index(
        'idx_approved_summary_round',
        'approved_summaries',
        ['round_id']
    )

    # Create thought_spaces table
    op.create_table(
        'thought_spaces',
        sa.Column('cluster_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('round_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('label_summary', sa.String(200), nullable=False),
        sa.Column('centroid_vector', sa.JSON(), nullable=True),
        sa.Column('member_count', sa.Integer(), nullable=False),
        sa.Column('member_pct', sa.Float(), nullable=False),
        sa.Column('display_group_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['round_id'], ['rounds.round_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('cluster_id'),
        sa.CheckConstraint('member_count >= 1', name='check_member_count_positive'),
        sa.CheckConstraint('member_pct >= 0.0 AND member_pct <= 1.0', name='check_member_pct_range'),
        sa.CheckConstraint('char_length(label_summary) <= 200', name='check_label_summary_length'),
        comment='Semantic clusters of approved summaries with constitutional guarantees'
    )

    # Create indexes for thought_spaces
    op.create_index(
        'ix_thought_spaces_round_id',
        'thought_spaces',
        ['round_id']
    )

    # Now add the foreign key constraint from approved_summaries to thought_spaces
    op.create_foreign_key(
        'fk_approved_summaries_cluster_id',
        'approved_summaries',
        'thought_spaces',
        ['cluster_id'],
        ['cluster_id'],
        ondelete='SET NULL'
    )

    # Create index for approved_summaries.cluster_id
    op.create_index(
        'idx_approved_summary_cluster',
        'approved_summaries',
        ['cluster_id']
    )

    # Create flows table
    op.create_table(
        'flows',
        sa.Column('flow_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('source_cluster_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_cluster_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('participant_count', sa.Integer(), nullable=False),
        sa.Column('participant_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['source_cluster_id'], ['thought_spaces.cluster_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_cluster_id'], ['thought_spaces.cluster_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('flow_id'),
        sa.CheckConstraint('participant_count >= 1', name='check_participant_count_positive'),
        comment='Participant movement between thought spaces across consecutive rounds'
    )

    # Create indexes for flows
    op.create_index(
        'ix_flows_source_cluster_id',
        'flows',
        ['source_cluster_id']
    )
    op.create_index(
        'ix_flows_target_cluster_id',
        'flows',
        ['target_cluster_id']
    )


def downgrade() -> None:
    """
    Drop User Story 1 schema tables and enums.
    """
    # Drop tables in reverse dependency order
    op.drop_index('ix_flows_target_cluster_id', table_name='flows')
    op.drop_index('ix_flows_source_cluster_id', table_name='flows')
    op.drop_table('flows')

    # Drop approved_summaries foreign key to thought_spaces
    op.drop_constraint('fk_approved_summaries_cluster_id', 'approved_summaries', type_='foreignkey')
    op.drop_index('idx_approved_summary_cluster', table_name='approved_summaries')

    op.drop_index('ix_thought_spaces_round_id', table_name='thought_spaces')
    op.drop_table('thought_spaces')

    op.drop_index('idx_approved_summary_round', table_name='approved_summaries')
    op.drop_index('idx_approved_summary_round_participant', table_name='approved_summaries')
    op.drop_table('approved_summaries')

    op.drop_index('idx_submission_deleted_at', table_name='submissions')
    op.drop_index('idx_submission_round_participant_time', table_name='submissions')
    op.drop_table('submissions')

    op.drop_index('ix_participants_user', table_name='participants')
    op.drop_index('ix_participants_discussion_user', table_name='participants')
    op.drop_table('participants')

    op.drop_index('ix_rounds_approval_deadline', table_name='rounds')
    op.drop_index('ix_rounds_status', table_name='rounds')
    op.drop_index('ix_rounds_discussion_round_num', table_name='rounds')
    op.drop_table('rounds')

    op.drop_index('ix_discussions_status', table_name='discussions')
    op.drop_index('ix_discussions_host_created', table_name='discussions')
    op.drop_index('ix_discussions_community_created', table_name='discussions')
    op.drop_table('discussions')

    # Drop ENUM types
    op.execute('DROP TYPE IF EXISTS summarystatus')
    op.execute('DROP TYPE IF EXISTS submissionmodality')
    op.execute('DROP TYPE IF EXISTS dropout_reason')
    op.execute('DROP TYPE IF EXISTS round_status')
    op.execute('DROP TYPE IF EXISTS discussion_status')
    op.execute('DROP TYPE IF EXISTS discussion_mode')
