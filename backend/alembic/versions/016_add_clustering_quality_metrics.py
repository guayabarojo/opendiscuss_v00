"""Add clustering quality metrics tables

Revision ID: 016_add_clustering_quality_metrics
Revises: 20260201_2015-0addeeb322ed
Create Date: 2026-02-06

Adds tables to track clustering quality metrics and near-duplicate warnings.
Supports continuous quality monitoring and improvement validation.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '016_add_clustering_quality_metrics'
down_revision = '015_add_async_timing_mode'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create cluster_quality_metrics table
    op.create_table(
        'cluster_quality_metrics',
        sa.Column('metric_id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('round_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('silhouette_score', sa.Float, nullable=True, comment='Silhouette score: [-1, 1], higher is better'),
        sa.Column('davies_bouldin_index', sa.Float, nullable=True, comment='Davies-Bouldin index: [0, ∞], lower is better'),
        sa.Column('near_duplicate_count', sa.Integer, nullable=False, default=0, comment='Count of cluster pairs with >0.8 similarity'),
        sa.Column('singleton_count', sa.Integer, nullable=False, comment='Number of single-member clusters'),
        sa.Column('avg_cluster_size', sa.Float, nullable=False, comment='Average participants per cluster'),
        sa.Column('min_within_cluster_cohesion', sa.Float, nullable=True, comment='Minimum intra-cluster similarity'),
        sa.Column('max_within_cluster_cohesion', sa.Float, nullable=True, comment='Maximum intra-cluster similarity'),
        sa.Column('avg_within_cluster_cohesion', sa.Float, nullable=True, comment='Average intra-cluster similarity'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('metric_id'),
        sa.ForeignKeyConstraint(['round_id'], ['rounds.round_id'], ondelete='CASCADE'),
        comment='Quality metrics for clustering results per round'
    )

    # Create index for fast round lookups
    op.create_index('idx_quality_metrics_round', 'cluster_quality_metrics', ['round_id'])

    # Create cluster_similarity_warnings table
    op.create_table(
        'cluster_similarity_warnings',
        sa.Column('warning_id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('round_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cluster_i_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cluster_j_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('similarity_score', sa.Float, nullable=False, comment='Cosine similarity between cluster centroids'),
        sa.Column('cluster_i_label', sa.Text, nullable=True, comment='Label text for cluster i'),
        sa.Column('cluster_j_label', sa.Text, nullable=True, comment='Label text for cluster j'),
        sa.Column('cluster_i_size', sa.Integer, nullable=False, comment='Member count for cluster i'),
        sa.Column('cluster_j_size', sa.Integer, nullable=False, comment='Member count for cluster j'),
        sa.Column('reviewed', sa.Boolean, nullable=False, default=False, comment='Has this warning been reviewed by a human?'),
        sa.Column('review_decision', sa.String(50), nullable=True, comment='Human decision: merge, keep_separate, defer'),
        sa.Column('review_notes', sa.Text, nullable=True, comment='Optional notes from human review'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('warning_id'),
        sa.ForeignKeyConstraint(['round_id'], ['rounds.round_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_i_id'], ['thought_spaces.cluster_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_j_id'], ['thought_spaces.cluster_id'], ondelete='CASCADE'),
        comment='Near-duplicate cluster warnings for human review'
    )

    # Create indexes
    op.create_index('idx_similarity_warnings_round', 'cluster_similarity_warnings', ['round_id'])
    op.create_index('idx_similarity_warnings_reviewed', 'cluster_similarity_warnings', ['reviewed'])
    op.create_index('idx_similarity_warnings_similarity', 'cluster_similarity_warnings', ['similarity_score'], postgresql_using='btree')


def downgrade() -> None:
    op.drop_index('idx_similarity_warnings_similarity', table_name='cluster_similarity_warnings')
    op.drop_index('idx_similarity_warnings_reviewed', table_name='cluster_similarity_warnings')
    op.drop_index('idx_similarity_warnings_round', table_name='cluster_similarity_warnings')
    op.drop_table('cluster_similarity_warnings')

    op.drop_index('idx_quality_metrics_round', table_name='cluster_quality_metrics')
    op.drop_table('cluster_quality_metrics')
