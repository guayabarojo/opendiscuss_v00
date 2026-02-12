# Quickstart Guide: Semantic Clustering & Hybrid Alignment Protocol

**Feature**: Semantic Clustering & Hybrid Alignment Protocol (Spec 004)
**Date**: 2026-01-29
**Audience**: Developers implementing or integrating with clustering/alignment

## Overview

This guide helps you:
1. Set up SBERT embedding model and HDBSCAN clustering
2. Run clustering on approved summaries
3. Test minority preservation and outlier handling
4. Implement cross-round alignment
5. Integrate with Spec 3 (input) and Spec 5 (output)

**Estimated time**: 45 minutes

---

## Prerequisites

### Required

- **Python 3.11+**: Language runtime (same as Spec 2/3)
- **PostgreSQL 15+ with pgvector**: For storing embeddings and centroids
- **Approved summaries**: From Spec 3 (Summarization & Approval Protocol)

### Optional

- **GPU**: For faster embedding generation (CPU sufficient for MVP)

---

## Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**requirements.txt** additions:
```
sentence-transformers==2.2.2
hdbscan==0.8.33
numpy==1.24.3
scipy==1.10.1
scikit-learn==1.3.0
```

### 2. Install pgvector Extension

```bash
# Connect to PostgreSQL
psql -U postgres -d opendiscuss_dev

# Install extension
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. Run Migrations

```bash
# Create clustering tables
alembic upgrade head
```

**Tables created**:
- `embeddings` (summary_id, embedding_vector[384], model_version)
- `clusters` (cluster_id, round_id, user_count, user_pct, label_summary_id, centroid_vector[384])
- `cluster_members` (cluster_id, summary_id, user_id)
- `alignment_maps` (alignment_id, round_r, round_r1, cluster_r_id, cluster_r1_id, similarity_score, display_group_id)

### 4. Download SBERT Model

```python
# Run once to download model (cached locally)
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
print(f"Model loaded: {model.get_sentence_embedding_dimension()} dimensions")
# Output: Model loaded: 384 dimensions
```

**Model size**: ~80 MB (downloads to `~/.cache/torch/sentence_transformers/`)

---

## Basic Usage

### Scenario 1: Cluster Approved Summaries

#### Step 1: Prepare Test Data

```python
# Create 10 approved summaries with clear themes
approved_summaries = [
    {"summary_id": uuid4(), "user_id": uuid4(), "round_id": ROUND_ID,
     "summary_text": "We need to reduce costs by 20%"},
    {"summary_id": uuid4(), "user_id": uuid4(), "round_id": ROUND_ID,
     "summary_text": "Budget cuts are essential"},
    {"summary_id": uuid4(), "user_id": uuid4(), "round_id": ROUND_ID,
     "summary_text": "Lowering expenses is critical"},

    {"summary_id": uuid4(), "user_id": uuid4(), "round_id": ROUND_ID,
     "summary_text": "Speed improvements are top priority"},
    {"summary_id": uuid4(), "user_id": uuid4(), "round_id": ROUND_ID,
     "summary_text": "Performance optimization matters most"},
    {"summary_id": uuid4(), "user_id": uuid4(), "round_id": ROUND_ID,
     "summary_text": "We must accelerate delivery"},
    {"summary_id": uuid4(), "user_id": uuid4(), "round_id": ROUND_ID,
     "summary_text": "Faster execution is key"},

    {"summary_id": uuid4(), "user_id": uuid4(), "round_id": ROUND_ID,
     "summary_text": "Fairness should be our guide"},
    {"summary_id": uuid4(), "user_id": uuid4(), "round_id": ROUND_ID,
     "summary_text": "Equity is fundamental"},

    {"summary_id": uuid4(), "user_id": uuid4(), "round_id": ROUND_ID,
     "summary_text": "This is a completely unique viewpoint"},  # Outlier
]

# Insert into database
for summary in approved_summaries:
    db.session.add(ApprovedSummary(**summary))
db.session.commit()
```

#### Step 2: Trigger Clustering

```bash
curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef"
  }'
```

**Response**:
```json
{
  "job_id": "j1234567-89ab-cdef-0123-456789abcdef",
  "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
  "status": "PROCESSING",
  "estimated_completion_ms": 3600,
  "message": "Clustering initiated for 10 approved summaries"
}
```

#### Step 3: Verify Clustering Complete

```bash
curl http://localhost:8000/api/v1/clusters?round_id=r1234567-89ab-cdef-0123-456789abcdef
```

**Expected Response**:
```json
{
  "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
  "cluster_count": 4,
  "total_participants": 10,
  "percentage_sum": 1.0,
  "clusters": [
    {
      "cluster_id": "c1111111-89ab-cdef-0123-456789abcdef",
      "user_count": 4,
      "user_pct": 0.4,
      "label_summary": "Speed improvements are top priority",
      "label_summary_id": "s1111111-89ab-cdef-0123-456789abcdef",
      "display_group_id": null,
      "centroid_vector": [0.123, -0.456, ...]
    },
    {
      "cluster_id": "c2222222-89ab-cdef-0123-456789abcdef",
      "user_count": 3,
      "user_pct": 0.3,
      "label_summary": "We need to reduce costs by 20%",
      "label_summary_id": "s2222222-89ab-cdef-0123-456789abcdef",
      "display_group_id": null,
      "centroid_vector": [-0.234, 0.567, ...]
    },
    {
      "cluster_id": "c3333333-89ab-cdef-0123-456789abcdef",
      "user_count": 2,
      "user_pct": 0.2,
      "label_summary": "Fairness should be our guide",
      "label_summary_id": "s3333333-89ab-cdef-0123-456789abcdef",
      "display_group_id": null,
      "centroid_vector": [0.345, 0.678, ...]
    },
    {
      "cluster_id": "c4444444-89ab-cdef-0123-456789abcdef",
      "user_count": 1,
      "user_pct": 0.1,
      "label_summary": "This is a completely unique viewpoint",
      "label_summary_id": "s4444444-89ab-cdef-0123-456789abcdef",
      "display_group_id": null,
      "centroid_vector": [0.789, -0.123, ...]
    }
  ]
}
```

**Validation**:
- ✅ 4 clusters created (speed:4, cost:3, fairness:2, outlier:1)
- ✅ Percentages sum to 1.0 (0.4 + 0.3 + 0.2 + 0.1 = 1.0)
- ✅ Minority cluster preserved (fairness: 2 members, 20%)
- ✅ Outlier converted to singleton cluster (unique view: 1 member, 10%)
- ✅ Medoid labels from actual participant language (no AI generation)

---

### Scenario 2: Test Minority Preservation

**Goal**: Verify system preserves 2-person minority cluster without forced merging

```python
# Create 20 summaries: 18 majority, 2 minority
summaries = []

# Majority: full remote work
for i in range(18):
    summaries.append({
        "summary_id": uuid4(),
        "user_id": uuid4(),
        "round_id": ROUND_ID,
        "summary_text": f"Full remote work is best option (variant {i})"
    })

# Minority: office-only
for i in range(2):
    summaries.append({
        "summary_id": uuid4(),
        "user_id": uuid4(),
        "round_id": ROUND_ID,
        "summary_text": f"Office-only policy is essential (variant {i})"
    })

# Trigger clustering
response = trigger_clustering(ROUND_ID)
clusters = get_clusters(ROUND_ID)

# Verify
assert len(clusters) == 2, f"Expected 2 clusters, got {len(clusters)}"
cluster_sizes = sorted([c['user_count'] for c in clusters])
assert cluster_sizes == [2, 18], f"Expected [2, 18], got {cluster_sizes}"

print("✅ Minority cluster preserved: 2 members (10%), NOT merged with majority")
```

**Expected Output**:
```
✅ Minority cluster preserved: 2 members (10%), NOT merged with majority
```

**Constitutional Compliance**: Semantic Accuracy Over Aesthetics (FR-012, FR-013, SC-004)

---

### Scenario 3: Cross-Round Alignment

**Goal**: Align semantically similar clusters across adjacent rounds for visual continuity

#### Step 1: Cluster Two Rounds

```python
# Round 1: "cost concerns"
round1_summaries = [
    {"summary_text": "We need to reduce costs"},
    {"summary_text": "Budget is a major concern"},
    {"summary_text": "Expenses are too high"},
]

# Round 2: "budget constraints" (similar) + "new topic" (different)
round2_summaries = [
    {"summary_text": "Budget constraints are limiting us"},
    {"summary_text": "Financial restrictions are tough"},
    {"summary_text": "We need better tools for collaboration"},  # New topic
]

cluster_round(round_id=1, summaries=round1_summaries)
cluster_round(round_id=2, summaries=round2_summaries)
```

#### Step 2: Trigger Alignment

```bash
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
    "round_r": 1,
    "round_r1": 2,
    "similarity_threshold": 0.7
  }'
```

**Response**:
```json
{
  "job_id": "a1234567-89ab-cdef-0123-456789abcdef",
  "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
  "round_r": 1,
  "round_r1": 2,
  "status": "PROCESSING",
  "estimated_completion_ms": 500
}
```

#### Step 3: Verify Alignment

```bash
curl "http://localhost:8000/api/v1/alignments?discussion_id=d1234567-89ab-cdef-0123-456789abcdef&round_r=1"
```

**Expected Response**:
```json
{
  "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
  "alignment_count": 1,
  "alignments": [
    {
      "alignment_id": "a1111111-89ab-cdef-0123-456789abcdef",
      "round_r": 1,
      "round_r1": 2,
      "cluster_r_id": "c1111111-89ab-cdef-0123-456789abcdef",  # "cost concerns"
      "cluster_r1_id": "c2222222-89ab-cdef-0123-456789abcdef",  # "budget constraints"
      "similarity_score": 0.82,
      "display_group_id": "d1111111-89ab-cdef-0123-456789abcdef",
      "alignment_type": "1-to-1"
    }
  ]
}
```

**Validation**:
- ✅ Similarity > 0.7 threshold (0.82)
- ✅ Display group ID assigned (same for both clusters → same color in Sankey)
- ✅ "new topic" cluster in Round 2 NOT aligned (no match in Round 1)

#### Step 4: Verify Alignment Invariance

```python
# Get clusters before alignment
clusters_before = get_clusters(round_id=1)

# Run alignment
trigger_alignment(discussion_id, round_r=1, round_r1=2)

# Get clusters after alignment
clusters_after = get_clusters(round_id=1)

# Verify membership unchanged
for c_before, c_after in zip(clusters_before, clusters_after):
    assert c_before['member_user_ids'] == c_after['member_user_ids'], "Members changed!"
    assert c_before['user_count'] == c_after['user_count'], "User count changed!"
    assert c_before['user_pct'] == c_after['user_pct'], "User pct changed!"

print("✅ Alignment did NOT change cluster membership (FR-037, SC-009)")
```

**Constitutional Compliance**: Alignment presentation-only (FR-037, FR-038, FR-039)

---

## Testing

### Run Unit Tests

```bash
cd backend
pytest tests/unit/test_clustering.py -v
```

**Key test files**:
- `test_embedding_determinism.py`: Same text → same embedding
- `test_medoid_selection.py`: Closest to centroid, tie-breaking
- `test_centroid_computation.py`: Mean of member vectors
- `test_outlier_handling.py`: Noise (-1) → singleton clusters

**Example Test**:
```python
def test_embedding_determinism():
    """FR-007: Same text produces same embedding"""
    model = load_embedding_model()
    text = "We need to reduce costs by 20%"

    embedding1 = model.encode([text])[0]
    embedding2 = model.encode([text])[0]

    assert np.allclose(embedding1, embedding2, atol=1e-9)
```

### Run Integration Tests

```bash
pytest tests/integration/test_clustering_flow.py -v
```

**Key test files**:
- `test_clustering_flow.py`: End-to-end clustering workflow
- `test_minority_preservation.py`: 18+2 split preserved
- `test_outlier_handling.py`: Outliers → singletons, 100% coverage
- `test_alignment_accuracy.py`: 70%+ match rate, no membership changes

**Example Test**:
```python
def test_minority_cluster_preservation():
    """SC-004: Minority clusters preserved without forced merging"""
    # 18 majority, 2 minority
    summaries = create_summaries(majority=18, minority=2)

    clusters = cluster_summaries(summaries)

    # Expect 2 clusters
    assert len(clusters) == 2

    # Minority cluster has exactly 2 members
    cluster_sizes = sorted([c.user_count for c in clusters])
    assert cluster_sizes == [2, 18]
```

---

## Integration with Spec 3 & Spec 5

### Event Bus Setup (In-Memory for MVP)

```python
# backend/src/events/in_memory_bus.py
subscribers = {}

def subscribe(event_type, handler):
    if event_type not in subscribers:
        subscribers[event_type] = []
    subscribers[event_type].append(handler)

async def publish(event_type, payload):
    if event_type in subscribers:
        for handler in subscribers[event_type]:
            await handler(payload)
```

### Subscribe to Spec 3 Events

```python
# backend/src/services/clustering_service.py
from src.events import subscribe, publish

@subscribe("summaries.approved_for_round")
async def trigger_clustering(event):
    """Auto-trigger clustering when all summaries approved."""
    round_id = event["data"]["round_id"]
    summary_count = event["data"]["summary_count"]

    logger.info(f"Clustering triggered for round {round_id}: {summary_count} summaries")

    # Fetch approved summaries
    summaries = fetch_approved_summaries(round_id)

    # Run clustering
    clusters = await run_clustering(summaries)

    # Publish completion event
    await publish("clustering.completed", {
        "event_id": str(uuid4()),
        "event_type": "clustering.completed",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "round_id": round_id,
            "cluster_count": len(clusters),
            "total_participants": sum(c.user_count for c in clusters),
            "singleton_count": sum(1 for c in clusters if c.user_count == 1),
            "processing_time_ms": processing_time
        }
    })
```

### Publish Events for Spec 5

```python
# Spec 5 subscribes to clustering.completed
@subscribe("clustering.completed")
async def on_clustering_complete(event):
    """Spec 5: Sankey Construction can now proceed."""
    round_id = event["data"]["round_id"]
    cluster_count = event["data"]["cluster_count"]

    logger.info(f"Thought spaces ready for Sankey: {cluster_count} clusters in round {round_id}")

    # Fetch clusters via API
    clusters = fetch_clusters(round_id)

    # Build Sankey column
    sankey_column = build_column(clusters)
```

---

## Troubleshooting

### Issue: HDBSCAN creates no clusters (all noise)

**Symptom**: `cluster_count = 0`, all participants labeled as noise (-1)

**Causes**:
1. `min_cluster_size` too high (data too sparse)
2. Embeddings not semantically similar (all unique)

**Solutions**:
```python
# Lower min_cluster_size (currently 2, try 1)
clusterer = hdbscan.HDBSCAN(
    min_cluster_size=1,  # Allow singletons
    min_samples=1
)

# Or fallback: if all noise, create singleton for each
if cluster_count == 0:
    for i, summary in enumerate(summaries):
        clusters.append(Cluster(
            cluster_id=uuid4(),
            user_count=1,
            user_pct=1.0 / len(summaries),
            label_summary_id=summary.summary_id,
            centroid_vector=embeddings[i]
        ))
```

---

### Issue: Percentages don't sum to 1.0

**Symptom**: `percentage_sum = 0.9999` or `1.0001`

**Cause**: Floating-point rounding

**Solution**:
```python
# Compute percentages
total_users = sum(c.user_count for c in clusters)
user_pcts = [c.user_count / total_users for c in clusters]

# Adjust last cluster to ensure sum = 1.0
user_pcts[-1] = 1.0 - sum(user_pcts[:-1])

# Verify
assert abs(sum(user_pcts) - 1.0) < 0.0001  # SC-005
```

---

### Issue: Medoid label is verbose/poor quality

**Symptom**: Medoid summary is long or poorly phrased

**Cause**: Medoid selection is deterministic (closest to centroid), may select verbose summary

**Solutions**:
- **Accept as-is**: Medoid uses actual participant language (Intent Fidelity principle)
- **Post-MVP**: Implement LLM-based label generation as optional enhancement (requires user consent)

**Current behavior**: Working as designed (FR-024, no AI-generated labels)

---

### Issue: Alignment finds no matches

**Symptom**: `alignment_count = 0`

**Causes**:
1. Similarity threshold too high (0.7 may be too strict)
2. Clusters genuinely different across rounds

**Solutions**:
```bash
# Lower threshold
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -d '{
    "discussion_id": "...",
    "round_r": 1,
    "round_r1": 2,
    "similarity_threshold": 0.6
  }'

# Or accept: No alignment is valid if clusters truly different
```

---

## Next Steps

1. **Implement Spec 5 Integration**: Subscribe to `clustering.completed` events in Sankey Construction service
2. **Tune HDBSCAN Parameters**: Test with real discussion data to optimize clustering quality
3. **Add Monitoring**: Log clustering performance, singleton rate, alignment success rate
4. **Deploy to Staging**: Test with 100 concurrent users (performance validation)

---

## Resources

- **API Spec**: `contracts/api-spec.yaml`
- **Event Contract**: `contracts/events.yaml`
- **Data Model**: `data-model.md`
- **Research**: `research.md`

**Support**: Open an issue at https://github.com/opendiscuss/issues
