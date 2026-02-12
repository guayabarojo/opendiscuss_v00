# Cross-Round Alignment: Quick Reference Guide

**Feature**: User Story 4 - Cross-Round Alignment for Visual Continuity
**Status**: ✅ Complete (T049-T061)

## Quick Start

### 1. Trigger Alignment (POST /api/v1/alignments/trigger)

```bash
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
    "round_r": 1,
    "round_r1": 2,
    "similarity_threshold": 0.7,
    "force_realign": false
  }'
```

**Response (202 Accepted):**
```json
{
  "job_id": "uuid",
  "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
  "round_r": 1,
  "round_r1": 2,
  "status": "COMPLETED",
  "estimated_completion_ms": 350
}
```

### 2. Retrieve Alignments (GET /api/v1/alignments)

```bash
# Get all alignments for a discussion
curl -X GET "http://localhost:8000/api/v1/alignments?discussion_id=d1234567-89ab-cdef-0123-456789abcdef" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Filter by specific round pair
curl -X GET "http://localhost:8000/api/v1/alignments?discussion_id=d1234567-89ab-cdef-0123-456789abcdef&round_r=1" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK):**
```json
{
  "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
  "alignment_count": 5,
  "alignments": [
    {
      "alignment_id": "a1111111-89ab-cdef-0123-456789abcdef",
      "round_r": 1,
      "round_r1": 2,
      "cluster_r_id": "c1234567-89ab-cdef-0123-456789abcdef",
      "cluster_r1_id": "c2345678-89ab-cdef-0123-456789abcdef",
      "similarity_score": 0.85,
      "display_group_id": "d1234567-89ab-cdef-0123-456789abcdef",
      "alignment_type": "1-to-1"
    }
  ]
}
```

## Key Concepts

### What is Alignment?
- **Aligns** semantically similar thought spaces (clusters) across adjacent rounds
- **Assigns** display group IDs for visual continuity in Sankey diagrams
- **Does NOT** change cluster membership or flow calculations
- **Presentation-only** - affects colors and labels, not data

### Display Groups
- Clusters with same `display_group_id` are **visually grouped**
- Used for color continuity across rounds in Sankey visualization
- Supports:
  - **1-to-1**: One cluster continues to one cluster (continuity)
  - **1-to-many**: One cluster splits into multiple (split)
  - **many-to-1**: Multiple clusters merge into one (merge)

### Similarity Threshold
- **Default**: 0.7 (configurable via `ALIGN_THRESHOLD` env var)
- **Range**: 0.0 to 1.0
- **Meaning**: Minimum cosine similarity for clusters to be aligned
- Clusters with similarity < threshold are NOT aligned (independent display groups)

## Error Codes

### 400 NON_ADJACENT_ROUNDS
**Cause**: Rounds are not adjacent (r+1 required)
```json
{
  "error": "NON_ADJACENT_ROUNDS",
  "message": "Alignment requires adjacent rounds (r+1). Provided: r=1, r+1=3",
  "details": {
    "round_r": 1,
    "round_r1": 3
  }
}
```
**Fix**: Use adjacent rounds (e.g., 1→2, 2→3)

### 400 ROUNDS_NOT_CLUSTERED
**Cause**: One or both rounds not clustered yet
```json
{
  "error": "ROUNDS_NOT_CLUSTERED",
  "message": "Both rounds must be clustered before alignment.",
  "details": {
    "round_r_clustered": true,
    "round_r1_clustered": false
  }
}
```
**Fix**: Run clustering first (POST /api/v1/clusters/trigger)

### 404 ROUNDS_NOT_FOUND
**Cause**: Rounds don't exist in discussion
```json
{
  "error": "ROUNDS_NOT_FOUND",
  "message": "One or both rounds not found in discussion",
  "details": {
    "discussion_id": "uuid",
    "round_r": 1,
    "round_r1": 2
  }
}
```
**Fix**: Verify discussion_id and round numbers

### 409 ALIGNMENT_EXISTS
**Cause**: Alignment already computed for this round pair
```json
{
  "error": "ALIGNMENT_EXISTS",
  "message": "Alignment already computed for these rounds. Use force_realign=true to override.",
  "details": {
    "discussion_id": "uuid",
    "round_r": 1,
    "round_r1": 2,
    "alignment_count": 5
  }
}
```
**Fix**: Use `force_realign: true` to recompute

### 500 ALIGNMENT_INVARIANCE_VIOLATED
**Cause**: Alignment changed cluster membership (should never happen)
```json
{
  "error": "ALIGNMENT_INVARIANCE_VIOLATED",
  "message": "Alignment changed cluster membership (invariant violation)"
}
```
**Fix**: This is a critical bug - report immediately

## Configuration

### Environment Variables

```bash
# .env file or environment
ALIGN_THRESHOLD=0.7              # Minimum similarity for alignment (0.0-1.0)
```

### Python Config

```python
from src.config import settings

# Get current threshold
threshold = settings.align_threshold  # Default: 0.7

# Use in API call
response = requests.post(
    "http://localhost:8000/api/v1/alignments/trigger",
    json={
        "discussion_id": "uuid",
        "round_r": 1,
        "round_r1": 2,
        "similarity_threshold": settings.align_threshold
    }
)
```

## Python Usage

### Programmatic Alignment

```python
from uuid import UUID
from src.services.alignment_service import (
    compute_similarity_matrix,
    greedy_matching,
    assign_display_groups,
)
from src.services.centroid_service import load_centroids

# Load centroids
round_1_id = UUID("...")
round_2_id = UUID("...")
centroids_map = await load_centroids(session, [round_1_id, round_2_id])

# Compute similarity
similarity_matrix = await compute_similarity_matrix(
    centroids_map[round_1_id],
    centroids_map[round_2_id]
)

# Greedy matching
matches = await greedy_matching(similarity_matrix, threshold=0.7)

# Assign display groups
display_groups = await assign_display_groups(matches)

print(f"Found {len(matches)} alignments")
print(f"Assigned {len(set(display_groups.values()))} display groups")
```

## Database Queries

### Check Alignment Status

```sql
-- Count alignments for a discussion
SELECT COUNT(*) as alignment_count
FROM alignment_maps
WHERE discussion_id = 'uuid';

-- Get alignment details
SELECT
    alignment_id,
    round_r,
    round_r1,
    cluster_r_id,
    cluster_r1_id,
    similarity_score,
    display_group_id
FROM alignment_maps
WHERE discussion_id = 'uuid'
ORDER BY round_r, round_r1, similarity_score DESC;
```

### Verify Display Groups

```sql
-- Get clusters with same display group
SELECT
    cluster_id,
    round_id,
    display_group_id,
    label_summary
FROM clusters
WHERE display_group_id = 'uuid';
```

### Check Membership Invariance

```sql
-- Verify member counts unchanged
SELECT
    c.cluster_id,
    c.user_count as stored_count,
    COUNT(cm.summary_id) as actual_count
FROM clusters c
LEFT JOIN cluster_members cm ON c.cluster_id = cm.cluster_id
WHERE c.round_id IN ('round_1_uuid', 'round_2_uuid')
GROUP BY c.cluster_id, c.user_count
HAVING c.user_count != COUNT(cm.summary_id);
-- Should return 0 rows (no discrepancies)
```

## Testing

### Run Integration Tests

```bash
# All alignment tests
pytest backend/tests/integration/test_alignment_accuracy.py -v

# Specific test
pytest backend/tests/integration/test_alignment_accuracy.py::test_alignment_does_not_change_membership -v

# With output
pytest backend/tests/integration/test_alignment_accuracy.py -v -s
```

### Verify Implementation

```bash
cd backend
python3 verify_alignment.py
```

**Expected Output:**
```
✓ Centroid service implementation
✓ Alignment service implementation
✓ Alignment API routes
✓ Alignment integration test
✓ All functions present
✓ ALL CHECKS PASSED - Implementation complete!
```

## Common Workflows

### Workflow 1: Align Two Rounds

1. **Cluster Round 1**
   ```bash
   POST /api/v1/clusters/trigger
   {"round_id": "round_1_uuid"}
   ```

2. **Cluster Round 2**
   ```bash
   POST /api/v1/clusters/trigger
   {"round_id": "round_2_uuid"}
   ```

3. **Align Rounds 1→2**
   ```bash
   POST /api/v1/alignments/trigger
   {
     "discussion_id": "discussion_uuid",
     "round_r": 1,
     "round_r1": 2,
     "similarity_threshold": 0.7
   }
   ```

4. **Retrieve Alignments**
   ```bash
   GET /api/v1/alignments?discussion_id=discussion_uuid
   ```

### Workflow 2: Multi-Round Discussion

```bash
# Cluster all rounds first
for round_id in round_1 round_2 round_3; do
  curl -X POST http://localhost:8000/api/v1/clusters/trigger \
    -d "{\"round_id\": \"$round_id\"}"
done

# Align adjacent pairs
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -d '{"discussion_id": "uuid", "round_r": 1, "round_r1": 2}'

curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -d '{"discussion_id": "uuid", "round_r": 2, "round_r1": 3}'

# Get all alignments
curl -X GET "http://localhost:8000/api/v1/alignments?discussion_id=uuid"
```

### Workflow 3: Re-align with Different Threshold

```bash
# Force re-alignment with lower threshold
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -d '{
    "discussion_id": "uuid",
    "round_r": 1,
    "round_r1": 2,
    "similarity_threshold": 0.6,
    "force_realign": true
  }'
```

## Events

### Listen for Alignment Completion

```python
from src.events.bus import event_bus

@event_bus.on("alignment.completed")
async def handle_alignment_completed(payload):
    print(f"Alignment completed for discussion {payload['discussion_id']}")
    print(f"Rounds {payload['round_r']} → {payload['round_r1']}")
    print(f"Matches: {payload['match_count']}")
    print(f"Display groups: {payload['display_group_count']}")
    print(f"Processing time: {payload['processing_time_ms']}ms")
```

**Event Payload:**
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

## Best Practices

### 1. Always Cluster First
- Run clustering (POST /api/v1/clusters/trigger) before alignment
- Alignment requires both rounds to be clustered
- Check clustering status before triggering alignment

### 2. Use Default Threshold First
- Start with default threshold (0.7)
- Adjust only if needed based on domain
- Higher threshold = more conservative alignment (fewer matches)
- Lower threshold = more liberal alignment (more matches)

### 3. Verify Invariance
- Check member counts before and after alignment
- Alignment should NEVER change cluster membership
- If invariance violated, rollback and investigate

### 4. Handle Errors Gracefully
- Check for adjacent rounds (r+1 requirement)
- Verify rounds are clustered
- Handle 409 conflict (already aligned) appropriately
- Retry with force_realign if needed

### 5. Monitor Performance
- Alignment should complete in < 500ms for typical discussions
- Check processing_time_ms in response
- For large discussions (100+ clusters), consider async processing

## Troubleshooting

### Problem: "Rounds not adjacent" error
**Solution**: Ensure round_r1 = round_r + 1
```python
round_r1 = round_r + 1  # Must be adjacent
```

### Problem: "Rounds not clustered" error
**Solution**: Run clustering first
```bash
POST /api/v1/clusters/trigger
{"round_id": "round_uuid"}
```

### Problem: No alignments found
**Solution**: Check similarity threshold
- Lower threshold (e.g., 0.6 instead of 0.7)
- Verify clusters are semantically related
- Check centroid computation

### Problem: Too many alignments
**Solution**: Increase threshold
- Higher threshold (e.g., 0.8 instead of 0.7)
- More conservative matching

### Problem: Alignment takes too long
**Solution**: Check cluster counts
- Alignment is O(n × m) where n, m = cluster counts
- For 100+ clusters, consider async processing
- Check database indexes

## File Locations

```
backend/
├── src/
│   ├── api/routes/
│   │   └── alignment.py              # API endpoints
│   ├── services/
│   │   ├── alignment_service.py      # Alignment logic
│   │   └── centroid_service.py       # Centroid utilities
│   └── config.py                     # Configuration (ALIGN_THRESHOLD)
└── tests/integration/
    └── test_alignment_accuracy.py    # Integration tests
```

## References

- **Spec**: `/specs/004-clustering-alignment/spec.md`
- **Tasks**: `/specs/004-clustering-alignment/tasks.md` (T049-T061)
- **API Contract**: `/specs/004-clustering-alignment/contracts/api-spec.yaml`
- **Implementation Summary**: `/USER_STORY_4_IMPLEMENTATION_SUMMARY.md`

## Support

For issues or questions:
1. Check error codes and solutions above
2. Review implementation summary
3. Run verification script: `python3 backend/verify_alignment.py`
4. Check integration tests: `pytest backend/tests/integration/test_alignment_accuracy.py -v`
5. Review logs for detailed error messages

---

**Status**: ✅ Complete - Ready for production use
**Last Updated**: 2026-02-02
