# Observability and Health Monitoring

## Overview

This document describes the production-ready observability and health monitoring features implemented for the OpenDiscuss Discussion Protocol (Tasks T083-T085).

## Features Implemented

### T083: Structured Logging

**Implementation**: Enhanced `backend/src/logging_config.py`

**Key Features**:
- JSON structured logging format for machine-readable logs
- Trace ID correlation across all requests via middleware
- Discussion ID and Round ID correlation context variables
- Automatic inclusion of correlation IDs in all log statements
- Context-aware logging helpers for services

**Usage Example**:
```python
from src.logging_config import get_logger, set_discussion_id, set_round_id

logger = get_logger(__name__)

# Set context for correlation
set_discussion_id(str(discussion.discussion_id))
set_round_id(str(round.round_id))

# All log statements will now include discussion_id and round_id
logger.info("Processing round", extra={"participant_count": 100})
```

**Log Format**:
```json
{
  "timestamp": "2026-01-29T12:34:56.789Z",
  "level": "INFO",
  "service": "opendiscuss-backend",
  "trace_id": "uuid-here",
  "discussion_id": "discussion-uuid",
  "round_id": "round-uuid",
  "logger": "opendiscuss.discussion_service",
  "message": "Processing round",
  "context": {
    "participant_count": 100
  }
}
```

**Updated Services**:
- `discussion_service.py`: Added contextual logging with discussion_id/round_id correlation
- All services use `get_logger(__name__)` for consistent structured logging
- TraceIDMiddleware added to main.py for automatic trace_id injection

### T084: OpenTelemetry Instrumentation

**Implementation**: New file `backend/src/telemetry.py`

**Key Features**:
1. **Distributed Tracing**
   - OTLP span exporter for remote collectors
   - Console exporter for local debugging
   - Automatic service resource tagging

2. **Custom Metrics**
   - Discussion lifecycle metrics (created, completed)
   - Round processing time histograms
   - State transition counters
   - Event emission tracking
   - Sub-protocol handoff latency
   - Participant count per round
   - Active discussion gauges

3. **Span Helpers**
   - `create_span()`: Create custom trace spans
   - `trace_state_transition()`: Track state machine transitions
   - `trace_event_emission()`: Track event bus emissions
   - `trace_subprotocol_handoff()`: Track sub-protocol coordination
   - `RoundProcessingSpan`: Context manager for round timing

4. **Decorator Support**
   - `@traced` decorator for automatic function tracing

**Usage Example**:
```python
from src.telemetry import (
    get_metrics,
    trace_state_transition,
    trace_event_emission,
    RoundProcessingSpan,
)

# Record metrics
metrics = get_metrics()
metrics.record_discussion_created(community_id, total_rounds)

# Trace state transition
with trace_state_transition("Discussion", discussion_id, "CREATED", "ACTIVE"):
    discussion.start()

# Trace event emission
with trace_event_emission("discussion.started", event.model_dump()):
    await event_bus.emit("discussion.started", event)

# Track round processing time
with RoundProcessingSpan(discussion_id, round_id, round_num):
    # Process round...
    pass
```

**Metrics Collected**:
- `discussion.created`: Counter of discussions created
- `discussion.active`: Gauge of active discussions
- `round.completed`: Counter of rounds completed
- `round.processing_time`: Histogram of round processing duration
- `state.transition`: Counter of state machine transitions
- `event.emitted`: Counter of events emitted by type
- `event.handler.error`: Counter of event handler errors
- `submission.window_duration`: Histogram of submission window durations
- `subprotocol.handoff_latency`: Histogram of sub-protocol handoff times
- `round.participants`: Histogram of participant counts per round

**Configuration**:
- Enabled via `enable_telemetry=true` in settings
- OTLP endpoint configurable for remote collectors
- Automatic FastAPI instrumentation support

**Dependencies Added to pyproject.toml**:
```toml
opentelemetry-api = "^1.22.0"
opentelemetry-sdk = "^1.22.0"
opentelemetry-exporter-otlp = "^1.22.0"
opentelemetry-instrumentation-fastapi = "^0.43b0"
```

### T085: Health Check Endpoints

**Implementation**: New file `backend/src/api/health_routes.py`

**Endpoints**:

#### 1. GET /health - Liveness Probe
- Returns 200 if application is running
- Does not check dependencies
- Use for Kubernetes liveness probes
- Minimal latency (<1ms)

**Response**:
```json
{
  "status": "healthy",
  "service": "opendiscuss-discussion-protocol",
  "version": "1.0.0",
  "timestamp": 1706534896.789
}
```

#### 2. GET /health/ready - Readiness Probe
- Validates database connectivity
- Validates Redis connectivity (via event bus)
- Validates event bus pub/sub
- Returns 200 if all dependencies healthy, 503 otherwise
- Non-blocking with 5-second timeout per component
- Parallel health checks for minimal latency

**Response (Healthy)**:
```json
{
  "status": "ready",
  "service": "opendiscuss-discussion-protocol",
  "version": "1.0.0",
  "timestamp": 1706534896.789,
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 12.34
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 8.56
    },
    "event_bus": {
      "status": "healthy",
      "latency_ms": 3.21
    }
  }
}
```

**Response (Unhealthy)**:
```json
{
  "status": "not_ready",
  "service": "opendiscuss-discussion-protocol",
  "version": "1.0.0",
  "timestamp": 1706534896.789,
  "checks": {
    "database": {
      "status": "unhealthy",
      "latency_ms": 5000.0,
      "error": "Connection timeout after 5s"
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 8.56
    },
    "event_bus": {
      "status": "healthy",
      "latency_ms": 3.21
    }
  }
}
```

#### 3. GET /health/startup - Startup Probe
- Similar to liveness check
- Used during initial startup phase
- More lenient timing for container initialization

**Health Check Features**:
- Non-blocking with timeouts (5 seconds per component)
- Parallel execution for all checks
- Detailed error messages for debugging
- Latency tracking for each component
- Kubernetes probe patterns compatible

**Kubernetes Configuration Example**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 2
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 10
  failureThreshold: 2

startupProbe:
  httpGet:
    path: /health/startup
    port: 8000
  initialDelaySeconds: 0
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 30
```

## Integration with Main Application

**Updated**: `backend/src/main.py`

**Changes**:
1. Added TraceIDMiddleware for automatic trace_id injection
2. Initialize structured logging on startup
3. Initialize OpenTelemetry if enabled
4. Initialize event bus on startup (with graceful failure)
5. Register health check routes
6. Proper cleanup on shutdown (database, event bus)

**Startup Sequence**:
```python
1. Configure structured logging (JSON format)
2. Initialize OpenTelemetry (if enabled)
3. Initialize database connection pool
4. Initialize event bus (connect to Redis)
5. Register health check routes
6. Start FastAPI application
```

**Shutdown Sequence**:
```python
1. Close database connections
2. Close event bus (disconnect from Redis)
3. Flush telemetry data
```

## Configuration

**Environment Variables**:
```bash
# Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json                   # json or text

# Telemetry
ENABLE_TELEMETRY=true            # Enable OpenTelemetry instrumentation
OTLP_ENDPOINT=http://localhost:4317  # OTLP collector endpoint

# Service Info
ENVIRONMENT=production           # development, staging, production
```

## Monitoring Best Practices

### 1. Log Aggregation
- Ship JSON logs to centralized logging (e.g., ELK, Loki)
- Index by trace_id, discussion_id, round_id
- Set up alerts for ERROR level logs

### 2. Distributed Tracing
- Use Jaeger, Tempo, or similar for trace visualization
- Monitor trace durations for performance regression
- Track error rates by span type

### 3. Metrics Monitoring
- Use Prometheus or similar for metrics collection
- Set up dashboards for key metrics:
  - Active discussions (gauge)
  - Round processing time (p95, p99)
  - Event emission rate
  - State transition rate
  - Health check latency

### 4. Alerting
- Alert on readiness probe failures
- Alert on high error rates (>1% of requests)
- Alert on slow round processing (>10 minutes)
- Alert on database connection pool exhaustion

## Performance Impact

**Structured Logging**:
- Minimal overhead (<1ms per log statement)
- JSON serialization is fast for small payloads
- No blocking I/O (async writes)

**OpenTelemetry**:
- Span creation: ~0.1ms overhead
- Batch processing minimizes network calls
- Sampling recommended for high-throughput scenarios
- Disable in production if performance critical

**Health Checks**:
- Liveness: <1ms response time
- Readiness: ~50-100ms (database + Redis ping)
- Non-blocking with timeouts
- Minimal resource usage

## Future Enhancements

1. **Metrics Dashboard**: Pre-built Grafana dashboards
2. **Trace Sampling**: Implement head-based sampling for high traffic
3. **Custom Exporters**: Support for additional backends (Datadog, New Relic)
4. **Performance Profiling**: Integrate continuous profiling (pyroscope)
5. **SLO Tracking**: Define and track Service Level Objectives
6. **Automated Alerting**: Integrate with PagerDuty/Opsgenie

## References

- OpenTelemetry Python Documentation: https://opentelemetry.io/docs/instrumentation/python/
- Structured Logging Best Practices: https://12factor.net/logs
- Kubernetes Health Check Patterns: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
