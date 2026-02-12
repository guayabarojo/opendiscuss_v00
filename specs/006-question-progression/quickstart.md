# Developer Quickstart: Question Progression Protocol

**Feature**: 006-question-progression
**Date**: 2026-01-29
**Audience**: Backend developers implementing the Question Progression Protocol

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Claude API key (Anthropic)
- Docker (optional, for local development)
- Git
- **Dependencies**: Spec 1 (Discussion Protocol) must be implemented and running

## Local Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/opendiscuss/opendiscuss.git
cd opendiscuss
git checkout 006-question-progression
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies (pytest, mypy, black, ruff)
pip install -r requirements-dev.txt
```

### 3. Start Dependencies (Docker Compose)

```bash
# Start PostgreSQL + Redis
docker-compose up -d postgres redis

# Verify services
docker-compose ps
# Should show postgres:5432 and redis:6379 running
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# Key variables:
#   DATABASE_URL=postgresql://user:pass@localhost:5432/opendiscuss
#   REDIS_URL=redis://localhost:6379/0
#   ANTHROPIC_API_KEY=sk-ant-... (get from https://console.anthropic.com)
#   SECRET_KEY=<generate with: openssl rand -hex 32>
```

**Critical**: Get your Anthropic API key from https://console.anthropic.com/settings/keys
- Create a new key with "All Resources" access
- Set rate limits: 60 requests/min (sufficient for testing)
- Store in `.env` as `ANTHROPIC_API_KEY=sk-ant-...`

### 5. Run Database Migrations

```bash
# Apply schema migrations (includes Spec 1 + Spec 6 tables)
alembic upgrade head

# Verify tables created
psql $DATABASE_URL -c "\dt"
# Should show: question_sequences, questions, question_provenance (new)
# Plus: discussions, rounds, participants (from Spec 1)
```

### 6. Run Tests

```bash
# Run full test suite
pytest

# Run with coverage
pytest --cov=src/question_progression --cov-report=html

# Run only Spec 6 tests
pytest tests/spec6/

# Run specific test categories
pytest tests/spec6/test_validation.py  # Question validation
pytest tests/spec6/test_generation.py  # Auto-generation
pytest tests/spec6/test_sequences.py   # Host-defined mode
```

### 7. Start Development Server

```bash
# Start FastAPI server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Verify API is running
curl http://localhost:8000/health
# Should return: {"status": "ok", "version": "1.0.0"}
```

### 8. Start Background Workers

Question auto-generation requires event bus workers:

```bash
# Terminal 1: Start event bus worker (listens for sankey.complete)
python -m src.question_progression.workers.generation_worker

# Terminal 2: Start API server (from step 7)
uvicorn src.main:app --reload
```

---

## Quick Integration Test

Test the full flow (HOST_DEFINED mode):

```bash
# 1. Create discussion with 3 questions
curl -X POST http://localhost:8000/v1/discussions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN" \
  -d '{
    "community_id": "test-community-uuid",
    "mode": "HOST_DEFINED",
    "questions": [
      "What challenges are most pressing?",
      "How could these challenges be addressed?",
      "What resources are needed?"
    ],
    "submission_window_duration_sec": 300
  }'

# Save discussion_id from response

# 2. Start discussion
curl -X POST http://localhost:8000/v1/discussions/{discussion_id}/start \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN"

# 3. Verify Round 1 has first question
curl http://localhost:8000/v1/discussions/{discussion_id}/current-round \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN"

# Should return: {"round_num": 1, "question_text": "What challenges are most pressing?", ...}

# 4. Advance to Round 2 (after Round 1 completes)
curl -X POST http://localhost:8000/v1/discussions/{discussion_id}/advance \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN"

# 5. Verify Round 2 has second question
curl http://localhost:8000/v1/discussions/{discussion_id}/current-round \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN"

# Should return: {"round_num": 2, "question_text": "How could these challenges be addressed?", ...}
```

Test AUTO_GENERATED mode (requires LLM API):

```bash
# 1. Create discussion with initial question only
curl -X POST http://localhost:8000/v1/discussions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN" \
  -d '{
    "community_id": "test-community-uuid",
    "mode": "AUTO_GENERATED",
    "initial_question": "What are the main barriers?",
    "submission_window_duration_sec": 300
  }'

# 2. Complete Round 1 (submit inputs, approve summaries, build Sankey)
# ... (see Spec 1-5 quickstarts for full round flow) ...

# 3. Wait for auto-generation (event bus worker processes sankey.complete)
# Monitor logs: python -m src.question_progression.workers.generation_worker

# 4. Check generation status
curl http://localhost:8000/v1/auto-generation/status/{round_1_id} \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN"

# Should return: {"status": "COMPLETED", "question_id": "...", "generation_latency_ms": 2847.3}

# 5. Verify Round 2 is QUESTION_READY
curl http://localhost:8000/v1/rounds/{round_2_id} \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN"

# Should return: {"status": "QUESTION_READY", "question_text": "How could funding gaps be addressed?", ...}

# 6. Advance to Round 2
curl -X POST http://localhost:8000/v1/discussions/{discussion_id}/advance \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN"
```

---

## Development Workflows

### Workflow 1: Validate Question Text (Pre-Check)

Before creating a discussion, hosts can validate questions:

```bash
curl -X POST http://localhost:8000/v1/questions/validate \
  -H "Content-Type: application/json" \
  -d '{"question_text": "Why did you choose that option?"}'

# Returns validation error:
# {
#   "valid": false,
#   "error": "Question cannot start with 'Why'",
#   "error_code": "PROHIBITED_OPENING"
# }

curl -X POST http://localhost:8000/v1/questions/validate \
  -H "Content-Type: application/json" \
  -d '{"question_text": "What constraints are limiting progress?"}'

# Returns success:
# {
#   "valid": true,
#   "validated_text": "What constraints are limiting progress?"
# }
```

### Workflow 2: Manual Question Entry (Fallback)

If auto-generation fails, host provides manual question:

```bash
# 1. Check generation status
curl http://localhost:8000/v1/auto-generation/status/{round_id}

# Returns: {"status": "FAILED", "error": "LLM API timeout after 3 retries"}

# 2. Add manual question
curl -X POST http://localhost:8000/v1/discussions/{discussion_id}/questions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN" \
  -d '{"question_text": "What alternatives should be explored?"}'

# 3. Advance to next round
curl -X POST http://localhost:8000/v1/discussions/{discussion_id}/advance \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN"
```

### Workflow 3: Query Question Provenance (Debugging)

For auto-generated questions, inspect provenance metadata:

```bash
curl http://localhost:8000/v1/questions/{question_id} \
  -H "Authorization: Bearer $YOUR_TEST_TOKEN"

# Returns full question with provenance:
# {
#   "question_id": "...",
#   "question_text": "How could funding gaps be addressed?",
#   "mode": "AUTO_GENERATED",
#   "provenance": {
#     "provenance_id": "...",
#     "generation_timestamp": "2026-01-29T14:32:18.234Z",
#     "generation_latency_ms": 2847.3,
#     "input_sankey_hash": "a3c5b8f2e1d4c7b9...",
#     "input_round_id": "...",
#     "llm_model": "claude-sonnet-4-5-20250929",
#     "prompt_tokens": 1823,
#     "completion_tokens": 47,
#     "retry_count": 0,
#     "validation_attempts": 1
#   }
# }
```

### Workflow 4: Monitor Auto-Generation Performance

Query provenance for operational insights:

```sql
-- Average generation latency (last hour)
SELECT AVG(generation_latency_ms) as avg_latency_ms
FROM question_provenance
WHERE generation_timestamp > NOW() - INTERVAL '1 hour';

-- Questions requiring retries (API instability indicator)
SELECT COUNT(*) as retry_count, AVG(retry_count) as avg_retries
FROM question_provenance
WHERE retry_count > 0
  AND generation_timestamp > NOW() - INTERVAL '1 hour';

-- Questions requiring multiple validations (prompt drift indicator)
SELECT COUNT(*) as validation_failures
FROM question_provenance
WHERE validation_attempts > 1
  AND generation_timestamp > NOW() - INTERVAL '1 hour';
```

---

## Testing Guidelines

### Unit Tests (Fast, No External Dependencies)

```bash
# Test question validation logic
pytest tests/spec6/test_validation.py -v

# Test question sequence logic
pytest tests/spec6/test_sequences.py -v

# Test provenance tracking
pytest tests/spec6/test_provenance.py -v
```

Example unit test:

```python
# tests/spec6/test_validation.py
def test_validate_what_question_passes():
    validator = QuestionValidator()
    result = validator.validate("What constraints are limiting progress?")
    assert result.valid is True
    assert result.validated_text == "What constraints are limiting progress?"

def test_validate_why_question_fails():
    validator = QuestionValidator()
    result = validator.validate("Why did you choose that option?")
    assert result.valid is False
    assert result.error_code == "PROHIBITED_OPENING"
    assert "cannot start with 'Why'" in result.error
```

### Integration Tests (Requires Database)

```bash
# Test HOST_DEFINED mode end-to-end
pytest tests/spec6/integration/test_host_defined_flow.py -v

# Test AUTO_GENERATED mode (mocked LLM)
pytest tests/spec6/integration/test_auto_generated_flow.py -v

# Test event bus integration (Spec 5 → Spec 6)
pytest tests/spec6/integration/test_event_integration.py -v
```

Example integration test:

```python
# tests/spec6/integration/test_host_defined_flow.py
async def test_host_defined_discussion_completes_all_rounds(db_session):
    # Create discussion with 3 questions
    discussion = await create_discussion(
        mode="HOST_DEFINED",
        questions=["What?", "How?", "What resources?"]
    )

    # Advance through all rounds
    for i in range(1, 4):
        await advance_round(discussion.id)
        current_round = await get_current_round(discussion.id)
        assert current_round.round_num == i
        assert current_round.question_text == questions[i-1]

    # Verify discussion completes after all questions
    discussion = await get_discussion(discussion.id)
    assert discussion.status == "COMPLETED"
```

### Contract Tests (Validates API Schemas)

```bash
# Test OpenAPI contract compliance
pytest tests/spec6/contract/test_question_api_contract.py -v

# Test AsyncAPI event schemas
pytest tests/spec6/contract/test_event_contract.py -v
```

### End-to-End Tests (Requires LLM API)

```bash
# Test real auto-generation (uses actual Claude API)
# WARNING: This consumes API quota
pytest tests/spec6/e2e/test_real_generation.py -v --e2e

# Run E2E tests only in CI (not local dev)
# Set environment variable: RUN_E2E_TESTS=true
```

---

## Common Development Tasks

### Task 1: Add New Question Constraint

1. Update validation logic in `src/question_progression/validators.py`
2. Add test cases in `tests/spec6/test_validation.py`
3. Update OpenAPI schema in `contracts/question-api.yaml` (error codes)
4. Run tests: `pytest tests/spec6/test_validation.py -v`

### Task 2: Tune Auto-Generation Prompt

1. Edit prompt template in `src/question_progression/prompts.py`
2. Update prompt building logic in `src/question_progression/services/generation.py`
3. Test with mock Sankey: `pytest tests/spec6/test_generation.py::test_prompt_includes_sankey_context`
4. Test with real LLM: `pytest tests/spec6/e2e/test_real_generation.py --e2e`
5. Monitor quality: Query `question_provenance` for `validation_attempts` metrics

### Task 3: Add New Event Handler

1. Define event schema in `contracts/spec5-to-spec6-events.yaml`
2. Implement handler in `src/question_progression/event_handlers.py`
3. Register handler in event bus: `event_bus.subscribe("event.type", handler)`
4. Test handler: `pytest tests/spec6/integration/test_event_integration.py`

### Task 4: Debug Auto-Generation Failure

```bash
# 1. Find failed generation in logs
grep "QuestionGenerationFailure" logs/generation_worker.log

# 2. Query provenance for failed round
psql $DATABASE_URL -c "
  SELECT input_round_id, retry_count, validation_attempts, error
  FROM question_provenance
  WHERE input_round_id = 'YOUR_ROUND_ID';"

# 3. Replay generation with same Sankey (reproducibility)
python -m src.question_progression.scripts.replay_generation \
  --sankey-hash a3c5b8f2e1d4c7b9... \
  --debug

# 4. Analyze LLM response
# Check logs for raw LLM output before validation
```

---

## API Endpoints Reference

### Question Management

- `GET /discussions/{id}/questions` - List all questions for discussion
- `POST /discussions/{id}/questions` - Add manual question (fallback)
- `GET /questions/{id}` - Get question details + provenance
- `POST /questions/validate` - Validate question text (pre-check)

### Sequence Management

- `GET /sequences/{id}` - Get question sequence details
- `GET /discussions/{id}/sequence` - Get sequence for discussion

### Auto-Generation

- `POST /auto-generation/generate` - Trigger generation (internal only)
- `GET /auto-generation/status/{round_id}` - Check generation status

### Round Advancement (Spec 1 Integration)

- `POST /discussions/{id}/advance` - Advance to next round
- `GET /discussions/{id}/current-round` - Get current round + question
- `POST /discussions/{id}/terminate` - Terminate discussion

---

## Monitoring and Observability

### Key Metrics

Monitor these metrics in production:

1. **Auto-generation latency**: p50, p95, p99 of `generation_latency_ms`
2. **Retry rate**: Percentage of generations with `retry_count > 0`
3. **Validation failure rate**: Percentage with `validation_attempts > 1`
4. **Fallback rate**: Percentage reaching QUESTION_GENERATION_FAILED state
5. **Question quality**: Human evaluations of auto-generated questions (post-launch)

### Alerting Thresholds

```yaml
# Prometheus alert rules
alerts:
  - name: HighGenerationLatency
    condition: p95(generation_latency_ms) > 10000  # 10 seconds
    severity: warning

  - name: HighRetryRate
    condition: avg(retry_count) > 1.0
    severity: warning
    description: LLM API instability

  - name: HighValidationFailureRate
    condition: avg(validation_attempts) > 1.5
    severity: critical
    description: Prompt drift or model regression

  - name: FrequentFallbacks
    condition: count(QUESTION_GENERATION_FAILED) > 5 per hour
    severity: critical
    description: Auto-generation system degraded
```

### Logging

Enable debug logging for development:

```bash
# Edit logging config
export LOG_LEVEL=DEBUG

# View generation worker logs
tail -f logs/generation_worker.log | grep "QuestionGeneration"

# View API logs
tail -f logs/api.log | grep "question"
```

---

## Troubleshooting

### Common Errors

#### Issue: "Question validation fails for valid question"

**Symptoms**: Question starting with "What" or "How" is rejected

**Diagnosis**:
```python
# Test validation in Python shell
from src.question_progression.validators import QuestionValidator
validator = QuestionValidator()
result = validator.validate("Your question here")
print(result)
```

**Common Causes**:
- Hidden characters (copy-paste from Word/PDF)
- Extra whitespace at start/end
- Prohibited keywords embedded in question
- Question doesn't have space after "What"/"How" (e.g., "What?" vs "What is...?")

**Solution**:
1. Check for hidden characters: `print(repr(question_text))`
2. Strip whitespace: `question_text = question_text.strip()`
3. Review validation error message for specific guidance
4. Use validation endpoint to pre-check: `POST /v1/questions/validate`

---

#### Issue: "Auto-generation times out"

**Symptoms**: Generation takes >30 seconds, triggers timeout

**Diagnosis**:
```bash
# Check LLM API latency
curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model": "claude-3-5-sonnet-20241022", "max_tokens": 150, "messages": [{"role": "user", "content": "Test"}]}'

# Check provenance for retry patterns
psql $DATABASE_URL -c "
  SELECT AVG(retry_count), AVG(generation_latency_ms)
  FROM question_provenance
  WHERE generation_timestamp > NOW() - INTERVAL '1 hour';"
```

**Solutions**:
1. Check API rate limits (default: 60 req/min)
2. Verify network connectivity to Anthropic API
3. Increase timeout: Set `QUESTION_GENERATION_TIMEOUT_SECONDS=60` in .env
4. Reduce prompt size: Limit Sankey context or previous questions
5. Check Claude API status: https://status.anthropic.com

---

#### Issue: "Event bus not processing sankey.complete"

**Symptoms**: Round completes but auto-generation never triggers

**Diagnosis**:
```bash
# Check event bus worker is running
ps aux | grep generation_worker

# Check event bus logs
tail -f logs/generation_worker.log | grep "sankey.complete"

# Verify Redis connection
redis-cli ping  # Should return "PONG"

# Check event subscriptions
redis-cli PUBSUB CHANNELS  # Should show "sankey.complete" channel
```

**Solutions**:
1. Restart generation worker: `python -m src.question_progression.workers.generation_worker`
2. Check Redis connection: Verify `REDIS_URL` in .env
3. Verify Spec 5 is emitting events: Check Sankey service logs
4. Manual trigger for testing: `POST /v1/auto-generation/generate`

---

#### Issue: "Rate limit exceeded (429)"

**Symptoms**: Generation API returns 429 Too Many Requests

**Cause**: Rate limit enforced (10 requests per minute per discussion) to prevent DoS

**Solution**:
1. Wait for retry-after period (check `Retry-After` header)
2. Don't repeatedly call generation endpoint
3. Use event-driven auto-generation instead of manual triggers
4. For testing: Increase rate limit in `auto_generation.py` (development only)

---

#### Issue: "Validation attempts > 1 (prompt drift)"

**Symptoms**: Questions require multiple regeneration attempts to pass validation

**Diagnosis**:
```sql
-- Check validation failure rate
SELECT AVG(validation_attempts) as avg_attempts,
       COUNT(*) FILTER (WHERE validation_attempts > 1) as failed_first_attempt
FROM question_provenance
WHERE generation_timestamp > NOW() - INTERVAL '1 hour';
```

**Solutions**:
1. Review prompt template in `prompts.py`
2. Add more explicit validation rules to prompt
3. Increase LLM temperature (currently strict)
4. Update constitutional principles context in prompt

---

### Performance Tuning

#### Optimize Question Retrieval

```sql
-- Verify indexes are active
EXPLAIN ANALYZE
SELECT * FROM questions
WHERE sequence_id = 'YOUR_SEQUENCE_ID'
ORDER BY question_order;

-- Should use: Index Scan using uq_questions_sequence_order
```

#### Optimize Provenance Queries

```sql
-- Verify time-series index
EXPLAIN ANALYZE
SELECT * FROM question_provenance
WHERE generation_timestamp > NOW() - INTERVAL '1 hour';

-- Should use: Index Scan using ix_question_provenance_generation_timestamp
```

#### Cache Hit Rate

Monitor Redis cache performance:

```bash
# Check cache hit rate
redis-cli INFO stats | grep keyspace_hits
redis-cli INFO stats | grep keyspace_misses

# Calculate hit rate: hits / (hits + misses)

# View cached sequences
redis-cli KEYS "question_sequence:*"

# Check TTL
redis-cli TTL "question_sequence:YOUR_DISCUSSION_ID"
```

Target metrics:
- Cache hit rate: >70%
- Avg latency with cache: <5ms
- Cache TTL: 10 minutes (600 seconds)

---

## Additional Resources

- **OpenAPI Spec**: `contracts/question-api.yaml` (import into Postman/Insomnia)
- **AsyncAPI Spec**: `contracts/spec5-to-spec6-events.yaml` (event schemas)
- **Data Model**: `data-model.md` (entity relationships and validation rules)
- **Research Decisions**: `research.md` (LLM selection, prompt engineering, validation logic)
- **Feature Spec**: `spec.md` (user stories and requirements)

---

**Last Updated**: 2026-01-29
**Maintained By**: Backend Team
**Questions?**: Ask in #spec6-question-progression Slack channel
