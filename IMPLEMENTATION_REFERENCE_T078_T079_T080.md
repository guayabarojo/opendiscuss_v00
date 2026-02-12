# Implementation Reference: T078-T080

Quick reference guide for implementing clustering and alignment features with monitoring, configuration, and authentication.

## Quick Start

### 1. Access Configuration Values

```python
from src.config import settings

# Clustering parameters
threshold = settings.align_threshold  # 0.7
min_size = settings.hdbscan_min_cluster_size  # 2
method = settings.hdbscan_cluster_selection_method  # 'eom'

# Monitoring parameters
latency_threshold = settings.clustering_latency_threshold_ms  # 5000
alignment_threshold = settings.alignment_latency_threshold_ms  # 1000
```

### 2. Monitor Clustering Operations

```python
from src.ml.clustering_monitoring import clustering_monitor, ClusteringMetrics

# Start operation
clustering_monitor.start_operation("op-123", round_id)

# Record stages
clustering_monitor.record_stage("op-123", "embedding")
clustering_monitor.record_stage("op-123", "hdbscan")
clustering_monitor.record_stage("op-123", "centroid")

# Log metrics
metrics = ClusteringMetrics(
    round_id=round_id,
    start_time_ms=start_ms,
    end_time_ms=end_ms,
    approved_summary_count=95,
    cluster_count=8,
    total_participants=95,
    singleton_count=2,
    min_cluster_size=1,
    max_cluster_size=32,
    avg_cluster_size=11.875,
    embedding_generation_ms=1500,
    hdbscan_clustering_ms=800,
    centroid_computation_ms=200,
    persistence_ms=100
)
clustering_monitor.log_clustering_metrics(metrics)
```

### 3. Authenticate in Route Handlers

```python
from fastapi import Request, HTTPException
from src.middleware.auth import get_participant_id_from_request

@router.get("/clusters")
async def get_clusters(request: Request, round_id: str):
    participant_id = get_participant_id_from_request(request)
    if not participant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # ... implementation ...
```

## Configuration Files

### Environment File (.env)

```bash
# Clustering Configuration (T079)
ALIGN_THRESHOLD=0.7
HDBSCAN_MIN_CLUSTER_SIZE=2
HDBSCAN_CLUSTER_SELECTION_METHOD=eom
EMBEDDING_MODEL_VERSION=all-MiniLM-L6-v2

# Monitoring Configuration (T078)
ENABLE_CLUSTERING_METRICS=true
CLUSTERING_LATENCY_THRESHOLD_MS=5000
ALIGNMENT_LATENCY_THRESHOLD_MS=1000

# Security Configuration (T080)
SECRET_KEY=your-256-bit-secret-key
```

## File Locations

| Task | File | Lines | Purpose |
|------|------|-------|---------|
| T078 | `backend/src/ml/clustering_monitoring.py` | 303 | Monitoring infrastructure |
| T079 | `backend/src/config.py` | +47 | Configuration parameters |
| T080 | `backend/src/middleware/auth.py` | 274 | JWT authentication |
| - | `backend/src/main.py` | +2 | Middleware integration |
| - | `backend/docs/config_security_monitoring.md` | - | Full documentation |
| - | `backend/docs/monitoring_examples.md` | - | Code examples |

## API Authentication

### Request Format

```bash
curl -H "Authorization: Bearer <JWT_TOKEN>" \
     http://localhost:8000/api/v1/clusters?round_id=round-123
```

### Token Structure

```python
{
  "participant_id": "user-123",
  "role": "user",
  "exp": 1707072645,
  "iat": 1707069045
}
```

## Monitoring Log Format

### Successful Clustering

```json
{
  "timestamp": "2026-02-02T14:30:45.123456+00:00",
  "level": "INFO",
  "service": "opendiscuss-backend",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Clustering completed successfully (8 clusters, 2600ms total)",
  "event": "clustering.completed",
  "metrics": {
    "total_latency_ms": 2600,
    "cluster_count": 8,
    "singleton_count": 2,
    "singleton_percentage": 2.1
  }
}
```

## Integration Checklist

- [ ] Import `settings` from `src.config` for clustering parameters
- [ ] Import monitors from `src.ml.clustering_monitoring`
- [ ] Use monitoring in clustering service (T029-T033)
- [ ] Use alignment threshold in alignment service (T055-T058)
- [ ] Extract participant_id in route handlers using auth helpers
- [ ] Test with generated JWT tokens
- [ ] Monitor logs for latency warnings
- [ ] Verify singleton count for minority preservation

## Parameter Defaults

| Parameter | Default | Type | Range |
|-----------|---------|------|-------|
| `align_threshold` | 0.7 | float | 0.0-1.0 |
| `hdbscan_min_cluster_size` | 2 | int | 2-100 |
| `hdbscan_cluster_selection_method` | 'eom' | str | 'eom', 'leaf' |
| `clustering_latency_threshold_ms` | 5000 | int | 1000-30000 |
| `alignment_latency_threshold_ms` | 1000 | int | 100-10000 |

## Monitoring Metrics

### Clustering Operation

- **total_latency_ms**: End-to-end operation time
- **cluster_count**: Number of clusters created
- **singleton_count**: Number of singleton clusters
- **singleton_percentage**: Percentage of participants in singletons
- **stage_breakdown_ms**: Per-stage timing (embedding, hdbscan, centroid, persistence)

### Alignment Operation

- **total_latency_ms**: End-to-end operation time
- **match_count**: Number of successful cluster matches
- **match_rate**: Percentage of successful matches
- **similarity_range**: Min/max/avg similarity of matched pairs

## Common Tasks

### Generate Test JWT Token

```python
import jwt
from datetime import datetime, timedelta, timezone
from src.config import settings

payload = {
    "participant_id": "test-user-123",
    "role": "user",
    "exp": datetime.now(timezone.utc) + timedelta(hours=1)
}

token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
print(f"Bearer {token}")
```

### Handle Clustering Errors

```python
try:
    # clustering operation
except Exception as e:
    clustering_monitor.log_clustering_error(
        operation_id=operation_id,
        round_id=round_id,
        error=e,
        stage="hdbscan"
    )
    raise
```

### Extract JWT Claims in Handler

```python
from src.middleware.auth import get_jwt_claims_from_request

@router.get("/clusters")
async def get_clusters(request: Request):
    claims = get_jwt_claims_from_request(request)
    participant_role = claims.get("role", "user") if claims else "user"
    # ... use role for authorization ...
```

## Performance Targets

- Clustering < 5 seconds (SC-001)
- Alignment < 1 second
- Minority clusters preserved (min_cluster_size=2)
- 100% participant coverage

## Security Checklist

- [ ] SECRET_KEY set to strong random value (256 bits)
- [ ] JWT tokens have expiration
- [ ] Bearer token validation on protected endpoints
- [ ] participant_id extracted from JWT claims
- [ ] API returns 401 for missing auth, 403 for invalid auth
- [ ] Rate limiting enabled (100 req/min per IP)
- [ ] CORS configured properly
- [ ] HTTPS in production

## Documentation References

- **Full Config & Security Docs**: `backend/docs/config_security_monitoring.md`
- **Usage Examples**: `backend/docs/monitoring_examples.md`
- **Task Completion**: `TASK_COMPLETION_T078_T079_T080.md`
- **API Spec**: `specs/004-clustering-alignment/contracts/api-spec.yaml`
- **Tasks**: `specs/004-clustering-alignment/tasks.md`

## Next Implementation Steps

1. **T029-T033 (Clustering API)**:
   - Use clustering_monitor for timing
   - Generate ClusteringMetrics
   - Call clustering_monitor.log_clustering_metrics()

2. **T055-T058 (Alignment API)**:
   - Use alignment_monitor for timing
   - Generate AlignmentMetrics
   - Use settings.align_threshold for matching

3. **All Route Handlers**:
   - Extract participant_id from request
   - Add JWT authentication context
   - Log operations with trace ID
