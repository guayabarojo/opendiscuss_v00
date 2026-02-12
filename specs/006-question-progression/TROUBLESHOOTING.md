# Troubleshooting Guide: Question Progression Protocol

**Feature**: 006-question-progression
**Last Updated**: 2026-01-31

---

## Common Issues

### Generation Issues

#### Issue: "Question generation always fails"

**Symptoms**:
- All generation attempts return 500 error
- Logs show "QuestionGenerationError" or "QuestionValidationExhausted"
- No questions generated in AUTO_GENERATED mode

**Diagnosis**:
```bash
# Check Anthropic API key is set
echo $ANTHROPIC_API_KEY | wc -c  # Should be > 50 characters

# Test API connectivity
python -c "
from anthropic import Anthropic
client = Anthropic(api_key='YOUR_KEY')
response = client.messages.create(
    model='claude-3-5-sonnet-20241022',
    max_tokens=10,
    messages=[{'role': 'user', 'content': 'test'}]
)
print('API OK')
"

# Check generation logs
tail -50 logs/generation_worker.log | grep -i error
```

**Common Causes**:
1. **Invalid API key**: Set correct `ANTHROPIC_API_KEY` in environment
2. **Network connectivity**: Check firewall rules, proxy settings
3. **Rate limit exceeded**: Check Anthropic dashboard for quota
4. **Model not available**: Verify model name in config

**Solutions**:
```bash
# Fix API key
export ANTHROPIC_API_KEY="sk-ant-..."  # Get from https://console.anthropic.com

# Test connectivity
curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model": "claude-3-5-sonnet-20241022", "max_tokens": 10, "messages": [{"role": "user", "content": "test"}]}'

# Check rate limits in Anthropic dashboard
# Increase timeout if needed (config.py)
```

---

#### Issue: "Generation times out after 30 seconds"

**Symptoms**:
- Logs show "APITimeoutError"
- Generation latency consistently > 30 seconds
- Retry count always maxes out

**Diagnosis**:
```bash
# Test API latency
time curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 150,
    "messages": [{"role": "user", "content": "What are the main challenges?"}]
  }'

# Check database query for timeout patterns
psql $DATABASE_URL -c "
  SELECT AVG(generation_latency_ms), AVG(retry_count)
  FROM question_provenance
  WHERE generation_timestamp > NOW() - INTERVAL '1 hour';"
```

**Common Causes**:
1. **Anthropic API slow**: Check https://status.anthropic.com
2. **Network latency**: High RTT to API endpoint
3. **Large prompts**: Too much Sankey context
4. **Timeout too strict**: 30 seconds may be insufficient during peak hours

**Solutions**:
```bash
# Increase timeout (config.py or .env)
export QUESTION_GENERATION_TIMEOUT_SECONDS=60

# Reduce prompt size (edit prompts.py)
# Limit Sankey nodes to top 5, reduce previous questions context

# Use faster model (if available)
export CLAUDE_MODEL="claude-3-haiku-20240307"  # Faster, less accurate
```

---

#### Issue: "Validation keeps failing"

**Symptoms**:
- `validation_attempts` in provenance > 1
- Logs show "Question validation failed, will regenerate"
- Same error_code repeated

**Diagnosis**:
```bash
# Check validation metrics
python -c "
from src.question_progression.validators import validation_metrics
print(validation_metrics.get_stats())
"

# Sample generated questions that failed validation
tail -100 logs/generation_worker.log | grep "validation failed" | jq -r '.question_text'

# Check most common failure reason
tail -1000 logs/generation_worker.log | grep "validation failed" | jq -r '.error_code' | sort | uniq -c | sort -nr
```

**Common Causes**:
1. **Prompt drift**: LLM not following instructions
2. **Model change**: New model version has different behavior
3. **Validation too strict**: Rules reject valid questions
4. **Sankey content triggers keywords**: E.g., "rank" in cluster labels

**Solutions**:
1. **Update prompt** (`prompts.py`): Add explicit examples of valid questions
2. **Review validation rules** (`validators.py`): Relax overly strict checks
3. **Whitelist exceptions**: Allow context-specific keywords
4. **Monitor for model updates**: Check Anthropic changelog

Example prompt improvement:
```python
# Before
"Generate a question starting with What or How"

# After
"Generate a question starting with 'What' or 'How'. Examples:
- What factors contribute to funding challenges?
- How could community engagement be improved?
Do NOT use words like: why, vote, rank, best, worst, choose."
```

---

### Validation Issues

#### Issue: "Valid questions rejected"

**Symptoms**:
- Questions that should pass fail validation
- Error code doesn't match question content
- Inconsistent validation results

**Diagnosis**:
```python
# Test question in Python shell
from src.question_progression.validators import QuestionValidator

validator = QuestionValidator()

# Test your question
result = validator.validate("What are the main challenges?")
print(f"Valid: {result.valid}")
print(f"Error: {result.error_message}")

# Check for hidden characters
question = "What are the main challenges?"
print(repr(question))  # Look for \r, \n, \xa0, etc.
```

**Common Causes**:
1. **Hidden characters**: Copy-paste from Word/PDF adds invisible characters
2. **Whitespace issues**: Multiple spaces, tabs, newlines
3. **Case sensitivity**: "WHAT" vs "What"
4. **Regex false positives**: Keyword matches in wrong context

**Solutions**:
```python
# Clean question text before validation
question = question.strip()  # Remove leading/trailing whitespace
question = ' '.join(question.split())  # Normalize internal whitespace
question = question.replace('\xa0', ' ')  # Replace non-breaking spaces
```

---

#### Issue: "Validation too slow"

**Symptoms**:
- `validation_duration_seconds` p95 > 10ms
- API response times slow
- High CPU usage on validation

**Diagnosis**:
```sql
-- Check validation performance
SELECT
  percentile_cont(0.50) WITHIN GROUP (ORDER BY duration_ms) as p50,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95,
  percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99
FROM (
  SELECT
    EXTRACT(EPOCH FROM (created_at - LAG(created_at) OVER (ORDER BY created_at))) * 1000 as duration_ms
  FROM questions
  WHERE created_at > NOW() - INTERVAL '1 hour'
) sub;
```

**Common Causes**:
1. **Regex inefficiency**: Complex regex patterns
2. **Large keyword lists**: Checking 50+ keywords per question
3. **No caching**: Re-compiling regexes every time

**Solutions**:
1. **Pre-compile regexes**: Done in `validators.py` (already optimized)
2. **Use sets for keyword checks**: O(1) lookup vs O(n) list iteration
3. **Early exit**: Fail-fast on first violation (already implemented)

---

### Database Issues

#### Issue: "Slow question queries"

**Symptoms**:
- API response time > 100ms for question retrieval
- Database CPU high
- Connection pool exhausted

**Diagnosis**:
```sql
-- Check slow queries
SELECT
  query,
  mean_exec_time,
  calls
FROM pg_stat_statements
WHERE query LIKE '%questions%'
  AND mean_exec_time > 50  -- milliseconds
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check index usage
EXPLAIN ANALYZE
SELECT * FROM questions
WHERE sequence_id = 'YOUR_SEQUENCE_ID'
ORDER BY question_order;
```

**Common Causes**:
1. **Missing indexes**: Migrations not applied
2. **Table bloat**: Need VACUUM
3. **N+1 queries**: Loading questions one by one

**Solutions**:
```bash
# Verify indexes exist
psql $DATABASE_URL -c "\di questions"

# Expected indexes:
# - uq_questions_sequence_order (sequence_id, question_order)
# - ix_questions_question_id (question_id)

# If missing, run migration:
alembic upgrade head

# Vacuum table
psql $DATABASE_URL -c "VACUUM ANALYZE questions;"

# Use selectinload in SQLAlchemy (already done in sequence.py)
```

---

#### Issue: "Provenance table growing too large"

**Symptoms**:
- Database disk usage increasing rapidly
- Provenance queries slow
- Backup time increasing

**Diagnosis**:
```sql
-- Check table size
SELECT
  pg_size_pretty(pg_total_relation_size('question_provenance')) as total_size,
  COUNT(*) as row_count
FROM question_provenance;

-- Check growth rate
SELECT
  DATE(generation_timestamp) as date,
  COUNT(*) as daily_generations
FROM question_provenance
GROUP BY date
ORDER BY date DESC
LIMIT 30;
```

**Common Causes**:
1. **No archival strategy**: Old records never deleted
2. **High generation volume**: More discussions than expected
3. **Failed generations not cleaned up**: Retries create duplicate attempts

**Solutions**:
```sql
-- Archive old provenance (> 90 days)
CREATE TABLE IF NOT EXISTS question_provenance_archive (LIKE question_provenance);

INSERT INTO question_provenance_archive
SELECT * FROM question_provenance
WHERE generation_timestamp < NOW() - INTERVAL '90 days';

DELETE FROM question_provenance
WHERE generation_timestamp < NOW() - INTERVAL '90 days';

VACUUM FULL question_provenance;

-- Set up regular archival job (cron)
```

---

### Cache Issues

#### Issue: "Low cache hit rate"

**Symptoms**:
- Cache hit rate < 50%
- Redis memory growing
- No performance improvement from cache

**Diagnosis**:
```bash
# Check Redis stats
redis-cli INFO stats | grep keyspace

# Calculate hit rate
hits=$(redis-cli INFO stats | grep keyspace_hits | cut -d: -f2)
misses=$(redis-cli INFO stats | grep keyspace_misses | cut -d: -f2)
echo "scale=2; $hits / ($hits + $misses)" | bc

# Check cache keys
redis-cli KEYS "question_sequence:*" | wc -l

# Check TTL distribution
for key in $(redis-cli --scan --pattern "question_sequence:*" | head -10); do
  echo "$key: $(redis-cli TTL $key)"
done
```

**Common Causes**:
1. **TTL too short**: Cache expires before reuse
2. **Cache not implemented**: Code not calling cache layer
3. **High churn**: Sequences updated frequently
4. **Wrong key format**: Cache miss due to key mismatch

**Solutions**:
```python
# Increase TTL (cache.py)
cache = SequenceCache(ttl_seconds=1800)  # 30 minutes

# Verify cache is being called
# Add logging in sequence.py

# Pre-warm cache for active discussions
for discussion_id in active_discussions:
    sequence = await sequence_service.get_sequence_by_discussion(discussion_id)
    await sequence_cache.set(discussion_id, serialize_sequence(sequence))
```

---

#### Issue: "Cache causing stale data"

**Symptoms**:
- Questions not updating after changes
- Users see old questions
- Inconsistent state across requests

**Diagnosis**:
```bash
# Check if invalidation is working
redis-cli MONITOR | grep "question_sequence"

# Verify invalidation is called after updates
# Check code for cache.invalidate() calls
```

**Common Causes**:
1. **Missing invalidation**: Code doesn't call `cache.invalidate()`
2. **Invalidation failure**: Redis down, error not caught
3. **Race condition**: Cache set after invalidation

**Solutions**:
```python
# Ensure invalidation after every update
async def update_sequence(sequence_id):
    # Update database
    await db.commit()

    # Invalidate cache
    await sequence_cache.invalidate(sequence.discussion_id)

    # Or use try-except to ensure it runs
    try:
        await sequence_cache.invalidate(sequence.discussion_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")
```

---

### Event Bus Issues

#### Issue: "sankey.complete events not processed"

**Symptoms**:
- Round completes but generation never triggers
- Event bus worker logs show no activity
- AUTO_GENERATED mode doesn't work

**Diagnosis**:
```bash
# Check worker is running
ps aux | grep generation_worker

# Check Redis connection
redis-cli -u $REDIS_URL ping  # Should return "PONG"

# Check event subscriptions
redis-cli PUBSUB CHANNELS  # Should show "sankey.complete"

# Monitor events
redis-cli MONITOR | grep "sankey.complete"

# Check worker logs
tail -f logs/generation_worker.log | grep "sankey.complete"
```

**Common Causes**:
1. **Worker not running**: Process crashed or not started
2. **Redis connection failed**: Wrong URL, auth failure
3. **Event not emitted**: Spec 5 (Sankey) not emitting events
4. **Wrong channel name**: Mismatch between publisher and subscriber

**Solutions**:
```bash
# Start worker
python -m src.question_progression.workers.generation_worker

# Verify Redis URL
echo $REDIS_URL  # Should be redis://host:port/db

# Test event emission manually
python -c "
import redis
r = redis.from_url('$REDIS_URL')
r.publish('sankey.complete', '{\"discussion_id\": \"test\"}')
print('Event published')
"

# Check Spec 5 logs for event emission
tail -f logs/sankey_worker.log | grep "sankey.complete"
```

---

### API Issues

#### Issue: "Rate limit errors (429)"

**Symptoms**:
- API returns 429 Too Many Requests
- `Retry-After` header present
- Manual generation endpoint blocked

**Diagnosis**:
```bash
# Check rate limiter state
python -c "
from src.question_progression.api.auto_generation import rate_limiter
print(rate_limiter.requests)
"

# Count requests in logs (last minute)
tail -1000 logs/api.log | grep "POST /auto-generation/generate" | grep -c "$(date -u +%Y-%m-%dT%H:%M)"
```

**Common Causes**:
1. **Accidental DoS**: Client making too many requests
2. **Bug in client**: Retry loop without backoff
3. **Rate limit too strict**: 10 req/min too low for use case

**Solutions**:
```bash
# Wait for retry-after period
# Check Retry-After header in response

# Fix client code to respect rate limits
# Add exponential backoff

# Increase rate limit (development only)
# Edit auto_generation.py:
# rate_limiter = RateLimiter(max_requests=50, window_seconds=60)

# Use event-driven generation instead of manual triggers
```

---

## Emergency Procedures

### Disable Auto-Generation

If auto-generation is causing issues:

```python
# Create emergency kill switch in config.py
ENABLE_AUTO_GENERATION = False

# Update event handler to check flag
if not settings.ENABLE_AUTO_GENERATION:
    logger.warning("Auto-generation disabled")
    return

# Restart workers
```

### Force Manual Question Entry

```bash
# API endpoint to add manual question
curl -X POST http://localhost:8000/api/v1/discussions/{discussion_id}/questions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question_text": "What should we discuss next?"}'
```

### Clear All Caches

```bash
# Emergency cache clear (Redis)
redis-cli --scan --pattern "question_sequence:*" | xargs redis-cli DEL

# Verify
redis-cli KEYS "question_sequence:*"  # Should be empty
```

---

## Support Contacts

- **Backend Team**: #backend-on-call (Slack)
- **DevOps**: #devops-alerts (Slack)
- **Anthropic Support**: support@anthropic.com
- **Documentation**: https://docs.opendiscuss.org/spec6

---

## Appendix: Useful Commands

### Check Service Health

```bash
# API health
curl http://localhost:8000/health

# Database connection
psql $DATABASE_URL -c "SELECT 1;"

# Redis connection
redis-cli -u $REDIS_URL ping

# Anthropic API
curl https://api.anthropic.com/v1/health
```

### View Recent Generations

```sql
SELECT
  q.question_text,
  qp.generation_latency_ms,
  qp.retry_count,
  qp.validation_attempts,
  qp.generation_timestamp
FROM questions q
JOIN question_provenance qp ON q.question_id = qp.question_id
WHERE qp.generation_timestamp > NOW() - INTERVAL '1 hour'
ORDER BY qp.generation_timestamp DESC
LIMIT 20;
```

### Monitor Metrics in Real-Time

```bash
# Watch validation metrics
watch -n 5 'python -c "from src.question_progression.validators import validation_metrics; print(validation_metrics.get_stats())"'

# Watch generation metrics
watch -n 5 'python -c "from src.question_progression.services.generation import generation_metrics; print(generation_metrics.get_stats())"'
```
