# API Documentation: Semantic Clustering & Hybrid Alignment Protocol

**Feature**: Spec 004 - Semantic Clustering & Hybrid Alignment Protocol
**Version**: 1.0.0
**Base URL**: `http://localhost:8000/api/v1`
**Date**: 2026-01-29

---

## Overview

This API provides endpoints for clustering approved summaries into thought spaces and aligning clusters across adjacent rounds for visual continuity in discussions.

### Key Capabilities

- **Clustering**: Convert approved summaries to semantic clusters using SBERT embeddings + HDBSCAN
- **Alignment**: Link semantically similar clusters across rounds for visual flow continuity
- **Thought Spaces**: Represent coherent ideas with participant distribution and medoid labels
- **Event Integration**: Publish events for downstream systems (Sankey Construction - Spec 5)

---

## Authentication

All endpoints require JWT authentication via `Authorization: Bearer <token>` header.

```bash
# Example header
-H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Clustering Endpoints

### 1. Trigger Clustering

**Endpoint**: `POST /clusters/trigger`

Initiates semantic clustering workflow for approved summaries in a round.

#### Request

```bash
curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
    "force_recluster": false
  }'
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `round_id` | UUID | Yes | Round ID to cluster (from Spec 3) |
| `force_recluster` | Boolean | No | Force reclustering if already exists (default: false) |

#### Success Response (202 Accepted)

```json
{
  "job_id": "j1234567-89ab-cdef-0123-456789abcdef",
  "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
  "status": "PROCESSING",
  "estimated_completion_ms": 3600,
  "message": "Clustering initiated for 95 approved summaries"
}
```

#### Error Responses

**400 Bad Request** - No approved summaries:
```json
{
  "error": "NO_APPROVED_SUMMARIES",
  "message": "Round has no approved summaries. Clustering cannot proceed.",
  "details": {
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
    "approved_count": 0
  }
}
```

**409 Conflict** - Clustering already exists:
```json
{
  "error": "CLUSTERING_EXISTS",
  "message": "Clustering already computed for this round. Use force_recluster=true to override.",
  "details": {
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
    "cluster_count": 8
  }
}
```

#### Workflow

1. Fetch approved summaries from Spec 3
2. Generate SBERT embeddings (all-MiniLM-L6-v2, 384-dim)
3. Run HDBSCAN clustering (variable K, min_cluster_size=2)
4. Convert outliers (label=-1) to singleton clusters
5. Compute centroid vectors (mean of member embeddings)
6. Select medoid labels (summary closest to centroid)
7. Persist clusters to database
8. Publish `clustering.completed` event to Redis

**Performance**: < 5 seconds for 100 participants

---

### 2. Get Clusters for Round

**Endpoint**: `GET /clusters`

Returns all thought spaces for a specified round with cluster details.

#### Request

```bash
curl http://localhost:8000/api/v1/clusters \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `round_id` | UUID | Yes | Round ID to fetch clusters for |
| `include_members` | Boolean | No | Include member details (default: false) |

#### Success Response (200 OK)

```json
{
  "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
  "cluster_count": 8,
  "total_participants": 95,
  "percentage_sum": 1.0,
  "clusters": [
    {
      "cluster_id": "c1111111-89ab-cdef-0123-456789abcdef",
      "user_count": 32,
      "user_pct": 0.337,
      "label_summary": "We need to reduce costs by 20%",
      "label_summary_id": "s1111111-89ab-cdef-0123-456789abcdef",
      "display_group_id": "d1111111-89ab-cdef-0123-456789abcdef",
      "centroid_vector": [0.123, -0.456, 0.789, ...]
    },
    {
      "cluster_id": "c2222222-89ab-cdef-0123-456789abcdef",
      "user_count": 28,
      "user_pct": 0.295,
      "label_summary": "Speed improvements are top priority",
      "label_summary_id": "s2222222-89ab-cdef-0123-456789abcdef",
      "display_group_id": "d1111111-89ab-cdef-0123-456789abcdef",
      "centroid_vector": [-0.234, 0.567, -0.123, ...]
    },
    {
      "cluster_id": "c3333333-89ab-cdef-0123-456789abcdef",
      "user_count": 1,
      "user_pct": 0.011,
      "label_summary": "This is a completely unique viewpoint",
      "label_summary_id": "s3333333-89ab-cdef-0123-456789abcdef",
      "display_group_id": "d3333333-89ab-cdef-0123-456789abcdef",
      "centroid_vector": [0.789, -0.123, 0.456, ...]
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `round_id` | UUID | Round ID from request |
| `cluster_count` | Integer | Number of thought spaces created |
| `total_participants` | Integer | Total participants assigned (100% coverage guarantee) |
| `percentage_sum` | Float | Sum of user_pct (should equal 1.0 ± 0.0001) |
| `clusters` | Array | Array of thought space objects (see below) |

#### Cluster Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `cluster_id` | UUID | Unique identifier for thought space |
| `user_count` | Integer | Number of participants in cluster |
| `user_pct` | Float | Percentage of participants (0.0 to 1.0) |
| `label_summary` | String | Medoid label (summary text closest to centroid) |
| `label_summary_id` | UUID | ID of medoid summary |
| `display_group_id` | UUID | Alignment group ID (for visual continuity) |
| `centroid_vector` | Array | 384-dim centroid vector (for Sankey flow calculation) |

#### With Members

Add `include_members=true` to include member details:

```bash
curl "http://localhost:8000/api/v1/clusters?round_id=r1234567-89ab-cdef-0123-456789abcdef&include_members=true" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response includes `members` array in each cluster:

```json
{
  "cluster_id": "c1111111-89ab-cdef-0123-456789abcdef",
  "user_count": 32,
  "user_pct": 0.337,
  "label_summary": "We need to reduce costs by 20%",
  "members": [
    {
      "summary_id": "s4444444-89ab-cdef-0123-456789abcdef",
      "user_id": "u4444444-89ab-cdef-0123-456789abcdef",
      "summary_text": "We need to reduce costs by 20%"
    },
    {
      "summary_id": "s5555555-89ab-cdef-0123-456789abcdef",
      "user_id": "u5555555-89ab-cdef-0123-456789abcdef",
      "summary_text": "Budget cuts are essential for survival"
    }
  ]
}
```

---

### 3. Get Specific Cluster

**Endpoint**: `GET /clusters/{cluster_id}`

Returns detailed information about a specific thought space.

#### Request

```bash
curl http://localhost:8000/api/v1/clusters/c1111111-89ab-cdef-0123-456789abcdef \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Success Response (200 OK)

```json
{
  "cluster_id": "c1111111-89ab-cdef-0123-456789abcdef",
  "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
  "user_count": 32,
  "user_pct": 0.337,
  "label_summary": "We need to reduce costs by 20%",
  "label_summary_id": "s1111111-89ab-cdef-0123-456789abcdef",
  "display_group_id": "d1111111-89ab-cdef-0123-456789abcdef",
  "centroid_vector": [0.123, -0.456, 0.789, ...],
  "members": [
    {
      "summary_id": "s4444444-89ab-cdef-0123-456789abcdef",
      "user_id": "u4444444-89ab-cdef-0123-456789abcdef",
      "summary_text": "We need to reduce costs by 20%"
    },
    {
      "summary_id": "s5555555-89ab-cdef-0123-456789abcdef",
      "user_id": "u5555555-89ab-cdef-0123-456789abcdef",
      "summary_text": "Budget cuts are essential"
    }
  ]
}
```

---

## Alignment Endpoints

### 4. Trigger Cross-Round Alignment

**Endpoint**: `POST /alignments/trigger`

Aligns semantically similar clusters across adjacent rounds for visual continuity.

#### Request

```bash
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
    "round_r": 1,
    "round_r1": 2,
    "similarity_threshold": 0.7
  }'
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `discussion_id` | UUID | Yes | Discussion context |
| `round_r` | Integer | Yes | Earlier round number |
| `round_r1` | Integer | Yes | Later round number (must be r+1) |
| `similarity_threshold` | Float | No | Cosine similarity threshold (default: 0.7, range: 0.0-1.0) |

#### Success Response (202 Accepted)

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

#### Error Responses

**400 Bad Request** - Non-adjacent rounds:
```json
{
  "error": "INVALID_ROUNDS",
  "message": "Rounds must be adjacent (r1 == r + 1)",
  "details": {
    "round_r": 1,
    "round_r1": 3
  }
}
```

**400 Bad Request** - Rounds not clustered:
```json
{
  "error": "NOT_CLUSTERED",
  "message": "Both rounds must be clustered before alignment",
  "details": {
    "round_r_clustered": true,
    "round_r1_clustered": false
  }
}
```

#### Workflow

1. Load centroid vectors for rounds r and r+1
2. Compute cosine similarity matrix (all cluster pairs)
3. Run greedy matching algorithm
4. Filter matches by similarity_threshold
5. Assign display_group_ids to aligned clusters
6. Persist alignment maps to database
7. **IMPORTANT**: Do NOT modify cluster membership or counts
8. Publish `alignment.completed` event to Redis

---

### 5. Get Alignments for Discussion

**Endpoint**: `GET /alignments`

Returns alignment maps showing how clusters connect across rounds.

#### Request

```bash
curl "http://localhost:8000/api/v1/alignments?discussion_id=d1234567-89ab-cdef-0123-456789abcdef&round_r=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `discussion_id` | UUID | Yes | Discussion to fetch alignments for |
| `round_r` | Integer | No | Filter by earlier round (optional) |

#### Success Response (200 OK)

```json
{
  "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
  "alignment_count": 6,
  "alignments": [
    {
      "alignment_id": "a1111111-89ab-cdef-0123-456789abcdef",
      "round_r": 1,
      "round_r1": 2,
      "cluster_r_id": "c1111111-89ab-cdef-0123-456789abcdef",
      "cluster_r1_id": "c2222222-89ab-cdef-0123-456789abcdef",
      "similarity_score": 0.82,
      "display_group_id": "d1111111-89ab-cdef-0123-456789abcdef",
      "alignment_type": "1-to-1"
    },
    {
      "alignment_id": "a2222222-89ab-cdef-0123-456789abcdef",
      "round_r": 1,
      "round_r1": 2,
      "cluster_r_id": "c3333333-89ab-cdef-0123-456789abcdef",
      "cluster_r1_id": "c4444444-89ab-cdef-0123-456789abcdef",
      "similarity_score": 0.75,
      "display_group_id": "d2222222-89ab-cdef-0123-456789abcdef",
      "alignment_type": "1-to-1"
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `alignment_id` | UUID | Unique alignment identifier |
| `round_r` | Integer | Earlier round |
| `round_r1` | Integer | Later round |
| `cluster_r_id` | UUID | Cluster in round r |
| `cluster_r1_id` | UUID | Cluster in round r+1 |
| `similarity_score` | Float | Cosine similarity (0.0-1.0) |
| `display_group_id` | UUID | Visual grouping ID (same for aligned clusters) |
| `alignment_type` | String | Match type: "1-to-1", "1-to-many", "many-to-1" |

---

## Data Model

### Embedding (384-dim SBERT)

```
{
  "summary_id": UUID,
  "embedding_vector": [float x 384],
  "model_version": "all-MiniLM-L6-v2",
  "created_at": ISO8601
}
```

### Cluster (Thought Space)

```
{
  "cluster_id": UUID,
  "round_id": UUID,
  "user_count": Integer,
  "user_pct": Float (0.0-1.0),
  "label_summary_id": UUID,
  "centroid_vector": [float x 384],
  "display_group_id": UUID (nullable, set by alignment),
  "created_at": ISO8601
}
```

### ClusterMember (Participant Assignment)

```
{
  "membership_id": UUID,
  "cluster_id": UUID,
  "summary_id": UUID,
  "user_id": UUID
}
```

### AlignmentMap (Cross-Round Link)

```
{
  "alignment_id": UUID,
  "round_r": Integer,
  "round_r1": Integer,
  "cluster_r_id": UUID,
  "cluster_r1_id": UUID,
  "similarity_score": Float (0.0-1.0),
  "display_group_id": UUID,
  "alignment_type": String,
  "created_at": ISO8601
}
```

---

## Event Flows

### Flow 1: Clustering Workflow (Spec 3 → Spec 4)

```
1. Spec 3 publishes: summaries.approved_for_round
   {
     "round_id": "r123",
     "summary_count": 95,
     "all_approved": true
   }

2. Spec 4 subscribes to event
   POST /clusters/trigger automatically triggered (or manual)

3. Clustering workflow executes:
   - Fetch 95 approved summaries
   - Generate embeddings (95 x 384)
   - Run HDBSCAN
   - Convert outliers to singletons
   - Compute centroids
   - Select medoid labels
   - Persist to database

4. Spec 4 publishes: clustering.completed
   {
     "round_id": "r123",
     "cluster_count": 8,
     "total_participants": 95,
     "singleton_count": 2,
     "processing_time_ms": 3600
   }
```

### Flow 2: Alignment Workflow (Spec 4 → Spec 4)

```
1. Both rounds clustered (r=1, r+1=2)

2. Manual trigger: POST /alignments/trigger
   {
     "discussion_id": "d123",
     "round_r": 1,
     "round_r1": 2
   }

3. Alignment workflow executes:
   - Load centroids (round 1 and 2)
   - Compute similarity matrix (8 x 7 = 56 pairs)
   - Greedy matching (best matches first)
   - Filter by similarity_threshold (0.7)
   - Assign display_group_ids
   - Persist alignment maps
   - **CRITICAL**: Do NOT modify cluster membership

4. Spec 4 publishes: alignment.completed
   {
     "discussion_id": "d123",
     "round_r": 1,
     "round_r1": 2,
     "match_count": 6,
     "display_group_count": 6
   }
```

### Flow 3: Integration with Spec 5 (Sankey Construction)

```
1. Spec 5 subscribes to clustering.completed
   Can now fetch clusters via GET /clusters?round_id=r123

2. Spec 5 receives alignment.completed
   Uses display_group_ids for visual flow continuity

3. Spec 5 builds Sankey diagram:
   - Left column (round 1): clusters with display_group colors
   - Right column (round 2): clusters with same colors
   - Flow paths: aligned clusters → continuous colors
   - Flow width: proportional to user_pct
```

---

## Usage Examples

### Example 1: Basic Clustering

```bash
# Step 1: Trigger clustering
curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef"
  }'

# Response: job_id and status PROCESSING

# Step 2: Wait for completion (poll or use webhooks)
sleep 5

# Step 3: Fetch clusters
curl http://localhost:8000/api/v1/clusters \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef"
  }' | jq '.clusters[] | {cluster_id, user_count, user_pct, label_summary}'

# Output:
# {
#   "cluster_id": "c1111111-89ab-cdef-0123-456789abcdef",
#   "user_count": 32,
#   "user_pct": 0.337,
#   "label_summary": "We need to reduce costs by 20%"
# }
```

### Example 2: Minority Preservation Test

```bash
# Cluster 20 summaries: 18 majority + 2 minority
curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"round_id": "r_minority_test"}'

# Fetch clusters
curl "http://localhost:8000/api/v1/clusters?round_id=r_minority_test" \
  -H "Authorization: Bearer $TOKEN" | jq '.clusters | length'

# Output: 2 (NOT 1 - minority preserved)
```

### Example 3: Cross-Round Alignment

```bash
# Round 1 clustered with 8 clusters
# Round 2 clustered with 7 clusters

# Trigger alignment
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "discussion_id": "d_align_test",
    "round_r": 1,
    "round_r1": 2,
    "similarity_threshold": 0.7
  }'

# Fetch alignments
curl "http://localhost:8000/api/v1/alignments?discussion_id=d_align_test&round_r=1" \
  -H "Authorization: Bearer $TOKEN" | jq '.alignments[] | {cluster_r_id, cluster_r1_id, similarity_score, display_group_id}'

# Output:
# {
#   "cluster_r_id": "c1111111-...",
#   "cluster_r1_id": "c2222222-...",
#   "similarity_score": 0.82,
#   "display_group_id": "d1111111-..."
# }
```

---

## Error Handling

### HTTP Status Codes

| Status | Meaning | Example |
|--------|---------|---------|
| 200 | OK - Request succeeded | GET /clusters successful |
| 202 | Accepted - Async processing started | POST /clusters/trigger accepted |
| 400 | Bad Request - Invalid input | Missing round_id, non-adjacent rounds |
| 401 | Unauthorized - Invalid token | Bearer token expired |
| 403 | Forbidden - Insufficient permissions | User lacks required role |
| 409 | Conflict - State conflict | Clustering already exists |
| 500 | Server Error - Unexpected error | Database connection failure |

### Error Response Format

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "specific information"
  }
}
```

### Common Errors

**HDBSCAN creates no clusters**:
- All summaries marked as noise (label=-1)
- Each converted to singleton cluster
- Result: 95 clusters, all user_count=1

**Percentages don't sum to 1.0**:
- Floating-point rounding error
- Last cluster user_pct adjusted to ensure sum=1.0
- Guaranteed: abs(sum(user_pct) - 1.0) < 0.0001

**No alignment matches found**:
- Similarity threshold too high
- Lower from 0.7 to 0.6 or 0.5
- Or accept: clusters genuinely different across rounds

---

## Performance Characteristics

| Operation | Time | Participants | Notes |
|-----------|------|--------------|-------|
| Embedding generation | ~3s | 100 | CPU/GPU dependent |
| HDBSCAN clustering | ~0.5s | 100 | Linear scaling |
| Centroid computation | ~0.1s | 100 | O(n*m) where m=384 |
| Medoid selection | ~0.2s | 100 | O(n*m) per cluster |
| Alignment (similarity + greedy) | ~0.2s | 100 clusters | O(n²) similarity matrix |
| **Total clustering workflow** | **< 5s** | **100** | SLA: SC-001 |

---

## Integration Checklist

- [ ] JWT authentication configured
- [ ] Redis event bus connected
- [ ] PostgreSQL with pgvector extension ready
- [ ] SBERT model cached locally (~80 MB)
- [ ] Test clustering with 10 approved summaries
- [ ] Test minority preservation (18+2 split)
- [ ] Test outlier handling (8 tight + 2 outliers)
- [ ] Test cross-round alignment
- [ ] Verify percentages sum to 1.0
- [ ] Verify 100% participant coverage
- [ ] Monitor clustering latency
- [ ] Log clustering events

---

## Support & Resources

- **API Spec**: `specs/004-clustering-alignment/contracts/api-spec.yaml`
- **Event Schema**: `specs/004-clustering-alignment/contracts/events.yaml`
- **Data Model**: `specs/004-clustering-alignment/data-model.md`
- **Research**: `specs/004-clustering-alignment/research.md`
- **Quickstart**: `specs/004-clustering-alignment/quickstart.md`

**Questions?** Open an issue or contact the OpenDiscuss team.
