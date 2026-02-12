## Production Deployment Checklist

**Feature**: 006-question-progression
**Date**: 2026-01-31
**Status**: Phase 11 Complete

---

### Pre-Deployment

#### Environment Configuration

- [ ] Set `ANTHROPIC_API_KEY` in production environment
- [ ] Verify `ANTHROPIC_API_KEY` has sufficient rate limits (recommend: 100 req/min)
- [ ] Set `DATABASE_URL` to production PostgreSQL instance
- [ ] Set `REDIS_URL` to production Redis instance (persistent, not ephemeral)
- [ ] Set `SECRET_KEY` to cryptographically secure value (32+ characters)
- [ ] Set `ENVIRONMENT=production`
- [ ] Set `DEBUG=false`
- [ ] Set `LOG_LEVEL=INFO` (or `WARNING` for high-traffic deployments)

#### Database Migrations

```bash
# Verify migrations are up-to-date
alembic current

# Apply all Question Progression migrations
alembic upgrade head

# Verify schema
psql $DATABASE_URL -c "\d questions"
psql $DATABASE_URL -c "\d question_sequences"
psql $DATABASE_URL -c "\d question_provenance"

# Check indexes are created
psql $DATABASE_URL -c "\di questions"
psql $DATABASE_URL -c "\di question_provenance"
```

Expected indexes:
- `uq_questions_sequence_order` (unique, composite on sequence_id + question_order)
- `ix_questions_question_id`
- `ix_question_provenance_question_id` (unique)
- `ix_question_provenance_generation_timestamp`
- `ix_question_provenance_timestamp_retry`

#### Dependencies

```bash
# Verify Python dependencies installed
pip list | grep anthropic  # Should show anthropic>=0.8.0
pip list | grep redis       # Should show redis>=5.0.0
pip list | grep fastapi     # Should show fastapi>=0.104.0

# Test Anthropic API connectivity
python -c "
from anthropic import Anthropic
client = Anthropic(api_key='YOUR_KEY')
print('API connectivity OK')
"

# Test Redis connectivity
redis-cli -u $REDIS_URL ping  # Should return "PONG"
```

---

### Deployment Steps

#### 1. Backup Database

```bash
# Create backup before deployment
pg_dump $DATABASE_URL > backup_before_spec6_$(date +%Y%m%d).sql

# Verify backup
ls -lh backup_before_spec6_*.sql
```

#### 2. Deploy Application Code

```bash
# Pull latest code
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Run linters
ruff check src/question_progression/
black --check src/question_progression/

# Run tests (skip E2E in production)
pytest tests/spec6/ -v --ignore=tests/spec6/e2e/
```

#### 3. Run Database Migrations

```bash
# Apply migrations
alembic upgrade head

# Verify migration success
alembic current  # Should show: 008_add_question_indexes (head)
```

#### 4. Start Services

```bash
# Start API server
gunicorn src.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --log-level info

# Start event bus worker (separate process/container)
python -m src.question_progression.workers.generation_worker

# Verify services are running
curl http://localhost:8000/health
```

#### 5. Smoke Tests

```bash
# Test validation endpoint
curl -X POST http://localhost:8000/api/v1/questions/validate \
  -H "Content-Type: application/json" \
  -d '{"question_text": "What are the main challenges?"}'

# Should return: {"valid": true, "validated_text": "..."}

# Test generation status endpoint
curl http://localhost:8000/api/v1/auto-generation/status/SOME_DISCUSSION_ID \
  -H "Authorization: Bearer $TEST_TOKEN"

# Should return 404 or valid status, not 500
```

---

### Post-Deployment

#### Monitoring Setup

1. **Configure Prometheus/OpenTelemetry**

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'question-progression'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

2. **Set up alerts**

```yaml
# alerts.yml
groups:
  - name: question_progression
    rules:
      - alert: HighGenerationLatency
        expr: histogram_quantile(0.95, generation_latency_seconds) > 10
        for: 5m
        annotations:
          summary: "Question generation p95 latency > 10s"

      - alert: HighValidationFailureRate
        expr: rate(validation_failure_count[5m]) / rate(validation_success_count[5m]) > 0.2
        for: 10m
        annotations:
          summary: "Validation failure rate > 20%"

      - alert: GenerationFailures
        expr: rate(generation_failure_count[5m]) > 0.1
        for: 5m
        annotations:
          summary: "Question generation failures detected"
```

3. **Enable logging**

```bash
# Configure structured logging
export LOG_FORMAT=json
export LOG_LEVEL=INFO

# Ship logs to aggregation service (e.g., CloudWatch, Datadog)
```

#### Performance Baseline

Establish baseline metrics within first 24 hours:

```sql
-- Question generation performance
SELECT
  percentile_cont(0.50) WITHIN GROUP (ORDER BY generation_latency_ms) as p50_latency_ms,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY generation_latency_ms) as p95_latency_ms,
  percentile_cont(0.99) WITHIN GROUP (ORDER BY generation_latency_ms) as p99_latency_ms,
  AVG(retry_count) as avg_retries,
  AVG(validation_attempts) as avg_validation_attempts
FROM question_provenance
WHERE generation_timestamp > NOW() - INTERVAL '24 hours';

-- Validation rejection rate
SELECT
  COUNT(*) FILTER (WHERE valid = false) * 100.0 / COUNT(*) as rejection_rate_pct
FROM (
  SELECT unnest(questions) as question_text
  FROM discussions
) sub;
```

Expected baselines:
- p95 latency: < 10 seconds
- p99 latency: < 15 seconds
- Avg retries: < 0.5
- Avg validation attempts: ~ 1.0
- Validation rejection rate: < 10%

#### Health Checks

Monitor these endpoints:

```bash
# Overall health
curl http://localhost:8000/health
# Expected: {"status": "ok", "services": {"database": "ok", "redis": "ok"}}

# Anthropic API health
curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model": "claude-3-5-sonnet-20241022", "max_tokens": 10, "messages": [{"role": "user", "content": "test"}]}'
# Should return 200, not 401/403

# Redis connectivity
redis-cli -u $REDIS_URL ping
# Should return "PONG"
```

---

### Rollback Plan

If deployment fails:

1. **Stop new services**

```bash
# Stop API server
pkill -f "gunicorn src.main:app"

# Stop event bus worker
pkill -f "generation_worker"
```

2. **Rollback database**

```bash
# Rollback migrations
alembic downgrade -1  # Rollback 1 migration
# or
alembic downgrade 007_round_question_fk  # Rollback to specific version

# Verify rollback
alembic current
```

3. **Restore previous code**

```bash
# Checkout previous version
git checkout PREVIOUS_TAG

# Restart services with old code
```

4. **Restore database backup (if needed)**

```bash
# Only if data corruption occurred
psql $DATABASE_URL < backup_before_spec6_YYYYMMDD.sql
```

---

### Security Checklist

- [ ] Anthropic API key stored in secrets manager (not .env file in production)
- [ ] API key has rate limits configured (prevent abuse)
- [ ] Database credentials rotated regularly
- [ ] Redis requires authentication (not open to public)
- [ ] API endpoints require authentication (Bearer tokens)
- [ ] CORS origins configured (only allow frontend domains)
- [ ] SQL injection prevention verified (parameterized queries)
- [ ] Input validation on all API endpoints
- [ ] Secrets not logged (check log output)
- [ ] TLS/SSL enabled for Anthropic API calls
- [ ] TLS/SSL enabled for database connections
- [ ] Rate limiting enabled on generation endpoints

---

### Scaling Considerations

#### Horizontal Scaling

- **API servers**: Can scale horizontally (stateless)
  - Run multiple instances behind load balancer
  - Recommended: 1 instance per 50 concurrent requests

- **Event bus workers**: Can scale horizontally
  - Run multiple workers subscribed to same Redis channel
  - Recommended: 1 worker per 10 discussions with AUTO mode

- **Database**: Vertical scaling recommended initially
  - Monitor connection pool usage
  - Add read replicas if query load increases

#### Resource Requirements

Per API instance:
- CPU: 2 cores minimum
- Memory: 4GB minimum
- Disk: 10GB (logs)

Per event worker:
- CPU: 1 core minimum
- Memory: 2GB minimum

Database:
- CPU: 4 cores minimum
- Memory: 8GB minimum
- Disk: 50GB minimum (grows with provenance data)

Redis:
- CPU: 2 cores
- Memory: 2GB (for caching + event bus)

---

### Maintenance

#### Database Cleanup

Question provenance grows over time. Archive old records:

```sql
-- Archive provenance older than 90 days
INSERT INTO question_provenance_archive
SELECT * FROM question_provenance
WHERE generation_timestamp < NOW() - INTERVAL '90 days';

DELETE FROM question_provenance
WHERE generation_timestamp < NOW() - INTERVAL '90 days';

-- Vacuum table
VACUUM ANALYZE question_provenance;
```

#### Cache Cleanup

Redis cache is self-cleaning (TTL-based), but monitor memory:

```bash
# Check Redis memory usage
redis-cli INFO memory

# Clear all sequence caches (emergency only)
redis-cli --scan --pattern "question_sequence:*" | xargs redis-cli DEL
```

---

### Support

**On-Call Playbook**: See `TROUBLESHOOTING.md` for incident response

**Escalation Path**:
1. Check logs: `tail -f logs/api.log logs/generation_worker.log`
2. Check metrics: Grafana dashboard or Prometheus queries
3. Check Anthropic API status: https://status.anthropic.com
4. Escalate to backend team if unresolved after 30 minutes

**Emergency Contacts**:
- Backend Team: #backend-on-call
- DevOps: #devops-alerts
- Anthropic Support: support@anthropic.com (for API issues)
