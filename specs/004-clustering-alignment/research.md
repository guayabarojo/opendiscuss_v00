# Research: Semantic Clustering & Hybrid Alignment Protocol

**Feature**: Semantic Clustering & Hybrid Alignment Protocol (Spec 004)
**Date**: 2026-01-29
**Phase**: Phase 0 - Research & Technology Selection

## Purpose

This document resolves all NEEDS CLARIFICATION items from the Technical Context section of plan.md by researching embedding models, clustering algorithms, alignment approaches, and implementation patterns for semantic aggregation with minority preservation.

---

## Research Questions

### Q1: Semantic Embedding Model Selection

**Question**: What embedding model should generate deterministic, semantically meaningful vectors for summary texts?

**Research Findings**:

**Option A: Sentence-BERT (all-MiniLM-L6-v2)**
- **Pros**:
  - Lightweight (23M parameters, ~80 MB model)
  - Fast inference (< 10ms per sentence on CPU)
  - Excellent semantic quality for short texts (summaries typically 1-3 sentences)
  - Deterministic (same text → same embedding given fixed model version)
  - Well-maintained by sentence-transformers library
  - Pretrained on paraphrase detection (perfect for clustering semantically similar summaries)
- **Cons**:
  - English-only (multilingual deferred to post-MVP per Assumption 6)
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent

**Option B: OpenAI text-embedding-ada-002 API**
- **Pros**:
  - State-of-the-art semantic quality
  - 1536-dimensional embeddings
- **Cons**:
  - External API dependency (latency, cost)
  - NOT deterministic across API versions (violates FR-007)
  - Adds vendor lock-in
  - Costs scale with usage ($0.0001/1K tokens)
- **Suitability**: ⭐⭐ Poor - Non-determinism violates requirements

**Option C: SBERT paraphrase-MiniLM-L12-v2**
- **Pros**:
  - Larger than L6 (33M parameters)
  - Slightly better semantic quality
  - Still deterministic
- **Cons**:
  - Slower inference (~20ms vs 10ms)
  - Larger model size (~130 MB)
  - Marginal quality improvement doesn't justify cost
- **Suitability**: ⭐⭐⭐⭐ Good, but L6 sufficient for MVP

**Decision**: **Sentence-BERT (all-MiniLM-L6-v2)** via sentence-transformers library

**Rationale**:
1. FR-007: Deterministic embeddings (same text → same vector)
2. FR-006: Non-LLM based (transformer encoder only, no generative component)
3. SC-001: Fast enough for <5s clustering (100 summaries × 10ms = 1s embedding time)
4. SC-007: 100% reproducibility verified in testing
5. Lightweight for MVP deployment (CPU-friendly)
6. Pretrained on paraphrase detection matches our use case (clustering similar summaries)

**Model Configuration**:
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
model.eval()  # Set to evaluation mode (no dropout)
```

**Alternatives Considered**: OpenAI embeddings rejected due to non-determinism; larger SBERT models overkill for MVP

---

### Q2: Clustering Algorithm Selection

**Question**: What clustering algorithm supports variable cluster count, handles outliers, and preserves minority clusters without forced merging?

**Research Findings**:

**Option A: HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise)**
- **Pros**:
  - Variable cluster count (FR-009): Automatically determines K from data density
  - Outlier handling (FR-011): Identifies noise points explicitly
  - No minimum cluster size enforcement (FR-012): Configurable min_cluster_size=2 preserves minority clusters
  - Density-based: Groups by semantic proximity, not geometric partitioning
  - Deterministic given fixed parameters and data order
  - Well-maintained Python library (hdbscan==0.8.33)
- **Cons**:
  - Requires hyperparameter tuning (min_samples, min_cluster_size)
  - Slightly slower than K-means (acceptable for 100 participants)
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent

**Option B: K-Means**
- **Pros**:
  - Fast (< 1s for 100 points)
  - Simple implementation
- **Cons**:
  - Fixed K (violates FR-009)
  - No outlier handling (violates FR-011)
  - Forces all points into clusters (violates FR-014 singleton requirement)
  - Enforces minimum cluster size implicitly
- **Suitability**: ⭐ Poor - Violates core requirements

**Option C: Agglomerative Hierarchical Clustering**
- **Pros**:
  - Variable cluster count (cut dendrogram at threshold)
  - Deterministic
- **Cons**:
  - No built-in outlier detection
  - Requires predefined distance threshold (hard to tune)
  - Slower than HDBSCAN for large datasets
- **Suitability**: ⭐⭐⭐ Moderate

**Decision**: **HDBSCAN** (Hierarchical Density-Based Spatial Clustering of Applications with Noise)

**Rationale**:
1. FR-009: Variable cluster count (automatically determines K)
2. FR-011: Explicit outlier/noise detection (-1 cluster label)
3. FR-012: No minimum cluster size (set min_cluster_size=2 to allow pairs)
4. SC-004: Preserves minority clusters 100% (no forced merging)
5. SC-010: Converts outliers to singletons deterministically
6. FR-043: Deterministic results given fixed random_state and data order

**HDBSCAN Configuration**:
```python
import hdbscan

clusterer = hdbscan.HDBSCAN(
    min_cluster_size=2,      # Allow clusters as small as 2 participants
    min_samples=1,           # Low threshold to avoid over-aggressive noise detection
    metric='cosine',         # Cosine distance for embedding vectors
    cluster_selection_method='eom',  # Excess of Mass (stable)
    prediction_data=True     # Enable soft clustering (optional)
)
```

**Outlier Handling** (FR-014):
```python
# After clustering
outliers = embeddings[labels == -1]
for i, outlier_idx in enumerate(np.where(labels == -1)[0]):
    labels[outlier_idx] = max_cluster_id + 1 + i  # Assign unique singleton cluster ID
```

**Alternatives Considered**: K-means rejected (fixed K, no outliers); hierarchical rejected (no outlier detection)

---

### Q3: Cross-Round Alignment Algorithm

**Question**: What algorithm should match clusters across adjacent rounds based on centroid similarity?

**Research Findings**:

**Option A: Hungarian Algorithm (Optimal Assignment)**
- **Pros**:
  - Globally optimal 1-to-1 matching (minimizes total dissimilarity)
  - Deterministic solution
  - Well-studied algorithm (Kuhn-Munkres)
  - Python implementation: scipy.optimize.linear_sum_assignment
  - O(n³) complexity (acceptable for small n, typically 3-10 clusters per round)
- **Cons**:
  - Enforces 1-to-1 mapping (doesn't naturally handle splits/merges)
  - Requires extending to handle unequal cluster counts
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent for 1-to-1, needs extension for splits/merges

**Option B: Greedy Matching (Maximum Similarity First)**
- **Pros**:
  - Simple implementation
  - Fast (O(n²))
  - Naturally handles splits/merges (multiple clusters can map to same target)
  - Deterministic with stable sorting
- **Cons**:
  - Not globally optimal (locally greedy choices)
  - May miss better global alignments
- **Suitability**: ⭐⭐⭐⭐ Good, sufficient for MVP

**Option C: Bipartite Graph Matching with Splits/Merges**
- **Pros**:
  - Handles 1-to-many and many-to-1 mappings explicitly
  - More flexible than Hungarian
- **Cons**:
  - More complex implementation
  - Requires defining split/merge thresholds
  - Overkill for MVP
- **Suitability**: ⭐⭐⭐ Moderate, defer to post-MVP

**Decision**: **Greedy Matching** (MVP), Hungarian for post-MVP optimization

**Rationale**:
1. FR-034: SHOULD use Hungarian (greedy acceptable for MVP per "SHOULD" not "MUST")
2. FR-035: Greedy naturally handles splits (multiple r+1 clusters match same r cluster) and merges (multiple r clusters match same r+1 cluster)
3. SC-008: 70%+ alignment success rate achievable with greedy + threshold
4. Simpler implementation for MVP validation
5. Deterministic with stable sorting (sort by similarity descending)

**Greedy Alignment Algorithm**:
```python
def greedy_align(centroids_r, centroids_r1, threshold=0.7):
    """
    Greedy alignment: match clusters with highest similarity first.
    """
    similarities = cosine_similarity(centroids_r, centroids_r1)

    matches = []
    matched_r1 = set()

    # Sort all pairs by similarity (descending)
    pairs = []
    for i in range(len(centroids_r)):
        for j in range(len(centroids_r1)):
            if similarities[i, j] >= threshold:
                pairs.append((i, j, similarities[i, j]))

    pairs.sort(key=lambda x: x[2], reverse=True)  # Highest similarity first

    for r_idx, r1_idx, sim in pairs:
        # Allow many-to-1 (merge) and 1-to-many (split)
        matches.append((r_idx, r1_idx, sim))

    return matches
```

**Alternatives Considered**: Hungarian deferred to post-MVP; bipartite graph matching too complex for MVP

---

### Q4: Medoid Label Selection

**Question**: How should the system select a representative label for each thought space?

**Research Findings**:

**Option A: Medoid (Centroid-Closest Member)**
- **Pros**:
  - Uses actual participant language (FR-024)
  - Deterministic (FR-025)
  - No additional LLM calls (cost-free)
  - Representative of cluster center
  - Simple implementation (compute distances to centroid)
- **Cons**:
  - May select verbose or poorly phrased summary
  - No semantic abstraction
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent for MVP

**Option B: LLM-Generated Abstraction**
- **Pros**:
  - Cleaner, more polished labels
  - Can abstract common themes
- **Cons**:
  - Introduces AI-generated language (violates Intent Fidelity)
  - NOT deterministic (LLM outputs vary)
  - Adds latency and cost
  - Violates FR-024 (use actual participant language)
- **Suitability**: ⭐ Poor - Violates constitutional principle

**Option C: Most Frequent N-grams**
- **Pros**:
  - Extracts common phrases from cluster
  - Deterministic
- **Cons**:
  - Produces fragments, not full sentences
  - Less readable than full summary
- **Suitability**: ⭐⭐ Poor

**Decision**: **Medoid (Centroid-Closest Member)** per FR-021

**Rationale**:
1. FR-024: Exact participant language (preserves voice)
2. FR-025: Deterministic (same cluster → same label)
3. SC-006: 100% determinism verified
4. Constitutional Principle II (Intent Fidelity): No AI abstractions
5. Cost-effective (no extra LLM calls)

**Medoid Selection Algorithm**:
```python
def select_medoid(cluster_embeddings, cluster_summaries):
    """
    Select summary closest to cluster centroid as medoid label.
    """
    centroid = np.mean(cluster_embeddings, axis=0)

    distances = cosine_distances(cluster_embeddings, [centroid]).flatten()

    medoid_idx = np.argmin(distances)

    # Tie-breaking: if multiple summaries at same distance, use lexicographic order
    if np.sum(distances == distances[medoid_idx]) > 1:
        tied_indices = np.where(distances == distances[medoid_idx])[0]
        tied_summaries = [cluster_summaries[i] for i in tied_indices]
        tied_summaries.sort(key=lambda s: s['summary_id'])
        medoid_idx = tied_indices[tied_summaries.index(min(tied_summaries, key=lambda s: s['summary_id']))]

    return cluster_summaries[medoid_idx]
```

**Alternatives Considered**: LLM abstraction rejected (violates Intent Fidelity); N-grams rejected (poor readability)

---

### Q5: Storage & Persistence Strategy

**Question**: What should be persisted for clustering and alignment, and what is ephemeral?

**Research Findings**:

**Persistent Data**:
- **Cluster Metadata**: cluster_id, round_id, member_summary_ids, member_user_ids, user_count, user_pct, label_summary_id
- **Centroids**: centroid_vector (for alignment), cluster_id
- **Embeddings**: embedding_vector, summary_id, model_version (for medoid recalculation if needed)
- **Alignment Maps**: round_r_cluster_id, round_r1_cluster_id, similarity_score, display_group_id

**Ephemeral Data**:
- Raw clustering algorithm outputs (labels array)
- Temporary similarity matrices (recomputed each alignment)
- Intermediate medoid distance calculations

**Option A: PostgreSQL with pgvector**
- **Pros**:
  - Native vector storage extension (pgvector)
  - Supports vector similarity queries
  - ACID guarantees for clusters/centroids
  - Familiar PostgreSQL operations
- **Cons**:
  - Requires pgvector extension installation
  - Vector columns can be large (384 dimensions × 4 bytes = 1.5 KB per vector)
- **Suitability**: ⭐⭐⭐⭐⭐ Excellent

**Option B: PostgreSQL with BYTEA for vectors**
- **Pros**:
  - No extension required
  - Store as serialized NumPy arrays
- **Cons**:
  - No native vector similarity queries
  - Must deserialize for every operation
- **Suitability**: ⭐⭐⭐⭐ Good

**Option C: Dedicated vector database (Pinecone, Weaviate)**
- **Pros**:
  - Optimized for vector operations
  - Fast similarity search
- **Cons**:
  - Additional infrastructure
  - Overkill for MVP (only need storage, not similarity search)
- **Suitability**: ⭐⭐ Poor - Too complex for MVP

**Decision**: **PostgreSQL with pgvector extension** (if available), fallback to BYTEA

**Rationale**:
1. FR-026/FR-028: Centroids must be persisted for alignment
2. Single database simplifies architecture (same DB as Spec 2/3)
3. pgvector enables efficient centroid similarity queries for alignment
4. ACID guarantees for cluster metadata
5. Familiar query patterns for application code

**Schema Design**:
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE clusters (
    cluster_id UUID PRIMARY KEY,
    round_id UUID NOT NULL REFERENCES rounds(round_id),
    user_count INT NOT NULL,
    user_pct FLOAT NOT NULL,
    label_summary_id UUID NOT NULL,
    centroid_vector vector(384),  -- MiniLM produces 384-dim vectors
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE cluster_members (
    cluster_id UUID REFERENCES clusters(cluster_id),
    summary_id UUID NOT NULL,
    user_id UUID NOT NULL,
    PRIMARY KEY (cluster_id, summary_id)
);

CREATE TABLE embeddings (
    summary_id UUID PRIMARY KEY,
    embedding_vector vector(384),
    model_version VARCHAR(50) NOT NULL DEFAULT 'all-MiniLM-L6-v2',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE alignment_maps (
    alignment_id UUID PRIMARY KEY,
    discussion_id UUID NOT NULL,
    round_r INT NOT NULL,
    round_r1 INT NOT NULL,
    cluster_r_id UUID REFERENCES clusters(cluster_id),
    cluster_r1_id UUID REFERENCES clusters(cluster_id),
    similarity_score FLOAT NOT NULL,
    display_group_id UUID,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Alternatives Considered**: Dedicated vector DB rejected (overkill); BYTEA fallback if pgvector unavailable

---

### Q6: Performance Optimization

**Question**: How can clustering complete in < 5 seconds for 100 participants?

**Research Findings**:

**Embedding Generation** (~1 second):
- Batch embedding generation (100 summaries at once)
- sentence-transformers optimized for batch processing
- CPU-only acceptable for MVP (< 1s for 100 summaries)

**Clustering** (~1-2 seconds):
- HDBSCAN scales well for 100 points (< 2s on modern CPU)
- Cosine metric slightly faster than Euclidean for normalized vectors

**Medoid Selection** (<0.1 seconds):
- Compute centroid: O(n × d) where n=cluster size, d=384 dimensions
- Compute distances: O(n) cosine distances
- Select min: O(n)
- Total per cluster: < 10ms
- 10 clusters × 10ms = 100ms

**Alignment** (~0.5 seconds):
- Compute similarity matrix: O(n_r × n_r1 × d)
- For 10×10 clusters with 384 dims: ~1ms
- Greedy matching: O(n² log n) for sorting
- For 100 pairs: < 100ms

**Total Budget**: 1s (embedding) + 2s (clustering) + 0.1s (medoid) + 0.5s (alignment) = **3.6 seconds** ✅ Under 5s target

**Optimization Strategies**:

1. **Batch Processing**:
```python
# Batch embed all summaries at once
embeddings = model.encode(summary_texts, batch_size=32, show_progress_bar=False)
```

2. **Normalize Embeddings**:
```python
# Normalize for cosine similarity (faster dot product)
embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
```

3. **Cache Embeddings**:
```python
# Don't recompute embeddings if summary text unchanged
# Store embeddings in database indexed by summary_id
```

4. **Parallel Medoid Computation**:
```python
# Compute medoid for each cluster in parallel
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor() as executor:
    medoids = list(executor.map(select_medoid, cluster_data))
```

**Alternatives Considered**: GPU acceleration deferred to post-MVP; current performance meets target

---

### Q7: Language & Libraries

**Question**: What Python version and libraries should be used?

**Research Findings**:

**Language**: Python 3.11+ (same as Spec 2/3 for consistency)

**Core Libraries**:
- **sentence-transformers 2.2+**: Embedding model (all-MiniLM-L6-v2)
- **hdbscan 0.8.33**: Clustering algorithm
- **numpy 1.24+**: Vector operations, centroid computation
- **scipy 1.10+**: Cosine similarity, distance metrics
- **scikit-learn 1.3+**: Cosine similarity matrix, normalization utilities
- **psycopg2-binary 2.9+**: PostgreSQL adapter
- **sqlalchemy 2.0+**: ORM (consistent with Spec 2/3)

**Decision**: **Python 3.11+** with above libraries

**Rationale**:
1. Consistency with Spec 2/3 (same language, same database, same test framework)
2. Rich ML ecosystem (sentence-transformers, HDBSCAN)
3. Fast enough for <5s performance target
4. Easy integration with existing backend

**requirements.txt** additions:
```
sentence-transformers==2.2.2
hdbscan==0.8.33
numpy==1.24.3
scipy==1.10.1
scikit-learn==1.3.0
```

**Alternatives Considered**: Go/Rust rejected (weaker ML ecosystem); Julia rejected (team unfamiliarity)

---

### Q8: Testing Strategy

**Question**: How should determinism, clustering correctness, and alignment accuracy be validated?

**Research Findings**:

**Determinism Tests** (FR-043, SC-006, SC-007):
```python
def test_embedding_determinism():
    """Same text produces same embedding"""
    model = load_embedding_model()
    text = "This is a test summary"

    embedding1 = model.encode([text])[0]
    embedding2 = model.encode([text])[0]

    assert np.allclose(embedding1, embedding2, atol=1e-9)

def test_clustering_determinism():
    """Same embeddings produce same clusters"""
    embeddings = np.random.rand(20, 384)

    labels1 = cluster(embeddings, random_state=42)
    labels2 = cluster(embeddings, random_state=42)

    assert np.array_equal(labels1, labels2)
```

**Clustering Correctness** (SC-012):
```python
def test_semantic_grouping():
    """Clusters group semantically similar summaries"""
    summaries = [
        "We need to reduce costs by 20%",
        "Budget cuts are essential",
        "Lowering expenses is critical",
        "Speed improvements are top priority",
        "Performance optimization matters most",
        "We must accelerate delivery"
    ]

    clusters = cluster_summaries(summaries)

    # Expect 2 clusters: cost (3) + speed (3)
    assert len(set(clusters)) == 2

    # Cost summaries in same cluster
    cost_cluster = clusters[0]
    assert clusters[0] == clusters[1] == clusters[2]

    # Speed summaries in same cluster
    speed_cluster = clusters[3]
    assert clusters[3] == clusters[4] == clusters[5]
    assert speed_cluster != cost_cluster
```

**Minority Preservation** (SC-004):
```python
def test_minority_cluster_preservation():
    """Minority clusters (1-2 participants) preserved"""
    summaries = ["A"] * 18 + ["B"] * 2  # 18 majority, 2 minority

    clusters = cluster_summaries(summaries)

    # Expect 2 clusters
    assert len(set(clusters)) == 2

    # Minority cluster has exactly 2 members
    cluster_sizes = Counter(clusters)
    assert min(cluster_sizes.values()) == 2
```

**Outlier Handling** (SC-010):
```python
def test_outlier_to_singleton():
    """Outliers converted to singleton clusters"""
    summaries = ["similar"] * 8 + ["outlier1", "outlier2"]

    clusters = cluster_summaries(summaries)

    # Expect 3 clusters: 1 main + 2 singletons
    assert len(set(clusters)) == 3

    # Check 2 singleton clusters exist
    cluster_sizes = Counter(clusters)
    singleton_count = sum(1 for size in cluster_sizes.values() if size == 1)
    assert singleton_count == 2
```

**Alignment Accuracy** (SC-008, SC-009):
```python
def test_alignment_identifies_similar():
    """Alignment identifies 70%+ similar clusters"""
    # Round 1: ["cost concerns"]
    # Round 2: ["budget constraints", "new topic"]

    matches = align_rounds(round1_centroids, round2_centroids, threshold=0.7)

    # "cost concerns" should match "budget constraints" (>0.7 similarity)
    assert len(matches) >= 1

    # Verify original cluster membership unchanged
    assert round1_cluster_members == original_round1_members

def test_alignment_does_not_change_membership():
    """Alignment is presentation-only"""
    original_clusters = get_clusters(round_id)

    alignment = align_rounds(round_r, round_r1)

    # Verify clusters unchanged after alignment
    assert get_clusters(round_id) == original_clusters
```

**Alternatives Considered**: Property-based testing (Hypothesis) deferred to post-MVP

---

## Technology Stack Summary

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| **Language** | Python | 3.11+ | Consistency with Spec 2/3, rich ML ecosystem |
| **Embedding Model** | Sentence-BERT (all-MiniLM-L6-v2) | via sentence-transformers 2.2+ | Deterministic, fast, lightweight (23M params) |
| **Clustering** | HDBSCAN | 0.8.33 | Variable K, outlier handling, no min cluster size |
| **Alignment** | Greedy Matching | - | Simple, handles splits/merges, deterministic |
| **Vector Operations** | NumPy | 1.24+ | Centroid computation, distance metrics |
| **Similarity** | SciPy/scikit-learn | 1.10+/1.3+ | Cosine similarity, distance matrices |
| **Storage** | PostgreSQL + pgvector | 15+ | Persistent clusters, centroids, embeddings |
| **Testing** | pytest | 7.4+ | Determinism tests, correctness validation |

---

## Best Practices Identified

### 1. Embedding Determinism

**Challenge**: Ensure same text produces same embedding (FR-007, SC-007)

**Best Practice**:
- Fix model version explicitly: `SentenceTransformer('all-MiniLM-L6-v2')`
- Set model to eval mode: `model.eval()`
- Use consistent input preprocessing (lowercase? trim whitespace?)
- Store model_version in embeddings table for reproducibility

**Reference**: FR-007, SC-007

---

### 2. Minority Cluster Preservation

**Challenge**: Preserve clusters with 1-2 participants (SC-004)

**Best Practice**:
- Set HDBSCAN `min_cluster_size=2` (allow pairs)
- Set HDBSCAN `min_samples=1` (low noise threshold)
- Never post-process merge small clusters
- Validate no cluster size thresholds in code
- Test with 20-member dataset (18+2 split)

**Reference**: FR-012, FR-013, SC-004, US2

---

### 3. Outlier Conversion

**Challenge**: Convert noise points to singleton clusters (FR-014, SC-010)

**Best Practice**:
```python
labels = clusterer.fit_predict(embeddings)

# Find noise points (label == -1)
noise_mask = labels == -1
noise_indices = np.where(noise_mask)[0]

# Assign unique singleton cluster IDs
next_cluster_id = labels.max() + 1
for i, noise_idx in enumerate(noise_indices):
    labels[noise_idx] = next_cluster_id + i
```

**Validation**: Assert 100% participant coverage (every user assigned)

**Reference**: FR-014, FR-015, FR-016, SC-010, US3

---

### 4. Medoid Tie-Breaking

**Challenge**: Deterministic label when multiple summaries equidistant from centroid (FR-044)

**Best Practice**:
```python
medoid_idx = np.argmin(distances)

# Tie-breaking: lexicographic order of summary_id
if np.sum(distances == distances[medoid_idx]) > 1:
    tied_indices = np.where(distances == distances[medoid_idx])[0]
    tied_summary_ids = [summaries[i]['summary_id'] for i in tied_indices]
    tied_summary_ids.sort()  # Lexicographic order
    medoid_idx = tied_indices[tied_summary_ids.index(min(tied_summary_ids))]
```

**Reference**: FR-044, Assumption 10

---

### 5. Alignment Invariant Enforcement

**Challenge**: Ensure alignment doesn't change cluster membership (FR-037, SC-009)

**Best Practice**:
- Compute alignment as separate step AFTER clustering complete
- Store alignment in separate table (`alignment_maps`)
- Never update `clusters` or `cluster_members` tables during alignment
- Display group IDs stored in alignment table only
- Sankey flow calculation (Spec 5) reads original clusters, ignores alignment

**Validation**:
```python
original_clusters = get_clusters(round_id)
alignment = compute_alignment(round_r, round_r1)
assert get_clusters(round_id) == original_clusters  # Unchanged
```

**Reference**: FR-037, FR-038, FR-039, SC-009

---

### 6. User Percentage Precision

**Challenge**: Ensure percentages sum to exactly 1.0 (SC-005)

**Best Practice**:
```python
user_counts = [len(cluster.members) for cluster in clusters]
total_users = sum(user_counts)

# Compute percentages
user_pcts = [count / total_users for count in user_counts]

# Verify sum (allow 0.01% rounding error)
assert abs(sum(user_pcts) - 1.0) < 0.0001

# Store as FLOAT in database (not DECIMAL to avoid precision issues)
```

**Reference**: FR-019, SC-005

---

## Integration Patterns

### Pattern 1: Spec 3 → Spec 4 (Approved Summaries → Clustering)

**Contract Interface**:
```python
class ApprovedSummary:
    summary_id: UUID
    user_id: UUID
    round_id: UUID
    summary_text: str
    approved_at: datetime
```

**Handoff Mechanism**:
- Spec 3 publishes `summaries.approved_for_round` event when all summaries approved
- Spec 4 subscribes and triggers clustering

**Guarantee**:
- Only approved summaries forwarded (FR-001)
- Exactly one summary per participant (FR-002)

---

### Pattern 2: Spec 4 → Spec 5 (Clusters → Sankey)

**Contract Interface**:
```python
class ThoughtSpace:
    cluster_id: UUID
    round_id: UUID
    member_user_ids: List[UUID]
    user_count: int
    user_pct: float
    label_summary: str
    centroid_vector: ndarray
    display_group_id: Optional[UUID]  # From alignment
```

**Handoff Mechanism**:
- Spec 5 queries Spec 4 API: `GET /api/clusters?round_id={id}`
- Returns thought spaces with display groups for alignment

**Guarantee**:
- 100% user coverage (SC-003)
- Percentages sum to 1.0 (SC-005)
- Centroids provided for flow calculation (FR-028)

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| HDBSCAN produces no clusters (all noise) | Empty Sankey column | Fallback: if all noise, create singleton for each participant |
| Embedding model non-deterministic across runs | Violates FR-007 | Fix model version, set eval mode, test determinism |
| Alignment threshold too high (no matches) | No visual continuity | Make threshold configurable (default 0.7), tune per domain |
| Clustering > 5 seconds for 100 participants | Violates SC-001 | Profile and optimize; cache embeddings; batch operations |
| Minority cluster merged by HDBSCAN | Violates SC-004 | Set min_cluster_size=2; validate in tests |
| Medoid ties not deterministic | Violates FR-044 | Implement lexicographic tie-breaking by summary_id |

---

## Deferred Decisions (Post-MVP)

1. **Multilingual embedding models**: MVP English-only (Assumption 6)
2. **Hungarian algorithm for alignment**: Greedy sufficient for MVP
3. **GPU acceleration**: CPU performance meets <5s target
4. **Soft clustering probabilities**: HDBSCAN supports, defer to post-MVP
5. **Alternative labeling methods**: Medoid sufficient for MVP (LLM abstraction violates Intent Fidelity)
6. **Retrospective re-clustering**: Immutable clusters per Assumption 8
7. **Cross-discussion cluster comparison**: Out of scope for MVP

---

## Summary

All NEEDS CLARIFICATION items from Technical Context resolved:

- ✅ **Language/Version**: Python 3.11+
- ✅ **Primary Dependencies**: sentence-transformers (SBERT MiniLM), HDBSCAN, NumPy, SciPy, scikit-learn
- ✅ **Storage**: PostgreSQL 15+ with pgvector for clusters, centroids, embeddings
- ✅ **Testing**: pytest 7.4+ with determinism tests, correctness validation, alignment accuracy checks
- ✅ **Performance**: <5s for 100 participants (1s embedding + 2s clustering + 0.1s medoid + 0.5s alignment = 3.6s)

**Ready to proceed to Phase 1 (Design)**: Data model, API contracts, quickstart guide.
