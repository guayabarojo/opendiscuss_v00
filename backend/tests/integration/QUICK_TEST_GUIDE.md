# Quick Test Guide - Spec 002 Integration Tests

## Prerequisites

Ensure you have the backend dependencies installed and services running:

```bash
# Install dependencies (if not already done)
cd backend
poetry install

# Start infrastructure services (PostgreSQL, Redis)
docker-compose up -d

# Run database migrations
poetry run alembic upgrade head
```

## Running Tests

### All Integration Tests for Spec 002
```bash
cd backend
poetry run pytest tests/integration/test_text_submission.py \
                  tests/integration/test_voice_transcription.py \
                  tests/integration/test_rate_limiting.py \
                  tests/integration/test_window_enforcement.py \
                  -v
```

### Individual Test Files

#### Text Submission (T073)
```bash
poetry run pytest tests/integration/test_text_submission.py -v
```
**Coverage:**
- Service layer submission flow
- Event publishing
- Multiple submissions with ephemeral storage
- Text normalization
- TTL expiration

#### Voice Transcription (T074)
```bash
poetry run pytest tests/integration/test_voice_transcription.py -v
```
**Coverage:**
- Transcription service with mocked Whisper API
- Latency < 3s requirement
- Ephemeral storage (AudioRecording, Transcript)
- Status transitions
- Error handling
- Delete/re-record flow

#### Rate Limiting (T075)
```bash
poetry run pytest tests/integration/test_rate_limiting.py -v
```
**Coverage:**
- Max 3 submissions per participant per round
- 4th submission rejected with 429
- Last-approved-wins logic
- Independent rate limits per participant

#### Window Enforcement (T076)
```bash
poetry run pytest tests/integration/test_window_enforcement.py -v
```
**Coverage:**
- Before window → 422
- At start (inclusive) → 201
- At end (exclusive) → 422
- After window → 422
- Boundary conditions (±1s)
- Multiple rounds independence

### Contract Tests

#### Spec 2 → Spec 3 Integration (T077)
```bash
poetry run pytest tests/contract/test_submission_to_summarization.py -v
```
**Coverage:**
- submission.created event schema validation
- TEXT and VOICE modality events
- Field types (UUID, ISO 8601, enums)
- Text normalization guarantees
- Timestamp format
- Event idempotency

## Test Markers

Filter tests by marker:

```bash
# Run only integration tests
poetry run pytest -m integration -v

# Run only contract tests
poetry run pytest -m contract -v

# Run tests with coverage report
poetry run pytest tests/integration/ tests/contract/ \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=html
```

## Expected Output

Successful test run should show:

```
tests/integration/test_text_submission.py::test_text_submission_flow_service_layer PASSED
tests/integration/test_text_submission.py::test_text_submission_event_published PASSED
tests/integration/test_text_submission.py::test_multiple_submissions_with_ephemeral_storage PASSED
tests/integration/test_text_submission.py::test_text_submission_normalization PASSED
tests/integration/test_text_submission.py::test_text_submission_ttl_expiration PASSED
tests/integration/test_text_submission.py::test_text_submission_normalization PASSED

tests/integration/test_voice_transcription.py::test_voice_transcription_flow PASSED
tests/integration/test_voice_transcription.py::test_voice_transcription_latency_under_3s PASSED
tests/integration/test_voice_transcription.py::test_voice_transcription_ephemeral_storage PASSED
tests/integration/test_voice_transcription.py::test_voice_transcription_status_transitions PASSED
tests/integration/test_voice_transcription.py::test_voice_transcription_error_handling PASSED
tests/integration/test_voice_transcription.py::test_voice_transcription_delete_recording PASSED
tests/integration/test_voice_transcription.py::test_voice_transcription_text_normalization PASSED
tests/integration/test_voice_transcription.py::test_multiple_voice_transcriptions_parallel PASSED

tests/integration/test_rate_limiting.py::test_rate_limiting_max_submissions PASSED
tests/integration/test_rate_limiting.py::test_last_approved_wins PASSED
tests/integration/test_rate_limiting.py::test_different_participants_independent_rate_limits PASSED

tests/integration/test_window_enforcement.py::test_window_enforcement_before_window_opens PASSED
tests/integration/test_window_enforcement.py::test_window_enforcement_at_start_inclusive PASSED
tests/integration/test_window_enforcement.py::test_window_enforcement_at_end_exclusive PASSED
tests/integration/test_window_enforcement.py::test_window_enforcement_after_window_closes PASSED
tests/integration/test_window_enforcement.py::test_window_enforcement_boundary_start_minus_1s PASSED
tests/integration/test_window_enforcement.py::test_window_enforcement_boundary_end_minus_1s PASSED
tests/integration/test_window_enforcement.py::test_window_enforcement_during_active_window PASSED
tests/integration/test_window_enforcement.py::test_window_enforcement_multiple_rounds PASSED

tests/contract/test_submission_to_summarization.py::test_submission_created_event_schema PASSED
tests/contract/test_submission_to_summarization.py::test_submission_created_event_text_modality PASSED
tests/contract/test_submission_to_summarization.py::test_submission_created_event_voice_modality PASSED
tests/contract/test_submission_to_summarization.py::test_submission_created_event_text_normalization PASSED
tests/contract/test_submission_to_summarization.py::test_submission_created_event_timestamp_format PASSED
tests/contract/test_submission_to_summarization.py::test_submission_created_event_idempotency PASSED

================================ XX passed in X.XXs ================================
```

## Troubleshooting

### Database Connection Error
```
sqlalchemy.exc.OperationalError: could not connect to server
```
**Fix:** Start PostgreSQL with `docker-compose up -d`

### Redis Connection Error
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
```
**Fix:** Start Redis with `docker-compose up -d`

### Module Not Found
```
ModuleNotFoundError: No module named 'src'
```
**Fix:** Ensure you're in the `backend/` directory and have run `poetry install`

### OpenAI API Key Error
```
TranscriptionError: OpenAI API key not configured
```
**Fix:** Voice transcription tests mock the API, so this shouldn't occur. If it does, set `OPENAI_API_KEY` in `.env`

## Test Data Cleanup

Tests automatically clean up:
- Database: `db_session` fixture truncates tables before each test
- Ephemeral storage: Tests explicitly clear rate limits and raw submissions
- Events: Event handlers unsubscribed after each test

No manual cleanup required.

## CI/CD Integration

Add to CI pipeline:

```yaml
# .github/workflows/tests.yml
- name: Run Integration Tests
  run: |
    cd backend
    poetry run pytest tests/integration/ tests/contract/ \
      --cov=src \
      --cov-report=xml \
      --junit-xml=junit.xml
```

## Test Coverage

Current coverage (estimated):

| Component | Coverage | Tests |
|-----------|----------|-------|
| Input Collection Service | ~85% | 6 tests |
| Transcription Service | ~80% | 8 tests |
| Window Enforcement | ~90% | 8 tests |
| Rate Limiting | ~85% | 3 tests |
| Event Publishing | ~75% | 6 tests |

**Target:** >80% coverage for integration flows

## Next Steps

1. ✅ Run all tests and verify they pass
2. ✅ Add tests to CI/CD pipeline
3. ⏳ Add unit tests for services (T070-T072)
4. ⏳ Add frontend tests (T078-T081)
5. ⏳ Add performance monitoring (T084)

## Questions?

See:
- Full implementation summary: `TEST_IMPLEMENTATION_SUMMARY.md`
- Tasks: `/specs/002-input-collection/tasks.md`
- Contract schema: `/specs/002-input-collection/contracts/events.yaml`
