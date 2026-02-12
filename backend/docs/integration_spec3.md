# Integration Guide: Spec 3 → Spec 4 (Summarization to Clustering)

**Feature**: Semantic Clustering & Hybrid Alignment Protocol (Spec 004)
**Integration Point**: Spec 3 (Summarization & Approval) → Spec 4 (Clustering)
**Date**: 2026-01-29

---

## Overview

Spec 3 (Micro-Summarization & Approval Protocol) provides approved summaries to Spec 4 (Clustering). Spec 4 consumes these summaries, clusters them semantically, and creates thought spaces representing coherent ideas in the discussion.

### Integration Architecture

```
┌─────────────────────┐
│  Spec 3             │
│  Summarization &    │
│  Approval           │
└──────────┬──────────┘
           │
           │ Event: summaries.approved_for_round
           │
           ▼
┌─────────────────────┐
│  Spec 4             │
│  Clustering &       │
│  Alignment          │
│                     │
│  - Receives event   │
│  - Fetches summaries│
│  - Clusters them    │
│  - Creates thought  │
│    spaces           │
└──────────┬──────────┘
           │
           │ Event: clustering.completed
           │
           ▼
┌─────────────────────┐
│  Spec 5             │
│  Sankey             │
│  Construction       │
└─────────────────────┘
```

---

## Event Contract: `summaries.approved_for_round`

This is the triggering event published by Spec 3 when all summaries for a round are approved.

### Event Payload (from Spec 3)

```json
{
  "event_id": "e1f2g3h4-5678-90ab-cdef-1234567890ab",
  "event_type": "summaries.approved_for_round",
  "timestamp": "2026-01-29T14:10:00.000Z",
  "data": {
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
    "summary_count": 95,
    "all_approved": true,
    "completed_at": "2026-01-29T14:10:00.000Z"
  }
}
```

### Event Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | UUID | Unique event identifier (for idempotency) |
| `event_type` | String | Always "summaries.approved_for_round" |
| `timestamp` | ISO8601 | Event publication time (UTC) |
| `data.round_id` | UUID | Round identifier from Spec 0 (Discussion Protocol) |
| `data.summary_count` | Integer | Number of approved summaries (= participants) |
| `data.all_approved` | Boolean | Always true (event only fires when all approved) |
| `data.completed_at` | ISO8601 | When last summary was approved |

---

## Spec 4 Event Subscription

### Setup (One-Time)

Spec 4 subscribes to the Redis channel where Spec 3 publishes events.

```python
# backend/src/services/event_service.py

import asyncio
import redis
import logging
from typing import Callable, Any, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class EventService:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.pubsub = self.redis.pubsub()

    async def subscribe_to_summaries_approved(self):
        """Subscribe to summaries.approved_for_round events from Spec 3."""
        channel = "opendiscuss.summaries.approved"
        self.pubsub.subscribe(channel)

        logger.info(f"Subscribed to {channel}")

        # Listen for events
        for message in self.pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])

                # Validate event
                if self._validate_event(data):
                    await self._on_summaries_approved(data)

    def _validate_event(self, event: Dict[str, Any]) -> bool:
        """Validate event schema and content."""
        required_fields = ['event_id', 'event_type', 'timestamp', 'data']

        if not all(f in event for f in required_fields):
            logger.warning(f"Invalid event: missing required fields")
            return False

        if event['event_type'] != 'summaries.approved_for_round':
            return False

        data = event['data']
        required_data = ['round_id', 'summary_count', 'all_approved', 'completed_at']

        if not all(f in data for f in required_data):
            logger.warning(f"Invalid event data: missing required fields")
            return False

        if not data['all_approved']:
            logger.warning(f"Event sent before all summaries approved (should not happen)")
            return False

        return True

    async def _on_summaries_approved(self, event: Dict[str, Any]):
        """Handler for summaries.approved_for_round event."""
        round_id = event['data']['round_id']
        summary_count = event['data']['summary_count']

        logger.info(f"Event: Summaries approved for round {round_id} ({summary_count} summaries)")

        # Trigger clustering (see next section)
        from src.services.clustering_service import ClusteringService
        clustering_service = ClusteringService()

        try:
            await clustering_service.trigger_clustering_workflow(round_id)
        except Exception as e:
            logger.error(f"Clustering failed for round {round_id}: {e}")
            # Publish error event or alert
```

### Subscribe at Startup

```python
# backend/src/api/main.py

from fastapi import FastAPI
from src.services.event_service import EventService

app = FastAPI()

event_service = EventService()

@app.on_event("startup")
async def startup():
    """Subscribe to events on app startup."""
    # Run subscription in background
    asyncio.create_task(event_service.subscribe_to_summaries_approved())

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    event_service.pubsub.unsubscribe()
```

---

## Fetching Approved Summaries

### HTTP Request to Spec 3 API

When clustering is triggered (either via event or manual API call), Spec 4 fetches approved summaries from Spec 3.

```python
# backend/src/services/clustering_service.py

import httpx
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

SPEC3_API_BASE = "http://localhost:8001/api/v1"  # Spec 3 API endpoint

async def fetch_approved_summaries(round_id: str) -> List[Dict[str, Any]]:
    """Fetch approved summaries from Spec 3."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SPEC3_API_BASE}/summaries",
            params={
                "round_id": round_id,
                "status": "approved"
            },
            headers={
                "Authorization": f"Bearer {SPEC4_SERVICE_TOKEN}"
            }
        )

    if response.status_code != 200:
        logger.error(f"Spec 3 returned {response.status_code}: {response.text}")
        raise Exception(f"Failed to fetch summaries from Spec 3")

    data = response.json()
    summaries = data.get('summaries', [])

    logger.info(f"Fetched {len(summaries)} approved summaries for round {round_id}")

    return summaries
```

### Spec 3 API Response Format (Expected)

```json
{
  "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
  "status": "all_approved",
  "summary_count": 95,
  "summaries": [
    {
      "summary_id": "s1111111-89ab-cdef-0123-456789abcdef",
      "user_id": "u1111111-89ab-cdef-0123-456789abcdef",
      "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
      "summary_text": "We need to reduce costs by 20%",
      "approval_status": "approved",
      "approved_at": "2026-01-29T14:05:30.000Z"
    },
    {
      "summary_id": "s2222222-89ab-cdef-0123-456789abcdef",
      "user_id": "u2222222-89ab-cdef-0123-456789abcdef",
      "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
      "summary_text": "Budget cuts are essential",
      "approval_status": "approved",
      "approved_at": "2026-01-29T14:05:25.000Z"
    }
  ]
}
```

### Validation

```python
def validate_summaries(summaries: List[Dict[str, Any]]) -> bool:
    """Validate summaries from Spec 3."""
    if not summaries:
        raise ValueError("No approved summaries provided")

    required_fields = ['summary_id', 'user_id', 'round_id', 'summary_text']

    for i, summary in enumerate(summaries):
        for field in required_fields:
            if field not in summary:
                raise ValueError(f"Summary {i} missing field: {field}")

        # Validate text not empty
        if not summary['summary_text'].strip():
            raise ValueError(f"Summary {i} has empty text")

    logger.info(f"Validated {len(summaries)} summaries")
    return True
```

---

## Clustering Workflow

Once approved summaries are fetched, Spec 4 executes the clustering workflow:

```python
# backend/src/services/clustering_service.py

async def trigger_clustering_workflow(round_id: str):
    """Complete clustering workflow triggered by Spec 3 event."""

    start_time = datetime.utcnow()

    try:
        # 1. Fetch approved summaries from Spec 3
        logger.info(f"[1/7] Fetching approved summaries for round {round_id}")
        summaries = await fetch_approved_summaries(round_id)
        validate_summaries(summaries)

        # 2. Generate embeddings
        logger.info(f"[2/7] Generating embeddings for {len(summaries)} summaries")
        embeddings = await generate_embeddings(
            [s['summary_text'] for s in summaries]
        )

        # 3. Run HDBSCAN clustering
        logger.info(f"[3/7] Running HDBSCAN clustering")
        cluster_labels = run_hdbscan(embeddings)

        # 4. Handle outliers (convert to singletons)
        logger.info(f"[4/7] Converting outliers to singleton clusters")
        cluster_labels = convert_outliers_to_singletons(cluster_labels)

        # 5. Compute centroids
        logger.info(f"[5/7] Computing cluster centroids")
        centroids = compute_centroids(embeddings, cluster_labels)

        # 6. Select medoid labels
        logger.info(f"[6/7] Selecting medoid labels from actual summaries")
        medoid_ids = select_medoid_labels(
            embeddings, centroids, cluster_labels, summaries
        )

        # 7. Persist to database
        logger.info(f"[7/7] Persisting clusters to database")
        clusters = persist_clusters(
            round_id, summaries, cluster_labels,
            centroids, medoid_ids
        )

        processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Publish success event
        await publish_clustering_completed(
            round_id=round_id,
            cluster_count=len(set(cluster_labels)),
            total_participants=len(summaries),
            singleton_count=sum(1 for label in cluster_labels if label >= 0),
            processing_time_ms=int(processing_time_ms)
        )

        logger.info(f"Clustering completed in {processing_time_ms:.0f}ms")

    except Exception as e:
        logger.error(f"Clustering failed for round {round_id}: {e}")
        # Publish error event
        await publish_clustering_error(round_id, str(e))
        raise
```

---

## Error Handling

### Spec 3 Unavailable

```python
async def fetch_approved_summaries_with_retry(round_id: str, max_retries: int = 3):
    """Fetch approved summaries with exponential backoff."""

    for attempt in range(max_retries):
        try:
            return await fetch_approved_summaries(round_id)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"Retry {attempt+1}/{max_retries} after {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Failed to fetch summaries after {max_retries} attempts")
                raise
```

### No Approved Summaries

```python
# Handle case where event published but no summaries found
if not summaries:
    logger.warning(f"Round {round_id}: Event fired but no summaries found")
    # Don't cluster empty rounds
    raise ValueError("No approved summaries for round {round_id}")
```

### Invalid Summaries from Spec 3

```python
# Validate each summary before clustering
try:
    validate_summaries(summaries)
except ValueError as e:
    logger.error(f"Invalid summaries from Spec 3: {e}")
    # Publish error event to alert Spec 3
    raise
```

---

## Performance Considerations

### Input Size Scaling

| Participants | Embedding Time | Clustering Time | Total | Notes |
|--------------|-----------------|----------------|----|-------|
| 10 | 0.3s | 0.1s | ~0.5s | Test case |
| 50 | 1.5s | 0.2s | ~2.0s | Typical |
| 100 | 3.0s | 0.3s | ~3.5s | SLA limit |
| 500 | 15s | 1.5s | ~17s | Scaling concern |

**SLA**: Clustering must complete in < 5 seconds for 100 participants (SC-001)

### Optimization Tips

1. **Cache embeddings**: If summaries are re-clustered, reuse cached embeddings
2. **Batch fetching**: Fetch summaries in batches from Spec 3 if dataset large
3. **GPU acceleration**: Use GPU for SBERT embedding if available
4. **Async operations**: Run embedding generation in parallel batches

---

## Integration Testing

### Test 1: Event Subscription

```python
# backend/tests/integration/test_spec3_integration.py

import pytest
import json
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_summaries_approved_event_triggers_clustering():
    """Test that summaries.approved_for_round event triggers clustering."""

    event_service = EventService()

    # Mock event
    event = {
        "event_id": "test-event-123",
        "event_type": "summaries.approved_for_round",
        "timestamp": "2026-01-29T14:10:00.000Z",
        "data": {
            "round_id": "r123",
            "summary_count": 10,
            "all_approved": True,
            "completed_at": "2026-01-29T14:10:00.000Z"
        }
    }

    # Mock clustering service
    with patch('src.services.clustering_service.ClusteringService.trigger_clustering_workflow') as mock_trigger:
        await event_service._on_summaries_approved(event)

        # Verify clustering was triggered
        mock_trigger.assert_called_once_with("r123")
```

### Test 2: Fetch Approved Summaries

```python
@pytest.mark.asyncio
async def test_fetch_approved_summaries():
    """Test fetching approved summaries from Spec 3."""

    # Mock Spec 3 API response
    mock_response = {
        "round_id": "r123",
        "status": "all_approved",
        "summary_count": 3,
        "summaries": [
            {
                "summary_id": "s1",
                "user_id": "u1",
                "round_id": "r123",
                "summary_text": "Cost reduction needed",
                "approval_status": "approved"
            },
            {
                "summary_id": "s2",
                "user_id": "u2",
                "round_id": "r123",
                "summary_text": "Speed improvements",
                "approval_status": "approved"
            },
            {
                "summary_id": "s3",
                "user_id": "u3",
                "round_id": "r123",
                "summary_text": "Fair allocation",
                "approval_status": "approved"
            }
        ]
    }

    with patch('httpx.AsyncClient.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        summaries = await fetch_approved_summaries("r123")

        assert len(summaries) == 3
        assert summaries[0]['summary_text'] == "Cost reduction needed"
```

### Test 3: End-to-End Spec 3 → Spec 4

```python
@pytest.mark.asyncio
async def test_end_to_end_spec3_to_spec4():
    """Test complete flow from Spec 3 event to Spec 4 clusters."""

    # Setup: Insert approved summaries
    summaries = create_test_summaries(count=10, themes=['cost', 'cost', 'speed', 'speed', 'speed', 'speed', 'fair', 'fair', 'unique', 'unique'])

    # Simulate Spec 3 event
    event = {
        "event_id": "test-123",
        "event_type": "summaries.approved_for_round",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "round_id": "r_test",
            "summary_count": len(summaries),
            "all_approved": True,
            "completed_at": datetime.utcnow().isoformat()
        }
    }

    # Trigger clustering
    clustering_service = ClusteringService()
    await clustering_service.trigger_clustering_workflow("r_test")

    # Verify clusters created
    clusters = get_clusters(round_id="r_test")

    assert len(clusters) == 4  # 3 themes + 1 unique + 1 unique = 4 clusters
    assert sum(c.user_count for c in clusters) == 10  # All participants assigned
```

---

## Troubleshooting

### Issue: Event Not Triggering Clustering

**Symptoms**: Summaries approved in Spec 3, but no clustering happens

**Causes**:
1. Event service not subscribed to Redis channel
2. Redis connection failed
3. Event published to wrong channel

**Solutions**:
```bash
# Check Redis connection
redis-cli ping

# Check subscribed channels
redis-cli PUBSUB CHANNELS

# Verify channel name matches (should be "opendiscuss.summaries.approved")

# Manually test event
redis-cli PUBLISH opendiscuss.summaries.approved '{"event_type": "summaries.approved_for_round", ...}'

# Check Spec 4 logs
docker logs spec4_service | grep "Subscribed to"
```

### Issue: Clustering Fails After Event

**Symptoms**: Event received, clustering starts, then fails

**Causes**:
1. Spec 3 API unavailable
2. Invalid summaries returned by Spec 3
3. Embedding model not loaded
4. Database connection lost

**Solutions**:
```python
# Add comprehensive logging
logger.info(f"Event received: {event}")
logger.info(f"Fetching summaries from {SPEC3_API_BASE}")
logger.info(f"Fetched {len(summaries)} summaries")
logger.info(f"Starting clustering workflow")

# Check Spec 3 API connectivity
async def health_check():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{SPEC3_API_BASE}/health")
        return response.status_code == 200

if not await health_check():
    logger.error("Spec 3 API unavailable")
```

### Issue: Duplicate Clustering

**Symptoms**: Clustering triggered twice for same round

**Causes**:
1. Event published twice
2. Manual API call + automatic event trigger
3. Retry logic triggering again

**Solutions**:
```python
# Check if clustering already exists
existing = check_existing_clustering(round_id)
if existing and not force_recluster:
    logger.info(f"Clustering already exists for round {round_id}")
    return existing

# Use idempotent event handling
event_processed = check_event_idempotency(event_id)
if event_processed:
    logger.info(f"Event {event_id} already processed")
    return
```

---

## Integration Checklist

- [ ] Redis event bus configured and running
- [ ] Spec 4 subscribed to `opendiscuss.summaries.approved` channel
- [ ] Spec 3 API endpoint URL configured in Spec 4
- [ ] Service-to-service authentication configured (JWT token)
- [ ] Database migration run (clustering tables created)
- [ ] SBERT model cached locally
- [ ] Test event subscription and clustering trigger
- [ ] Test error handling (Spec 3 unavailable, invalid summaries)
- [ ] Monitor event processing latency
- [ ] Setup alerts for clustering failures

---

## Related Documentation

- **API Documentation**: `backend/docs/api_documentation.md`
- **Spec 5 Integration**: `backend/docs/integration_spec5.md`
- **Quickstart**: `specs/004-clustering-alignment/quickstart.md`
- **Event Contract**: `specs/004-clustering-alignment/contracts/events.yaml`
- **API Contract**: `specs/004-clustering-alignment/contracts/api-spec.yaml`

---

## Support

For integration issues:
1. Check Redis connectivity: `redis-cli ping`
2. Verify Spec 3 API is running: `curl http://localhost:8001/api/v1/health`
3. Review Spec 4 logs for error details
4. Consult quickstart.md for example flows
5. Open GitHub issue with event payload and error logs
