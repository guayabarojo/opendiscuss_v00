-- Database Schema: Semantic Clustering & Hybrid Alignment Protocol (Spec 004)
-- PostgreSQL 15+ with pgvector extension
-- Date: 2026-02-02
-- Purpose: Stores embeddings, clusters, cluster membership, and cross-round alignment
--          for semantic clustering of approved summaries into thought spaces

-- ============================================================================
-- Extension: pgvector for semantic vector operations
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- Table: embeddings
-- Purpose: Stores semantic embedding vectors for approved summary texts.
--          Enables deterministic clustering and medoid recalculation.
-- Dependencies: Requires approved_summaries table from Spec 003
-- ============================================================================

CREATE TABLE embeddings (
    -- Primary key linking to approved summary
    summary_id UUID PRIMARY KEY,

    -- Semantic embedding vector (384 dimensions from SBERT all-MiniLM-L6-v2)
    -- Normalized to L2 norm = 1.0 for optimized cosine similarity computation
    embedding_vector vector(384) NOT NULL,

    -- Model version for reproducibility and future model upgrades
    -- Default: 'all-MiniLM-L6-v2' (SBERT model)
    model_version VARCHAR(50) NOT NULL DEFAULT 'all-MiniLM-L6-v2',

    -- Timestamp for audit trail
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Foreign key constraint: embedding must link to approved summary
    CONSTRAINT fk_summary
        FOREIGN KEY (summary_id)
        REFERENCES approved_summaries(summary_id)
        ON DELETE CASCADE
);

-- Index for model version queries (useful for model migration/upgrade)
CREATE INDEX idx_embeddings_model_version
    ON embeddings(model_version);

-- ============================================================================
-- Table: clusters
-- Purpose: Represents semantic groupings of approved summaries (thought spaces).
--          Core aggregation unit for Sankey visualization (Spec 005).
-- Dependencies: Requires rounds table and approved_summaries table
-- ============================================================================

CREATE TABLE clusters (
    -- Unique cluster identifier (auto-generated)
    cluster_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Round this cluster belongs to
    round_id UUID NOT NULL,

    -- Number of participants in this cluster (must be > 0)
    -- Computed from cluster_members table
    user_count INT NOT NULL CHECK (user_count > 0),

    -- Percentage of total participants in round (0.0 to 1.0)
    -- Sum across all clusters in a round must equal 1.0 ± 0.0001
    user_pct FLOAT NOT NULL CHECK (user_pct > 0 AND user_pct <= 1.0),

    -- Medoid summary used as cluster label (actual participant language)
    -- Label is the cluster member closest to centroid (deterministic)
    label_summary_id UUID NOT NULL,

    -- Mean embedding of all member summaries (384 dimensions)
    -- Used for cross-round alignment and flow calculation
    centroid_vector vector(384) NOT NULL,

    -- Timestamp for audit trail
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Foreign key constraint: cluster belongs to a round
    CONSTRAINT fk_round
        FOREIGN KEY (round_id)
        REFERENCES rounds(round_id)
        ON DELETE CASCADE,

    -- Foreign key constraint: label must be an approved summary
    CONSTRAINT fk_label_summary
        FOREIGN KEY (label_summary_id)
        REFERENCES approved_summaries(summary_id)
);

-- Index for round-based queries (fetch all clusters for a round)
CREATE INDEX idx_clusters_round
    ON clusters(round_id);

-- Index for label summary lookup
CREATE INDEX idx_clusters_label_summary
    ON clusters(label_summary_id);

-- Index for centroid similarity queries during alignment
-- Uses IVFFlat algorithm with cosine distance for approximate nearest neighbor search
CREATE INDEX idx_clusters_centroid
    ON clusters USING ivfflat (centroid_vector vector_cosine_ops)
    WITH (lists = 100);

-- ============================================================================
-- Table: cluster_members
-- Purpose: Join table linking clusters to their member summaries and participants.
--          Enforces one summary per user per cluster constraint.
-- Dependencies: Requires clusters and approved_summaries tables
-- ============================================================================

CREATE TABLE cluster_members (
    -- Cluster this member belongs to
    cluster_id UUID NOT NULL,

    -- Approved summary in this cluster
    summary_id UUID NOT NULL,

    -- Participant who submitted the summary
    user_id UUID NOT NULL,

    -- Composite primary key: each summary appears in exactly one cluster
    PRIMARY KEY (cluster_id, summary_id),

    -- Foreign key constraint: member belongs to a cluster
    CONSTRAINT fk_cluster
        FOREIGN KEY (cluster_id)
        REFERENCES clusters(cluster_id)
        ON DELETE CASCADE,

    -- Foreign key constraint: member must be an approved summary
    CONSTRAINT fk_summary
        FOREIGN KEY (summary_id)
        REFERENCES approved_summaries(summary_id)
        ON DELETE CASCADE,

    -- Unique constraint: one summary per user per cluster (denormalized for query performance)
    CONSTRAINT uq_user_per_cluster
        UNIQUE (cluster_id, user_id)
);

-- Index for summary-based queries (find which cluster a summary belongs to)
CREATE INDEX idx_cluster_members_summary
    ON cluster_members(summary_id);

-- Index for user-based queries (find which cluster a user belongs to in a round)
CREATE INDEX idx_cluster_members_user
    ON cluster_members(user_id);

-- ============================================================================
-- Table: alignment_maps
-- Purpose: Records cross-round alignment between semantically similar clusters
--          for visual continuity in Sankey diagrams. Presentation-only, does
--          not affect cluster membership or flow calculations.
-- Dependencies: Requires clusters table
-- ============================================================================

CREATE TABLE alignment_maps (
    -- Unique alignment record identifier (auto-generated)
    alignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Discussion context for this alignment
    discussion_id UUID NOT NULL,

    -- Earlier round number (r)
    round_r INT NOT NULL,

    -- Later round number (r+1) - must be adjacent
    round_r1 INT NOT NULL,

    -- Cluster from round r
    cluster_r_id UUID NOT NULL,

    -- Cluster from round r+1
    cluster_r1_id UUID NOT NULL,

    -- Cosine similarity between centroids (0.0 to 1.0)
    -- Must be >= ALIGN_THRESHOLD (default 0.7) for inclusion
    similarity_score FLOAT NOT NULL CHECK (similarity_score >= 0 AND similarity_score <= 1.0),

    -- Visual grouping ID for aligned clusters (same ID = aligned)
    -- Used for color continuity and label families in Sankey visualization
    display_group_id UUID,

    -- Timestamp for audit trail
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Foreign key constraint: alignment references cluster from round r
    CONSTRAINT fk_cluster_r
        FOREIGN KEY (cluster_r_id)
        REFERENCES clusters(cluster_id)
        ON DELETE CASCADE,

    -- Foreign key constraint: alignment references cluster from round r+1
    CONSTRAINT fk_cluster_r1
        FOREIGN KEY (cluster_r1_id)
        REFERENCES clusters(cluster_id)
        ON DELETE CASCADE,

    -- Check constraint: rounds must be adjacent (r+1 follows r)
    CONSTRAINT chk_adjacent_rounds
        CHECK (round_r1 = round_r + 1)
);

-- Index for discussion and round-based queries
CREATE INDEX idx_alignment_discussion
    ON alignment_maps(discussion_id, round_r, round_r1);

-- Index for display group queries (find all aligned clusters in a group)
CREATE INDEX idx_alignment_display_group
    ON alignment_maps(display_group_id);

-- Index for cluster pair lookups
CREATE INDEX idx_alignment_clusters
    ON alignment_maps(cluster_r_id, cluster_r1_id);

-- ============================================================================
-- Schema Validation Queries
-- ============================================================================

-- Query to verify 100% participant coverage per round
-- SELECT COUNT(DISTINCT cm.user_id) AS assigned_users
-- FROM cluster_members cm
-- JOIN clusters c ON cm.cluster_id = c.cluster_id
-- WHERE c.round_id = ?;
-- -- Result must equal total participants in round

-- Query to verify user_pct sum equals 1.0 per round
-- SELECT SUM(user_pct) AS total_pct
-- FROM clusters
-- WHERE round_id = ?;
-- -- Result must be 1.0 ± 0.0001

-- Query to verify medoid is a cluster member
-- SELECT COUNT(*) AS is_member
-- FROM clusters c
-- JOIN cluster_members cm ON c.cluster_id = cm.cluster_id AND c.label_summary_id = cm.summary_id
-- WHERE c.cluster_id = ?;
-- -- Result must be 1 (label_summary_id must be in cluster_members)

-- ============================================================================
-- End of Schema
-- ============================================================================
