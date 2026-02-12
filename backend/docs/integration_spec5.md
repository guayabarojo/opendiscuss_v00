# Integration Guide: Spec 4 → Spec 5 (Clustering to Sankey Construction)

**Feature**: Semantic Clustering & Hybrid Alignment Protocol (Spec 004)
**Integration Point**: Spec 4 (Clustering) → Spec 5 (Sankey Diagram Construction)
**Date**: 2026-01-29

---

## Overview

Spec 4 publishes two events that Spec 5 (Sankey Construction) consumes to build visual diagrams representing how discussions evolve:

1. **`clustering.completed`**: Thought spaces are ready (when a round is clustered)
2. **`alignment.completed`**: Display groups are assigned (when rounds are aligned for visual continuity)

Spec 5 uses clusters + alignment data to create interactive Sankey diagrams showing participant flow across rounds.

### Integration Architecture

```
┌─────────────────────────────────┐
│  Spec 4                         │
│  Clustering & Alignment         │
│                                 │
│  - Clusters summaries           │
│  - Aligns cross-rounds          │
│  - Computes display groups      │
└──────────┬──────────┬───────────┘
           │          │
           │ Event:   │ Event:
           │ clustering.completed
           │          │ alignment.completed
           │          │
           ▼          ▼
┌──────────────────────────────────┐
│  Spec 5                          │
│  Sankey Construction             │
│                                  │
│  - Listens to events             │
│  - Fetches clusters via API      │
│  - Fetches alignments via API    │
│  - Builds Sankey columns & flows │
│  - Renders interactive diagram   │
└──────────────────────────────────┘
```

---

## Event 1: `clustering.completed`

Published when clustering finishes for a round.

### Event Payload

```json
{
  "event_id": "f2g3h4i5-5678-90ab-cdef-1234567890bc",
  "event_type": "clustering.completed",
  "timestamp": "2026-01-29T14:10:03.600Z",
  "data": {
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
    "cluster_count": 8,
    "total_participants": 95,
    "singleton_count": 2,
    "processing_time_ms": 3600,
    "completed_at": "2026-01-29T14:10:03.600Z"
  }
}
```

### Event Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | UUID | Unique event identifier (for idempotency) |
| `event_type` | String | Always "clustering.completed" |
| `timestamp` | ISO8601 | Event publication time (UTC) |
| `data.round_id` | UUID | Round that was clustered |
| `data.cluster_count` | Integer | Number of thought spaces created |
| `data.total_participants` | Integer | All participants assigned (100% coverage) |
| `data.singleton_count` | Integer | Number of 1-person clusters (outliers converted) |
| `data.processing_time_ms` | Integer | Time to complete clustering (for monitoring) |
| `data.completed_at` | ISO8601 | Clustering completion time |

### Usage in Spec 5

```python
# backend/src/services/sankey_service.py (hypothetical Spec 5)

import asyncio
import json
import redis
import httpx
from datetime import datetime

SPEC4_API_BASE = "http://localhost:8000/api/v1"

class SankeyService:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.pubsub = self.redis.pubsub()

    async def subscribe_to_clustering_events(self):
        """Subscribe to clustering.completed events from Spec 4."""
        channel = "opendiscuss.clustering.completed"
        self.pubsub.subscribe(channel)

        print(f"Spec 5: Subscribed to {channel}")

        for message in self.pubsub.listen():
            if message['type'] == 'message':
                event = json.loads(message['data'])

                if event.get('event_type') == 'clustering.completed':
                    await self._on_clustering_completed(event)

    async def _on_clustering_completed(self, event: dict):
        """Handler: Clustering complete, fetch clusters and build Sankey column."""
        round_id = event['data']['round_id']
        cluster_count = event['data']['cluster_count']
        total_participants = event['data']['total_participants']

        print(f"Spec 5: Clustering completed for round {round_id}")
        print(f"  - {cluster_count} thought spaces")
        print(f"  - {total_participants} participants")

        try:
            # Fetch clusters from Spec 4 API
            clusters = await self._fetch_clusters_from_spec4(round_id)

            # Build Sankey column for this round
            sankey_column = self._build_sankey_column(round_id, clusters)

            # Persist Sankey column
            self._save_sankey_column(sankey_column)

            print(f"Spec 5: Built Sankey column for round {round_id}")

        except Exception as e:
            print(f"Spec 5 ERROR: Failed to build Sankey for round {round_id}: {e}")

    async def _fetch_clusters_from_spec4(self, round_id: str):
        """Fetch clusters from Spec 4 API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SPEC4_API_BASE}/clusters",
                params={"round_id": round_id, "include_members": True},
                headers={"Authorization": f"Bearer {SPEC5_SERVICE_TOKEN}"}
            )

        if response.status_code != 200:
            raise Exception(f"Spec 4 API returned {response.status_code}")

        data = response.json()
        return data['clusters']

    def _build_sankey_column(self, round_id: str, clusters: list):
        """Build Sankey column from clusters."""
        sankey_column = {
            "round_id": round_id,
            "nodes": [],
            "total_width": sum(c['user_pct'] for c in clusters)
        }

        # Create nodes for each cluster
        for cluster in clusters:
            node = {
                "cluster_id": cluster['cluster_id'],
                "label": cluster['label_summary'],
                "value": cluster['user_pct'],  # Width proportional to percentage
                "participant_count": cluster['user_count'],
                "display_group_id": cluster['display_group_id'],
                "members": cluster.get('members', [])
            }
            sankey_column['nodes'].append(node)

        return sankey_column
```

---

## Event 2: `alignment.completed`

Published when cross-round alignment finishes (linking clusters across rounds).

### Event Payload

```json
{
  "event_id": "g3h4i5j6-5678-90ab-cdef-1234567890cd",
  "event_type": "alignment.completed",
  "timestamp": "2026-01-29T14:15:04.100Z",
  "data": {
    "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
    "round_r": 1,
    "round_r1": 2,
    "match_count": 6,
    "similarity_threshold": 0.7,
    "processing_time_ms": 500,
    "completed_at": "2026-01-29T14:15:04.100Z"
  }
}
```

### Event Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | UUID | Unique event identifier (for idempotency) |
| `event_type` | String | Always "alignment.completed" |
| `timestamp` | ISO8601 | Event publication time (UTC) |
| `data.discussion_id` | UUID | Discussion context |
| `data.round_r` | Integer | Earlier round number |
| `data.round_r1` | Integer | Later round number (r+1) |
| `data.match_count` | Integer | Number of cluster pairs aligned (≥ similarity threshold) |
| `data.similarity_threshold` | Float | Threshold used (e.g., 0.7) |
| `data.processing_time_ms` | Integer | Time to compute alignment |
| `data.completed_at` | ISO8601 | Alignment completion time |

### Usage in Spec 5

```python
# Continuing SankeyService...

async def subscribe_to_alignment_events(self):
    """Subscribe to alignment.completed events from Spec 4."""
    channel = "opendiscuss.alignment.completed"
    self.pubsub.subscribe(channel)

    print(f"Spec 5: Subscribed to {channel}")

    for message in self.pubsub.listen():
        if message['type'] == 'message':
            event = json.loads(message['data'])

            if event.get('event_type') == 'alignment.completed':
                await self._on_alignment_completed(event)

async def _on_alignment_completed(self, event: dict):
    """Handler: Alignment complete, update display groups for visual continuity."""
    discussion_id = event['data']['discussion_id']
    round_r = event['data']['round_r']
    round_r1 = event['data']['round_r1']
    match_count = event['data']['match_count']

    print(f"Spec 5: Alignment completed for {discussion_id}")
    print(f"  - Rounds {round_r} → {round_r1}")
    print(f"  - {match_count} cluster pairs aligned")

    try:
        # Fetch alignment maps from Spec 4 API
        alignments = await self._fetch_alignments_from_spec4(discussion_id, round_r)

        # Build display group mappings
        display_groups = self._build_display_group_mapping(alignments)

        # Update Sankey diagram with display groups (same color for aligned clusters)
        self._update_sankey_display_groups(round_r, round_r1, display_groups)

        print(f"Spec 5: Updated Sankey with display groups")

    except Exception as e:
        print(f"Spec 5 ERROR: Failed to update alignment for rounds {round_r} → {round_r1}: {e}")

async def _fetch_alignments_from_spec4(self, discussion_id: str, round_r: int):
    """Fetch alignment maps from Spec 4 API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SPEC4_API_BASE}/alignments",
            params={"discussion_id": discussion_id, "round_r": round_r},
            headers={"Authorization": f"Bearer {SPEC5_SERVICE_TOKEN}"}
        )

    if response.status_code != 200:
        raise Exception(f"Spec 4 API returned {response.status_code}")

    data = response.json()
    return data['alignments']

def _build_display_group_mapping(self, alignments: list) -> dict:
    """Build mapping of cluster_id → display_group_id."""
    display_groups = {}

    for alignment in alignments:
        cluster_r_id = alignment['cluster_r_id']
        cluster_r1_id = alignment['cluster_r1_id']
        display_group_id = alignment['display_group_id']

        # Both clusters get same display_group (same color)
        display_groups[cluster_r_id] = display_group_id
        display_groups[cluster_r1_id] = display_group_id

    return display_groups

def _update_sankey_display_groups(self, round_r: int, round_r1: int, display_groups: dict):
    """Update Sankey diagram with display groups for visual continuity."""
    # This connects round_r → round_r1 with colored flows
    # Clusters with same display_group_id get same color
    # Flow width = aligned cluster's user_pct

    for cluster_id, display_group_id in display_groups.items():
        # Update cluster display_group in Sankey model
        # Flow paths: cluster_r → cluster_r1 with display_group color
        pass
```

---

## Fetching Cluster Details from Spec 4

When Spec 5 receives `clustering.completed` event, it fetches full cluster details via HTTP API.

### GET /clusters - Full Response

```bash
curl "http://localhost:8000/api/v1/clusters?round_id=r1234567-89ab-cdef-0123-456789abcdef&include_members=true" \
  -H "Authorization: Bearer SERVICE_TOKEN"
```

Response:

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
      "centroid_vector": [0.123, -0.456, 0.789, ...],
      "members": [
        {
          "summary_id": "s4444444-89ab-cdef-0123-456789abcdef",
          "user_id": "u4444444-89ab-cdef-0123-456789abcdef",
          "summary_text": "We need to reduce costs by 20%"
        }
      ]
    }
  ]
}
```

### Parsing for Sankey

```python
def build_sankey_from_clusters(clusters_response: dict) -> dict:
    """Convert Spec 4 clusters into Sankey diagram structure."""

    sankey = {
        "round_id": clusters_response['round_id'],
        "columns": [],
        "flows": []
    }

    # Create nodes for each cluster
    for cluster in clusters_response['clusters']:
        node = {
            "id": cluster['cluster_id'],
            "label": cluster['label_summary'][:50] + "...",  # Truncate for UI
            "value": cluster['user_pct'],
            "count": cluster['user_count'],
            "percentage": f"{cluster['user_pct']*100:.1f}%",
            "color": get_color_from_display_group(cluster.get('display_group_id')),
            "details": {
                "centroid": cluster['centroid_vector'][:10],  # First 10 dims for preview
                "member_count": len(cluster.get('members', [])),
                "members": cluster.get('members', [])
            }
        }
        sankey['columns'].append(node)

    # Total width verification (should be 1.0)
    total_width = sum(node['value'] for node in sankey['columns'])
    assert abs(total_width - 1.0) < 0.0001, f"Width sum {total_width} ≠ 1.0"

    return sankey
```

---

## Fetching Alignment Details from Spec 4

When Spec 5 receives `alignment.completed` event, it fetches alignment maps via HTTP API.

### GET /alignments - Full Response

```bash
curl "http://localhost:8000/api/v1/alignments?discussion_id=d1234567-89ab-cdef-0123-456789abcdef&round_r=1" \
  -H "Authorization: Bearer SERVICE_TOKEN"
```

Response:

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

### Parsing for Sankey Flows

```python
def build_sankey_flows_from_alignments(alignments_response: dict, clusters_r: dict, clusters_r1: dict) -> list:
    """Convert Spec 4 alignments into Sankey flow connections."""

    flows = []

    for alignment in alignments_response['alignments']:
        # Get cluster details
        cluster_r = next(c for c in clusters_r['clusters'] if c['cluster_id'] == alignment['cluster_r_id'])
        cluster_r1 = next(c for c in clusters_r1['clusters'] if c['cluster_id'] == alignment['cluster_r1_id'])

        flow = {
            "source": alignment['cluster_r_id'],
            "target": alignment['cluster_r1_id'],
            "value": min(cluster_r['user_pct'], cluster_r['user_pct']),  # Use actual flow width
            "similarity": alignment['similarity_score'],
            "color": alignment['display_group_id'],  # Same color for aligned clusters
            "type": alignment['alignment_type'],
            "details": {
                "round_r": alignment['round_r'],
                "round_r1": alignment['round_r1'],
                "similarity_threshold_exceeded": alignment['similarity_score'] >= 0.7
            }
        }
        flows.append(flow)

    return flows
```

---

## Event Subscription Setup (Spec 5)

```python
# backend/src/api/main.py (Spec 5 hypothetical)

from fastapi import FastAPI
from src.services.sankey_service import SankeyService

app = FastAPI()
sankey_service = SankeyService()

@app.on_event("startup")
async def startup():
    """Subscribe to Spec 4 events on startup."""
    # Run both subscriptions in parallel
    asyncio.create_task(sankey_service.subscribe_to_clustering_events())
    asyncio.create_task(sankey_service.subscribe_to_alignment_events())

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    sankey_service.pubsub.unsubscribe()
```

---

## Event Flow Diagrams

### Flow 1: Single Round Clustering

```
Time  Spec 3              Spec 4                    Spec 5
─────────────────────────────────────────────────────────

      [Summaries
       Approved]
                 ├─ clustering.completed ────────>  [Fetches
                 │  - round_id                       clusters]
                 │  - cluster_count: 8
                 │  - total_participants: 95    [Builds
                 │                               Sankey
                 │                               column]
                 │
```

### Flow 2: Cross-Round Alignment

```
Time  Spec 4                        Spec 5
──────────────────────────────────────────
      [Round 1 clustered (8)]
      [Round 2 clustered (7)]

                 ├─ alignment.completed ──> [Fetches
                 │  - round_r: 1             alignments]
                 │  - round_r1: 2
                 │  - match_count: 6     [Updates
                 │                        display
                 │                        groups]
                 │
                 │                    [Renders
                 │                     Sankey
                 │                     with flows]
```

### Flow 3: Full Discussion Lifecycle

```
Time  Spec 3      Spec 4              Spec 5
────────────────────────────────────────────────────

Round 1:
        [Approve]──> [Cluster r1] ──> [Build column 1]
                          ↓
                    [publish: clustering.completed]

Round 2:
        [Approve]──> [Cluster r2] ──> [Build column 2]
                          ↓
                    [publish: clustering.completed]

                [Align r1→r2]
                     ↓
             [publish: alignment.completed]
                                    ──> [Connect
                                         flows r1→r2]

Result: Full Sankey diagram with 2 columns + flows
```

---

## Data Flow from Spec 4 to Spec 5

```
Spec 4 Processing                Spec 5 Consumption
─────────────────────────────────────────────────────

1. Clustering completes
   ├─ Round 1: 8 clusters
   ├─ Publish clustering.completed
   └─ Spec 5 event received
                                   ↓
                            2. Fetch /clusters?round_id=r1
                               ├─ Returns all 8 clusters
                               ├─ With members, medoid labels
                               └─ Display group IDs (if aligned)
                                   ↓
                            3. Build Sankey column 1
                               ├─ 8 nodes
                               ├─ Width = user_pct
                               └─ Color = display_group_id

2. Alignment completes
   ├─ Round 1 & 2 aligned
   ├─ Publish alignment.completed
   └─ Spec 5 event received
                                   ↓
                            4. Fetch /alignments?discussion_id=d
                               ├─ Returns 6 matches
                               ├─ Display group mappings
                               └─ Similarity scores
                                   ↓
                            5. Update Sankey flows
                               ├─ Connect r1→r2 nodes
                               ├─ Same color for aligned
                               └─ Flow width = cluster size
                                   ↓
                            6. Render interactive diagram
```

---

## Integration Testing

### Test 1: Event Subscription

```python
# backend/tests/integration/test_spec4_spec5_integration.py

import pytest
import json
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_clustering_completed_event_triggers_sankey_build():
    """Test that clustering.completed event triggers Sankey column build."""

    sankey_service = SankeyService()

    # Mock event
    event = {
        "event_id": "test-123",
        "event_type": "clustering.completed",
        "timestamp": "2026-01-29T14:10:03.600Z",
        "data": {
            "round_id": "r_test",
            "cluster_count": 8,
            "total_participants": 95,
            "singleton_count": 2,
            "processing_time_ms": 3600,
            "completed_at": "2026-01-29T14:10:03.600Z"
        }
    }

    # Mock fetching clusters from Spec 4
    mock_clusters = {
        "round_id": "r_test",
        "cluster_count": 8,
        "total_participants": 95,
        "clusters": [...]  # Full cluster data
    }

    with patch.object(sankey_service, '_fetch_clusters_from_spec4', return_value=mock_clusters):
        with patch.object(sankey_service, '_save_sankey_column') as mock_save:
            await sankey_service._on_clustering_completed(event)

            # Verify Sankey column was saved
            mock_save.assert_called_once()
```

### Test 2: Alignment Event Processing

```python
@pytest.mark.asyncio
async def test_alignment_completed_event_updates_flows():
    """Test that alignment.completed event updates Sankey flows."""

    sankey_service = SankeyService()

    event = {
        "event_id": "test-456",
        "event_type": "alignment.completed",
        "timestamp": "2026-01-29T14:15:04.100Z",
        "data": {
            "discussion_id": "d_test",
            "round_r": 1,
            "round_r1": 2,
            "match_count": 6,
            "similarity_threshold": 0.7,
            "processing_time_ms": 500,
            "completed_at": "2026-01-29T14:15:04.100Z"
        }
    }

    mock_alignments = {
        "discussion_id": "d_test",
        "alignment_count": 6,
        "alignments": [...]  # Alignment data
    }

    with patch.object(sankey_service, '_fetch_alignments_from_spec4', return_value=mock_alignments):
        with patch.object(sankey_service, '_update_sankey_display_groups') as mock_update:
            await sankey_service._on_alignment_completed(event)

            mock_update.assert_called_once()
```

### Test 3: End-to-End Sankey Build

```python
@pytest.mark.asyncio
async def test_end_to_end_spec4_to_spec5():
    """Test complete flow from clustering to Sankey rendering."""

    # Setup: Create test clusters in Spec 4
    clusters = create_test_clusters(round_id="r_test", count=8)

    # Simulate clustering event
    clustering_event = {
        "event_id": "e1",
        "event_type": "clustering.completed",
        "data": {
            "round_id": "r_test",
            "cluster_count": 8,
            "total_participants": 95
        }
    }

    # Process in Spec 5
    sankey_service = SankeyService()
    await sankey_service._on_clustering_completed(clustering_event)

    # Verify Sankey column created
    sankey_column = get_sankey_column("r_test")
    assert len(sankey_column['nodes']) == 8

    # Verify widths sum to 1.0
    total_width = sum(n['value'] for n in sankey_column['nodes'])
    assert abs(total_width - 1.0) < 0.0001
```

---

## Spec 5 API to Display Sankey

Once Spec 5 has built the Sankey data, it exposes an API for frontend to consume:

```python
# Hypothetical Spec 5 endpoint
@app.get("/api/v1/sankey/{discussion_id}")
async def get_sankey_diagram(discussion_id: str):
    """Get complete Sankey diagram for discussion."""

    return {
        "discussion_id": discussion_id,
        "rounds": [
            {
                "round_id": "r1",
                "round_number": 1,
                "columns": [
                    {
                        "cluster_id": "c1",
                        "label": "Cost reduction",
                        "value": 0.337,
                        "color": "#FF5733"
                    }
                ]
            },
            {
                "round_id": "r2",
                "round_number": 2,
                "columns": [
                    {
                        "cluster_id": "c2",
                        "label": "Budget constraints",
                        "value": 0.295,
                        "color": "#FF5733"  # Same color = aligned
                    }
                ]
            }
        ],
        "flows": [
            {
                "source": "c1",
                "target": "c2",
                "value": 0.30,
                "similarity": 0.82,
                "color": "#FF5733"
            }
        ]
    }
```

Frontend renders this using D3.js Sankey diagram library.

---

## Troubleshooting

### Issue: Spec 5 Not Receiving Events

**Symptoms**: No Sankey columns built, events not processed

**Causes**:
1. Redis connection failed
2. Channel name mismatch
3. Spec 5 service not running
4. Event publisher not sending events

**Solutions**:
```bash
# Check Redis connection
redis-cli ping

# List subscribed channels
redis-cli PUBSUB CHANNELS

# Verify channel name (should be "opendiscuss.clustering.completed" and "opendiscuss.alignment.completed")

# Manually test event
redis-cli PUBLISH opendiscuss.clustering.completed '{"event_type": "clustering.completed", ...}'

# Check Spec 5 logs
docker logs spec5_service | grep "Subscribed to"
```

### Issue: Spec 4 API Call Fails

**Symptoms**: Sankey build fails with "Failed to fetch clusters"

**Causes**:
1. Spec 4 API unavailable
2. Invalid JWT token
3. Round ID not found

**Solutions**:
```bash
# Test Spec 4 API connectivity
curl -I http://localhost:8000/api/v1/clusters \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"round_id": "r_test"}'

# Check Spec 4 logs for errors
docker logs spec4_service

# Verify service token valid
# Test with curl before Spec 5 integration
```

### Issue: Display Groups Not Aligned

**Symptoms**: Sankey built but flows all different colors

**Causes**:
1. Alignment not triggered
2. Alignment failed silently
3. No matches above similarity threshold

**Solutions**:
```python
# Manually trigger alignment
curl -X POST http://localhost:8000/api/v1/alignments/trigger \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "discussion_id": "d_test",
    "round_r": 1,
    "round_r1": 2,
    "similarity_threshold": 0.6  # Lower threshold to find matches
  }'

# Check alignment events published
redis-cli SUBSCRIBE opendiscuss.alignment.completed
```

---

## Integration Checklist

- [ ] Spec 5 subscribed to Redis events
- [ ] Spec 4 API accessible from Spec 5 (network configured)
- [ ] Service-to-service JWT authentication working
- [ ] Sankey column generation tested with mock data
- [ ] Sankey flow generation tested with alignment data
- [ ] Event processing error handling implemented
- [ ] Retry logic for transient failures
- [ ] Logging for debugging event flows
- [ ] Frontend Sankey rendering library integrated
- [ ] Performance tested with 100+ participants
- [ ] E2E test from clustering to rendered diagram

---

## Related Documentation

- **API Documentation**: `backend/docs/api_documentation.md`
- **Spec 3 Integration**: `backend/docs/integration_spec3.md`
- **Quickstart**: `specs/004-clustering-alignment/quickstart.md`
- **Event Contract**: `specs/004-clustering-alignment/contracts/events.yaml`
- **Data Model**: `specs/004-clustering-alignment/data-model.md`

---

## Support

For Spec 5 integration issues:
1. Verify Redis event bus working: `redis-cli PUBSUB CHANNELS`
2. Check Spec 4 API running: `curl http://localhost:8000/api/v1/clusters`
3. Review event payloads in Redis
4. Check Spec 5 logs for errors
5. Test with manual events first before live clustering
6. Open GitHub issue with full event trace and error logs
