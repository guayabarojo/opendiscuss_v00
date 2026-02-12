# Error Handling Reference - Question Progression Protocol

Quick reference for error handling patterns in Spec 006 implementation.

## LLM Error Types & Responses

### 1. TimeoutError (30s exceeded)
**Cause**: Claude API call exceeds configured timeout

**Handling**:
- Exponential backoff: 1s, 2s, 4s
- Max 3 retries
- Logs: "Claude API timeout"

**Example**:
```python
except APITimeoutError as e:
    logger.warning("Claude API timeout", extra={"timeout_seconds": 30})
    if api_attempt < max_retries - 1:
        delay = 2 ** api_attempt  # 1s, 2s, 4s
        await asyncio.sleep(delay)
```

### 2. RateLimitError (429)
**Cause**: Claude API rate limit exceeded

**Handling**:
- Extended exponential backoff: 2s, 4s, 8s
- Max 3 retries
- Logs: "Claude API rate limit exceeded"

**Example**:
```python
except RateLimitError as e:
    logger.warning("Claude API rate limit exceeded")
    if api_attempt < max_retries - 1:
        delay = 2 ** (api_attempt + 1)  # 2s, 4s, 8s
        await asyncio.sleep(delay)
```

### 3. APIStatusError (500, 503)
**Cause**: Claude API service unavailable

**Handling**:
- Standard exponential backoff: 1s, 2s, 4s
- Max 3 retries
- Logs: "Claude API service error"

**Example**:
```python
except APIStatusError as e:
    logger.error("Claude API service error", extra={"status_code": e.status_code})
    if api_attempt < max_retries - 1:
        delay = 2 ** api_attempt
        await asyncio.sleep(delay)
```

### 4. AuthenticationError (401)
**Cause**: Invalid API key

**Handling**:
- **NO RETRY** (non-retryable error)
- Raises QuestionGenerationError immediately
- Logs: "Claude API authentication error"

**Example**:
```python
except AuthenticationError as e:
    logger.error("Claude API authentication error - invalid API key")
    raise QuestionGenerationError(f"Authentication failed: {str(e)}")
```

## Validation Error Handling

### Validation Failure → Regeneration Loop
**Cause**: Generated question fails constitutional validation

**Handling**:
1. First attempt fails validation
2. Regenerate with stricter prompt including:
   - Failed question text
   - Rejection reason
3. Max 3 validation attempts
4. If all fail → QuestionValidationExhausted

**Example**:
```python
validation_result = validator.validate(question_text)
if not validation_result.valid:
    failed_question = question_text
    rejection_reason = validation_result.error_message
    # Continue to next validation attempt with stricter prompt
```

## Fallback States

### QUESTION_GENERATION_FAILED
**Triggered When**:
- All 3 API retries exhausted (timeout/service errors)
- All 3 validation attempts exhausted
- Any unrecoverable error

**Round Status**: `RoundStatus.QUESTION_GENERATION_FAILED`

**Host Actions**:
1. Check generation status: `GET /auto-generation/status/{discussion_id}`
2. Provide manual question: `POST /questions/sequences` (or similar endpoint)
3. Round transitions to `QUESTION_READY`

**API Response**:
```json
{
  "generation_status": "FAILED",
  "manual_entry_required": true,
  "error_message": "Question generation failed after maximum retries. Please provide a question manually to continue the discussion."
}
```

## Immutability Enforcement

### Question Modification Rejection
**Endpoint**: `PATCH /questions/{question_id}`

**Rejection Criteria**:
- `question.immutable_since IS NOT NULL`

**HTTP Response**:
```json
{
  "error": "IMMUTABLE_QUESTION",
  "message": "Cannot modify question after round has started (Round 2). Question became immutable at 2026-01-31T12:34:56",
  "details": {
    "immutable_since": "2026-01-31T12:34:56",
    "round_num": 2
  }
}
```

**Status Code**: 400 Bad Request

## Sequence Integrity Validation

### validate_sequence_integrity()
**Location**: `src/question_progression/services/sequence.py`

**Validation Rules**:
1. No gaps in question order (1, 2, 3, ... no skips)
2. No duplicate order values
3. current_index <= total_questions count

**Exceptions**:

#### ORDER_GAP
```python
SequenceIntegrityError(
    "Gap in question sequence at order 2. Found order 4 instead. Sequence must be linear (1, 2, 3, ...).",
    violation="ORDER_GAP"
)
```

#### DUPLICATE_ORDER
```python
SequenceIntegrityError(
    "Duplicate question order 3 found in sequence {uuid}",
    violation="DUPLICATE_ORDER"
)
```

#### INDEX_OUT_OF_BOUNDS
```python
SequenceIntegrityError(
    "current_index (5) exceeds question count (3)",
    violation="INDEX_OUT_OF_BOUNDS"
)
```

**Usage**:
```python
service = QuestionSequenceService(db_session)
try:
    await service.validate_sequence_integrity(sequence_id)
except SequenceIntegrityError as e:
    logger.error(f"Sequence integrity violation: {e.violation}")
```

## Stall Detection

### detect_stalled_discussions()
**Location**: `src/services/discussion_service.py`

**Criteria**:
- Discussion status is ACTIVE
- Last activity timestamp > 7 days ago

**Usage** (cron job):
```python
service = DiscussionService(db_session, event_bus, timing_service)
stalled_discussions = await service.detect_stalled_discussions()

for discussion in stalled_discussions:
    # Notify host
    # Offer termination option
    pass
```

**Marks**: `discussion.is_stalled = True`

## Error Response Formats

### Standard Error Response
```python
class ErrorResponse(BaseModel):
    error: str           # Error code (e.g., "IMMUTABLE_QUESTION")
    message: str         # Human-readable message
    details: Optional[dict] = None  # Additional context
```

### Validation Error Response
```python
{
    "error": "VALIDATION_ERROR",
    "message": "Question 1 validation failed: Question must start with 'What' or 'How'",
    "details": {
        "error_code": "INVALID_STARTER"
    }
}
```

### Generation Status Response
```python
{
    "discussion_id": "uuid",
    "current_round_num": 2,
    "generation_status": "FAILED",  # SUCCESS | FAILED | IN_PROGRESS
    "question_ready": false,
    "manual_entry_required": true,
    "error_message": "Question generation failed after maximum retries...",
    "retry_count": 3,
    "validation_attempts": 3
}
```

## Logging Patterns

### Structured Logging
All error handlers use structured logging with context:

```python
logger.error(
    "Operation failed",
    extra={
        "error_type": type(e).__name__,
        "attempt": api_attempt + 1,
        "retry_count": retry_count,
        "validation_attempts": validation_attempts,
        # Additional context...
    },
    exc_info=True  # Include full stack trace
)
```

### Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Successful validation, normal operations |
| `INFO` | Successful generation, retry attempts |
| `WARNING` | Timeouts, rate limits, validation failures |
| `ERROR` | Service errors, authentication failures, unrecoverable errors |

## Configuration

### Error Handling Settings
**File**: `src/config.py`

```python
question_generation_timeout_seconds: int = 30  # Claude API timeout
question_generation_max_retries: int = 3       # Max retry attempts
```

## Testing Error Scenarios

### Unit Test Pattern
```python
@pytest.mark.asyncio
async def test_error_scenario(generation_service):
    with patch.object(service.client.messages, 'create') as mock_create:
        mock_create.side_effect = APITimeoutError("Timeout")

        with pytest.raises(QuestionGenerationError):
            await service.generate_from_sankey(...)
```

### Integration Test Pattern
```python
@pytest.mark.asyncio
async def test_recovery_flow(db_session):
    # 1. Trigger failure
    # 2. Verify QUESTION_GENERATION_FAILED status
    # 3. Provide manual question
    # 4. Verify recovery to QUESTION_READY
```

## Recovery Procedures

### Scenario 1: LLM Generation Fails
1. Check generation status: `GET /auto-generation/status/{discussion_id}`
2. Verify `generation_status == "FAILED"` and `manual_entry_required == true`
3. Create manual question:
   ```python
   question = Question(
       sequence_id=sequence_id,
       order=next_order,
       question_text="Manual question text",
       mode=QuestionMode.HOST_DEFINED,
       validation_status=ValidationStatus.VALID
   )
   ```
4. Update round:
   ```python
   round.question_id = question.question_id
   round.question_text = question.question_text
   round.status = RoundStatus.QUESTION_READY
   ```

### Scenario 2: Sequence Integrity Violation
1. Run integrity check: `validate_sequence_integrity(sequence_id)`
2. If gap detected: Renumber questions to fill gap
3. If duplicate: Update order field to make unique
4. If index out of bounds: Reset current_index

### Scenario 3: Discussion Stalled
1. Daily cron job detects stall
2. Host receives notification
3. Host options:
   - Resume discussion (send reminder to participants)
   - Terminate discussion
   - Extend deadline

## HTTP Status Codes

| Code | Usage | Example |
|------|-------|---------|
| 400 | Bad Request | Validation errors, immutable question edit |
| 404 | Not Found | Question/sequence not found |
| 409 | Conflict | Sequence already exists |
| 500 | Internal Error | Unhandled exceptions |

## Quick Checklist for Error Handling

When implementing new features:
- [ ] Handle all expected exceptions explicitly
- [ ] Use exponential backoff for retries
- [ ] Provide clear error messages
- [ ] Log with structured context
- [ ] Return actionable error responses
- [ ] Test error paths with unit tests
- [ ] Document recovery procedures
- [ ] Consider fallback states
- [ ] Validate inputs early
- [ ] Never fail silently

---

**Last Updated**: 2026-01-31
**Related**: PHASE9_ERROR_HANDLING_SUMMARY.md
