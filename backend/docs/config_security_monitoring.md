# Configuration, Security & Monitoring Implementation (Spec 004: T078-T080)

## Overview

This document describes the implementation of three critical configuration and security tasks for the Semantic Clustering & Hybrid Alignment Protocol (Spec 004):

- **T078**: Monitoring and observability logging for clustering and alignment operations
- **T079**: Configuration management for clustering parameters (ALIGN_THRESHOLD, HDBSCAN settings)
- **T080**: Security review for API authentication using JWT bearer tokens

## T079: Configuration Management

### Changes to `backend/src/config.py`

Added six new configuration parameters for Spec 004 clustering and alignment:

#### Alignment Configuration
```python
align_threshold: float = Field(
    default=0.7,
    ge=0.0,
    le=1.0,
    description="Minimum cosine similarity threshold for cross-round cluster alignment"
)
```

**Purpose**: Controls the greedy matching threshold for alignment (FR-032, FR-033)
- Default: 0.7 (70% semantic similarity required)
- Range: 0.0 to 1.0 (cosine similarity metric)
- Environment variable: `ALIGN_THRESHOLD`

#### HDBSCAN Configuration
```python
hdbscan_min_cluster_size: int = Field(
    default=2,
    ge=2,
    le=100,
    description="HDBSCAN min_cluster_size parameter - minimum points to form a cluster"
)

hdbscan_cluster_selection_method: str = Field(
    default="eom",
    pattern="^(eom|leaf)$",
    description="HDBSCAN cluster_selection_method - 'eom' (Excess of Mass) or 'leaf'"
)
```

**Purpose**: Configures HDBSCAN clustering algorithm (FR-009, FR-012)
- `min_cluster_size`: Default 2 (allows singleton clusters for minority preservation)
- `cluster_selection_method`: Default 'eom' (better for variable-density data)
- Environment variables: `HDBSCAN_MIN_CLUSTER_SIZE`, `HDBSCAN_CLUSTER_SELECTION_METHOD`

#### Embedding Configuration
```python
embedding_model_version: str = Field(
    default="all-MiniLM-L6-v2",
    description="SBERT embedding model version (default all-MiniLM-L6-v2, 384-dimensional)"
)
```

**Purpose**: Specifies the embedding model for clustering (FR-007)
- Default: all-MiniLM-L6-v2 (384-dimensional SBERT model)
- Environment variable: `EMBEDDING_MODEL_VERSION`

#### Monitoring Configuration
```python
enable_clustering_metrics: bool = Field(
    default=True,
    description="Enable clustering performance metrics and observability logging"
)

clustering_latency_threshold_ms: int = Field(
    default=5000,
    ge=1000,
    le=30000,
    description="Threshold for clustering latency warning logs (5s default)"
)

alignment_latency_threshold_ms: int = Field(
    default=1000,
    ge=100,
    le=10000,
    description="Threshold for alignment latency warning logs (1s default)"
)
```

**Purpose**: Controls monitoring and observability behavior (T078)
- Enable/disable clustering metrics collection
- Set latency thresholds for warning logs
- Default: clustering 5000ms, alignment 1000ms
- Environment variables: `ENABLE_CLUSTERING_METRICS`, `CLUSTERING_LATENCY_THRESHOLD_MS`, `ALIGNMENT_LATENCY_THRESHOLD_MS`

### Usage in Code

Access configuration values anywhere in the application:

```python
from src.config import settings

# Use in clustering service
align_threshold = settings.align_threshold  # 0.7
min_cluster_size = settings.hdbscan_min_cluster_size  # 2
cluster_method = settings.hdbscan_cluster_selection_method  # 'eom'

# Use in monitoring
if settings.enable_clustering_metrics:
    monitor.log_metrics(metrics)

if latency_ms > settings.clustering_latency_threshold_ms:
    logger.warning("Slow clustering detected")
```

### Environment Configuration

Create `.env` file in project root:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://opendiscuss:opendiscuss_dev@localhost:5432/opendiscuss

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
SECRET_KEY=your-256-bit-secret-key-for-production
```

## T078: Monitoring and Observability Logging

### Implementation in `backend/src/ml/clustering_monitoring.py`

Created comprehensive monitoring infrastructure with two main monitor classes:

#### ClusteringMonitor

Tracks and logs clustering operation metrics:

**Metrics Collected**:
- Total latency (end-to-end clustering time)
- Input metrics (approved summary count)
- Cluster distribution (count, min/max/avg size)
- Singleton count and percentage
- Per-stage latency breakdown:
  - Embedding generation
  - HDBSCAN clustering
  - Centroid computation
  - Persistence

**Usage**:

```python
from src.ml.clustering_monitoring import (
    clustering_monitor,
    ClusteringMetrics
)

# Start operation
operation_id = "clustering-round-123"
clustering_monitor.start_operation(operation_id, round_id)

# Record stages
clustering_monitor.record_stage(operation_id, "embedding")
clustering_monitor.record_stage(operation_id, "hdbscan")
clustering_monitor.record_stage(operation_id, "centroid")
clustering_monitor.record_stage(operation_id, "persistence")

# Log final metrics
metrics = ClusteringMetrics(
    round_id=round_id,
    start_time_ms=start_time,
    end_time_ms=end_time,
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

**Log Output** (JSON structured logging):

```json
{
  "timestamp": "2026-02-02T14:30:45.123456+00:00",
  "level": "INFO",
  "service": "opendiscuss-backend",
  "trace_id": "uuid",
  "message": "Clustering completed successfully (8 clusters, 2600ms total)",
  "event": "clustering.completed",
  "operation_type": "clustering",
  "round_id": "round-123",
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

#### AlignmentMonitor

Tracks and logs alignment operation metrics:

**Metrics Collected**:
- Total latency (end-to-end alignment time)
- Cluster counts for both rounds
- Match count and match rate percentage
- Similarity statistics (min, max, avg matched)
- Unmatched cluster count

**Usage**:

```python
from src.ml.clustering_monitoring import (
    alignment_monitor,
    AlignmentMetrics
)

# Start operation
operation_id = "alignment-r1-r2"
alignment_monitor.start_operation(operation_id, discussion_id, round_r=1, round_r1=2)

# Log metrics
metrics = AlignmentMetrics(
    discussion_id=discussion_id,
    round_r=1,
    round_r1=2,
    start_time_ms=start_time,
    end_time_ms=end_time,
    cluster_count_r=8,
    cluster_count_r1=7,
    match_count=12,
    similarity_threshold=0.7,
    min_similarity_found=0.65,
    max_similarity_found=0.94,
    avg_similarity_matched=0.82,
    unmatched_clusters=3
)
alignment_monitor.log_alignment_metrics(metrics)
```

**Log Output**:

```json
{
  "timestamp": "2026-02-02T14:31:00.456789+00:00",
  "level": "INFO",
  "service": "opendiscuss-backend",
  "trace_id": "uuid",
  "message": "Alignment completed successfully (12 matches, 85.7% match rate, 450ms total)",
  "event": "alignment.completed",
  "operation_type": "alignment",
  "discussion_id": "discussion-123",
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

### Performance Metrics

**Latency Tracking** (SC-001: < 5 seconds for 100 participants):

- Clustering operation must complete within 5000ms threshold
- Alignment operation must complete within 1000ms threshold
- Logs include warning if thresholds are exceeded

**Distribution Analysis**:

- Min, max, and average cluster sizes
- Singleton count and percentage for minority preservation validation
- Used for constitutional compliance verification

### Error Logging

Both monitors include comprehensive error handling:

```python
clustering_monitor.log_clustering_error(
    operation_id=operation_id,
    round_id=round_id,
    error=exception,
    stage="hdbscan"
)

alignment_monitor.log_alignment_error(
    operation_id=operation_id,
    discussion_id=discussion_id,
    round_r=1,
    round_r1=2,
    error=exception
)
```

## T080: Security Review - API Authentication

### Implementation in `backend/src/middleware/auth.py`

Created `BearerAuthMiddleware` for JWT bearer token authentication per api-spec.yaml securitySchemes:

#### Security Scheme (api-spec.yaml)

```yaml
securitySchemes:
  bearerAuth:
    type: http
    scheme: bearer
    bearerFormat: JWT
    description: JWT token for authenticated requests

security:
  - bearerAuth: []
```

#### Authentication Middleware

**Features**:

1. **Bearer Token Validation**:
   - Extracts bearer token from `Authorization: Bearer <token>` header
   - Validates JWT signature using HS256 algorithm
   - Checks token expiration
   - Verifies required claims (participant_id)

2. **Error Handling**:
   - 401 Unauthorized: Missing or invalid bearer token format
   - 403 Forbidden: Invalid, expired, or malformed JWT token
   - Proper HTTP authentication scheme response headers

3. **Authentication Exempt Paths**:
   - `/health` - Health check endpoint
   - `/docs`, `/openapi.json` - API documentation
   - `/api/v1/health` - API health check
   - Other paths require valid JWT token

4. **Request Context**:
   - Extracts `participant_id` from JWT claims
   - Stores claims in `request.state.jwt_claims`
   - Available to downstream route handlers

#### Configuration

```python
# In backend/src/config.py
secret_key: str = Field(
    default="dev-secret-key-change-in-production",
    min_length=32,
    description="Secret key for JWT token signing and session management"
)
```

**Production Setup**:

```bash
# Generate production secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in environment
export SECRET_KEY="your-256-bit-secret-key"
```

#### Integration in FastAPI

Added to middleware stack in `backend/src/main.py`:

```python
from src.middleware.auth import BearerAuthMiddleware

# Add authentication middleware (T080)
app.add_middleware(BearerAuthMiddleware)
```

**Middleware Stack Order**:
1. Error handling (catches all exceptions)
2. Request logging (logs requests/responses)
3. Structured logging context
4. CORS (browser requests)
5. Security (rate limiting, security headers)
6. Authentication (JWT bearer token validation) ← Added in T080

#### Using Authentication in Route Handlers

Helper functions to extract authentication context:

```python
from fastapi import Request
from src.middleware.auth import (
    get_participant_id_from_request,
    get_jwt_claims_from_request
)

@router.get("/clusters")
async def get_clusters(request: Request, round_id: str):
    # Get participant ID from authenticated request
    participant_id = get_participant_id_from_request(request)
    if not participant_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Use participant_id for authorization or logging
    logger.info(f"Fetching clusters for participant {participant_id}")

    # ... implementation ...


@router.post("/alignments/trigger")
async def trigger_alignment(request: Request, body: AlignmentRequest):
    # Get full JWT claims for advanced authorization
    claims = get_jwt_claims_from_request(request)
    if not claims:
        raise HTTPException(status_code=401, detail="Not authenticated")

    participant_role = claims.get("role", "user")

    # ... implementation ...
```

#### Security Best Practices Implemented

1. **Token Validation**:
   - Signature verification (HS256)
   - Expiration checking
   - Required claims validation

2. **Error Messages**:
   - Clear error codes (MISSING_TOKEN, INVALID_TOKEN)
   - Structured error responses
   - No sensitive information leakage

3. **Logging**:
   - Authentication failures logged
   - Client IP tracked
   - Failed token validation reason logged

4. **Headers**:
   - Standard `WWW-Authenticate` header on 401 responses
   - Secure header configuration in SecurityMiddleware

#### Testing Authentication

**Generate test JWT token**:

```python
import jwt
from datetime import datetime, timedelta, timezone

secret_key = "dev-secret-key-change-in-production"

# Create token with 1-hour expiration
payload = {
    "participant_id": "test-participant-123",
    "exp": datetime.now(timezone.utc) + timedelta(hours=1)
}

token = jwt.encode(payload, secret_key, algorithm="HS256")
print(f"Bearer {token}")
```

**Test with curl**:

```bash
# Without authentication (should fail)
curl http://localhost:8000/api/v1/clusters

# With valid token (should succeed)
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/clusters

# With invalid token (should fail)
curl -H "Authorization: Bearer invalid.token.here" http://localhost:8000/api/v1/clusters
```

## Integration with Clustering/Alignment APIs

### Clustering Endpoint (T029)

```
POST /api/v1/clusters/trigger
Authorization: Bearer <JWT token>
Content-Type: application/json

{
  "round_id": "round-123",
  "force_recluster": false
}
```

### Alignment Endpoint (T055)

```
POST /api/v1/alignments/trigger
Authorization: Bearer <JWT token>
Content-Type: application/json

{
  "discussion_id": "discussion-123",
  "round_r": 1,
  "round_r1": 2,
  "similarity_threshold": 0.7
}
```

## Verification Checklist

- [x] T078: Monitoring logging implemented with ClusteringMonitor and AlignmentMonitor
- [x] T078: Logs include: clustering latency, cluster distribution, singleton count, alignment match rate
- [x] T078: Structured JSON logging with trace_id correlation
- [x] T079: Configuration created in backend/src/config.py
- [x] T079: ALIGN_THRESHOLD parameter (default 0.7)
- [x] T079: HDBSCAN min_cluster_size parameter (default 2)
- [x] T079: HDBSCAN cluster_selection_method parameter (default 'eom')
- [x] T079: Embedding model version configuration
- [x] T079: Monitoring latency threshold configuration
- [x] T080: BearerAuthMiddleware created for JWT validation
- [x] T080: Implements bearerAuth per api-spec.yaml securitySchemes
- [x] T080: Proper 401/403 error responses
- [x] T080: Integrated into main.py middleware stack
- [x] T080: Helper functions for accessing participant_id and JWT claims

## Security Considerations

### Production Deployment

1. **Secret Key Management**:
   - Use environment variable with strong random key
   - Minimum 32 characters (recommended 256 bits)
   - Never commit to version control

2. **HTTPS**:
   - Always use HTTPS in production
   - Enable HSTS header for API endpoints
   - SecurityMiddleware sets appropriate headers

3. **Token Expiration**:
   - Implement token rotation for long-running sessions
   - Default: 1-hour expiration recommended

4. **Rate Limiting**:
   - API-level rate limiting (100 req/min per IP)
   - Configured in SecurityMiddleware
   - Prevents brute force token attacks

## References

- api-spec.yaml: Security schemes and endpoint documentation
- config.py: Configuration parameters
- clustering_monitoring.py: Monitoring implementation
- auth.py: Authentication middleware
- main.py: Middleware stack integration
