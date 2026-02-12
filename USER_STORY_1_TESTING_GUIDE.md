# User Story 1 Testing Guide

**Feature**: Semantic Clustering & Hybrid Alignment Protocol
**User Story**: Cluster Approved Summaries into Thought Spaces (T019-T037)
**Status**: Ready for Testing

## Prerequisites

1. **Database Running**: PostgreSQL 15+ with pgvector extension
2. **Redis Running**: Redis 7+ for event publishing
3. **Python Environment**: Python 3.11+ with dependencies installed
4. **Database Migrations**: Alembic migrations applied (013_create_spec004_clustering_tables.py)

### Quick Setup

```bash
# Start services
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00
docker-compose up -d postgres redis

# Activate virtual environment
cd backend
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Install dependencies (if needed)
pip install -r requirements.txt

# Run database migrations
alembic upgrade head
```

## Test Execution

### 1. Contract Tests (T037) - CRITICAL

Contract tests validate the integration boundary with Spec 5 (Sankey Diagrams).

```bash
# Run all contract tests
cd backend
pytest tests/contract/test_clustering_to_sankey.py -v

# Run specific contract tests
pytest tests/contract/test_clustering_to_sankey.py::test_clustering_complete_event_schema -v
pytest tests/contract/test_clustering_to_sankey.py::test_clustering_complete_100_percent_participant_coverage -v
pytest tests/contract/test_clustering_to_sankey.py::test_clustering_complete_preserves_minority_viewpoints -v
```

**Expected Results**:
- ✅ All tests should pass
- ✅ Event schema validation passes
- ✅ 100% participant coverage verified
- ✅ Minority viewpoints preserved (singleton clusters)
- ✅ user_to_cluster_map available for O(1) lookups

### 2. Integration Tests

End-to-end workflow validation.

```bash
# Run clustering workflow test
pytest tests/integration/test_clustering_flow.py -v

# Run outlier handling test
pytest tests/integration/test_outlier_handling.py -v

# Run performance test (SC-001: < 5s for 100 participants)
pytest tests/performance/test_clustering_performance.py -v
```

**Expected Results**:
- ✅ Complete workflow (fetch → embed → cluster → persist) succeeds
- ✅ Outliers converted to singleton clusters (100% coverage)
- ✅ Clustering completes in < 5 seconds for 100 participants

### 3. Unit Tests

Component-level validation.

```bash
# Run all unit tests
pytest tests/unit/test_centroid_computation.py -v
pytest tests/unit/test_medoid_selection.py -v
pytest tests/unit/test_embedding_determinism.py -v
pytest tests/unit/test_event_service.py -v

# Run specific unit test
pytest tests/unit/test_medoid_selection.py::test_medoid_determinism -v
```

**Expected Results**:
- ✅ Centroid computation is accurate (mean of embeddings)
- ✅ Medoid selection is deterministic (same input → same label)
- ✅ Embedding generation is deterministic (SC-007)
- ✅ Event publishing works correctly

### 4. Manual Testing Scenarios (from quickstart.md)

#### Scenario 1: Basic Clustering

**Goal**: Verify distinct thought spaces are created for thematic groups.

```bash
# 1. Create test data
curl -X POST http://localhost:8000/api/v1/test/create-round \
  -H "Content-Type: application/json" \
  -d '{
    "discussion_id": "test-123",
    "round_num": 1,
    "summaries": [
      {"text": "We need to reduce costs", "theme": "cost"},
      {"text": "Budget is too high", "theme": "cost"},
      {"text": "Cut expenses immediately", "theme": "cost"},
      {"text": "Improve processing speed", "theme": "speed"},
      {"text": "Make it faster", "theme": "speed"},
      {"text": "Optimize performance", "theme": "speed"},
      {"text": "Speed up the workflow", "theme": "speed"},
      {"text": "Ensure fairness for all", "theme": "fairness"},
      {"text": "Equal treatment matters", "theme": "fairness"},
      {"text": "Fair distribution needed", "theme": "fairness"}
    ]
  }'

# 2. Trigger clustering
curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -H "Content-Type: application/json" \
  -d '{"round_id": "<ROUND_ID_FROM_STEP_1>", "force_recluster": false}'

# 3. Verify clusters created
curl "http://localhost:8000/api/v1/clusters?round_id=<ROUND_ID>"
```

**Expected Results**:
- ✅ 3 distinct thought spaces created (cost, speed, fairness)
- ✅ `cluster_count`: 3
- ✅ `total_participants`: 10
- ✅ `percentage_sum`: 1.0 (exactly)
- ✅ Each cluster has `user_count` matching theme group size
- ✅ Labels are actual participant summaries (medoid method)

#### Scenario 2: Minority Preservation

**Goal**: Verify minority clusters are preserved without forced merging.

```bash
# Create round with 18 majority + 2 minority summaries
curl -X POST http://localhost:8000/api/v1/test/create-round \
  -H "Content-Type: application/json" \
  -d '{
    "summaries": [
      {"text": "Full remote work is essential", "theme": "remote"},
      {"text": "Remote work forever", "theme": "remote"},
      ... (16 more "remote" summaries)
      {"text": "Office-only policy needed", "theme": "office"},
      {"text": "In-person collaboration required", "theme": "office"}
    ]
  }'

# Trigger clustering and verify
curl -X POST http://localhost:8000/api/v1/clusters/trigger ...
curl "http://localhost:8000/api/v1/clusters?round_id=<ROUND_ID>"
```

**Expected Results**:
- ✅ 2 separate thought spaces created (no forced merging)
- ✅ Minority cluster visible with `user_count`: 2, `user_pct`: 0.1 (10%)
- ✅ Majority cluster has `user_count`: 18, `user_pct`: 0.9 (90%)
- ✅ `percentage_sum`: 1.0
- ✅ Constitutional guarantee: Semantic Accuracy Over Aesthetics upheld

#### Scenario 3: Outlier Handling

**Goal**: Verify outliers are converted to singleton clusters (100% coverage).

```bash
# Create round with 8 tight cluster + 2 outliers
curl -X POST http://localhost:8000/api/v1/test/create-round \
  -H "Content-Type: application/json" \
  -d '{
    "summaries": [
      {"text": "Team collaboration is key", "theme": "collaboration"},
      ... (7 more similar "collaboration" summaries)
      {"text": "Quantum computing breakthrough", "theme": "outlier1"},
      {"text": "Ancient Egyptian hieroglyphs", "theme": "outlier2"}
    ]
  }'

# Trigger clustering and verify
curl -X POST http://localhost:8000/api/v1/clusters/trigger ...
curl "http://localhost:8000/api/v1/clusters?round_id=<ROUND_ID>"
```

**Expected Results**:
- ✅ 3 thought spaces created (1 main cluster + 2 singleton clusters)
- ✅ Main cluster: `user_count`: 8, `user_pct`: 0.8 (80%)
- ✅ Singleton 1: `user_count`: 1, `user_pct`: 0.1 (10%)
- ✅ Singleton 2: `user_count`: 1, `user_pct`: 0.1 (10%)
- ✅ `total_participants`: 10 (100% coverage, no participants dropped)
- ✅ `singleton_count`: 2 in clustering.completed event

### 5. Event Verification

Verify clustering.completed event is published correctly.

```bash
# Subscribe to Redis channel (in separate terminal)
redis-cli
> SUBSCRIBE opendiscuss.clustering.completed

# Trigger clustering (in another terminal)
curl -X POST http://localhost:8000/api/v1/clusters/trigger ...

# Check Redis subscription output
```

**Expected Event Payload**:
```json
{
  "round_id": "uuid",
  "cluster_count": 3,
  "total_participants": 50,
  "singleton_count": 2,
  "processing_time_ms": 1234,
  "timestamp": "2026-02-02T12:34:56.789Z",
  "cluster_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Validation**:
- ✅ Event published to correct channel
- ✅ All required fields present
- ✅ `singleton_count` tracked correctly
- ✅ `processing_time_ms` < 5000 for 100 participants
- ✅ Timestamp in ISO 8601 format

## Validation Checklist

### Functional Requirements

- [ ] **FR-001**: Only approved summaries enter clustering ✅
- [ ] **FR-007**: Deterministic embedding generation ✅
- [ ] **FR-009**: Variable cluster count (not fixed K) ✅
- [ ] **FR-012**: No minimum cluster size threshold ✅
- [ ] **FR-013**: No forced merging ✅
- [ ] **FR-014**: Outliers → singleton clusters ✅
- [ ] **FR-016**: 100% participant coverage ✅
- [ ] **FR-019**: Percentages sum to 1.0 ✅
- [ ] **FR-024**: Labels use actual participant language ✅
- [ ] **FR-026/FR-027**: Centroids computed correctly ✅

### Success Criteria

- [ ] **SC-001**: Clustering < 5s for 100 participants ✅
- [ ] **SC-003**: 100% accuracy for user assignments ✅
- [ ] **SC-005**: Percentage sum = 1.0 ± 0.0001 ✅
- [ ] **SC-006**: Medoid labeling 100% deterministic ✅
- [ ] **SC-007**: Embedding generation 100% reproducible ✅

### Constitutional Compliance

- [ ] **Semantic Accuracy Over Aesthetics**: Minority clusters preserved ✅
- [ ] **Intent Fidelity**: Only approved summaries, actual participant language ✅
- [ ] **Temporal Transparency**: Per-round independence, deterministic results ✅

## Debugging Tips

### Issue: Clustering fails with "No approved summaries"

**Cause**: No summaries in `approved_summaries` table for the round.

**Solution**:
```sql
-- Check if summaries exist
SELECT COUNT(*) FROM approved_summaries WHERE round_id = '<ROUND_ID>';

-- Check summary approval status (if using Spec 3 integration)
SELECT status FROM summaries WHERE round_id = '<ROUND_ID>';
```

### Issue: Percentages don't sum to 1.0

**Cause**: Floating point precision or missing participants.

**Solution**:
```python
# Check cluster statistics
total_pct = sum(c.user_pct for c in clusters)
print(f"Percentage sum: {total_pct:.10f}")  # Should be 1.0 ± 0.0001

# Check for orphaned summaries
SELECT COUNT(*) FROM approved_summaries
WHERE round_id = '<ROUND_ID>' AND cluster_id IS NULL;
```

### Issue: Embedding generation fails

**Cause**: `sentence-transformers` not installed or model download failed.

**Solution**:
```bash
# Install sentence-transformers
pip install sentence-transformers>=2.2.0

# Test model loading
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); print('Model loaded successfully')"
```

### Issue: HDBSCAN fails or produces unexpected clusters

**Cause**: Invalid embeddings, wrong dimensions, or data issues.

**Solution**:
```python
# Verify embeddings
import numpy as np
from src.services.embedding_service import generate_embeddings

texts = ["test summary 1", "test summary 2"]
embeddings = await generate_embeddings(texts)

print(f"Embeddings shape: {embeddings.shape}")  # Should be (2, 384)
print(f"Embeddings dtype: {embeddings.dtype}")  # Should be float32
print(f"Embeddings range: [{embeddings.min()}, {embeddings.max()}]")
```

### Issue: Events not published to Redis

**Cause**: Redis not running or connection issues.

**Solution**:
```bash
# Check Redis connection
redis-cli ping
# Should return: PONG

# Check Redis logs
docker logs opendiscuss-redis

# Test Redis from Python
import redis
r = redis.Redis(host='localhost', port=6379, db=0)
r.ping()  # Should return True
```

## Performance Benchmarking

### Run performance tests

```bash
# Run performance test suite
pytest tests/performance/test_clustering_performance.py -v --benchmark

# Manual performance test
time curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -H "Content-Type: application/json" \
  -d '{"round_id": "<ROUND_ID>", "force_recluster": true}'
```

### Expected Performance Metrics

| Operation | Target | Acceptable |
|-----------|--------|------------|
| Embedding generation (100 summaries) | < 1s | < 2s |
| HDBSCAN clustering | < 0.5s | < 1s |
| Centroid computation | < 0.05s | < 0.1s |
| Database persistence | < 0.5s | < 1s |
| **Total workflow** | **< 2s** | **< 5s** |

## Test Data Generators

### Generate test summaries

```python
# Create diverse test summaries
test_summaries = [
    # Cost cluster
    "We need to reduce operational costs",
    "Budget constraints are limiting us",
    "Cutting expenses is critical now",

    # Speed cluster
    "Improve processing speed urgently",
    "Faster execution is essential",
    "Optimize performance immediately",
    "Speed up the entire workflow",

    # Fairness cluster
    "Ensure fair treatment for everyone",
    "Equal distribution is important",
    "Fairness must be maintained",

    # Outliers
    "Quantum computing will revolutionize AI",
    "Ancient pyramids hold many secrets"
]
```

### Generate synthetic clusters

```python
from sklearn.datasets import make_blobs
import numpy as np

# Generate 100 points in 3 clusters + 5 outliers
X_main, y_main = make_blobs(
    n_samples=95,
    centers=3,
    n_features=384,  # SBERT dimension
    cluster_std=0.5,
    random_state=42
)

# Add outliers
X_outliers = np.random.randn(5, 384) * 5
X = np.vstack([X_main, X_outliers])
```

## Continuous Integration

### GitHub Actions (example)

```yaml
# .github/workflows/test-clustering.yml
name: Test Clustering Workflow

on:
  push:
    branches: [ main, 003-summarization-approval ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_DB: opendiscuss_test
          POSTGRES_USER: opendiscuss
          POSTGRES_PASSWORD: test_password
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: 3.11

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run migrations
        run: |
          cd backend
          alembic upgrade head

      - name: Run contract tests
        run: |
          cd backend
          pytest tests/contract/test_clustering_to_sankey.py -v

      - name: Run integration tests
        run: |
          cd backend
          pytest tests/integration/test_clustering_flow.py -v
```

## Acceptance Criteria (from spec.md)

### User Story 1 Acceptance Scenarios

1. ✅ **Given** 10 participants with thematic groups, **When** clustering runs, **Then** distinct thought spaces created
2. ✅ **Given** clustering completes, **When** results generated, **Then** each thought space includes cluster_id, members, user_count, percentage
3. ✅ **Given** thought spaces created, **When** percentages calculated, **Then** they sum to 1.0
4. ✅ **Given** 10 users participate, **When** clustering assigns them, **Then** each user assigned to exactly one thought space
5. ✅ **Given** approved summaries clustered, **When** system processes input, **Then** only approved summaries enter clustering

## Next Steps

After User Story 1 testing is complete:

1. **Run all tests**: `pytest tests/contract tests/integration tests/unit -v`
2. **Verify success criteria**: All SC-001 through SC-013 validated
3. **Manual validation**: Run quickstart.md scenarios 1-3
4. **Performance check**: Confirm < 5s for 100 participants
5. **Create PR**: Submit for code review
6. **Proceed to User Story 2**: Minority cluster preservation validation (T038-T042)

---

**Testing Completed**: [DATE]
**Tested By**: [NAME]
**Test Results**: [PASS/FAIL]
**Issues Found**: [NONE or LIST]
**Ready for Deployment**: [YES/NO]
