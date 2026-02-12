# User Story 5 Implementation Summary: Deterministic Medoid Labels

**Date**: 2026-02-02
**Feature**: Semantic Clustering & Hybrid Alignment Protocol (Spec 004)
**User Story**: US5 - Generate Deterministic Cluster Labels Using Medoid (Priority P5)
**Status**: ✅ **COMPLETE**

---

## Overview

User Story 5 implements deterministic cluster labeling using the medoid method. The medoid is the cluster member whose embedding is closest to the cluster centroid, ensuring that labels use actual participant language rather than AI-generated text.

---

## Tasks Completed

### ✅ T062: Implement compute_medoid function
**Location**: `/backend/src/services/medoid_labeling.py` (lines 28-141)

**Implementation Details**:
- Finds cluster member with smallest cosine distance to centroid
- Uses `scipy.spatial.distance.cosine` for distance calculation
- Validates input dimensions (384-dim vectors)
- Handles NaN/infinite distances gracefully
- Applies deterministic tie-breaking when multiple members are equidistant

**Requirements Satisfied**:
- FR-022: Medoid method (centroid-closest member)
- FR-023: Use cosine distance metric
- FR-024: Label is actual participant text

**Key Code**:
```python
def compute_medoid(
    cluster_id: UUID,
    centroid_vector: np.ndarray,
    member_embeddings: List[Tuple[UUID, np.ndarray]]
) -> UUID:
    # Compute cosine distances from each member to centroid
    distances: List[Tuple[float, UUID]] = []
    for summary_id, embedding in member_embeddings:
        distance = cosine(embedding, centroid_vector)
        distances.append((distance, summary_id))

    # Find minimum distance
    min_distance = min(d[0] for d in distances)
    closest_members = [
        summary_id for distance, summary_id in distances
        if distance == min_distance
    ]

    # Apply deterministic tie-breaking if needed
    if len(closest_members) > 1:
        medoid_id = deterministic_tiebreaker(closest_members)
    else:
        medoid_id = closest_members[0]

    return medoid_id
```

---

### ✅ T063: Implement deterministic_tiebreaker function
**Location**: `/backend/src/services/medoid_labeling.py` (lines 144-189)

**Implementation Details**:
- Uses lexicographic order of summary_id (UUID string representation)
- Ensures deterministic selection when multiple members are equidistant
- Guarantees same result across multiple runs

**Requirements Satisfied**:
- FR-044: Deterministic tie-breaking with lexicographic order
- SC-006: Same cluster → same medoid across runs

**Key Code**:
```python
def deterministic_tiebreaker(candidate_summary_ids: List[UUID]) -> UUID:
    # Sort by string representation of UUID (lexicographic order)
    sorted_candidates = sorted(candidate_summary_ids, key=lambda uid: str(uid))
    selected = sorted_candidates[0]
    return selected
```

**Example**:
Given candidates:
- `dddddddd-0000-0000-0000-000000000001`
- `aaaaaaaa-0000-0000-0000-000000000001`
- `cccccccc-0000-0000-0000-000000000001`

Returns: `aaaaaaaa-0000-0000-0000-000000000001` (lexicographically first)

---

### ✅ T064: Implement assign_medoid_labels function
**Location**: `/backend/src/services/medoid_labeling.py` (lines 192-282)

**Implementation Details**:
- Processes multiple clusters in batch
- Computes medoid for each cluster
- Returns list of (cluster_id, label_summary_id) tuples
- Validates all clusters have valid medoids
- Raises `MedoidLabelingError` if any cluster fails

**Requirements Satisfied**:
- FR-021: Every cluster has a label
- FR-024: Labels use actual participant language
- FR-025: Deterministic labeling

**Key Code**:
```python
def assign_medoid_labels(
    clusters_data: List[dict]
) -> List[Tuple[UUID, UUID]]:
    labels: List[Tuple[UUID, UUID]] = []

    for cluster in clusters_data:
        cluster_id = cluster.get('cluster_id')
        centroid_vector = cluster.get('centroid_vector')
        members = cluster.get('members', [])

        medoid_id = compute_medoid(
            cluster_id=cluster_id,
            centroid_vector=centroid_vector,
            member_embeddings=members
        )

        labels.append((cluster_id, medoid_id))

    return labels
```

---

### ✅ T065: Integrate medoid labeling into clustering workflow
**Location**: `/backend/src/api/routes/clustering.py` (lines 623-645)

**Implementation Details**:
- Integrated into `execute_full_clustering_workflow()` function
- Executed after centroid computation (Step 5)
- Executed before cluster persistence (Step 8)
- Medoids computed for all clusters in single batch

**Workflow Integration**:
```python
# Step 5: Compute centroids
centroids = compute_centroids(cluster_assignments, embeddings_dict)

# Step 6: Calculate cluster statistics
cluster_stats = await calculate_cluster_stats(cluster_assignments, db)

# Step 7: Select medoid labels (T065)
label_summaries = {}
for cluster_label in centroids.keys():
    # Get member embeddings for this cluster
    member_embeddings = [
        (sid, embeddings_dict[sid])
        for sid, label in cluster_assignments.items()
        if label == cluster_label
    ]

    # Compute medoid
    medoid_id = compute_medoid(
        cluster_id=uuid.uuid4(),  # Temp ID for computation
        centroid_vector=centroids[cluster_label],
        member_embeddings=member_embeddings
    )

    label_summaries[cluster_label] = medoid_id

# Step 8: Persist clusters (includes medoid labels)
cluster_id_map = await persist_clusters(
    round_id=round_id,
    cluster_assignments=cluster_assignments,
    cluster_stats=cluster_stats,
    centroids=centroids,
    label_summaries=label_summaries,  # Medoid labels passed here
    db=db
)
```

**Requirements Satisfied**:
- Complete workflow includes medoid labeling
- Labels persisted to database with clusters
- Labels available for API responses

---

### ✅ T066: Add label_summary to API response
**Location**: `/backend/src/api/routes/clustering.py`

**Endpoints Updated**:

1. **GET /api/v1/clusters** (lines 273-395)
   - Returns `ClusterResponse` with `label_summary` field
   - Field contains actual medoid summary text
   - Also includes `label_summary_id` (optional UUID)

2. **GET /api/v1/clusters/{cluster_id}** (lines 402-497)
   - Returns `ClusterDetailResponse` with `label_summary` field
   - Includes full member list with summary texts
   - Medoid is one of the members

**Response Schema**:
```python
class ClusterResponse(BaseModel):
    cluster_id: UUID
    user_count: int
    user_pct: float
    label_summary: str  # ← Medoid summary text (T066)
    label_summary_id: Optional[UUID]  # ← Medoid summary ID
    display_group_id: Optional[UUID]
    centroid_vector: Optional[List[float]]
```

**Example Response**:
```json
{
  "round_id": "550e8400-e29b-41d4-a716-446655440000",
  "cluster_count": 3,
  "total_participants": 20,
  "percentage_sum": 1.0,
  "clusters": [
    {
      "cluster_id": "660e8400-e29b-41d4-a716-446655440000",
      "user_count": 12,
      "user_pct": 0.6,
      "label_summary": "We need to focus on reducing costs while maintaining quality.",
      "label_summary_id": "770e8400-e29b-41d4-a716-446655440000",
      "display_group_id": null,
      "centroid_vector": [0.123, -0.456, ...]
    }
  ]
}
```

**Requirements Satisfied**:
- FR-024: Medoid summary text returned in API
- Labels use actual participant language
- No AI-generated text

---

### ✅ T067: Unit tests for determinism
**Location**: `/backend/tests/unit/test_medoid_selection.py`

**Test Suite**: `TestMedoidDeterminism` class (lines 247-387)

**Tests Implemented**:

#### Test 1: Single Cluster Determinism (lines 254-290)
```python
def test_determinism_single_cluster_10_runs(self):
    """Run medoid selection 10 times, assert same result."""
    cluster_id = uuid4()

    # Fixed centroid and 5 members
    np.random.seed(42)
    centroid = np.random.randn(384) / np.linalg.norm(...)
    members = [(uuid4(), np.random.randn(384)/norm) for _ in range(5)]

    # Run 10 times
    results = [compute_medoid(cluster_id, centroid, members) for _ in range(10)]

    # Assert all identical
    assert len(set(results)) == 1
```

**Status**: ✅ PASS - Same medoid selected across all 10 runs

#### Test 2: Tie-Breaking Determinism (lines 292-338)
```python
def test_determinism_with_equidistant_members_10_runs(self):
    """Test deterministic tie-breaking with equidistant members."""
    # Create 3 members with IDENTICAL embeddings (equidistant from centroid)
    member_vec = np.random.randn(384) / norm
    member_ids = [
        UUID('dddddddd-0000-0000-0000-000000000001'),
        UUID('aaaaaaaa-0000-0000-0000-000000000001'),
        UUID('cccccccc-0000-0000-0000-000000000001')
    ]
    members = [(mid, member_vec.copy()) for mid in member_ids]

    # Run 10 times
    results = [compute_medoid(cluster_id, centroid, members) for _ in range(10)]

    # Assert all identical AND lexicographically first
    assert len(set(results)) == 1
    assert results[0] == UUID('aaaaaaaa-0000-0000-0000-000000000001')
```

**Status**: ✅ PASS - Tie-breaker selects lexicographically first UUID consistently

#### Test 3: Multiple Clusters Determinism (lines 340-387)
```python
def test_determinism_multiple_clusters_10_runs(self):
    """Test determinism for 3 clusters simultaneously."""
    # Create 3 clusters with 4 members each
    clusters_data = [create_cluster() for _ in range(3)]

    # Run label assignment 10 times
    all_results = []
    for run in range(10):
        labels = assign_medoid_labels(clusters_data)
        labels_sorted = sorted(labels, key=lambda x: str(x[0]))
        all_results.append(labels_sorted)

    # Assert all runs identical
    first_result = all_results[0]
    for result in all_results[1:]:
        assert result == first_result
```

**Status**: ✅ PASS - All 3 clusters produce same medoids across 10 runs

**Requirements Satisfied**:
- SC-006: Deterministic medoid selection across runs
- FR-044: Deterministic tie-breaking validated
- FR-025: Same cluster → same medoid

**Test Coverage**:
- ✅ Single cluster determinism
- ✅ Tie-breaking with equidistant members
- ✅ Multiple clusters in batch
- ✅ Edge cases (empty members, invalid centroids)
- ✅ Medoid validation (medoid is cluster member)

---

## Validation Summary

### Code Review Checklist

- [x] **T062**: `compute_medoid()` implemented with cosine distance
- [x] **T063**: `deterministic_tiebreaker()` uses lexicographic order
- [x] **T064**: `assign_medoid_labels()` processes all clusters
- [x] **T065**: Medoid labeling integrated into workflow (Step 7)
- [x] **T066**: API returns `label_summary` field with medoid text
- [x] **T067**: Unit tests validate determinism across 10 runs

### Requirements Mapping

| Requirement | Implementation | Status |
|------------|----------------|--------|
| FR-021: Every cluster has label | `assign_medoid_labels()` | ✅ |
| FR-022: Medoid method | `compute_medoid()` | ✅ |
| FR-023: Cosine distance | `scipy.spatial.distance.cosine` | ✅ |
| FR-024: Actual participant text | Medoid is cluster member | ✅ |
| FR-025: Deterministic labeling | Tie-breaker + tests | ✅ |
| FR-044: Deterministic tie-breaking | Lexicographic order | ✅ |
| SC-006: Same cluster → same medoid | Test suite validates | ✅ |

### Architectural Guarantees

1. **Intent Fidelity**: Labels use actual participant language, not AI-generated text ✅
2. **Determinism**: Same cluster data produces same medoid every time ✅
3. **Transparency**: Medoid selection is explainable (closest to centroid) ✅
4. **Correctness**: Medoid is always a cluster member ✅
5. **Performance**: O(n) computation per cluster ✅

---

## Integration Points

### 1. Clustering Workflow
**File**: `/backend/src/api/routes/clustering.py`

Medoid labeling is Step 7 in the 9-step workflow:
1. Fetch approved summaries
2. Generate embeddings
3. Run HDBSCAN clustering
4. Handle outliers
5. Compute centroids
6. Calculate statistics
7. **Select medoid labels** ← T065
8. Persist clusters
9. Publish event

### 2. Database Persistence
**File**: `/backend/src/services/clustering_service.py`

`persist_clusters()` receives `label_summaries` dict and:
- Fetches medoid summary text from database
- Stores text in `ThoughtSpace.label_summary` field
- Validates medoid is a cluster member

### 3. API Response
**File**: `/backend/src/api/routes/clustering.py`

Both endpoints return medoid data:
- `GET /api/v1/clusters` → List with `label_summary`
- `GET /api/v1/clusters/{cluster_id}` → Details with `label_summary`

### 4. Data Model
**File**: `/backend/src/models/cluster.py`

`Cluster` model includes:
- `label_summary_id`: UUID (FK to `approved_summaries`)
- Validation: Medoid must be cluster member

---

## Example Usage

### Computing Medoid for a Single Cluster
```python
from src.services.medoid_labeling import compute_medoid
import numpy as np
from uuid import uuid4

# Cluster data
cluster_id = uuid4()
centroid = np.array([...])  # 384-dim centroid vector

# Member embeddings (summary_id, embedding pairs)
members = [
    (uuid4(), np.array([...])),  # Member 1
    (uuid4(), np.array([...])),  # Member 2
    (uuid4(), np.array([...]))   # Member 3
]

# Compute medoid
medoid_id = compute_medoid(cluster_id, centroid, members)
# Returns: UUID of member closest to centroid
```

### Batch Processing Multiple Clusters
```python
from src.services.medoid_labeling import assign_medoid_labels

# Clusters data
clusters = [
    {
        'cluster_id': cluster1_id,
        'centroid_vector': centroid1,
        'members': [(sid1, emb1), (sid2, emb2)]
    },
    {
        'cluster_id': cluster2_id,
        'centroid_vector': centroid2,
        'members': [(sid3, emb3), (sid4, emb4)]
    }
]

# Assign labels
labels = assign_medoid_labels(clusters)
# Returns: [(cluster1_id, medoid1_id), (cluster2_id, medoid2_id)]
```

### API Query
```bash
# Get clusters with medoid labels
curl -X GET "http://localhost:8000/api/v1/clusters?round_id={round_id}" \
  -H "Authorization: Bearer {token}"

# Response includes label_summary for each cluster
{
  "clusters": [
    {
      "cluster_id": "...",
      "label_summary": "Actual participant text from medoid summary",
      "user_count": 5,
      "user_pct": 0.25
    }
  ]
}
```

---

## Performance Characteristics

### Time Complexity
- **Single cluster**: O(n) where n = number of members
  - Compute distance for each member: O(n)
  - Find minimum: O(n)
  - Tie-breaking: O(k log k) where k ≤ n

- **Multiple clusters**: O(C × n) where C = cluster count
  - Linear in number of clusters
  - Linear in average cluster size

### Space Complexity
- **Single cluster**: O(n)
  - Store distances for all members
  - Store candidate list (at most n)

- **Multiple clusters**: O(C × n)
  - Store labels for all clusters

### Typical Performance
For a round with:
- 100 participants
- 10 clusters (average 10 members each)
- 384-dim embeddings

**Expected time**: < 50ms for all medoid computations

---

## Known Limitations and Edge Cases

### 1. Floating-Point Precision
**Issue**: Tie-breaking may be triggered due to floating-point rounding

**Mitigation**: Deterministic tie-breaker ensures consistent results

**Example**: Two members at distances 0.123456789 and 0.123456788 might be considered equal

### 2. Singleton Clusters
**Issue**: Single-member clusters have only one option for medoid

**Behavior**: Works correctly (medoid = only member)

**Test**: Validated in test suite

### 3. Empty Clusters
**Issue**: Cannot compute medoid without members

**Behavior**: Raises `MedoidLabelingError`

**Prevention**: Workflow ensures all clusters have at least one member

### 4. Invalid Embeddings
**Issue**: Member with wrong dimensions (not 384)

**Behavior**: Logged as warning, member skipped

**Fallback**: Use other valid members

---

## Constitutional Compliance

### Intent Fidelity ✅
**Principle**: Preserve participant intent without AI interpretation

**Implementation**:
- Labels use actual participant text (medoid summary)
- No AI-generated abstractions or paraphrasing
- Medoid selection based on mathematical proximity, not semantic judgment

**Validation**: FR-024, SC-006

### Semantic Accuracy Over Aesthetics ✅
**Principle**: Truth over presentation simplicity

**Implementation**:
- Medoid might not be "prettiest" summary, but it's most representative
- No manual curation or editing of labels
- Mathematical guarantee of centrality

**Validation**: FR-022, FR-023

### Temporal Transparency ✅
**Principle**: Per-round processing without cross-round influence

**Implementation**:
- Medoids computed independently per round
- No reuse of labels across rounds
- Determinism within round, not across rounds

**Validation**: FR-025

---

## Future Enhancements (Out of Scope)

### 1. Medoid Quality Metrics
- Measure representativeness of medoid
- Compare medoid centrality to other members
- Flag clusters where medoid is not highly representative

### 2. Alternative Labeling Methods
- Weighted medoid (consider member importance)
- Multi-sentence labels (combine multiple members)
- Hierarchical labels (nested thought spaces)

### 3. Medoid Caching
- Cache medoid distances for alignment reuse
- Incremental updates when members change
- Precompute medoids during embedding generation

### 4. Visualization
- Show medoid position relative to cluster boundary
- Highlight medoid in member list
- Display distance to centroid for all members

---

## References

### Code Files
- `/backend/src/services/medoid_labeling.py` - Core implementation
- `/backend/src/api/routes/clustering.py` - Workflow integration
- `/backend/tests/unit/test_medoid_selection.py` - Test suite
- `/backend/src/models/cluster.py` - Data model
- `/backend/src/services/clustering_service.py` - Persistence

### Specification Documents
- `/specs/004-clustering-alignment/spec.md` - User Story 5
- `/specs/004-clustering-alignment/plan.md` - Technical design
- `/specs/004-clustering-alignment/tasks.md` - Task breakdown
- `/specs/004-clustering-alignment/data-model.md` - Entity definitions

### Requirements
- FR-021: Every cluster has a label (medoid)
- FR-022: Medoid method (centroid-closest member)
- FR-023: Use cosine distance (same metric as clustering)
- FR-024: Labels use actual participant text
- FR-025: Deterministic labeling
- FR-044: Deterministic tie-breaking with lexicographic order
- SC-006: Same cluster produces same medoid across runs

---

## Sign-Off

**User Story 5 Status**: ✅ **COMPLETE**

All tasks (T062-T067) have been implemented and validated:
- ✅ Medoid computation with cosine distance
- ✅ Deterministic tie-breaking with lexicographic order
- ✅ Batch label assignment for multiple clusters
- ✅ Integration into clustering workflow
- ✅ API response includes medoid labels
- ✅ Test suite validates determinism (10 runs)

**Constitutional Compliance**: ✅ Verified
- Intent Fidelity: Labels use actual participant text
- Semantic Accuracy: Mathematical guarantee of centrality
- Temporal Transparency: Per-round processing

**Ready for Deployment**: ✅ Yes

---

**Implementation Date**: 2026-02-02
**Validated By**: Claude Sonnet 4.5
**Next Steps**: Phase 8 (Polish & Cross-Cutting Concerns)
