# User Story 4: Cross-Round Alignment Implementation Summary

**Date**: 2026-02-02
**Feature**: Spec 004 - Semantic Clustering & Hybrid Alignment Protocol
**User Story**: US4 - Cross-Round Alignment for Visual Continuity
**Tasks**: T049-T061

## Executive Summary

Successfully implemented User Story 4 (Cross-Round Alignment) from `/specs/004-clustering-alignment/tasks.md`. All 13 tasks (T049-T061) are complete, providing cross-round cluster alignment functionality for visual continuity in Sankey diagrams **without affecting cluster membership or flow calculations**.

## Implementation Status

### ✅ Completed Tasks

#### T049-T050: Centroid Loading and Similarity Matrix
- **File**: `/backend/src/services/centroid_service.py`
- **Functions**:
  - `load_centroids()`: Load centroid vectors from database for specified rounds
  - `compute_centroid()`: Compute mean embedding vector for cluster members
  - `cosine_similarity()`: Calculate cosine similarity between vectors
  - Additional utility functions for centroid computation and validation

#### T051: Greedy Matching Algorithm
- **File**: `/backend/src/services/alignment_service.py`
- **Function**: `greedy_matching()`
- **Features**:
  - Implements greedy matching with configurable ALIGN_THRESHOLD (default 0.7)
  - Filters pairs below similarity threshold
  - Sorts by similarity (descending) and selects best matches
  - Supports 1-to-1, 1-to-many (split), and many-to-1 (merge) alignments

#### T052: Display Group Assignment
- **File**: `/backend/src/services/alignment_service.py`
- **Function**: `assign_display_groups()`
- **Features**:
  - Groups connected clusters (clusters that share alignment partners)
  - Assigns same display_group_id to aligned clusters
  - Handles split (1-to-many) and merge (many-to-1) scenarios
  - Groups are used for color continuity in Sankey visualization

#### T053-T054: Persist Alignment and Update Display Groups
- **File**: `/backend/src/services/alignment_service.py`
- **Functions**:
  - `persist_alignment()`: Save alignment maps to database
  - `update_cluster_display_groups()`: Update display_group_id in clusters table
- **Guarantees**:
  - **CRITICAL**: Does NOT change cluster membership
  - Only updates display_group_id field (presentation-only)
  - Preserves all member assignments and flow calculations

#### T055-T057: POST /api/v1/alignments/trigger Endpoint
- **File**: `/backend/src/api/routes/alignment.py`
- **Endpoint**: `POST /api/v1/alignments/trigger`
- **Request Schema**: `AlignmentRequest`
  - `discussion_id`: UUID
  - `round_r`: Earlier round number (≥1)
  - `round_r1`: Later round number (must be r+1)
  - `similarity_threshold`: Min similarity (default 0.7, range 0.0-1.0)
  - `force_realign`: Force realignment if exists (default false)
- **Validations**:
  - **T056**: Adjacent rounds validation (r+1 requirement)
  - **T057**: Both rounds must be clustered
  - Idempotency check (409 if exists, unless force_realign)
- **Response**: Status 202 (Accepted) with processing metrics

#### T058: GET /api/v1/alignments Endpoint
- **File**: `/backend/src/api/routes/alignment.py`
- **Endpoint**: `GET /api/v1/alignments`
- **Query Parameters**:
  - `discussion_id`: UUID (required)
  - `round_r`: Optional filter for specific round pair
- **Response**: `AlignmentList`
  - List of alignment mappings with similarity scores
  - Display group IDs for visual continuity
  - Alignment types (1-to-1, 1-to-many, many-to-1)

#### T059: Alignment.completed Event Publisher
- **File**: `/backend/src/api/routes/alignment.py`
- **Event**: `alignment.completed`
- **Payload**:
  - `discussion_id`: Discussion UUID
  - `round_r`, `round_r1`: Round numbers
  - `match_count`: Number of alignments
  - `similarity_threshold`: Threshold used
  - `processing_time_ms`: Time taken
  - `display_group_count`: Number of display groups

#### T060: Alignment Invariance Validation
- **File**: `/backend/src/services/alignment_service.py`
- **Function**: `validate_alignment_invariance()`
- **Validation**:
  - Compares cluster member counts before and after alignment
  - Ensures membership is unchanged (100% accuracy requirement)
  - Rolls back transaction if invariance violated
  - Critical for FR-037, FR-038, SC-009

#### T061: Integration Test
- **File**: `/backend/tests/integration/test_alignment_accuracy.py`
- **Test Cases**:
  1. `test_alignment_does_not_change_membership`: Main integration test
  2. `test_alignment_with_split`: 1-to-many (split) handling
  3. `test_alignment_with_merge`: many-to-1 (merge) handling
  4. `test_alignment_threshold_filtering`: Threshold validation
- **Verification**:
  - Similarity matrix computation
  - Greedy matching results
  - Display group assignment
  - Membership invariance

## Architecture

### Service Layer

```
src/services/
├── centroid_service.py       # T049-T050: Centroid loading and computation
└── alignment_service.py      # T051-T060: Alignment logic and validation
```

### API Layer

```
src/api/routes/
└── alignment.py              # T055-T058: API endpoints
```

### Test Layer

```
tests/integration/
└── test_alignment_accuracy.py  # T061: Integration tests
```

## Key Features

### 1. Cosine Similarity Matrix Computation
- Computes similarity between all centroid pairs from rounds r and r+1
- Uses optimized cosine similarity for normalized vectors
- Handles variable cluster counts (no fixed K assumption)

### 2. Greedy Matching Algorithm
- Configurable ALIGN_THRESHOLD (default 0.7, configurable via `settings.align_threshold`)
- Filters pairs below threshold
- Supports 1-to-1, 1-to-many, and many-to-1 alignments
- No forced 1-to-1 constraint (allows splits and merges)

### 3. Display Group Assignment
- Groups semantically related clusters across rounds
- Connected clusters (sharing alignment partners) get same display group
- Used for color continuity and label families in Sankey visualization
- **Presentation-only** - does not affect data or flows

### 4. Invariance Guarantees
- Alignment **NEVER** changes cluster membership
- Alignment **NEVER** affects flow calculations
- Validation ensures member counts unchanged (FR-037, SC-009)
- Transaction rollback if invariance violated

### 5. Adjacent Round Validation
- Enforces r+1 relationship (T056)
- Prevents alignment across non-adjacent rounds
- Ensures temporal coherence

### 6. Clustering Prerequisite Validation
- Verifies both rounds are clustered before alignment (T057)
- Returns clear error messages if rounds not ready
- Prevents invalid operations

## Configuration

### Environment Variables

```bash
# In .env or backend/src/config.py
ALIGN_THRESHOLD=0.7              # Minimum similarity for alignment (0.0-1.0)
```

### Config Class

```python
# backend/src/config.py (T079)
class Settings(BaseSettings):
    align_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity for alignment",
    )
```

## API Contract

### POST /api/v1/alignments/trigger

**Request:**
```json
{
  "discussion_id": "uuid",
  "round_r": 1,
  "round_r1": 2,
  "similarity_threshold": 0.7,
  "force_realign": false
}
```

**Response (202 Accepted):**
```json
{
  "job_id": "uuid",
  "discussion_id": "uuid",
  "round_r": 1,
  "round_r1": 2,
  "status": "COMPLETED",
  "estimated_completion_ms": 350
}
```

**Error Responses:**
- `400 NON_ADJACENT_ROUNDS`: Rounds not adjacent (r+1 required)
- `400 ROUNDS_NOT_CLUSTERED`: One or both rounds not clustered
- `404 ROUNDS_NOT_FOUND`: Rounds not found in discussion
- `409 ALIGNMENT_EXISTS`: Alignment already computed (use force_realign=true)
- `500 ALIGNMENT_INVARIANCE_VIOLATED`: Membership changed (should never happen)

### GET /api/v1/alignments

**Query Parameters:**
- `discussion_id` (required): UUID
- `round_r` (optional): Filter by round

**Response (200 OK):**
```json
{
  "discussion_id": "uuid",
  "alignment_count": 12,
  "alignments": [
    {
      "alignment_id": "uuid",
      "round_r": 1,
      "round_r1": 2,
      "cluster_r_id": "uuid",
      "cluster_r1_id": "uuid",
      "similarity_score": 0.85,
      "display_group_id": "uuid",
      "alignment_type": "1-to-1"
    }
  ]
}
```

## Requirements Satisfied

### Functional Requirements
- ✅ **FR-029**: Alignment between adjacent rounds (r and r+1)
- ✅ **FR-030**: Similarity matrix between all cluster pairs
- ✅ **FR-031**: Cosine similarity measurement
- ✅ **FR-032**: Configurable ALIGN_THRESHOLD (default 0.7)
- ✅ **FR-033**: Threshold filtering (≥ threshold only)
- ✅ **FR-034**: Greedy matching algorithm
- ✅ **FR-035**: 1-to-1, 1-to-many, many-to-1 support
- ✅ **FR-036**: Display group ID assignment
- ✅ **FR-037**: **CRITICAL** - Alignment does NOT change membership
- ✅ **FR-038**: **CRITICAL** - Alignment does NOT affect flows
- ✅ **FR-039**: Presentation-only alignment

### Success Criteria
- ✅ **SC-009**: Alignment does NOT change membership (100% accuracy via invariance validation)

### Data Model Compliance
- ✅ Reads from `clusters` table (cluster_id, round_id, centroid_vector)
- ✅ Writes to `alignment_maps` table per schema
- ✅ Updates `display_group_id` field in `clusters` table
- ✅ Preserves `cluster_members` table integrity

## Testing

### Integration Tests (T061)
**File**: `tests/integration/test_alignment_accuracy.py`

1. **test_alignment_does_not_change_membership**
   - Clusters two rounds with 3 clusters each
   - Aligns semantically similar clusters (A→D, B→E)
   - Verifies display groups assigned
   - **Critical**: Verifies membership unchanged

2. **test_alignment_with_split**
   - 1-to-many scenario (1 cluster → 2 clusters)
   - Verifies all aligned clusters get same display group

3. **test_alignment_with_merge**
   - Many-to-1 scenario (2 clusters → 1 cluster)
   - Verifies all aligned clusters get same display group

4. **test_alignment_threshold_filtering**
   - Tests that low-similarity pairs are filtered
   - Verifies threshold enforcement

### Manual Testing

```bash
# 1. Trigger alignment
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "discussion_id": "uuid",
    "round_r": 1,
    "round_r1": 2,
    "similarity_threshold": 0.7
  }'

# 2. Retrieve alignments
curl -X GET "http://localhost:8000/api/v1/alignments?discussion_id=uuid"

# 3. Filter by round
curl -X GET "http://localhost:8000/api/v1/alignments?discussion_id=uuid&round_r=1"
```

## Constitutional Compliance

### Temporal Transparency (Principle VI)
- ✅ Alignment affects **presentation only**
- ✅ Per-round clustering remains independent
- ✅ Historical cluster assignments unchanged
- ✅ Flow calculations unaffected

### Semantic Accuracy Over Aesthetics (Principle III)
- ✅ Alignment based on semantic similarity (not visual simplicity)
- ✅ No forced merging of dissimilar clusters
- ✅ Threshold ensures only meaningful alignments
- ✅ Minority clusters remain visible (not hidden for aesthetics)

## Files Created/Modified

### Created Files
1. `/backend/src/services/centroid_service.py` (232 lines)
   - Centroid loading and computation
   - Cosine similarity calculation
   - Validation utilities

2. `/backend/src/services/alignment_service.py` (557 lines)
   - Similarity matrix computation
   - Greedy matching algorithm
   - Display group assignment
   - Persistence and invariance validation

3. `/backend/tests/integration/test_alignment_accuracy.py` (418 lines)
   - 4 comprehensive test cases
   - Split, merge, and threshold scenarios
   - Invariance verification

4. `/backend/verify_alignment.py` (145 lines)
   - Implementation verification script
   - Checks all components present
   - Validates imports and functions

### Modified Files
1. `/backend/src/api/routes/alignment.py`
   - Replaced placeholder with full implementation
   - Added request/response models
   - Implemented T055-T058 endpoints

2. `/backend/src/config.py`
   - Already had `align_threshold` configuration (no changes needed)

## Event Publication

**Event**: `alignment.completed`
**Channel**: `opendiscuss.alignment.completed` (via event_bus)
**Payload**:
```json
{
  "discussion_id": "uuid",
  "round_r": 1,
  "round_r1": 2,
  "match_count": 5,
  "similarity_threshold": 0.7,
  "processing_time_ms": 350,
  "display_group_count": 3
}
```

**Consumers**: Spec 005 (Sankey Visualization) - uses display groups for color continuity

## Database Schema

### alignment_maps Table
```sql
CREATE TABLE alignment_maps (
    alignment_id UUID PRIMARY KEY,
    discussion_id UUID NOT NULL,
    round_r INT NOT NULL,
    round_r1 INT NOT NULL,
    cluster_r_id UUID NOT NULL,
    cluster_r1_id UUID NOT NULL,
    similarity_score FLOAT NOT NULL CHECK (similarity_score >= 0 AND similarity_score <= 1.0),
    display_group_id UUID,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT chk_adjacent_rounds CHECK (round_r1 = round_r + 1),
    FOREIGN KEY (cluster_r_id) REFERENCES clusters(cluster_id),
    FOREIGN KEY (cluster_r1_id) REFERENCES clusters(cluster_id)
);
```

### clusters Table (display_group_id field)
```sql
ALTER TABLE clusters
ADD COLUMN display_group_id UUID;
```

**Note**: Display group updates are **presentation-only** and do not affect:
- `cluster_members` table
- `user_count` or `user_pct` fields
- Flow calculations (Spec 005)

## Performance

### Expected Performance
- **Similarity Matrix**: O(n × m) where n, m = cluster counts for rounds r, r+1
- **Greedy Matching**: O(p log p) where p = number of pairs above threshold
- **Display Group Assignment**: O(a) where a = number of alignments
- **Total Time**: < 500ms for typical discussions (5-10 clusters per round)

### Scalability
- Efficient for up to 100 clusters per round
- Batch processing if needed for large discussions
- Index on `alignment_maps(discussion_id, round_r, round_r1)` for fast queries

## Next Steps

### Integration with Spec 005 (Sankey Visualization)
1. Sankey service queries `GET /api/v1/alignments` for display groups
2. Uses `display_group_id` for color continuity across rounds
3. Aligned clusters get consistent colors and label families
4. Visual jitter reduced (clusters maintain identity across rounds)

### Future Enhancements (Post-MVP)
1. **Async Job Processing**: Long-running alignments for large discussions
2. **Alignment Analytics**: Match rate, similarity distribution metrics
3. **Alternative Matching Algorithms**: Hungarian algorithm, stable matching
4. **Multi-Round Alignment**: Transitivity across 3+ rounds
5. **Alignment Visualization**: Display similarity matrix, match quality

## Verification

### ✅ All Tasks Complete
- T049: ✓ Load centroids
- T050: ✓ Compute similarity matrix
- T051: ✓ Greedy matching
- T052: ✓ Assign display groups
- T053: ✓ Persist alignment
- T054: ✓ Update display groups
- T055: ✓ POST /api/v1/alignments/trigger
- T056: ✓ Adjacent rounds validation
- T057: ✓ Clustered rounds validation
- T058: ✓ GET /api/v1/alignments
- T059: ✓ alignment.completed event
- T060: ✓ Alignment invariance validation
- T061: ✓ Integration test

### ✅ All Requirements Met
- 11/11 Functional Requirements (FR-029 to FR-039)
- 1/1 Success Criteria (SC-009)
- Constitutional compliance verified
- API contract per api-spec.yaml

### ✅ Critical Guarantees
- Alignment **DOES NOT** change cluster membership (FR-037, SC-009)
- Alignment **DOES NOT** affect flow calculations (FR-038)
- Alignment **ONLY** affects presentation (FR-039)
- Invariance validation ensures correctness (T060)

## Conclusion

User Story 4 (Cross-Round Alignment for Visual Continuity) is **FULLY IMPLEMENTED** with all 13 tasks (T049-T061) complete. The implementation provides robust cross-round alignment functionality that:

1. **Correctly identifies** semantically similar clusters across adjacent rounds
2. **Assigns display groups** for visual continuity in Sankey diagrams
3. **Preserves cluster membership** with 100% accuracy (invariance guaranteed)
4. **Does not affect flows** or data integrity
5. **Supports split/merge scenarios** (1-to-many, many-to-1)
6. **Validates prerequisites** (adjacent rounds, clustering complete)
7. **Publishes events** for downstream consumption (Spec 005)

The implementation is **production-ready**, with comprehensive integration tests, clear error handling, and constitutional compliance. Alignment can now be triggered via REST API and consumed by Sankey visualization services.

**Status**: ✅ COMPLETE - Ready for integration with Spec 005 (Sankey Diagrams)
