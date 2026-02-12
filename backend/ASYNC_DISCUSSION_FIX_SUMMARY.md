# Async Discussion Flow - Fix Summary

## Issue
Sankey diagrams were being generated with 0 edges even though participant movements existed in the database.

## Root Cause
The `compute_user_intersection()` function in `backend/src/services/dropout_handler.py` was extracting user_ids from cluster objects using attributes (`.members` or `.member_ids`) that don't exist on pseudo-cluster objects created from ThoughtSpace entries. This caused an empty set to be returned, filtering out all movements.

## Fix
**File**: `backend/src/services/dropout_handler.py`
**Lines**: 63-78

Changed from extracting user_ids from cluster object attributes to using `get_participant_assignments()`:

```python
# BEFORE: Tried to extract from cluster.members or cluster.member_ids (didn't exist)
from_clusters = await cluster_client.get_clusters_for_round(from_round_id)
for cluster in from_clusters:
    if hasattr(cluster, 'members'):
        from_users.update(member.user_id for member in cluster.members)

# AFTER: Use get_participant_assignments() which works with both tables
from_assignments = await cluster_client.get_participant_assignments(from_round_id)
from_users = set(from_assignments.keys())
```

## Verification

### Backend E2E Flow
- ✅ Discussion creation (ASYNCHRONOUS mode)
- ✅ Round 1: 3 participants → SBERT embeddings → HDBSCAN clustering → 1 thought space
- ✅ Round 2: 3 participants → SBERT embeddings → HDBSCAN clustering → 1 thought space
- ✅ Movement tracking: All 3 participants moved from Round 1 cluster to Round 2 cluster
- ✅ Edge creation: 1 edge with user_count=3 generated
- ✅ Sankey diagram saved to database

### Database State
```sql
-- ThoughtSpaces (clusters)
Round 1: cluster_id = 373a0008-e9c9-484d-aa43-08b6ac99e80c (3 members)
Round 2: cluster_id = 3b7141f9-2f30-4966-940d-ebc2c7c3dcd4 (3 members)

-- Participant Movements
User d4f6117d-... : 373a0008-... → 3b7141f9-...
User c18e7a62-... : 373a0008-... → 3b7141f9-...
User f0a3f447-... : 373a0008-... → 3b7141f9-...

-- Sankey Graph
Columns: 2
Nodes: 2 (1 per column)
Edges: 1 (373a0008-... → 3b7141f9-..., user_count=3)
```

### Playwright Tests
- ✅ Discussion Live page: Shows COMPLETED status with round information
- ✅ Sankey Diagram page: Loads successfully
- ⚠️ Report page: Frontend FlowRenderer component has d3-sankey error (separate frontend issue)

## Related Files Modified
1. `backend/src/services/dropout_handler.py` - Fixed compute_user_intersection()
2. `backend/src/services/cluster_api_client.py` - Already had correct get_participant_assignments()
3. `backend/src/models/sankey_graph_db.py` - Renamed metadata → graph_metadata (SQLAlchemy reserved word)
4. `backend/src/services/node_builder.py` - Handle both label_summary and medoid_summary attributes

## Discussion ID
`0df96a6f-f005-470c-b7e4-bebe3e2884be`

## View URLs
- Live: http://localhost:3000/discussions/0df96a6f-f005-470c-b7e4-bebe3e2884be/live
- Sankey: http://localhost:3000/discussions/0df96a6f-f005-470c-b7e4-bebe3e2884be/sankey
- Report: http://localhost:3000/discussions/0df96a6f-f005-470c-b7e4-bebe3e2884be/report

## Next Steps
Frontend Report page has a separate issue with d3-sankey FlowRenderer component that needs investigation. The backend is generating correct Sankey data with edges.
