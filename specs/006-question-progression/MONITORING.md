# Monitoring Guide: Question Progression Protocol

**Feature**: 006-question-progression
**Last Updated**: 2026-01-31

---

## Overview

This document describes monitoring strategy, key metrics, alerting thresholds, and operational dashboards for the Question Progression Protocol.

---

## Key Metrics

### Auto-Generation Metrics (T102)

Collected in `src/question_progression/services/generation.py`:

#### Success Metrics

- **`generation_success_count`** (Counter)
  - Description: Total successful question generations
  - Labels: None
  - Query: `generation_success_count`

- **`generation_latency_seconds`** (Histogram)
  - Description: Time from request to completion
  - Buckets: 0-1s, 1-2s, 2-5s, 5-10s, 10s+
  - Labels: None
  - Query: `histogram_quantile(0.95, generation_latency_seconds_bucket)`

- **`generation_retry_count`** (Histogram)
  - Description: Number of retries per generation attempt
  - Buckets: 0, 1, 2, 3+
  - Labels: None
  - Query: `avg(generation_retry_count)`

#### Failure Metrics

- **`generation_failure_count`** (Counter)
  - Description: Total failed question generations
  - Labels: `error_type` (timeout, api_error, validation_exhausted)
  - Query: `sum by (error_type) (generation_failure_count)`

- **`generation_failure_rate`** (Calculated)
  - Formula: `failure_count / (success_count + failure_count)`
  - Query: `generation_failure_count / (generation_success_count + generation_failure_count)`

### Validation Metrics (T103)

Collected in `src/question_progression/validators.py`:

#### Success Metrics

- **`validation_success_count`** (Counter)
  - Description: Total successful validations
  - Labels: None
  - Query: `validation_success_count`

- **`validation_duration_seconds`** (Histogram)
  - Description: Time to validate a question
  - Buckets: 0-1ms, 1-5ms, 5-10ms, 10-50ms, 50ms+
  - Labels: None
  - Target: p95 < 10ms

#### Failure Metrics

- **`validation_failure_count`** (Counter)
  - Description: Total failed validations by error code
  - Labels: `error_code` (INVALID_LENGTH, INVALID_START, CONTAINS_PROHIBITED_WORD, CONTAINS_RANKING_KEYWORD, BINARY_CHOICE)
  - Query: `sum by (error_code) (validation_failure_count)`

- **`validation_rejection_rate`** (Calculated)
  - Formula: `failure_count / (success_count + failure_count)`
  - Query: `validation_failure_count / (validation_success_count + validation_failure_count)`

- **`most_common_failure`** (String)
  - Description: Most frequently rejected error code
  - Source: Logs or metrics aggregation

### Database Performance

#### Query Latency

```sql
-- Question retrieval latency
SELECT
  percentile_cont(0.50) WITHIN GROUP (ORDER BY query_duration_ms) as p50,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY query_duration_ms) as p95,
  percentile_cont(0.99) WITHIN GROUP (ORDER BY query_duration_ms) as p99
FROM pg_stat_statements
WHERE query LIKE '%questions%sequence_id%'
  AND calls > 100;
```

Target: p95 < 5ms

#### Index Usage

```sql
-- Verify indexes are being used
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan,
  idx_tup_read,
  idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename IN ('questions', 'question_provenance')
ORDER BY idx_scan DESC;
```

Expected:
- `uq_questions_sequence_order`: High usage (every question fetch)
- `ix_question_provenance_generation_timestamp`: Moderate usage (time-series queries)

### Cache Performance

#### Hit Rate

```bash
# Redis stats
redis-cli INFO stats

# Calculate hit rate
hit_rate = keyspace_hits / (keyspace_hits + keyspace_misses)
```

Target: > 70%

#### Memory Usage

```bash
# Redis memory
redis-cli INFO memory | grep used_memory_human
```

Target: < 500MB for sequence caching

---

## Alerting Rules

### Critical Alerts (Page on-call)

#### High Generation Failure Rate

```yaml
alert: HighGenerationFailureRate
expr: |
  rate(generation_failure_count[5m]) /
  rate(generation_success_count[5m] + generation_failure_count[5m]) > 0.5
for: 10m
severity: critical
annotations:
  summary: "Question generation failure rate > 50%"
  description: "Over half of generation attempts are failing. Check Anthropic API status and logs."
  runbook: "https://docs.opendiscuss.org/runbooks/generation-failures"
```

#### API Timeout Spike

```yaml
alert: APITimeoutSpike
expr: |
  rate(generation_failure_count{error_type="timeout"}[5m]) > 0.5
for: 5m
severity: critical
annotations:
  summary: "Anthropic API timeouts spiking"
  description: "Multiple timeouts detected. Likely API outage or network issue."
  runbook: "https://status.anthropic.com"
```

### Warning Alerts (Notify Slack)

#### High Generation Latency

```yaml
alert: HighGenerationLatency
expr: histogram_quantile(0.95, generation_latency_seconds_bucket) > 10
for: 15m
severity: warning
annotations:
  summary: "Question generation p95 latency > 10 seconds"
  description: "Generation is slower than expected. Monitor for degradation."
```

#### High Validation Rejection Rate

```yaml
alert: HighValidationRejectionRate
expr: |
  rate(validation_failure_count[10m]) /
  rate(validation_success_count[10m] + validation_failure_count[10m]) > 0.2
for: 30m
severity: warning
annotations:
  summary: "Validation rejection rate > 20%"
  description: "Unusually high validation failures. Check for prompt drift or model changes."
```

#### Cache Hit Rate Low

```yaml
alert: LowCacheHitRate
expr: redis_keyspace_hits / (redis_keyspace_hits + redis_keyspace_misses) < 0.5
for: 15m
severity: warning
annotations:
  summary: "Redis cache hit rate < 50%"
  description: "Cache is not effective. Check TTL settings or query patterns."
```

---

## Dashboards

### Operational Dashboard (Grafana)

**Panel 1: Generation Overview**
- Line chart: Success rate over time (hourly)
- Stat panel: Total generations (24h)
- Stat panel: Current failure rate

**Panel 2: Latency Distribution**
- Heatmap: Generation latency over time
- Line chart: p50, p95, p99 latency (5min intervals)

**Panel 3: Validation Quality**
- Pie chart: Rejection reasons (by error_code)
- Line chart: Rejection rate over time
- Table: Most rejected questions (sample)

**Panel 4: System Health**
- Line chart: Database query latency
- Line chart: Cache hit rate
- Stat panel: Redis memory usage

### Example Prometheus Queries

```promql
# Success rate (5min rolling average)
sum(rate(generation_success_count[5m])) /
(sum(rate(generation_success_count[5m])) + sum(rate(generation_failure_count[5m])))

# p95 latency
histogram_quantile(0.95, sum(rate(generation_latency_seconds_bucket[5m])) by (le))

# Validation rejections by type
sum by (error_code) (rate(validation_failure_count[5m]))

# Cache hit rate
redis_keyspace_hits / (redis_keyspace_hits + redis_keyspace_misses)
```

---

## Log Queries

### Find Recent Generation Failures

```bash
# Search logs for failures
grep "Generation metrics: failure" logs/generation_worker.log | tail -20

# Or with jq (if JSON logs)
cat logs/generation_worker.log | jq 'select(.metric_type == "generation_failure")'
```

### Find Slow Generations

```bash
# Find generations > 10 seconds
cat logs/generation_worker.log | jq 'select(.latency_seconds > 10)'
```

### Find Validation Rejection Patterns

```bash
# Count rejections by error code (last 1000 lines)
tail -1000 logs/api.log | grep "validation_failure" | jq -r '.error_code' | sort | uniq -c | sort -nr
```

---

## Database Queries

### Generation Performance (Last 24h)

```sql
SELECT
  COUNT(*) as total_generations,
  percentile_cont(0.50) WITHIN GROUP (ORDER BY generation_latency_ms) as p50_latency_ms,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY generation_latency_ms) as p95_latency_ms,
  percentile_cont(0.99) WITHIN GROUP (ORDER BY generation_latency_ms) as p99_latency_ms,
  AVG(retry_count) as avg_retries,
  AVG(validation_attempts) as avg_validation_attempts,
  COUNT(*) FILTER (WHERE retry_count > 0) * 100.0 / COUNT(*) as retry_rate_pct
FROM question_provenance
WHERE generation_timestamp > NOW() - INTERVAL '24 hours';
```

### Failed Generations (Last Hour)

```sql
-- Note: Failed generations don't have provenance records
-- Query event bus logs or application metrics instead
```

### Most Common Validation Failures

```sql
-- Approximate via question history (if stored)
SELECT
  error_code,
  COUNT(*) as occurrences,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
FROM validation_history  -- If you track this
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY error_code
ORDER BY occurrences DESC;
```

### Question Generation Trends

```sql
SELECT
  DATE_TRUNC('hour', generation_timestamp) as hour,
  COUNT(*) as generations,
  AVG(generation_latency_ms) as avg_latency_ms,
  AVG(retry_count) as avg_retries
FROM question_provenance
WHERE generation_timestamp > NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour DESC;
```

---

## Health Check Endpoints

### Application Health

```bash
GET /health
```

Response:
```json
{
  "status": "ok",
  "services": {
    "database": "ok",
    "redis": "ok",
    "anthropic_api": "ok"
  },
  "metrics": {
    "generation_success_rate": 0.95,
    "validation_rejection_rate": 0.08,
    "cache_hit_rate": 0.73
  }
}
```

### Metrics Endpoint (Prometheus format)

```bash
GET /metrics
```

---

## Incident Response

### Generation Failures Spike

**Symptoms**: High failure rate, generation_failure_count increasing

**Response**:
1. Check Anthropic API status: https://status.anthropic.com
2. Check API key rate limits: Review Anthropic dashboard
3. Check network connectivity: `curl https://api.anthropic.com`
4. Review recent code changes: `git log --since="2 hours ago"`
5. Check error logs: `grep "QuestionGenerationError" logs/`
6. If API down: Enable manual question entry fallback

### High Latency

**Symptoms**: p95 latency > 10 seconds

**Response**:
1. Check Anthropic API latency: Make test request
2. Check database query latency: Review slow query logs
3. Check Redis latency: `redis-cli --latency`
4. Increase timeout threshold if necessary (config change)
5. Scale horizontally if load-related

### Validation Quality Degradation

**Symptoms**: Validation rejection rate > 20%

**Response**:
1. Review recent prompt changes: `git diff HEAD~5 -- prompts.py`
2. Check for model changes: Verify `claude_model` in config
3. Sample rejected questions: Review validation error messages
4. Adjust prompt or validation rules if needed
5. Monitor for model updates from Anthropic

---

## SLOs (Service Level Objectives)

### Target SLOs

- **Availability**: 99.5% uptime (measured per discussion, not per generation)
- **Generation Success Rate**: > 95%
- **Generation Latency (p95)**: < 10 seconds
- **Generation Latency (p99)**: < 15 seconds
- **Validation Speed (p95)**: < 10ms
- **Cache Hit Rate**: > 70%

### Measurement Windows

- Real-time: 5-minute rolling average
- Daily reports: 24-hour aggregates
- Monthly review: 30-day trends

---

## Contact & Escalation

**Primary On-Call**: Backend team (#backend-on-call)
**Secondary**: DevOps (#devops-alerts)
**Vendor Support**: Anthropic (support@anthropic.com for API issues)

**Escalation Path**:
1. Check dashboards and logs (5 minutes)
2. Engage backend on-call (immediate)
3. Escalate to DevOps if infrastructure issue (15 minutes)
4. Contact Anthropic support if API-related (30 minutes)
