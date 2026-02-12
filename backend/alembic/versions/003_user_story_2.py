"""user_story_2_indexes

Revision ID: 003_user_story_2
Revises: 002_user_story_1
Create Date: 2026-01-29 16:00:00.000000

User Story 2 optimization indexes for OpenDiscuss Discussion Protocol.
Adds composite indexes to optimize flow computation and dropout detection queries
between consecutive rounds.

Optimization Goals:
- Participant lookups across rounds (dropout detection)
- Cluster membership queries (flow computation)
- Flow edge lookups (Sankey construction)
- Temporal ordering (multi-round visualization)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_user_story_2'
down_revision: Union[str, None] = '002_user_story_1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add composite indexes for User Story 2 flow computation optimization.

    New Indexes:
    1. idx_approved_summaries_round_cluster (round_id, cluster_id)
       - Optimizes flow computation queries that need to find all participants
         in a specific cluster within a round
       - Used by FlowService._get_participants_in_cluster() when building
         participant intersections between consecutive rounds
       - Enables efficient O(1) cluster membership lookups

    2. idx_flows_source_target (source_cluster_id, target_cluster_id)
       - Composite index for optimizing flow edge lookups during Sankey construction
       - Allows fast retrieval of flows between specific source/target cluster pairs
       - Improves multi-round Sankey diagram rendering performance
       - Complements existing single-column indexes on source and target

    3. idx_thought_spaces_round_created (round_id, created_at)
       - Optimizes temporal ordering queries for multi-round visualization
       - Enables efficient retrieval of thought spaces in chronological order
       - Supports Sankey diagram column ordering by round sequence
       - created_at provides stable sort order within each round

    Note: idx_approved_summary_round_participant already exists from 002_user_story_1
    (unique index on round_id, participant_id for last-approved-wins enforcement)
    """

    # Index 1: approved_summaries (round_id, cluster_id)
    # Optimizes: SELECT participant_id FROM approved_summaries
    #            WHERE round_id = ? AND cluster_id = ?
    # Used by: FlowService._get_participants_in_cluster()
    op.create_index(
        'idx_approved_summaries_round_cluster',
        'approved_summaries',
        ['round_id', 'cluster_id'],
        unique=False
    )

    # Index 2: flows (source_cluster_id, target_cluster_id)
    # Optimizes: SELECT * FROM flows
    #            WHERE source_cluster_id = ? AND target_cluster_id = ?
    # Used by: Sankey diagram construction, flow validation
    op.create_index(
        'idx_flows_source_target',
        'flows',
        ['source_cluster_id', 'target_cluster_id'],
        unique=False
    )

    # Index 3: thought_spaces (round_id, created_at)
    # Optimizes: SELECT * FROM thought_spaces
    #            WHERE round_id = ? ORDER BY created_at
    # Used by: Multi-round Sankey column ordering, temporal visualization
    op.create_index(
        'idx_thought_spaces_round_created',
        'thought_spaces',
        ['round_id', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    """
    Remove User Story 2 optimization indexes.
    """
    # Drop indexes in reverse order
    op.drop_index('idx_thought_spaces_round_created', table_name='thought_spaces')
    op.drop_index('idx_flows_source_target', table_name='flows')
    op.drop_index('idx_approved_summaries_round_cluster', table_name='approved_summaries')
