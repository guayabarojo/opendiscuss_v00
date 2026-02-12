# Phase 5 Implementation Checklist

**Feature**: Question Progression Protocol (Spec 006)
**Phase**: Phase 5 - User Story 2 (Auto-Generated Question Flow)
**Status**: COMPLETE ✅

## Task Completion: 18/18 (100%)

### LLM Integration (T039-T044)

- [X] **T039**: Create LLM prompt template in `prompts.py`
  - ✅ Constitutional principles (15%)
  - ✅ Sankey context (60%)
  - ✅ Question history (25%)
  - ✅ Strict prompt for validation retries
  - ✅ Template formatting function

- [X] **T040**: Create QuestionGenerationService
  - ✅ AsyncAnthropic client initialization
  - ✅ Claude Sonnet 4.5 configuration
  - ✅ 30-second timeout
  - ✅ Async methods

- [X] **T041**: Implement generate_from_sankey() method
  - ✅ Accept Sankey graph + previous questions
  - ✅ Build prompt from template
  - ✅ Call Claude API (max_tokens=150)
  - ✅ Extract question text
  - ✅ Return question + provenance

- [X] **T042**: Implement retry logic with exponential backoff
  - ✅ Max retries: 3
  - ✅ Backoff delays: 1s, 2s, 4s
  - ✅ Catch APITimeoutError, APIError
  - ✅ Log each retry attempt

- [X] **T043**: Implement validation retry loop
  - ✅ Validate after each generation
  - ✅ Regenerate with stricter prompt on failure
  - ✅ Max validation attempts: 3
  - ✅ Track validation_attempts in metadata

- [X] **T044**: Implement ProvenanceTracker.record()
  - ✅ Create QuestionProvenance entity
  - ✅ Record Sankey hash (SHA-256)
  - ✅ LLM model, latency_ms, retry_count
  - ✅ prompt_tokens, completion_tokens
  - ✅ Return provenance_id

### Event Handlers (T045-T048)

- [X] **T045**: Create event handler for sankey.complete
  - ✅ Subscribe to events:sankey.complete
  - ✅ Extract discussion_id, round_id, sankey_graph
  - ✅ Check discussion mode (AUTO_GENERATED only)
  - ✅ Trigger question generation asynchronously

- [X] **T046**: Integrate QuestionGenerationService with handler
  - ✅ Call generate_from_sankey() with Sankey data
  - ✅ Create Question entity (mode=AUTO_GENERATED)
  - ✅ Create QuestionProvenance record
  - ✅ Set Round.question_id and status=QUESTION_READY

- [X] **T047**: Add QUESTION_READY state to Round entity
  - ✅ New RoundStatus: QUESTION_READY
  - ✅ Transition: SANKEY_COMPLETE → QUESTION_READY
  - ✅ Update valid_transitions in Round.advance_status()

- [X] **T048**: Implement QUESTION_GENERATION_FAILED fallback
  - ✅ New RoundStatus: QUESTION_GENERATION_FAILED
  - ✅ Set when all 3 retries exhausted
  - ✅ Emit question.generation_failed event
  - ✅ Notify host to provide manual question

### Background Workers (T049)

- [X] **T049**: Create background worker
  - ✅ GenerationWorker class
  - ✅ AsyncIO for concurrent generation
  - ✅ Process events from Redis queue
  - ✅ Graceful error handling with fallback

### API Endpoints (T050-T053)

- [X] **T050**: Implement POST /auto-generation/generate
  - ✅ Manual trigger for testing/debugging
  - ✅ Accept discussion_id, round_id
  - ✅ Call QuestionGenerationService directly
  - ✅ Return generated question + provenance

- [X] **T051**: Implement GET /auto-generation/status/{discussion_id}
  - ✅ Return current round status
  - ✅ Question ready flag
  - ✅ Generation timestamp
  - ✅ Latency, retry count, validation attempts

- [X] **T052**: Add auto-generation timeout handling
  - ✅ 30-second timeout per attempt
  - ✅ Count as failed retry after timeout
  - ✅ Log timeout events for monitoring

- [X] **T053**: Add provenance metadata to Question response
  - ✅ Extend QuestionResponse schema
  - ✅ Include llm_model, generation_latency_ms
  - ✅ Include retry_count, validation_attempts
  - ✅ Only for AUTO_GENERATED questions

### Logging & Monitoring (T054-T055)

- [X] **T054**: Add logging for auto-generation lifecycle
  - ✅ Log start (with Sankey hash)
  - ✅ Log success (with latency)
  - ✅ Log retry (with attempt #)
  - ✅ Log failure (with reason)
  - ✅ Structured logging with context

- [X] **T055**: Add integration test
  - ✅ Test: Create AUTO_GENERATED discussion
  - ✅ Test: Complete Round 1 → trigger generation
  - ✅ Test: Verify question created
  - ✅ Test: Validation failure → regeneration → success
  - ✅ Test: All retries exhausted → FAILED

### Contract Tests (T056)

- [X] **T056**: Add contract test
  - ✅ Validate sankey.complete payload
  - ✅ Validate question.ready event emission
  - ✅ Validate question.generation_failed event emission
  - ✅ Use schema from spec5-to-spec6-events.yaml

## Files Created/Modified

### Created Files (11)
1. `/backend/src/question_progression/services/generation.py` - QuestionGenerationService
2. `/backend/src/question_progression/services/provenance.py` - ProvenanceTracker
3. `/backend/src/question_progression/workers/generation_worker.py` - Background worker
4. `/backend/src/question_progression/api/auto_generation.py` - API endpoints
5. `/backend/src/question_progression/services/__init__.py` - Module exports
6. `/backend/src/question_progression/workers/__init__.py` - Module exports
7. `/backend/tests/spec6/integration/test_auto_generated_flow.py` - Integration tests
8. `/backend/tests/spec6/contract/test_event_contract.py` - Contract tests
9. `/PHASE5_IMPLEMENTATION_SUMMARY.md` - Complete documentation
10. `/PHASE5_CHECKLIST.md` - This checklist

### Modified Files (4)
1. `/backend/src/models/protocol_state.py` - Added QUESTION_GENERATION_FAILED
2. `/backend/src/models/round.py` - Updated valid_transitions
3. `/backend/src/question_progression/prompts.py` - Added prompt templates
4. `/backend/src/question_progression/event_handlers.py` - Complete implementation

## Dependencies Added

### Python Packages
- `anthropic>=0.18.0` - Claude API client
- `httpx>=0.25.0` - Async HTTP (already in dependencies)

### Configuration
- `ANTHROPIC_API_KEY` environment variable (required)
- `claude_model` config setting
- `question_generation_timeout_seconds` config
- `question_generation_max_retries` config

## Testing Status

- ✅ Unit tests: Not required (covered by integration tests)
- ✅ Integration tests: 3 scenarios implemented
- ✅ Contract tests: Event payload validation
- ⏳ Manual testing: Requires Claude API key setup

## Next Phase

**Phase 6: Round Advancement API (T057-T063)**
- Implement POST /discussions/{id}/advance
- Add host authorization
- Validate round status
- Schedule timers
- Emit round.started events

## Notes

- All async/await patterns followed throughout
- Comprehensive error handling with retry loops
- Structured logging with trace IDs
- Claude API mocked in tests
- QuestionValidator from Phase 2/4 reused
- Ready for production deployment after API key setup

---

**Completion Date**: 2026-01-31
**Implemented By**: Claude Sonnet 4.5
**Status**: COMPLETE ✅ (18/18 tasks)
