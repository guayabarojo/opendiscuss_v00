# Data Model: Semantic Clustering & Hybrid Alignment Protocol

**Feature**: Semantic Clustering & Hybrid Alignment Protocol (Spec 004)
**Date**: 2026-01-29
**Phase**: Phase 1 - Design

## Purpose

This document defines the data model for semantic clustering of approved summaries into thought spaces, including entities, schemas, relationships, validation rules, and state transitions. Extracted from functional requirements in spec.md and informed by research.md technology decisions.

---

## Entity Relationship Diagram

```
┌─────────────────────┐
│  ApprovedSummary    │ (From Spec 3)
│                     │
│  summary_id (PK)    │
│  user_id            │
│  round_id           │
│  summary_text       │
│  approved_at        │
└──────────┬──────────┘
           │
           │ (Input to clustering)
           ▼
┌─────────────────────┐
│  Embedding          │
│                     │
│  summary_id (PK)    │◄────────┐
│  embedding_vector   │         │
│  model_version      │         │
│  created_at         │         │
└──────────┬──────────┘         │
           │                    │
           │ (Clustered)        │
           ▼                    │
┌─────────────────────┐         │
│  Cluster            │         │
│  (ThoughtSpace)     │         │
│                     │         │
│  cluster_id (PK)    │         │
│  round_id (FK)      │         │
│  user_count         │         │
│  user_pct           │         │
│  label_summary_id   ├─────────┘ (medoid)
│  centroid_vector    │
│  created_at         │
└──────────┬──────────┘
           │
           │ (Members)
           ▼
┌─────────────────────┐
│  ClusterMember      │
│                     │
│  cluster_id (FK)    │
│  summary_id (FK)    │
│  user_id            │
└─────────────────────┘


┌─────────────────────┐
│  AlignmentMap       │
│                     │
│  alignment_id (PK)  │
│  discussion_id      │
│  round_r            │
│  round_r1           │
│  cluster_r_id (FK)  ├────────┐
│  cluster_r1_id (FK) ├────┐   │
│  similarity_score   │    │   │
│  display_group_id   │    │   │
│  created_at         │    │   │
└─────────────────────┘    │   │
                           │   │
                           ▼   ▼
                    ┌─────────────────────┐
                    │  Cluster (Round r)  │
                    │  Cluster (Round r+1)│
                    └─────────────────────┘
```

**Legend**:
- **PK**: Primary key
- **FK**: Foreign key relationship
- Embedding → Cluster: One-to-one (each summary embedded once, assigned to one cluster)
- Cluster → ClusterMember: One-to-many (cluster has multiple members)
- AlignmentMap: Many-to-many between clusters across adjacent rounds

---

## Persistent Entities

### 1. Embedding

**Purpose**: Stores semantic embedding vectors for approved summary texts. Enables deterministic clustering and medoid recalculation.

**Schema**:
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embeddings (
    summary_id UUID PRIMARY KEY,
    embedding_vector vector(384),  -- SBERT all-MiniLM-L6-v2 produces 384-dim vectors
    model_version VARCHAR(50) NOT NULL DEFAULT 'all-MiniLM-L6-v2',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_summary
        FOREIGN KEY (summary_id)
        REFERENCES approved_summaries(summary_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_embeddings_model_version
    ON embeddings(model_version);
```

**Fields**:

| Field | Type | Constraints | Description | Source Requirement |
|-------|------|-------------|-------------|-------------------|
| `summary_id` | UUID | PRIMARY KEY, FK | Links to approved summary | FR-004 |
| `embedding_vector` | vector(384) | NOT NULL | Semantic embedding (384 dimensions) | FR-005, FR-008 |
| `model_version` | VARCHAR(50) | NOT NULL | Model version for reproducibility | FR-007, Assumption 2 |
| `created_at` | TIMESTAMP | NOT NULL | Embedding generation timestamp | Audit trail |

**Validation Rules**:
- `embedding_vector` must be 384 dimensions (SBERT MiniLM output)
- `embedding_vector` must be normalized (L2 norm = 1.0 for cosine similarity optimization)
- `model_version` must match current deployment version
- Embedding is immutable after creation (same summary_id → same vector)

**Lifecycle**:
- **Created**: When approved summary enters clustering pipeline
- **Read**: During clustering (HDBSCAN input), medoid selection, alignment
- **Updated**: Never (immutable)
- **Deleted**: When summary is deleted (CASCADE)

**Determinism Guarantee** (FR-007, SC-007):
```python
# Same text always produces same embedding
embedding1 = model.encode([summary_text])[0]
embedding2 = model.encode([summary_text])[0]
assert np.allclose(embedding1, embedding2, atol=1e-9)
```

---

### 2. Cluster (Thought Space)

**Purpose**: Represents a semantic grouping of approved summaries (thought space). Core aggregation unit for Sankey visualization.

**Schema**:
```sql
CREATE TABLE clusters (
    cluster_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    round_id UUID NOT NULL,
    user_count INT NOT NULL CHECK (user_count > 0),
    user_pct FLOAT NOT NULL CHECK (user_pct > 0 AND user_pct <= 1.0),
    label_summary_id UUID NOT NULL,
    centroid_vector vector(384) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_round
        FOREIGN KEY (round_id)
        REFERENCES rounds(round_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_label_summary
        FOREIGN KEY (label_summary_id)
        REFERENCES approved_summaries(summary_id)
);

CREATE INDEX idx_clusters_round
    ON clusters(round_id);
CREATE INDEX idx_clusters_label_summary
    ON clusters(label_summary_id);

-- Index for centroid similarity queries (alignment)
CREATE INDEX idx_clusters_centroid
    ON clusters USING ivfflat (centroid_vector vector_cosine_ops);
```

**Fields**:

| Field | Type | Constraints | Description | Source Requirement |
|-------|------|-------------|-------------|-------------------|
| `cluster_id` | UUID | PRIMARY KEY | Unique cluster identifier (per-round) | FR-020 |
| `round_id` | UUID | NOT NULL, FK | Round this cluster belongs to | FR-040 |
| `user_count` | INT | NOT NULL, > 0 | Number of participants in cluster | FR-018 |
| `user_pct` | FLOAT | NOT NULL, 0-1 | Percentage of total participants | FR-019 |
| `label_summary_id` | UUID | NOT NULL, FK | Medoid summary used as label | FR-021, FR-024 |
| `centroid_vector` | vector(384) | NOT NULL | Mean embedding of member summaries | FR-026, FR-027 |
| `created_at` | TIMESTAMP | NOT NULL | Cluster creation timestamp | Audit trail |

**Validation Rules**:
- `user_count` equals number of unique `user_id` in `cluster_members` (FR-018)
- `user_pct` sum across all clusters in round must equal 1.0 ± 0.0001 (FR-019, SC-005)
- `label_summary_id` must be a member of this cluster (medoid is a cluster member)
- `centroid_vector` must be mean of member embedding vectors (FR-027)
- `cluster_id` unique within round (may reuse across rounds per FR-041)

**Cluster Types**:
- **Regular Cluster**: `user_count ≥ 2` (normal semantic grouping)
- **Singleton Cluster**: `user_count = 1` (outlier converted per FR-014)

**Lifecycle**:
- **Created**: After HDBSCAN clustering completes for a round
- **Read**: By Spec 5 (Sankey Construction) for visualization, by alignment service
- **Updated**: Never (immutable once created)
- **Deleted**: When round is deleted (CASCADE)

**Invariants**:
- Every participant assigned to exactly one cluster per round (FR-016, SC-003)
- No minimum cluster size enforced (FR-012, SC-004)
- All clusters visible (no hiding of singletons per FR-015)

---

### 3. ClusterMember

**Purpose**: Join table linking clusters to their member summaries and participants.

**Schema**:
```sql
CREATE TABLE cluster_members (
    cluster_id UUID NOT NULL,
    summary_id UUID NOT NULL,
    user_id UUID NOT NULL,
    PRIMARY KEY (cluster_id, summary_id),

    CONSTRAINT fk_cluster
        FOREIGN KEY (cluster_id)
        REFERENCES clusters(cluster_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_summary
        FOREIGN KEY (summary_id)
        REFERENCES approved_summaries(summary_id)
        ON DELETE CASCADE,
    CONSTRAINT uq_user_per_cluster_in_round
        UNIQUE (cluster_id, user_id)  -- One summary per user per cluster
);

CREATE INDEX idx_cluster_members_summary
    ON cluster_members(summary_id);
CREATE INDEX idx_cluster_members_user
    ON cluster_members(user_id);
```

**Fields**:

| Field | Type | Constraints | Description | Source Requirement |
|-------|------|-------------|-------------|-------------------|
| `cluster_id` | UUID | PRIMARY KEY (composite), FK | Cluster this member belongs to | - |
| `summary_id` | UUID | PRIMARY KEY (composite), FK | Approved summary in cluster | FR-017 |
| `user_id` | UUID | NOT NULL | Participant who submitted summary | FR-017 |

**Validation Rules**:
- Each `summary_id` appears in exactly one cluster per round (FR-016)
- Each `user_id` appears in exactly one cluster per round (SC-003)
- All approved summaries for a round must be assigned (100% coverage per FR-016)

**Lifecycle**:
- **Created**: During cluster assignment after HDBSCAN completes
- **Read**: For cluster member queries, user count calculation, medoid selection
- **Updated**: Never (immutable)
- **Deleted**: When cluster or summary is deleted (CASCADE)

**Query Patterns**:
```sql
-- Get all members of a cluster
SELECT summary_id, user_id
FROM cluster_members
WHERE cluster_id = ?;

-- Get cluster for a specific user in a round
SELECT c.cluster_id, c.label_summary_id
FROM clusters c
JOIN cluster_members cm ON c.cluster_id = cm.cluster_id
WHERE cm.user_id = ? AND c.round_id = ?;

-- Verify 100% coverage
SELECT COUNT(DISTINCT user_id) AS assigned_users
FROM cluster_members cm
JOIN clusters c ON cm.cluster_id = c.cluster_id
WHERE c.round_id = ?;
-- Must equal total participants in round
```

---

### 4. AlignmentMap

**Purpose**: Records cross-round alignment between semantically similar clusters for visual continuity. Presentation-only, does not affect cluster membership.

**Schema**:
```sql
CREATE TABLE alignment_maps (
    alignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discussion_id UUID NOT NULL,
    round_r INT NOT NULL,
    round_r1 INT NOT NULL,
    cluster_r_id UUID NOT NULL,
    cluster_r1_id UUID NOT NULL,
    similarity_score FLOAT NOT NULL CHECK (similarity_score >= 0 AND similarity_score <= 1.0),
    display_group_id UUID,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_cluster_r
        FOREIGN KEY (cluster_r_id)
        REFERENCES clusters(cluster_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_cluster_r1
        FOREIGN KEY (cluster_r1_id)
        REFERENCES clusters(cluster_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_adjacent_rounds
        CHECK (round_r1 = round_r + 1)
);

CREATE INDEX idx_alignment_discussion
    ON alignment_maps(discussion_id, round_r, round_r1);
CREATE INDEX idx_alignment_display_group
    ON alignment_maps(display_group_id);
CREATE INDEX idx_alignment_clusters
    ON alignment_maps(cluster_r_id, cluster_r1_id);
```

**Fields**:

| Field | Type | Constraints | Description | Source Requirement |
|-------|------|-------------|-------------|-------------------|
| `alignment_id` | UUID | PRIMARY KEY | Unique alignment record | - |
| `discussion_id` | UUID | NOT NULL | Discussion context | - |
| `round_r` | INT | NOT NULL | Earlier round number | FR-029 |
| `round_r1` | INT | NOT NULL | Later round number (r+1) | FR-029 |
| `cluster_r_id` | UUID | NOT NULL, FK | Cluster from round r | FR-030 |
| `cluster_r1_id` | UUID | NOT NULL, FK | Cluster from round r+1 | FR-030 |
| `similarity_score` | FLOAT | NOT NULL, 0-1 | Cosine similarity of centroids | FR-031 |
| `display_group_id` | UUID | NULL | Visual grouping ID (same ID = aligned) | FR-036 |
| `created_at` | TIMESTAMP | NOT NULL | Alignment computation timestamp | Audit trail |

**Validation Rules**:
- `round_r1` must equal `round_r + 1` (adjacent rounds only per FR-029)
- `similarity_score` must be ≥ ALIGN_THRESHOLD (default 0.7) for inclusion (FR-032, FR-033)
- `display_group_id` same across all aligned clusters (visual continuity)
- Alignment does NOT modify `clusters` or `cluster_members` tables (FR-037, SC-009)

**Alignment Types** (FR-035):
- **1-to-1**: One cluster in r maps to one cluster in r+1 (continuity)
- **1-to-many (split)**: One cluster in r maps to multiple clusters in r+1
- **many-to-1 (merge)**: Multiple clusters in r map to one cluster in r+1

**Example Alignment**:
```
Round 1 Cluster A (cost concerns) → similarity 0.85 → Round 2 Cluster X (budget constraints)
Round 1 Cluster B (speed)        → similarity 0.75 → Round 2 Cluster Y (performance)
Round 1 Cluster B (speed)        → similarity 0.72 → Round 2 Cluster Z (latency)  [SPLIT]
```

**Lifecycle**:
- **Created**: After clustering both rounds r and r+1 completes
- **Read**: By Spec 5 (Sankey) for color/label continuity, by UI for display groups
- **Updated**: Never (immutable)
- **Deleted**: When discussion or clusters are deleted (CASCADE)

**Presentation-Only Guarantee** (FR-037, FR-038, FR-039):
```python
# Before alignment
original_clusters = get_clusters(round_id)

# Compute alignment
alignment = compute_alignment(round_r, round_r1)

# After alignment
assert get_clusters(round_id) == original_clusters  # UNCHANGED
```

---

## Computed/Derived Entities

### 5. Medoid

**Purpose**: Conceptual entity representing the cluster member closest to centroid (used as label). Not stored separately, computed from Cluster + ClusterMember + Embedding.

**Computation**:
```python
def compute_medoid(cluster_id):
    """
    Select medoid: cluster member with smallest distance to centroid.
    """
    # Get cluster centroid
    centroid = get_cluster_centroid(cluster_id)

    # Get all member embeddings
    members = get_cluster_members(cluster_id)
    member_embeddings = [get_embedding(m.summary_id) for m in members]

    # Compute distances to centroid
    distances = cosine_distances(member_embeddings, [centroid]).flatten()

    # Select min distance
    medoid_idx = np.argmin(distances)

    # Tie-breaking: lexicographic order of summary_id
    if np.sum(distances == distances[medoid_idx]) > 1:
        tied_indices = np.where(distances == distances[medoid_idx])[0]
        tied_summary_ids = [members[i].summary_id for i in tied_indices]
        tied_summary_ids.sort()
        medoid_idx = next(i for i, m in enumerate(members) if m.summary_id == tied_summary_ids[0])

    return members[medoid_idx]
```

**Stored Reference**: `clusters.label_summary_id` points to medoid summary

**Properties**:
- Deterministic (FR-025, SC-006)
- Actual participant language (FR-024, no AI generation)
- Representative of cluster center (FR-022)

---

## State Transitions

### Clustering Workflow State Machine

```
┌──────────────────────┐
│ Approved Summaries   │ (From Spec 3)
│ Ready for Clustering │
└──────────┬───────────┘
           │
           │ (Trigger: All summaries approved for round)
           ▼
┌──────────────────────┐
│ Generate Embeddings  │
│ - SBERT MiniLM       │
│ - 384-dim vectors    │
│ - Store in DB        │
└──────────┬───────────┘
           │
           │ (Embeddings ready)
           ▼
┌──────────────────────┐
│ Run HDBSCAN          │
│ - min_cluster_size=2 │
│ - metric=cosine      │
│ - Variable K output  │
└──────────┬───────────┘
           │
           │ (Clustering complete)
           ▼
┌──────────────────────┐
│ Handle Outliers      │
│ - Noise (-1) labels  │
│ - Convert to         │
│   singleton clusters │
└──────────┬───────────┘
           │
           │ (All participants assigned)
           ▼
┌──────────────────────┐
│ Compute Centroids    │
│ - Mean of member     │
│   embeddings         │
│ - Persist vectors    │
└──────────┬───────────┘
           │
           │ (Centroids computed)
           ▼
┌──────────────────────┐
│ Select Medoid Labels │
│ - Closest to centroid│
│ - Tie-breaking by ID │
│ - Store label_summary│
└──────────┬───────────┘
           │
           │ (Labels assigned)
           ▼
┌──────────────────────┐
│ Persist Clusters     │
│ - Write to clusters  │
│   table              │
│ - Write members      │
│ - Validate 100% cov. │
└──────────┬───────────┘
           │
           │ (Round r clustering complete)
           ▼
┌──────────────────────┐
│ Clusters Available   │
│ for Sankey (Spec 5)  │
└──────────────────────┘
```

**State Invariants**:
- After embedding: 100% of summaries have embeddings (FR-008)
- After clustering: 100% of participants assigned to clusters (FR-016, SC-003)
- After outlier handling: No noise labels (-1) remain (FR-014)
- After medoid selection: Every cluster has a label (FR-021)
- After persistence: `user_pct` sum = 1.0 ± 0.0001 (FR-019, SC-005)

---

### Alignment Workflow State Machine

```
┌──────────────────────┐
│ Round r Clustered    │
└──────────┬───────────┘
           │
           │ (Wait for round r+1)
           ▼
┌──────────────────────┐
│ Round r+1 Clustered  │
└──────────┬───────────┘
           │
           │ (Both rounds ready)
           ▼
┌──────────────────────┐
│ Load Centroids       │
│ - Round r centroids  │
│ - Round r+1 centroids│
└──────────┬───────────┘
           │
           │ (Centroids loaded)
           ▼
┌──────────────────────┐
│ Compute Similarity   │
│ Matrix               │
│ - Cosine similarity  │
│ - All pairs (r × r+1)│
└──────────┬───────────┘
           │
           │ (Similarity matrix ready)
           ▼
┌──────────────────────┐
│ Greedy Matching      │
│ - Sort by similarity │
│ - Match ≥ threshold  │
│ - Allow splits/merges│
└──────────┬───────────┘
           │
           │ (Matches identified)
           ▼
┌──────────────────────┐
│ Assign Display Groups│
│ - Same group ID for  │
│   aligned clusters   │
│ - Color families     │
└──────────┬───────────┘
           │
           │ (Display groups assigned)
           ▼
┌──────────────────────┐
│ Persist Alignment    │
│ - Write to           │
│   alignment_maps     │
│ - Verify no membership│
│   changes            │
└──────────┬───────────┘
           │
           │ (Alignment complete)
           ▼
┌──────────────────────┐
│ Alignment Available  │
│ for Sankey Visual    │
│ Continuity           │
└──────────────────────┘
```

**Alignment Invariants**:
- Before alignment: Clusters have original membership
- After alignment: Clusters have SAME membership (FR-037, SC-009)
- Only adjacent rounds aligned (r → r+1) (FR-029)
- Only pairs with similarity ≥ threshold matched (FR-033)
- Display groups affect presentation only (FR-039)

---

## Validation Rules Summary

### Clustering Input Validation (FR-001 to FR-004)

A summary enters clustering if ALL of the following are TRUE:

1. **Approval Status**: Summary must be approved (strict invariant per FR-001)
2. **User Coverage**: Exactly one approved summary per participant per round (FR-002)
3. **Required Fields**: Must include summary_id, user_id, summary_text (FR-004)

**Defensive Check**:
```python
def validate_clustering_input(summaries):
    """Validate approved summaries before clustering."""
    for summary in summaries:
        assert summary.approved == True, "Unapproved summary detected"
        assert summary.summary_id and summary.user_id and summary.summary_text, "Missing fields"

    # Check one summary per user
    user_counts = Counter([s.user_id for s in summaries])
    assert all(count == 1 for count in user_counts.values()), "Multiple summaries per user"
```

---

### Clustering Output Validation (FR-016 to FR-020)

Clustering output is valid if ALL of the following are TRUE:

1. **100% Coverage**: Every user_id assigned to exactly one cluster (FR-016, SC-003)
2. **User Count Accuracy**: `cluster.user_count` equals unique user_ids in members (FR-018)
3. **Percentage Sum**: `sum(user_pct) = 1.0 ± 0.0001` across all clusters (FR-019, SC-005)
4. **Unique Cluster IDs**: `cluster_id` unique within round (FR-020)
5. **No Forced Merging**: Low-frequency clusters preserved (FR-012, SC-004)

**Validation Check**:
```python
def validate_clustering_output(clusters, summaries):
    """Validate clustering results."""
    # 100% coverage
    assigned_users = set()
    for cluster in clusters:
        assigned_users.update(cluster.member_user_ids)
    input_users = set(s.user_id for s in summaries)
    assert assigned_users == input_users, "Not all users assigned"

    # User count accuracy
    for cluster in clusters:
        assert cluster.user_count == len(cluster.member_user_ids), "User count mismatch"

    # Percentage sum
    total_pct = sum(c.user_pct for c in clusters)
    assert abs(total_pct - 1.0) < 0.0001, f"Percentages sum to {total_pct}, not 1.0"

    # No minimum cluster size enforced
    assert any(c.user_count == 1 for c in clusters) or len(clusters) == 1, "Singletons should exist for outliers"
```

---

### Medoid Validation (FR-021 to FR-025)

Medoid label is valid if ALL of the following are TRUE:

1. **Medoid Method**: Label selected as centroid-closest member (FR-021, FR-022)
2. **Same Distance Metric**: Uses cosine distance (same as clustering) (FR-023)
3. **Actual Participant Text**: Label is exact summary_text from medoid (FR-024)
4. **Deterministic**: Same cluster produces same medoid (FR-025, SC-006)

**Validation Check**:
```python
def validate_medoid(cluster, label_summary):
    """Validate medoid label selection."""
    # Label must be a cluster member
    assert label_summary.summary_id in cluster.member_summary_ids, "Label not in cluster"

    # Recompute medoid
    centroid = cluster.centroid_vector
    distances = [cosine_distance(get_embedding(sid), centroid) for sid in cluster.member_summary_ids]
    expected_medoid_idx = np.argmin(distances)
    expected_medoid_id = cluster.member_summary_ids[expected_medoid_idx]

    # Verify matches stored label
    assert label_summary.summary_id == expected_medoid_id, "Medoid mismatch"
```

---

### Alignment Validation (FR-037 to FR-039, SC-009)

Alignment is valid if ALL of the following are TRUE:

1. **Membership Unchanged**: Clusters have same members before and after alignment (FR-037, SC-009)
2. **Flow Calculation Unaffected**: Alignment does not change user_count or user_pct (FR-038)
3. **Presentation Only**: Only `display_group_id` added, no cluster data modified (FR-039)

**Validation Check**:
```python
def validate_alignment_invariance(clusters_before, alignment, clusters_after):
    """Validate alignment doesn't change cluster membership."""
    for c_before, c_after in zip(clusters_before, clusters_after):
        # Same members
        assert c_before.member_user_ids == c_after.member_user_ids, "Members changed"

        # Same metrics
        assert c_before.user_count == c_after.user_count, "User count changed"
        assert c_before.user_pct == c_after.user_pct, "User pct changed"
        assert c_before.centroid_vector == c_after.centroid_vector, "Centroid changed"
```

---

## Data Flow Diagram

### Clustering Data Flow

```
┌─────────────────────────┐
│ Spec 3: Approved         │
│ Summaries Ready          │
└───────────┬─────────────┘
            │
            │ Event: summaries.approved_for_round
            ▼
┌─────────────────────────┐
│ Spec 4: Clustering       │
│ Service                  │
│                          │
│ 1. Fetch summaries       │
│ 2. Generate embeddings   │
│    - SBERT MiniLM        │
│    - Store in embeddings │
│      table               │
│ 3. Run HDBSCAN           │
│    - Variable K          │
│    - Outliers → singletons│
│ 4. Compute centroids     │
│ 5. Select medoid labels  │
│ 6. Persist clusters      │
│    - clusters table      │
│    - cluster_members     │
└───────────┬─────────────┘
            │
            │ Query: GET /api/clusters?round_id={id}
            ▼
┌─────────────────────────┐
│ Spec 5: Sankey           │
│ Construction             │
│                          │
│ - Fetch thought spaces   │
│ - user_count, user_pct   │
│ - label_summary          │
│ - display_group_id (if aligned)│
└─────────────────────────┘
```

---

### Alignment Data Flow

```
┌─────────────────────────┐
│ Round r Clustering       │
│ Complete                 │
└───────────┬─────────────┘
            │
            │ (Wait)
            ▼
┌─────────────────────────┐
│ Round r+1 Clustering     │
│ Complete                 │
└───────────┬─────────────┘
            │
            │ Event: round_r1.clustered
            ▼
┌─────────────────────────┐
│ Alignment Service        │
│                          │
│ 1. Load round r centroids│
│ 2. Load round r+1        │
│    centroids             │
│ 3. Compute similarity    │
│    matrix (cosine)       │
│ 4. Greedy matching       │
│    (≥ threshold)         │
│ 5. Assign display groups │
│ 6. Persist alignment_maps│
└───────────┬─────────────┘
            │
            │ Query: GET /api/alignments?discussion_id={id}
            ▼
┌─────────────────────────┐
│ Spec 5: Sankey with      │
│ Visual Continuity        │
│                          │
│ - Same color for aligned │
│   clusters across rounds │
│ - Label families for     │
│   splits/merges          │
└─────────────────────────┘
```

---

## Integration Contracts

### Contract 1: Spec 3 → Spec 4 (Approved Summaries → Clustering)

**Interface**:
```python
class ApprovedSummary:
    summary_id: UUID
    user_id: UUID
    round_id: UUID
    summary_text: str
    approved_at: datetime
```

**Event** (preferred):
```python
# Publisher: Spec 3
publish_event("summaries.approved_for_round", {
    "round_id": round_id,
    "summary_count": len(summaries),
    "all_approved": True
})

# Subscriber: Spec 4
@on_event("summaries.approved_for_round")
def trigger_clustering(event):
    round_id = event["round_id"]
    summaries = fetch_approved_summaries(round_id)
    clusters = cluster_summaries(summaries)
    persist_clusters(clusters)
```

**Guarantees**:
- Only approved summaries (FR-001)
- Exactly one per participant (FR-002)
- 100% coverage (all approved summaries clustered)

---

### Contract 2: Spec 4 → Spec 5 (Clusters → Sankey Construction)

**Interface**:
```python
class ThoughtSpace:
    cluster_id: UUID
    round_id: UUID
    member_user_ids: List[UUID]
    user_count: int
    user_pct: float
    label_summary: str  # From medoid
    centroid_vector: ndarray  # For flow calculation
    display_group_id: Optional[UUID]  # From alignment (if available)
```

**API Endpoint**:
```http
GET /api/v1/clusters?round_id={round_id}

Response:
{
  "clusters": [
    {
      "cluster_id": "uuid",
      "round_id": "uuid",
      "member_user_ids": ["uuid1", "uuid2", "uuid3"],
      "user_count": 3,
      "user_pct": 0.3,
      "label_summary": "We need to reduce costs by 20%",
      "centroid_vector": [0.123, -0.456, ...],  # 384 dims
      "display_group_id": "uuid"  # Null if no alignment
    }
  ],
  "total_participants": 10,
  "percentage_sum": 1.0
}
```

**Guarantees**:
- 100% participant coverage (SC-003)
- Percentages sum to 1.0 (SC-005)
- Centroids provided for flow calculation (FR-028)
- Display groups for visual continuity (FR-036)

---

## Performance Considerations

### Expected Load (MVP)

- **Embedding generation**: 100 summaries × 10ms = 1 second
- **HDBSCAN clustering**: 100 points × 384 dims = < 2 seconds
- **Medoid selection**: 10 clusters × 10ms = 0.1 seconds
- **Alignment**: 10×10 matrix × cosine similarity = 0.5 seconds
- **Total**: ~3.6 seconds ✅ Under 5s target (SC-001)

### Optimizations

1. **Batch Embedding**:
```python
# Batch all summaries at once (faster than one-by-one)
embeddings = model.encode(summary_texts, batch_size=32, show_progress_bar=False)
```

2. **Normalize Vectors**:
```python
# Normalize for faster cosine similarity (dot product instead)
embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
```

3. **Cache Embeddings**:
```python
# Don't recompute if summary text unchanged
existing = get_embedding(summary_id)
if existing and existing.model_version == current_version:
    return existing.embedding_vector
```

4. **Parallel Medoid Computation**:
```python
# Compute medoid for each cluster in parallel
with ThreadPoolExecutor(max_workers=10) as executor:
    medoids = list(executor.map(select_medoid, clusters))
```

5. **Indexed Centroid Queries**:
```sql
-- Use pgvector index for alignment similarity
SELECT cluster_id, centroid_vector
FROM clusters
WHERE round_id = ?
ORDER BY centroid_vector <=> ? -- Cosine distance operator
LIMIT 10;
```

---

## Summary

**Persistent Entities**: 4 (Embedding, Cluster, ClusterMember, AlignmentMap)
**Computed Entities**: 1 (Medoid - derived from Embedding + Cluster + ClusterMember)
**State Machines**: 2 (Clustering Workflow, Alignment Workflow)
**Integration Contracts**: 2 (Spec 3 → Spec 4, Spec 4 → Spec 5)

**Key Design Decisions**:
1. **Embedding Persistence**: Store in PostgreSQL with pgvector for determinism and alignment queries
2. **Centroid Storage**: Persist for cross-round alignment without recomputing
3. **Medoid as Label**: Use actual participant language (no LLM), deterministic selection
4. **Alignment Separation**: AlignmentMap table isolates presentation concerns from cluster membership
5. **Outlier Handling**: Convert HDBSCAN noise (-1) to singleton clusters (100% coverage)

**Ready to proceed to**: API contract definition (contracts/)
