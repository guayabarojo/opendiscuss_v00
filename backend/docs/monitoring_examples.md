# Monitoring & Configuration Usage Examples

## Configuration Usage (T079)

### Reading Configuration Values

```python
from src.config import settings

# Access clustering parameters
print(f"Alignment threshold: {settings.align_threshold}")
print(f"HDBSCAN min cluster size: {settings.hdbscan_min_cluster_size}")
print(f"Clustering selection method: {settings.hdbscan_cluster_selection_method}")
print(f"Embedding model: {settings.embedding_model_version}")

# Access monitoring parameters
print(f"Metrics enabled: {settings.enable_clustering_metrics}")
print(f"Clustering latency threshold: {settings.clustering_latency_threshold_ms}ms")
print(f"Alignment latency threshold: {settings.alignment_latency_threshold_ms}ms")
```

### Environment Variable Override

Create `.env` file:
```bash
# Change default values via environment
ALIGN_THRESHOLD=0.8
HDBSCAN_MIN_CLUSTER_SIZE=3
HDBSCAN_CLUSTER_SELECTION_METHOD=leaf
CLUSTERING_LATENCY_THRESHOLD_MS=3000
```

Load with:
```bash
export $(cat .env | xargs)
python -m uvicorn src.main:app --reload
```

## Monitoring Usage (T078)

### Basic Clustering Operation Monitoring

```python
from src.ml.clustering_monitoring import clustering_monitor, ClusteringMetrics
import time
import uuid

async def cluster_summaries(round_id: str, summaries: List[str]):
    """Example: Monitor a clustering operation."""

    operation_id = str(uuid.uuid4())

    # Start operation timing
    clustering_monitor.start_operation(operation_id, round_id)

    try:
        # Generate embeddings
        start_embedding = time.time()
        embeddings = await generate_embeddings(summaries)
        embedding_time = (time.time() - start_embedding) * 1000
        clustering_monitor.record_stage(operation_id, "embedding")

        # Run HDBSCAN
        start_hdbscan = time.time()
        labels = run_hdbscan(embeddings)
        hdbscan_time = (time.time() - start_hdbscan) * 1000
        clustering_monitor.record_stage(operation_id, "hdbscan")

        # Compute centroids
        start_centroid = time.time()
        centroids = compute_centroids(embeddings, labels)
        centroid_time = (time.time() - start_centroid) * 1000
        clustering_monitor.record_stage(operation_id, "centroid")

        # Persist
        start_persist = time.time()
        await persist_clusters(round_id, labels, centroids)
        persist_time = (time.time() - start_persist) * 1000
        clustering_monitor.record_stage(operation_id, "persistence")

        # Calculate metrics
        unique_labels = set(labels)
        cluster_count = len(unique_labels) - (1 if -1 in unique_labels else 0)
        singleton_count = sum(1 for label in labels if label == -1)

        clusters_by_label = {}
        for i, label in enumerate(labels):
            if label not in clusters_by_label:
                clusters_by_label[label] = []
            clusters_by_label[label].append(i)

        cluster_sizes = [len(c) for c in clusters_by_label.values() if c[0] >= 0]

        metrics = ClusteringMetrics(
            round_id=round_id,
            start_time_ms=clustering_monitor.timers[operation_id] * 1000,
            end_time_ms=time.time() * 1000,
            approved_summary_count=len(summaries),
            cluster_count=cluster_count,
            total_participants=len(summaries),
            singleton_count=singleton_count,
            min_cluster_size=min(cluster_sizes) if cluster_sizes else 0,
            max_cluster_size=max(cluster_sizes) if cluster_sizes else 0,
            avg_cluster_size=sum(cluster_sizes) / len(cluster_sizes) if cluster_sizes else 0,
            embedding_generation_ms=embedding_time,
            hdbscan_clustering_ms=hdbscan_time,
            centroid_computation_ms=centroid_time,
            persistence_ms=persist_time
        )

        # Log metrics (triggers JSON structured log with all context)
        clustering_monitor.log_clustering_metrics(metrics)

        return labels, centroids

    except Exception as e:
        clustering_monitor.log_clustering_error(
            operation_id=operation_id,
            round_id=round_id,
            error=e,
            stage="clustering"
        )
        raise
```

### Alignment Operation Monitoring

```python
from src.ml.clustering_monitoring import alignment_monitor, AlignmentMetrics
import time
import uuid
import numpy as np
from scipy.spatial.distance import cosine

async def align_rounds(discussion_id: str, round_r: int, round_r1: int):
    """Example: Monitor an alignment operation."""

    operation_id = str(uuid.uuid4())

    # Start operation timing
    alignment_monitor.start_operation(operation_id, discussion_id, round_r, round_r1)

    try:
        # Load centroids
        centroids_r = await load_centroids(round_r)
        centroids_r1 = await load_centroids(round_r1)

        # Compute similarity matrix
        similarity_scores = []
        match_count = 0
        threshold = 0.7

        for centroid_r in centroids_r:
            for centroid_r1 in centroids_r1:
                similarity = 1 - cosine(centroid_r, centroid_r1)
                similarity_scores.append(similarity)
                if similarity >= threshold:
                    match_count += 1

        # Calculate metrics
        if similarity_scores:
            min_similarity = min(similarity_scores)
            max_similarity = max(similarity_scores)
            matched_scores = [s for s in similarity_scores if s >= threshold]
            avg_matched = sum(matched_scores) / len(matched_scores) if matched_scores else 0
        else:
            min_similarity = max_similarity = avg_matched = 0

        unmatched = len(centroids_r) + len(centroids_r1) - match_count

        metrics = AlignmentMetrics(
            discussion_id=discussion_id,
            round_r=round_r,
            round_r1=round_r1,
            start_time_ms=alignment_monitor.timers[operation_id] * 1000,
            end_time_ms=time.time() * 1000,
            cluster_count_r=len(centroids_r),
            cluster_count_r1=len(centroids_r1),
            match_count=match_count,
            similarity_threshold=threshold,
            min_similarity_found=min_similarity,
            max_similarity_found=max_similarity,
            avg_similarity_matched=avg_matched,
            unmatched_clusters=unmatched
        )

        # Log metrics
        alignment_monitor.log_alignment_metrics(metrics)

        return match_count

    except Exception as e:
        alignment_monitor.log_alignment_error(
            operation_id=operation_id,
            discussion_id=discussion_id,
            round_r=round_r,
            round_r1=round_r1,
            error=e
        )
        raise
```

## Authentication Usage (T080)

### Route Handler with Authentication

```python
from fastapi import Router, Request, HTTPException, status
from src.middleware.auth import get_participant_id_from_request, get_jwt_claims_from_request

router = Router()

@router.get("/clusters")
async def get_clusters(request: Request, round_id: str):
    """Get clusters for a round (requires authentication)."""

    # Extract participant ID from JWT
    participant_id = get_participant_id_from_request(request)
    if not participant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Get JWT claims for additional authorization checks
    claims = get_jwt_claims_from_request(request)

    # Example: Check if participant has admin role
    participant_role = claims.get("role", "user") if claims else "user"

    # Log access
    logger.info(
        f"Fetching clusters for participant {participant_id}",
        extra={"role": participant_role, "round_id": round_id}
    )

    # Fetch clusters (would query database)
    clusters = await db.get_clusters(round_id)

    return {
        "round_id": round_id,
        "cluster_count": len(clusters),
        "clusters": clusters,
        "requested_by": participant_id
    }


@router.post("/alignments/trigger")
async def trigger_alignment(request: Request, body: AlignmentRequest):
    """Trigger cross-round alignment (requires authentication)."""

    # Get participant info for audit logging
    participant_id = get_participant_id_from_request(request)
    claims = get_jwt_claims_from_request(request)

    if not participant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Log operation
    logger.info(
        f"Alignment triggered by participant {participant_id}",
        extra={
            "discussion_id": body.discussion_id,
            "round_r": body.round_r,
            "round_r1": body.round_r1
        }
    )

    # Trigger alignment job
    job_id = await trigger_alignment_job(
        discussion_id=body.discussion_id,
        round_r=body.round_r,
        round_r1=body.round_r1,
        requested_by=participant_id
    )

    return {
        "job_id": job_id,
        "status": "PROCESSING",
        "requested_by": participant_id
    }
```

### Generating Test JWT Tokens

```python
import jwt
from datetime import datetime, timedelta, timezone
from src.config import settings

def generate_test_token(participant_id: str, role: str = "user", hours: int = 1) -> str:
    """Generate a test JWT token."""

    payload = {
        "participant_id": participant_id,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=hours)
    }

    token = jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256"
    )

    return token


# Test tokens
user_token = generate_test_token("user-123", role="user")
admin_token = generate_test_token("admin-456", role="admin")

print(f"User token: {user_token}")
print(f"Admin token: {admin_token}")
```

### Testing with curl

```bash
# Generate a test token
TOKEN=$(python -c "
import jwt
from datetime import datetime, timedelta, timezone
from src.config import settings

payload = {
    'participant_id': 'test-user-123',
    'role': 'user',
    'exp': datetime.now(timezone.utc) + timedelta(hours=1)
}

token = jwt.encode(payload, settings.secret_key, algorithm='HS256')
print(token)
")

# Test endpoint with authentication
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     http://localhost:8000/api/v1/clusters?round_id=round-123

# Test endpoint without authentication (should fail with 401)
curl http://localhost:8000/api/v1/clusters?round_id=round-123

# Test with invalid token (should fail with 403)
curl -H "Authorization: Bearer invalid.token.here" \
     http://localhost:8000/api/v1/clusters?round_id=round-123
```

## Monitoring Log Examples

### Successful Clustering Log

```json
{
  "timestamp": "2026-02-02T14:30:45.123456+00:00",
  "level": "INFO",
  "service": "opendiscuss-backend",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "round_id": "round-abc123",
  "logger": "opendiscuss.clustering_monitoring",
  "message": "Clustering completed successfully (8 clusters, 2600ms total)",
  "event": "clustering.completed",
  "operation_type": "clustering",
  "metrics": {
    "total_latency_ms": 2600,
    "approved_summary_count": 95,
    "cluster_count": 8,
    "total_participants": 95,
    "singleton_count": 2,
    "singleton_percentage": 2.1,
    "min_cluster_size": 1,
    "max_cluster_size": 32,
    "avg_cluster_size": 11.875,
    "stage_breakdown_ms": {
      "embedding_generation": 1500,
      "hdbscan_clustering": 800,
      "centroid_computation": 200,
      "persistence": 100
    }
  }
}
```

### Slow Clustering Warning Log

```json
{
  "timestamp": "2026-02-02T14:31:15.456789+00:00",
  "level": "WARNING",
  "service": "opendiscuss-backend",
  "trace_id": "660f9511-f30c-52e5-b827-557766551111",
  "round_id": "round-def456",
  "logger": "opendiscuss.clustering_monitoring",
  "message": "Clustering latency exceeded threshold (6200ms > 5000ms)",
  "event": "clustering.completed",
  "operation_type": "clustering",
  "metrics": {
    "total_latency_ms": 6200,
    "approved_summary_count": 150,
    "cluster_count": 12,
    "total_participants": 150,
    "singleton_count": 5,
    "singleton_percentage": 3.3,
    "min_cluster_size": 1,
    "max_cluster_size": 45,
    "avg_cluster_size": 12.5
  }
}
```

### Alignment Completed Log

```json
{
  "timestamp": "2026-02-02T14:31:30.789012+00:00",
  "level": "INFO",
  "service": "opendiscuss-backend",
  "trace_id": "770g1622-g41d-63f6-c838-668877662222",
  "discussion_id": "discussion-xyz789",
  "logger": "opendiscuss.clustering_monitoring",
  "message": "Alignment completed successfully (12 matches, 85.7% match rate, 450ms total)",
  "event": "alignment.completed",
  "operation_type": "alignment",
  "round_pair": "r1→r2",
  "metrics": {
    "total_latency_ms": 450,
    "cluster_count_r": 8,
    "cluster_count_r1": 7,
    "match_count": 12,
    "match_rate": 85.7,
    "unmatched_clusters": 3,
    "similarity_threshold": 0.7,
    "similarity_range": {
      "min": 0.65,
      "max": 0.94,
      "avg_matched": 0.82
    }
  }
}
```

### Authentication Failure Log

```json
{
  "timestamp": "2026-02-02T14:32:00.111222+00:00",
  "level": "WARNING",
  "service": "opendiscuss-backend",
  "logger": "opendiscuss.middleware.auth",
  "message": "Token validation failed: Token expired",
  "path": "/api/v1/clusters",
  "method": "GET",
  "error": "Token expired",
  "client_ip": "192.168.1.100"
}
```
