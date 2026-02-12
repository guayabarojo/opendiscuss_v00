# Feature Specification: Semantic Clustering & Hybrid Alignment Protocol

**Feature Branch**: `004-clustering-alignment`
**Created**: 2026-01-27
**Status**: Draft
**Input**: User description: "Spec 3 — Semantic Clustering & Hybrid Alignment Protocol - Cluster approved summaries into thought spaces with cross-round alignment for continuity"

**Constitution Compliance**: All features MUST comply with `.specify/memory/constitution.md`.
Check MVP Boundaries section for explicit non-features before proceeding.

**Dependencies**: This spec depends on Spec 0 (Discussion Protocol - 001-discussion-protocol) and Spec 2 (Micro-Summarization & Approval - 003-summarization-approval)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cluster Approved Summaries into Thought Spaces (Priority: P1)

After participants approve their summaries in a round, the system clusters semantically similar
summaries into thought spaces using embedding-based semantic similarity. Each thought space
represents a coherent idea or position, with participants automatically assigned based on their
approved summary content.

**Why this priority**: This is the core aggregation mechanism that transforms individual approved
summaries into collective thought spaces. Without clustering, there's no way to show how participants
group around ideas. It validates the "semantic accuracy over aesthetics" principle.

**Independent Test**: Can be fully tested by providing 10 approved summaries with clear thematic
groups (e.g., 3 about cost, 4 about speed, 3 about fairness), running clustering, and verifying
distinct thought spaces are created. Delivers immediate value by revealing collective patterns.

**Acceptance Scenarios**:

1. **Given** 10 participants have approved summaries with 3 discussing cost concerns, 4 discussing
   speed improvements, and 3 discussing fairness, **When** clustering runs, **Then** the system
   creates distinct thought spaces grouping semantically similar summaries
2. **Given** clustering completes, **When** results are generated, **Then** each thought space
   includes cluster_id, member summary IDs, member user IDs, user count, and percentage
3. **Given** thought spaces are created, **When** percentages are calculated, **Then** they sum to
   exactly 1.0 (100%) across all clusters for the round
4. **Given** 10 users participate, **When** clustering assigns them, **Then** each user is assigned
   to exactly one thought space (no duplicates, no missing users)
5. **Given** approved summaries are clustered, **When** the system processes input, **Then** only
   approved summaries enter clustering (unapproved summaries are excluded)

---

### User Story 2 - Preserve Minority Clusters Without Forced Merging (Priority: P2)

A discussion has 20 participants where 18 support one position and 2 express a distinct minority
view. The system creates separate thought spaces for both majority and minority positions, refusing
to force-merge the minority into the majority for visual simplicity.

**Why this priority**: Critical for "semantic accuracy over aesthetics" constitutional principle.
Prevents false consensus by ensuring low-frequency clusters remain visible. Protects minority
voices from being erased.

**Independent Test**: Can be tested by clustering 20 summaries where 2 are semantically distinct
from the other 18, and verifying 2 separate thought spaces are created. Delivers value by
preserving semantic accuracy.

**Acceptance Scenarios**:

1. **Given** 18 summaries favor "full remote work" and 2 summaries favor "office-only", **When**
   clustering runs, **Then** two distinct thought spaces are created (no forced merging)
2. **Given** a minority cluster has only 2 members, **When** the system evaluates it, **Then** it
   is preserved as a visible thought space (no minimum cluster size threshold)
3. **Given** clustering identifies semantically distinct groups, **When** determining cluster count,
   **Then** the system uses variable cluster count (not a fixed K value)
4. **Given** a minority view exists, **When** the Sankey column is rendered, **Then** the minority
   thought space is visible with width proportional to its 2 participants (10% if total is 20)
5. **Given** clustering completes with minority clusters, **When** metrics are calculated, **Then**
   minority cluster percentages (e.g., 10%) are accurate and visible

---

### User Story 3 - Handle Outliers as Singleton Clusters (Priority: P3)

The clustering algorithm identifies some summaries as "noise" or outliers that don't fit well into
any group. The system converts each noise point into its own singleton cluster, ensuring every
participant is assigned to a visible thought space.

**Why this priority**: Ensures "all clusters are visible" invariant. Prevents participants from
being dropped or hidden due to outlier status. Maintains complete participant representation.

**Independent Test**: Can be tested by providing 10 summaries where 8 form a tight cluster and 2
are outliers, and verifying 3 thought spaces are created (1 main + 2 singletons). Delivers value by
ensuring no participant is lost.

**Acceptance Scenarios**:

1. **Given** a clustering algorithm identifies 2 summaries as noise/outliers, **When** the system
   processes them, **Then** each outlier becomes its own singleton cluster (2 clusters created)
2. **Given** singleton clusters exist, **When** the Sankey column is rendered, **Then** singleton
   thought spaces are visible (not hidden or dropped)
3. **Given** 10 participants with 2 outliers, **When** clustering completes, **Then** all 10
   participants are assigned to thought spaces (100% coverage, no dropped participants)
4. **Given** a singleton cluster, **When** metrics are calculated, **Then** it has user_count=1 and
   user_pct reflects its proportion (e.g., 10% if total is 10)
5. **Given** outliers are converted to singletons, **When** participants view the Sankey diagram,
   **Then** they can see that their unique view is represented (not lost in aggregation)

---

### User Story 4 - Cross-Round Alignment for Visual Continuity (Priority: P4)

A discussion runs across 3 rounds. Semantically similar thought spaces across adjacent rounds (e.g.,
"cost concerns" in Round 1 and "budget constraints" in Round 2) are aligned for visual continuity
using display group IDs and stable colors. This alignment does NOT change cluster membership or
flow calculations.

**Why this priority**: Improves user experience by reducing visual jitter in the Sankey diagram.
Makes it easier to track how ideas evolve across rounds. Does not compromise data accuracy since
alignment is presentational only.

**Independent Test**: Can be tested by clustering two rounds with semantically similar thought
spaces, running alignment, and verifying display group IDs are assigned without changing cluster
membership. Delivers value through improved readability.

**Acceptance Scenarios**:

1. **Given** Round 1 has a thought space about "cost concerns" and Round 2 has a thought space about
   "budget constraints", **When** cross-round alignment runs, **Then** the system computes cosine
   similarity between cluster centroids
2. **Given** similarity is computed, **When** it exceeds ALIGN_THRESHOLD (e.g., 0.7), **Then** the
   clusters are aligned and assigned the same display_group_id
3. **Given** clusters are aligned, **When** the Sankey diagram is rendered, **Then** aligned thought
   spaces use consistent colors and labels across rounds
4. **Given** alignment assigns display groups, **When** flow calculations occur (Spec 4), **Then**
   alignment does NOT affect cluster membership or participant assignment
5. **Given** one Round 1 cluster aligns with two Round 2 clusters (split), **When** display groups
   are assigned, **Then** both Round 2 clusters receive the same display family (indicating split)

---

### User Story 5 - Generate Deterministic Cluster Labels Using Medoid (Priority: P5)

Each thought space needs a human-readable label. The system selects the summary closest to the
cluster centroid (medoid) as the representative label. This is deterministic, faithful to
participant language, and requires no additional LLM calls.

**Why this priority**: Provides readable labels without introducing AI-generated abstractions. Keeps
labels faithful to actual participant language. Avoids extra LLM costs and latency.

**Independent Test**: Can be tested by clustering summaries, computing centroids, and verifying the
label is the actual member summary closest to the centroid. Delivers value through faithful,
cost-effective labeling.

**Acceptance Scenarios**:

1. **Given** a thought space has 5 member summaries, **When** labeling occurs, **Then** the system
   computes the centroid of the 5 summary embeddings
2. **Given** the centroid is computed, **When** selecting a label, **Then** the system identifies
   the member summary with the smallest distance to the centroid (medoid)
3. **Given** the medoid is identified, **When** the label is assigned, **Then** the exact text of
   the medoid summary becomes the thought space label (no AI generation)
4. **Given** labels are assigned, **When** participants view the Sankey diagram, **Then** thought
   space labels are actual participant summaries (preserving participant voice)
5. **Given** clustering runs multiple times with the same input, **When** labels are generated,
   **Then** the medoid label is deterministic (same input produces same label)

---

### Edge Cases

- **All summaries semantically identical**: System should create a single thought space containing
  all participants (100% in one cluster)
- **Every summary is completely unique**: System creates N singleton clusters for N participants
  (valid state, all visible)
- **Exactly 2 participants, opposite views**: System creates 2 clusters with 50% each (no minimum
  cluster size enforced)
- **Alignment finds no similar clusters across rounds**: Valid - no alignment occurs, display groups
  are independent per round
- **Multiple Round 1 clusters align to one Round 2 cluster (merge)**: All Round 1 clusters receive
  the same display family as the Round 2 cluster (indicating merge)
- **Embedding service fails**: Clustering cannot proceed - error returned, participants notified
- **Zero approved summaries in a round**: Valid but degenerate - round produces zero thought spaces
  (empty Sankey column)
- **Medoid calculation ties (two summaries equidistant from centroid)**: Use deterministic
  tie-breaking (e.g., lexicographic order of summary_id)

## Requirements *(mandatory)*

### Functional Requirements

#### Input Validation & Filtering

- **FR-001**: System MUST accept only approved summaries as input to clustering (strict invariant)
- **FR-002**: System MUST ensure each approved summary represents exactly one counted participant
  per round (per Spec 1/Spec 2 rules)
- **FR-003**: System MUST reject any unapproved summaries if accidentally provided (defensive check)
- **FR-004**: Each approved summary input MUST include: summary_id, user_id, summary_text

#### Semantic Embedding

- **FR-005**: System MUST use a deterministic semantic embedding model producing fixed-length vectors
- **FR-006**: Embedding model MUST be non-LLM based (e.g., SBERT, MiniLM sentence transformers)
- **FR-007**: Embedding function MUST be stable across runs (same text produces same vector given
  same model/version)
- **FR-008**: System MUST generate embedding vectors for all approved summary texts before clustering

#### Clustering Algorithm

- **FR-009**: Clustering algorithm MUST support variable cluster count (not fixed K-means style)
- **FR-010**: Clustering algorithm MUST be non-LLM based (e.g., HDBSCAN, hierarchical clustering)
- **FR-011**: Clustering algorithm MUST handle outliers/noise points without dropping them
- **FR-012**: System MUST NOT enforce minimum cluster size thresholds (preserve low-frequency
  clusters)
- **FR-013**: System MUST NOT perform forced merging of semantically distinct clusters for visual
  simplicity

#### Outlier Handling

- **FR-014**: If clustering algorithm identifies noise points, each noise point MUST become its own
  singleton cluster
- **FR-015**: Singleton clusters MUST be visible in outputs (not hidden or filtered)
- **FR-016**: Every participating user MUST be assigned to exactly one thought space (100% coverage)

#### Cluster Outputs

- **FR-017**: Each cluster output MUST include: cluster_id, member_summary_ids, member_user_ids,
  user_count, user_pct, label_summary
- **FR-018**: User count MUST equal the number of unique user IDs assigned to the cluster
- **FR-019**: User percentages MUST sum to exactly 1.0 (100%) across all clusters in a round
- **FR-020**: Cluster IDs MUST be unique within a round (but may be reused across rounds)

#### Cluster Labeling (Medoid Method)

- **FR-021**: System MUST generate thought space labels using the medoid method (MVP default)
- **FR-022**: Medoid MUST be defined as the member summary closest to the cluster centroid
- **FR-023**: Distance calculation MUST use the same metric as clustering (e.g., cosine distance)
- **FR-024**: Label text MUST be the exact summary_text of the medoid summary (no AI generation)
- **FR-025**: Labels MUST be deterministic (same input produces same medoid label)

#### Centroid Computation

- **FR-026**: System MUST compute and persist cluster centroid vectors for each thought space
- **FR-027**: Centroids MUST be calculated as the mean of member summary embedding vectors
- **FR-028**: Centroids MUST be persisted for use in cross-round alignment

#### Cross-Round Hybrid Alignment

- **FR-029**: System MUST support alignment between clusters from adjacent rounds (r and r+1)
- **FR-030**: Alignment MUST compute a similarity matrix between all cluster centroid pairs
- **FR-031**: Similarity MUST be measured using cosine similarity between centroids
- **FR-032**: Alignment MUST use a configurable ALIGN_THRESHOLD (e.g., 0.7) to determine matches
- **FR-033**: Only cluster pairs with similarity ≥ ALIGN_THRESHOLD MUST be aligned

#### Alignment Matching

- **FR-034**: System SHOULD use Hungarian algorithm or greedy matching to solve best-match alignment
- **FR-035**: Alignment MAY produce 1-to-1, 1-to-many (split), or many-to-1 (merge) mappings
- **FR-036**: Alignment MUST assign display_group_ids for visual continuity (stable colors/labels)

#### Alignment Invariants

- **FR-037**: Alignment MUST NOT change cluster membership or participant assignments
- **FR-038**: Alignment MUST NOT affect Sankey flow calculations (handled by Spec 4)
- **FR-039**: Alignment affects presentation only (colors, label families, display grouping)

#### Round Independence

- **FR-040**: Clustering MUST be performed independently per round (no cross-round semantic
  enforcement)
- **FR-041**: Cluster IDs are per-round (cluster_id=1 in Round 1 is independent from cluster_id=1
  in Round 2)
- **FR-042**: Alignment is computed after per-round clustering completes (separate step)

#### Determinism and Repeatability

- **FR-043**: Given the same approved summaries and model version, clustering MUST produce
  deterministic results
- **FR-044**: Medoid selection MUST use deterministic tie-breaking if multiple summaries are
  equidistant from centroid

### Key Entities

- **Thought Space (Cluster)**: A semantic grouping of approved summaries representing a coherent
  idea. Attributes: cluster_id, round_id, member_summary_ids, member_user_ids, user_count, user_pct,
  label_summary, centroid_vector. Related to: Round, Summary, Participant.

- **Cluster Centroid**: The mean embedding vector of all member summaries in a cluster. Attributes:
  centroid_vector (fixed-length float array), cluster_id. Used for medoid calculation and cross-round
  alignment. Related to: Thought Space.

- **Medoid**: The member summary closest to the cluster centroid, used as the thought space label.
  Attributes: medoid_summary_id, distance_to_centroid. Related to: Thought Space, Summary.

- **Semantic Embedding**: A fixed-length vector representation of summary text. Attributes: vector
  (float array), summary_id, model_version. Generated by deterministic embedding model. Related to:
  Summary.

- **Alignment Map**: A mapping between clusters in adjacent rounds based on centroid similarity.
  Attributes: round_r_cluster_id, round_r+1_cluster_id, similarity_score. Related to: Thought Space
  (cross-round).

- **Display Group**: A visual grouping identifier for aligned clusters across rounds. Attributes:
  display_group_id, member_cluster_ids (across rounds), color_family, label_family. Used for
  presentation only. Related to: Thought Space (cross-round).

- **Singleton Cluster**: A thought space containing exactly one participant (outlier case).
  Attributes: same as Thought Space, user_count=1. Created from noise points. Related to: Thought
  Space.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Clustering completes within 5 seconds for rounds with up to 100 participants (scalable
  performance)

- **SC-002**: 100% of approved summaries are assigned to thought spaces (no summaries lost or
  dropped)

- **SC-003**: Every participating user is assigned to exactly one thought space per round with 100%
  accuracy

- **SC-004**: Low-frequency clusters (e.g., 1-2 participants) are preserved as visible thought spaces
  100% of the time (no forced merging)

- **SC-005**: User percentages sum to exactly 1.0 (100%) across all clusters in a round with
  sub-0.01% rounding error tolerance

- **SC-006**: Medoid labeling achieves 100% determinism (same input produces same label given fixed
  model version)

- **SC-007**: Embedding generation is deterministic with 100% reproducibility given same text and
  model version

- **SC-008**: Cross-round alignment identifies at least 70% of semantically similar clusters across
  adjacent rounds (effective continuity)

- **SC-009**: Alignment does NOT change cluster membership or flow counts with 100% accuracy
  (strict invariant)

- **SC-010**: Outliers are converted to singleton clusters with 100% success rate (all participants
  visible)

### Protocol Correctness

- **SC-011**: All clustering invariants (approved summaries only, no forced merging, all clusters
  visible, per-round assignments, alignment presentation-only) are verifiable through automated tests

- **SC-012**: Synthetic test datasets with clear theme groups, paraphrases, and minority themes
  produce expected clustering (semantic accuracy validation)

- **SC-013**: Integration with Spec 2 (approved summaries only) and Spec 4 (centroid provision for
  flows) is verifiable through end-to-end tests

## Assumptions

1. **Embedding model availability**: A deterministic semantic embedding model (e.g., SBERT, MiniLM)
   is available with reasonable latency and model size constraints

2. **Embedding model stability**: The embedding model version is fixed per discussion or explicitly
   versioned to ensure deterministic results

3. **Clustering algorithm choice**: MVP uses HDBSCAN or similar density-based algorithm that handles
   variable cluster counts and outliers (specific algorithm is implementation choice)

4. **Alignment threshold tuning**: ALIGN_THRESHOLD (default 0.7) may need tuning based on domain and
   discussion characteristics (configurable parameter)

5. **Computational resources**: Clustering and embedding computation can complete within 5 seconds
   for 100 participants (adequate compute resources assumed)

6. **Single language**: MVP assumes summaries are in a single language; multilingual embedding is
   post-MVP

7. **Centroid storage**: Centroid vectors are persisted for cross-round alignment but are not
   displayed to users (internal data structure)

8. **No retrospective re-clustering**: Once a round is clustered, results are immutable; alignment
   is computed forward-only (Round r → r+1)

9. **Display group assignment**: Display groups are advisory for UI rendering; the exact color/label
   assignment algorithm is implementation-defined

10. **Medoid tie-breaking**: In case of ties (multiple summaries equidistant from centroid), a
    deterministic rule (e.g., lexicographic order of summary_id) is used
