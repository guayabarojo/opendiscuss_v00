# T077: Quickstart Validation Guide

**Feature**: Semantic Clustering & Hybrid Alignment Protocol (Spec 004)
**Task**: T077 - Manual validation of quickstart scenarios
**Date**: 2026-02-06
**Status**: ⚠️ REQUIRES MANUAL EXECUTION

---

## Purpose

Execute the manual curl commands from `specs/004-clustering-alignment/quickstart.md` to validate that all API endpoints work end-to-end. This validates the complete implementation of Spec 004.

---

## Prerequisites

1. **Backend server running**: `uvicorn src.main:app --reload --port 8000`
2. **PostgreSQL database**: With all migrations applied
3. **Redis**: Running on port 6379 (for events)
4. **Test data**: Approved summaries in database

---

## Validation Scenarios

### Scenario 1: Basic Clustering (Lines 92-211 in quickstart.md)

**Goal**: Verify clustering creates thought spaces from approved summaries

#### Step 1: Prepare Test Data

```python
# Create 10 approved summaries with clear themes
approved_summaries = [
    {"summary_text": "We need to reduce costs by 20%"},           # Theme: Cost (3 summaries)
    {"summary_text": "Budget cuts are essential"},
    {"summary_text": "Lowering expenses is critical"},

    {"summary_text": "Speed improvements are top priority"},     # Theme: Speed (4 summaries)
    {"summary_text": "Performance optimization matters most"},
    {"summary_text": "We must accelerate delivery"},
    {"summary_text": "Faster execution is key"},

    {"summary_text": "Fairness should be our guide"},           # Theme: Fairness (2 summaries)
    {"summary_text": "Equity is fundamental"},

    {"summary_text": "This is a completely unique viewpoint"},  # Outlier (1 singleton)
]
```

**Execute**:
```bash
# Insert test data
python3 backend/create_sample_data.py --scenario clustering_basic

# Trigger clustering
curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef"
  }'
```

#### Step 2: Verify Clustering Complete

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
      "cluster_id": "c1111111-...",
      "user_count": 4,
      "user_pct": 0.4,
      "label_summary": "Speed improvements are top priority",
      "display_group_id": null,
      "centroid_vector": [0.123, -0.456, ...]
    },
    {
      "cluster_id": "c2222222-...",
      "user_count": 3,
      "user_pct": 0.3,
      "label_summary": "We need to reduce costs by 20%",
      "display_group_id": null,
      "centroid_vector": [-0.234, 0.567, ...]
    },
    {
      "cluster_id": "c3333333-...",
      "user_count": 2,
      "user_pct": 0.2,
      "label_summary": "Fairness should be our guide",
      "display_group_id": null,
      "centroid_vector": [0.345, 0.678, ...]
    },
    {
      "cluster_id": "c4444444-...",
      "user_count": 1,
      "user_pct": 0.1,
      "label_summary": "This is a completely unique viewpoint",
      "display_group_id": null,
      "centroid_vector": [0.789, -0.123, ...]
    }
  ]
}
```

**Validation Checklist**:
- [ ] ✅ 4 clusters created (speed:4, cost:3, fairness:2, outlier:1)
- [ ] ✅ Percentages sum to 1.0 (0.4 + 0.3 + 0.2 + 0.1 = 1.0)
- [ ] ✅ Minority cluster preserved (fairness: 2 members, 20%)
- [ ] ✅ Outlier converted to singleton (unique view: 1 member, 10%)
- [ ] ✅ Medoid labels use actual participant language (no AI-generated text)

---

### Scenario 2: Minority Preservation (Lines 214-258 in quickstart.md)

**Goal**: Verify 2-person minority cluster is NOT force-merged with 18-person majority

#### Test Data

```python
# 20 summaries: 18 majority, 2 minority
summaries = []

# Majority: full remote work (18 summaries)
for i in range(18):
    summaries.append({
        "summary_text": f"Full remote work is best option (variant {i})"
    })

# Minority: office-only (2 summaries)
for i in range(2):
    summaries.append({
        "summary_text": f"Office-only policy is essential (variant {i})"
    })
```

**Execute**:
```bash
# Insert test data
python3 backend/create_sample_data.py --scenario minority_preservation

# Trigger clustering
curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "round_id": "r2234567-89ab-cdef-0123-456789abcdef"
  }'

# Verify
curl http://localhost:8000/api/v1/clusters?round_id=r2234567-89ab-cdef-0123-456789abcdef
```

**Expected Response**:
```json
{
  "cluster_count": 2,
  "total_participants": 20,
  "percentage_sum": 1.0,
  "clusters": [
    {
      "user_count": 18,
      "user_pct": 0.9,
      "label_summary": "Full remote work is best option (variant 0)"
    },
    {
      "user_count": 2,
      "user_pct": 0.1,
      "label_summary": "Office-only policy is essential (variant 0)"
    }
  ]
}
```

**Validation Checklist**:
- [ ] ✅ Exactly 2 clusters created (NOT 1)
- [ ] ✅ Minority cluster has 2 members (10%)
- [ ] ✅ Majority cluster has 18 members (90%)
- [ ] ✅ No forced merging despite size difference
- [ ] ✅ Constitutional principle upheld: "Semantic Accuracy Over Aesthetics"

---

### Scenario 3: Cross-Round Alignment (Lines 261-364 in quickstart.md)

**Goal**: Verify semantically similar clusters across rounds get display group IDs

#### Test Data

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
```

**Execute**:
```bash
# Insert test data for both rounds
python3 backend/create_sample_data.py --scenario cross_round_alignment

# Cluster Round 1
curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -d '{"round_id": "r1234567-89ab-cdef-0123-456789abcdef"}'

# Cluster Round 2
curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -d '{"round_id": "r2234567-89ab-cdef-0123-456789abcdef"}'

# Trigger Alignment
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
    "round_r": 1,
    "round_r1": 2,
    "similarity_threshold": 0.7
  }'
```

**Verify Alignment**:
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
      "alignment_id": "a1111111-...",
      "round_r": 1,
      "round_r1": 2,
      "cluster_r_id": "c1111111-...",  // "cost concerns"
      "cluster_r1_id": "c2222222-...",  // "budget constraints"
      "similarity_score": 0.82,
      "display_group_id": "d1111111-...",  // Same display group
      "alignment_type": "1-to-1"
    }
  ]
}
```

**Validation Checklist**:
- [ ] ✅ Similarity > 0.7 threshold (e.g., 0.82)
- [ ] ✅ Display group ID assigned to both clusters
- [ ] ✅ "new topic" cluster in Round 2 NOT aligned (no match in Round 1)
- [ ] ✅ Alignment does NOT change cluster membership (alignment is presentation-only)

---

## Alignment Invariance Verification

**Critical Test**: Verify alignment does NOT change cluster membership

```bash
# Get clusters before alignment
curl http://localhost:8000/api/v1/clusters?round_id=r1234567-89ab-cdef-0123-456789abcdef > before.json

# Run alignment
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -d '{
    "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
    "round_r": 1,
    "round_r1": 2,
    "similarity_threshold": 0.7
  }'

# Get clusters after alignment
curl http://localhost:8000/api/v1/clusters?round_id=r1234567-89ab-cdef-0123-456789abcdef > after.json

# Compare (should be identical except display_group_id)
diff <(jq '.clusters[] | {user_count, user_pct, member_user_ids}' before.json) \
     <(jq '.clusters[] | {user_count, user_pct, member_user_ids}' after.json)
```

**Expected**: No differences (FR-037, SC-009)

---

## Performance Validation

### Success Criteria (SC-001)

**Requirement**: Clustering completes in < 5 seconds for 100 participants

**Test**:
```bash
# Create 100 approved summaries
python3 backend/create_sample_data.py --scenario performance_100

# Trigger with timing
time curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -d '{"round_id": "r-perf-test"}'

# Check processing_time_ms in response
curl http://localhost:8000/api/v1/clusters?round_id=r-perf-test | jq '.processing_time_ms'
```

**Expected**: `processing_time_ms < 5000`

---

## Event Bus Validation

### Verify Events Published

```python
# Subscribe to Redis events
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
pubsub = r.pubsub()
pubsub.subscribe('opendiscuss.clustering.completed')
pubsub.subscribe('opendiscuss.alignment.completed')

# Trigger clustering
# ... (see above)

# Check events received
for message in pubsub.listen():
    if message['type'] == 'message':
        print(f"Event: {message['channel']}")
        print(f"Payload: {message['data']}")
```

**Expected Events**:
1. `clustering.completed` after clustering finishes
2. `alignment.completed` after alignment finishes

---

## Summary: T077 Validation Checklist

### Scenario 1: Basic Clustering
- [ ] API endpoint works (`POST /api/v1/clusters/trigger`)
- [ ] Clustering creates 4 thought spaces from 10 summaries
- [ ] Percentages sum to 1.0
- [ ] Minority cluster (2 members) preserved
- [ ] Outlier becomes singleton cluster
- [ ] Medoid labels use participant language

### Scenario 2: Minority Preservation
- [ ] API endpoint works
- [ ] 2 clusters created (18 + 2 split)
- [ ] No forced merging despite 9:1 ratio
- [ ] Constitutional principle upheld

### Scenario 3: Cross-Round Alignment
- [ ] Alignment API endpoint works (`POST /api/v1/alignments/trigger`)
- [ ] Semantically similar clusters aligned (similarity > 0.7)
- [ ] Display group IDs assigned
- [ ] Alignment does NOT change membership

### Performance
- [ ] Clustering < 5s for 100 participants (SC-001)

### Events
- [ ] `clustering.completed` event published
- [ ] `alignment.completed` event published

---

## Next Steps

Once backend is running:
1. Start backend: `cd backend && uvicorn src.main:app --reload --port 8000`
2. Execute each scenario above
3. Document results in `T077_VALIDATION_RESULTS.md`
4. Mark T077 complete in `tasks.md`

---

## References

- **Quickstart Guide**: `/specs/004-clustering-alignment/quickstart.md`
- **API Documentation**: `/backend/docs/api_documentation.md`
- **Integration Spec 5**: `/backend/docs/integration_spec5.md`
- **Success Criteria**: `/specs/004-clustering-alignment/spec.md` (SC-001 through SC-013)
