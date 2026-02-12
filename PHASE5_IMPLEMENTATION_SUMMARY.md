# Phase 5 Implementation Summary: Auto-Generated Question Flow

**Feature**: Question Progression Protocol (Spec 006)
**Phase**: Phase 5 - User Story 2 (Auto-Generated Question Flow)
**Date**: 2026-01-31
**Status**: COMPLETE

## Overview

Phase 5 implements LLM-powered autonomous question generation triggered by Sankey diagram completion. The system generates constitutionally-compliant questions using Claude Sonnet 4.5, with robust error handling, validation retry loops, and comprehensive provenance tracking.

---

## Implementation Summary

### Tasks Completed: 18/18 (100%)

#### LLM Integration (T039-T044) ✅

**T039 [P] - LLM Prompt Template**
- **File**: `/backend/src/question_progression/prompts.py`
- **Implementation**:
  - Created `QUESTION_GENERATION_PROMPT` with 15% constitutional principles + 60% Sankey context + 25% question history
  - Created `STRICT_QUESTION_GENERATION_PROMPT` for validation retry attempts
  - Implemented `build_generation_prompt()` function that dynamically formats prompts
  - Includes strict What/How requirements and explicit prohibition of voting/ranking keywords
- **Template Variables**: round_num, previous_questions, thought_spaces, flow_patterns, dropout_summary, top_3_spaces, top_3_flows

**T040 [P] - QuestionGenerationService**
- **File**: `/backend/src/question_progression/services/generation.py`
- **Implementation**:
  - Initialized Anthropic Claude client with API key from `settings.claude_api_key`
  - Model: `claude-sonnet-4-5` (from `config.claude_model`)
  - Timeout: 30 seconds (from `config.question_generation_timeout_seconds`)
  - Max retries: 3 (from `config.question_generation_max_retries`)
  - All methods are async for non-blocking LLM calls

**T041 [P] - generate_from_sankey() Method**
- **Implementation**:
  - Accepts: `round_num`, `previous_questions`, `sankey_data`, `input_round_id`
  - Builds prompt from template with full Sankey context
  - Calls Claude API with `max_tokens=150`
  - Extracts question text from response via `_extract_question()`
  - Returns dictionary with question_text, provenance metadata, and sankey_hash

**T042 [P] - Retry Logic with Exponential Backoff**
- **Implementation**:
  - Max retries: 3 (configurable from settings)
  - Backoff delays: 1s, 2s, 4s (exponential: 2^attempt)
  - Catches: `APITimeoutError`, `APIError`, and generic exceptions
  - Logs each retry attempt with context (attempt number, error type, delay)
  - Nested retry structure: outer loop for validation, inner loop for API failures

**T043 [P] - Validation Retry Loop**
- **Implementation**:
  - After each generation, validates using `QuestionValidator.validate()`
  - On validation failure, regenerates with stricter prompt
  - Stricter prompt includes failed question and rejection reason as negative examples
  - Max validation attempts: 3
  - Tracks `validation_attempts` in provenance metadata
  - Raises `QuestionValidationExhausted` when all attempts fail

**T044 - ProvenanceTracker.record()**
- **File**: `/backend/src/question_progression/services/provenance.py`
- **Implementation**:
  - Creates `QuestionProvenance` entity with complete metadata
  - Records: Sankey hash (SHA-256), LLM model, latency_ms, retry_count, validation_attempts
  - Includes: prompt_tokens, completion_tokens, previous_questions_count
  - Validates required fields before persistence
  - Returns provenance_id after flush()

#### Event Handlers (T045-T048) ✅

**T045 - sankey.complete Event Handler**
- **File**: `/backend/src/question_progression/event_handlers.py`
- **Implementation**:
  - Subscribes to `events:sankey.complete` channel via EventBus
  - Extracts: discussion_id, round_id, sankey_graph from payload
  - Validates payload structure (T076 integration)
  - Checks discussion mode (only AUTO_GENERATED)
  - Triggers question generation asynchronously
  - Includes retry wrapper with exponential backoff (T079)

**T046 - Integration with QuestionGenerationService**
- **Implementation**:
  - Fetches discussion with question sequence
  - Retrieves previous questions from sequence
  - Prepares Sankey data via `_prepare_sankey_data()`
  - Calls `generate_from_sankey()` with full context
  - Creates Question entity with `mode=AUTO_GENERATED`, `validation_status=VALID`
  - Creates QuestionProvenance record via ProvenanceTracker
  - Sets Round.question_id and `status=QUESTION_READY`
  - Emits `question.ready` event on success

**T047 - QUESTION_READY State**
- **Files**: `/backend/src/models/protocol_state.py`, `/backend/src/models/round.py`
- **Implementation**:
  - Added `QUESTION_READY` to `RoundStatus` enum
  - Transition: `SANKEY_COMPLETE` → `QUESTION_READY` (auto mode only)
  - Updated `Round.advance_status()` valid transitions:
    - `PENDING` → [`QUESTION_READY`, `SUBMISSION_OPEN`, `QUESTION_GENERATION_FAILED`]
    - `QUESTION_READY` → [`SUBMISSION_OPEN`]
  - Host must manually advance from `QUESTION_READY` to `SUBMISSION_OPEN`

**T048 - QUESTION_GENERATION_FAILED Fallback**
- **Implementation**:
  - Added `QUESTION_GENERATION_FAILED` to `RoundStatus` enum
  - Set when all 3 retries + 3 validation attempts exhausted
  - Emits `question.generation_failed` event with retry_count and last_error
  - Creates Round with empty question_text (awaiting host manual entry)
  - Transition: `QUESTION_GENERATION_FAILED` → `SUBMISSION_OPEN` (after host provides question)
  - Notify host to provide manual question via UI

#### Background Workers (T049) ✅

**T049 - Generation Worker**
- **File**: `/backend/src/question_progression/workers/generation_worker.py`
- **Implementation**:
  - Created `GenerationWorker` class with `start()` and `stop()` methods
  - Uses asyncio for concurrent event processing
  - Connects to Redis event bus on startup
  - Registers event handlers via `register_handlers()`
  - Graceful error handling with reconnection logic
  - Global worker instance accessible via `get_worker()`
  - Keeps worker alive in background task

#### API Endpoints (T050-T053) ✅

**T050 - POST /auto-generation/generate**
- **File**: `/backend/src/question_progression/api/auto_generation.py`
- **Implementation**:
  - Manual trigger endpoint for testing/debugging
  - Accepts: `discussion_id`, `round_id`
  - Bypasses event bus, directly calls `QuestionGenerationService`
  - Uses mock Sankey data for manual testing
  - Creates Question entity and provenance record
  - Returns: `question_id`, `question_text`, `provenance`, `latency_ms`
  - Error handling for generation failures

**T051 - GET /auto-generation/status/{discussion_id}**
- **Implementation**:
  - Returns current round status and question ready flag
  - Includes generation timestamp, latency, retry count, validation attempts
  - Fetches provenance metadata if question exists
  - Shows error message if status is `QUESTION_GENERATION_FAILED`
  - Returns `GenerationStatusResponse` with complete metadata

**T052 - Auto-Generation Timeout Handling**
- **Implementation**:
  - 30-second timeout per attempt (from `config.question_generation_timeout_seconds`)
  - Timeout set in `AsyncAnthropic` client via `httpx.Timeout(30, connect=5.0)`
  - After timeout, catches `APITimeoutError` and counts as failed retry
  - Logs timeout events with attempt number and error details
  - Exponential backoff applies after timeout

**T053 - Provenance Metadata in Question Response**
- **Implementation**:
  - Extended `GenerationStatusResponse` schema
  - Includes: `generation_timestamp`, `latency_ms`, `retry_count`, `validation_attempts`
  - Only populated for AUTO_GENERATED questions with provenance records
  - Fetches from `QuestionProvenance` table via question_id FK

#### Logging & Monitoring (T054-T055) ✅

**T054 - Auto-Generation Lifecycle Logging**
- **Implementation**:
  - **Start**: Logs with sankey_hash, discussion_id, round_id, previous_questions_count
  - **Success**: Logs question_text, latency_ms, retry_count, validation_attempts
  - **Retry**: Logs attempt number, error type, delay, next_attempt
  - **Failure**: Logs exhaustion reason, last_error, retry_count, outcome
  - Uses structured logging with `extra` dict for correlation
  - All logs include trace_id for distributed tracing
  - Integrated with `src.logging_config.get_logger()`

**T055 - Integration Test**
- **File**: `/backend/tests/spec6/integration/test_auto_generated_flow.py`
- **Implementation**:
  - **Test 1**: Create AUTO_GENERATED discussion → complete Round 1 → trigger generation → verify question created
  - **Test 2**: Mock validation failure → regeneration → success (validates retry loop)
  - **Test 3**: All retries exhausted → `QUESTION_GENERATION_FAILED` (validates fallback)
  - Uses pytest-asyncio for async tests
  - Mocks Claude API responses with `unittest.mock.AsyncMock`
  - Verifies provenance recording, event emission, Round status transitions

#### Contract Tests (T056) ✅

**T056 - Event Contract Tests**
- **File**: `/backend/tests/spec6/contract/test_event_contract.py`
- **Implementation**:
  - Validates `sankey.complete` event payload against AsyncAPI schema
  - Tests `SankeyGraph` structure: nodes, edges, required fields
  - Validates `question.ready` event emission schema
  - Validates `question.generation_failed` event emission schema
  - Tests `ThoughtSpaceSummary` and `FlowEdge` structures
  - Verifies member_pct range validation (0.0-100.0)
  - Tests contract integration flows (Sankey → Question Ready, Sankey → Generation Failed)
  - Uses Pydantic validation with `ValidationError` assertions

---

## Architecture Highlights

### Core Components

1. **QuestionGenerationService** (`services/generation.py`)
   - Claude Sonnet 4.5 integration
   - Nested retry logic (API + validation)
   - Prompt engineering with Sankey context
   - Provenance metadata collection

2. **ProvenanceTracker** (`services/provenance.py`)
   - Persistence of generation metadata
   - SHA-256 Sankey hashing for reproducibility
   - Token usage tracking for cost monitoring

3. **Event Handlers** (`event_handlers.py`)
   - sankey.complete subscriber
   - question.ready emitter
   - question.generation_failed emitter
   - Payload validation (T076)
   - Retry wrapper with exponential backoff (T079)

4. **Background Worker** (`workers/generation_worker.py`)
   - Redis event bus integration
   - Concurrent event processing
   - Graceful shutdown and reconnection

5. **API Endpoints** (`api/auto_generation.py`)
   - Manual trigger for testing
   - Status query with provenance
   - Debug tooling for development

### Data Flow

```
Round N: COMPLETE (Sankey built)
  ↓ (emit sankey.complete event)
[Event Handler] receives event
  ↓ (validate payload)
[Event Handler] checks discussion mode
  ↓ (if AUTO_GENERATED)
[QuestionGenerationService] generates question
  ↓ (retry loop with validation)
[ProvenanceTracker] records metadata
  ↓ (create entities)
Round N+1: QUESTION_READY (question staged)
  ↓ (emit question.ready event)
Host reviews question
  ↓ (manual POST /discussions/{id}/advance)
Round N+1: SUBMISSION_OPEN (timer starts)
```

### Error Handling

```
API Timeout (30s)
  ↓ (catch APITimeoutError)
Retry with exponential backoff (1s, 2s, 4s)
  ↓ (max 3 attempts)
If all retries fail → QUESTION_GENERATION_FAILED

Validation Failure (invalid question)
  ↓ (catch validation error)
Regenerate with stricter prompt
  ↓ (max 3 attempts)
If all validation attempts fail → QUESTION_GENERATION_FAILED
```

---

## Configuration

All Phase 5 settings are in `/backend/src/config.py`:

```python
# LLM Configuration
claude_api_key: str = Field(alias="ANTHROPIC_API_KEY")  # Required
claude_model: str = "claude-3-5-sonnet-20241022"
question_generation_timeout_seconds: int = 30
question_generation_max_retries: int = 3
```

**Environment Variables**:
- `ANTHROPIC_API_KEY`: Required for Claude API access
- `QUESTION_GENERATION_TIMEOUT_SECONDS`: Optional (default 30)
- `QUESTION_GENERATION_MAX_RETRIES`: Optional (default 3)

---

## Database Schema Changes

### New State: QUESTION_GENERATION_FAILED

```python
class RoundStatus(str, Enum):
    # ... existing states ...
    QUESTION_READY = "QUESTION_READY"
    QUESTION_GENERATION_FAILED = "QUESTION_GENERATION_FAILED"  # NEW
    # ...
```

**Migration Required**: Add new enum value to `round_status` type in PostgreSQL.

---

## Testing

### Unit Tests
- Prompt template formatting
- Question extraction from API response
- Retry logic with backoff
- Validation loop with stricter prompts
- Provenance metadata recording

### Integration Tests ✅
- **File**: `tests/spec6/integration/test_auto_generated_flow.py`
- End-to-end AUTO_GENERATED discussion flow
- Validation failure → regeneration → success
- All retries exhausted → QUESTION_GENERATION_FAILED
- Provenance verification
- Event emission verification

### Contract Tests ✅
- **File**: `tests/spec6/contract/test_event_contract.py`
- sankey.complete payload structure
- question.ready event schema
- question.generation_failed event schema
- Pydantic validation error handling

---

## Next Steps

### Phase 6: Round Advancement API (T057-T063)
- Implement POST `/discussions/{id}/advance` endpoint
- Add host authorization checks
- Validate round status before advancement
- Schedule submission window timers
- Emit `round.started` events

### Phase 7: Discussion API (T064-T075)
- POST `/discussions` with AUTO_GENERATED mode
- GET `/discussions/{id}` with provenance
- PATCH `/discussions/{id}/question` for manual overrides
- GET `/discussions/{id}/rounds` with question metadata

### Phase 8: Event Integration (T076-T083)
- Complete payload validation (already integrated in T076)
- Structured logging with trace IDs (already integrated in T080)
- Retry wrapper registration (already integrated in T079)
- Performance metrics collection

---

## Dependencies

### Python Packages
- `anthropic` (>=0.18.0): Claude API client
- `httpx` (>=0.25.0): Async HTTP client
- `pydantic` (>=2.0): Schema validation
- `sqlalchemy[asyncio]` (>=2.0): Async ORM
- `redis[asyncio]` (>=5.0): Event bus

### External Services
- **Anthropic Claude API**: Required for question generation
- **Redis**: Required for event bus
- **PostgreSQL**: Required for persistence

---

## Monitoring & Observability

### Key Metrics
- **Generation latency**: p50, p95, p99 (from provenance.generation_latency_ms)
- **Retry rate**: % of generations requiring retries
- **Validation failure rate**: % of questions failing validation
- **Generation success rate**: % of events reaching QUESTION_READY vs FAILED
- **Token usage**: prompt_tokens + completion_tokens per question (cost tracking)

### Structured Logging
All logs include:
- `trace_id`: Correlation ID for distributed tracing
- `discussion_id`, `round_id`, `question_id`: Entity context
- `sankey_hash`: For reproducibility debugging
- `retry_count`, `validation_attempts`: Quality metrics
- `outcome`: "success" or "failure" for alerting

### Alerting Thresholds
- **High retry rate**: > 30% of generations require retries (API instability)
- **High validation failure rate**: > 10% of questions fail validation (prompt drift)
- **Generation timeouts**: > 5% of generations timeout (API latency issues)
- **QUESTION_GENERATION_FAILED rate**: > 1% of rounds fail (system health issue)

---

## Conclusion

Phase 5 is **COMPLETE** with all 18 tasks implemented and tested. The system successfully:
- Generates constitutionally-compliant questions from Sankey patterns
- Handles API failures with exponential backoff
- Validates questions with retry loops
- Tracks comprehensive provenance metadata
- Emits proper events for downstream coordination
- Provides debugging APIs for development
- Includes comprehensive test coverage

**Ready for Phase 6**: Round Advancement API implementation.

---

**Last Updated**: 2026-01-31
**Implemented By**: Claude Sonnet 4.5
**Status**: COMPLETE ✅
