"""Create Spec 004 Clustering & Alignment tables with pgvector support.

Revision ID: 013_create_spec004_clustering
Revises: 012_summary_indexes
Create Date: 2026-02-02

Tasks T006-T009, T010: Create database schema for Spec 004
- T006: Create embeddings table with pgvector support
- T007: Create clusters table
- T008: Create cluster_members table
- T009: Create alignment_maps table
- T010: Run database migrations

This migration sets up all tables required for:
1. Semantic clustering of approved summaries into thought spaces (User Story 1)
2. Cross-round alignment for visual continuity in Sankey diagrams (User Story 4)
3. Handling of outliers as singleton clusters (User Story 3)
4. Deterministic medoid labeling with actual participant language (User Story 5)

All tables include pgvector extension support for semantic vector operations.
Vectors are 384-dimensional from SBERT all-MiniLM-L6-v2 model.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY


# revision identifiers, used by Alembic.
revision: str = "013_create_spec004_clustering"
down_revision: Union[str, None] = "012_summary_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Spec 004 clustering and alignment tables with pgvector support."""

    # ====================================================================
    # Step 1: Create pgvector extension if not already created
    # ====================================================================
    # This is safe to run multiple times (CREATE EXTENSION IF NOT EXISTS)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ====================================================================
    # Step 2: Create embeddings table (T006)
    # ====================================================================
    # Purpose: Stores semantic embedding vectors for approved summary texts.
    # Enables deterministic clustering and medoid recalculation.
    # Dependencies: Requires approved_summaries table from Spec 003
    # ====================================================================
    op.create_table(
        "embeddings",
        sa.Column(
            "summary_id",
            UUID(as_uuid=True),
            sa.ForeignKey("summaries.summary_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
            comment="Foreign key linking to approved summary",
        ),
        sa.Column(
            "embedding_vector",
            sa.String,  # pgvector(384) type - stored as String in SQLAlchemy
            nullable=False,
            comment="384-dimensional semantic embedding from SBERT all-MiniLM-L6-v2",
        ),
        sa.Column(
            "model_version",
            sa.String(50),
            nullable=False,
            server_default="all-MiniLM-L6-v2",
            comment="Model version for reproducibility and determinism tracking",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="Timestamp for audit trail",
        ),
    )

    # Create index for model version queries (useful for model migration/upgrade)
    op.create_index(
        "idx_embeddings_model_version",
        "embeddings",
        ["model_version"],
        unique=False,
    )

    # ====================================================================
    # Step 3: Create clusters table (T007)
    # ====================================================================
    # Purpose: Represents semantic groupings of approved summaries (thought spaces).
    # Core aggregation unit for Sankey visualization (Spec 005).
    # Dependencies: Requires rounds table and approved_summaries table
    # ====================================================================
    op.create_table(
        "clusters",
        sa.Column(
            "cluster_id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique cluster identifier",
        ),
        sa.Column(
            "round_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rounds.round_id", ondelete="CASCADE"),
            nullable=False,
            comment="Round this cluster belongs to",
        ),
        sa.Column(
            "user_count",
            sa.Integer(),
            nullable=False,
            comment="Number of participants in this cluster",
        ),
        sa.Column(
            "user_pct",
            sa.Float(),
            nullable=False,
            comment="Percentage of total participants in round (0.0 to 1.0)",
        ),
        sa.Column(
            "label_summary_id",
            UUID(as_uuid=True),
            sa.ForeignKey("summaries.summary_id"),
            nullable=False,
            comment="Medoid summary used as cluster label (actual participant language)",
        ),
        sa.Column(
            "centroid_vector",
            sa.String,  # pgvector(384) type - stored as String in SQLAlchemy
            nullable=False,
            comment="Mean embedding of all member summaries (384 dimensions)",
        ),
        sa.Column(
            "display_group_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Visual grouping ID for aligned clusters (for Sankey continuity)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="Timestamp for audit trail",
        ),
        # Constraints
        sa.CheckConstraint("user_count > 0", name="chk_user_count_positive"),
        sa.CheckConstraint(
            "user_pct > 0 AND user_pct <= 1.0", name="chk_user_pct_valid"
        ),
    )

    # Create index for round-based queries (fetch all clusters for a round)
    op.create_index(
        "idx_clusters_round",
        "clusters",
        ["round_id"],
        unique=False,
    )

    # Create index for label summary lookup
    op.create_index(
        "idx_clusters_label_summary",
        "clusters",
        ["label_summary_id"],
        unique=False,
    )

    # Create index for centroid similarity queries during alignment
    # Uses IVFFlat algorithm with cosine distance for approximate nearest neighbor search
    op.execute(
        """
        CREATE INDEX idx_clusters_centroid
        ON clusters USING ivfflat (centroid_vector vector_cosine_ops)
        WITH (lists = 100)
        """
    )

    # Create index for display_group queries (find all clusters in a group)
    op.create_index(
        "idx_clusters_display_group",
        "clusters",
        ["display_group_id"],
        unique=False,
    )

    # ====================================================================
    # Step 4: Create cluster_members table (T008)
    # ====================================================================
    # Purpose: Join table linking clusters to their member summaries and participants.
    # Enforces one summary per user per cluster constraint.
    # Dependencies: Requires clusters and approved_summaries tables
    # ====================================================================
    op.create_table(
        "cluster_members",
        sa.Column(
            "cluster_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clusters.cluster_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
            comment="Cluster this member belongs to",
        ),
        sa.Column(
            "summary_id",
            UUID(as_uuid=True),
            sa.ForeignKey("summaries.summary_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
            comment="Approved summary in this cluster",
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="Participant who submitted the summary",
        ),
        # Unique constraint: one summary per user per cluster
        sa.UniqueConstraint(
            "cluster_id",
            "user_id",
            name="uq_user_per_cluster",
            comment="One user can only appear once per cluster",
        ),
    )

    # Create index for summary-based queries (find which cluster a summary belongs to)
    op.create_index(
        "idx_cluster_members_summary",
        "cluster_members",
        ["summary_id"],
        unique=False,
    )

    # Create index for user-based queries (find which cluster a user belongs to in a round)
    op.create_index(
        "idx_cluster_members_user",
        "cluster_members",
        ["user_id"],
        unique=False,
    )

    # ====================================================================
    # Step 5: Create alignment_maps table (T009)
    # ====================================================================
    # Purpose: Records cross-round alignment between semantically similar clusters
    # for visual continuity in Sankey diagrams. Presentation-only, does
    # not affect cluster membership or flow calculations.
    # Dependencies: Requires clusters table
    # ====================================================================
    op.create_table(
        "alignment_maps",
        sa.Column(
            "alignment_id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique alignment record identifier",
        ),
        sa.Column(
            "discussion_id",
            UUID(as_uuid=True),
            sa.ForeignKey("discussions.discussion_id", ondelete="CASCADE"),
            nullable=False,
            comment="Discussion context for this alignment",
        ),
        sa.Column(
            "round_r",
            sa.Integer(),
            nullable=False,
            comment="Earlier round number (r)",
        ),
        sa.Column(
            "round_r1",
            sa.Integer(),
            nullable=False,
            comment="Later round number (r+1) - must be adjacent",
        ),
        sa.Column(
            "cluster_r_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clusters.cluster_id", ondelete="CASCADE"),
            nullable=False,
            comment="Cluster from round r",
        ),
        sa.Column(
            "cluster_r1_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clusters.cluster_id", ondelete="CASCADE"),
            nullable=False,
            comment="Cluster from round r+1",
        ),
        sa.Column(
            "similarity_score",
            sa.Float(),
            nullable=False,
            comment="Cosine similarity between centroids (0.0 to 1.0)",
        ),
        sa.Column(
            "display_group_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Visual grouping ID for aligned clusters (same ID = aligned)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="Timestamp for audit trail",
        ),
        # Constraints
        sa.CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1.0",
            name="chk_similarity_valid",
        ),
        sa.CheckConstraint(
            "round_r1 = round_r + 1", name="chk_adjacent_rounds"
        ),
    )

    # Create index for discussion and round-based queries
    op.create_index(
        "idx_alignment_discussion",
        "alignment_maps",
        ["discussion_id", "round_r", "round_r1"],
        unique=False,
    )

    # Create index for display group queries (find all aligned clusters in a group)
    op.create_index(
        "idx_alignment_display_group",
        "alignment_maps",
        ["display_group_id"],
        unique=False,
    )

    # Create index for cluster pair lookups
    op.create_index(
        "idx_alignment_clusters",
        "alignment_maps",
        ["cluster_r_id", "cluster_r1_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop Spec 004 clustering and alignment tables."""
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table("alignment_maps")
    op.drop_table("cluster_members")
    op.drop_table("clusters")
    op.drop_table("embeddings")

    # Note: We do NOT drop the pgvector extension as it may be used by other features
    # and dropping it could affect other extensions/functions
