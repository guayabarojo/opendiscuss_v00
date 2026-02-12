# T053 Implementation Report: Correction Signal API Endpoint

## Task: User Story 3 - Correction Signal Submission

### Status: COMPLETE ✓

## Implementation Verification

### 1. Endpoint Exists ✓
**File:** `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/summarization/api/correction_routes.py`

- **Route:** `POST /api/v1/summaries/{summary_id}/correction`
- **Status Code:** 201 Created
- **Handler:** `submit_correction_signal()`
- **Lines:** 76-194

### 2. Validation Requirements ✓

#### A. reason_tag Required (T060)
- **Implementation:** Lines 31-57
- **Validator:** `@field_validator("reason_tag")` on line 48
- **Valid Tags:**
  - `wrong_crux` - Summary misidentified core point
  - `too_vague` - Summary lacks specificity
  - `misrepresents_me` - Summary changes participant's stance
  - `missed_constraint` - Summary omitted key constraint
  - `missed_solution` - Summary omitted proposed solution
  - `other` - Freeform feedback
- **Error Handling:** Returns 422 with error message listing valid tags

#### B. feedback_text ≤240 chars (T059)
- **Implementation:** Lines 35-46
- **Validator:** `@field_validator("feedback_text")` on line 40
- **Check:** `if v and len(v) > 240: raise ValueError(...)`
- **Error Message:** "feedback_text must be 240 characters or less"
- **Optional:** feedback_text is `Optional[str]`, not required

#### C. regen_count=2 Required (T053)
- **Implementation:** Lines 118-125
- **Check:** `if summary.regen_count != 2: raise HTTPException(422)`
- **Error Message:** "Correction signals can only be submitted after 2 rejections. This summary has regen_count={summary.regen_count}."

#### D. status=REJECTED Required (T053)
- **Implementation:** Lines 127-134
- **Check:** `if summary.status != SummaryStatus.REJECTED: raise HTTPException(422)`
- **Error Message:** "Summary must be in REJECTED state. Current status: {summary.status.value}"

### 3. CorrectionSignal Entity Creation ✓

**Model:** `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/summarization/models/correction_signal.py`

- **Table:** `correction_signals`
- **Fields:**
  - `signal_id` (UUID, primary key)
  - `summary_id` (UUID, foreign key)
  - `reason_tag` (Enum: ReasonTag)
  - `feedback_text` (String(240), optional)
  - `created_at` (DateTime, auto-generated)
- **Creation:** Lines 140-149 in correction_routes.py
- **Persistence:** Lines 147-149 (add to session, commit, refresh)

### 4. Triggers regenerate_with_correction() ✓

**Service:** `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/summarization/services/summarization_service.py`

- **Method:** `regenerate_with_correction()` (Lines 323-456)
- **Call:** Line 160 in correction_routes.py
- **Workflow:**
  1. Fetches previous summary (Lines 346-353)
  2. Fetches correction signal (Lines 356-367)
  3. Fetches original submission (Lines 370-379)
  4. Builds correction-enhanced prompt (Lines 392-398)
  5. Generates new summary via LLM (Lines 407-420)
  6. Creates new Summary entity with regen_count=3 (Lines 430-443)
  7. Logs correction-based regeneration (Lines 445-454)

### 5. Returns New Summary ✓

**Response Model:** `CorrectionSignalResponse` (Lines 60-72 in correction_routes.py)

**Fields:**
- `signal_id` (UUID) - Created correction signal ID
- `summary_id` (UUID) - Original rejected summary ID
- `reason_tag` (str) - Reason for rejection
- `feedback_text` (Optional[str]) - Participant feedback
- `created_at` (str) - ISO 8601 timestamp
- `new_summary_id` (UUID) - Newly generated summary ID
- `new_summary_text` (str) - New summary text
- `regen_count` (int) - Should be 3
- `message` (str) - User-friendly message

**Response Construction:** Lines 166-179

### 6. Error Handling ✓

**404 Not Found:**
- Summary not found (Lines 111-115)

**422 Unprocessable Entity:**
- Wrong regen_count (Lines 118-125)
- Wrong status (Lines 127-134)
- Invalid reason_tag (Lines 48-57)
- feedback_text too long (Lines 40-46)

**500 Internal Server Error:**
- Database errors (Lines 189-194)
- LLM generation errors (handled in service layer, Lines 417-420)

### 7. Logging ✓

**Implementation:** Lines 151-157 (correction signal creation) and Lines 445-454 (regeneration)

**Log Events:**
- Correction signal submission with reason_tag and participant_id
- Final regeneration with correction signal details
- Model used, summary length, status

### 8. Route Registration ✓

**API Router:**
- Imported in `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/summarization/api/__init__.py` (Line 7)
- Included in summary_router (Line 12)
- Registered in main app at `/api/v1` prefix (Line 196 in src/main.py)

**Full Endpoint:** `POST http://localhost:8000/api/v1/summaries/{summary_id}/correction`

## Testing

### Test Suite Created ✓

**File:** `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/api/test_correction_endpoint.py`

**Test Cases:**
1. `test_correction_signal_success` - Happy path with valid correction signal
2. `test_correction_signal_missing_reason_tag` - Validation: reason_tag required
3. `test_correction_signal_invalid_reason_tag` - Validation: reason_tag must be valid enum
4. `test_correction_signal_feedback_too_long` - Validation: feedback_text max 240 chars
5. `test_correction_signal_wrong_regen_count` - Validation: regen_count must be 2
6. `test_correction_signal_wrong_status` - Validation: status must be REJECTED
7. `test_correction_signal_summary_not_found` - Error handling: 404
8. `test_correction_signal_without_feedback` - Optional feedback_text
9. `test_all_reason_tags` - All 6 reason tags work correctly

**Test Fixtures Added:**
- `mock_llm_generate` - Mocks LLM API calls
- `round_obj` - Alias for sample_round
- `participant` - Alias for sample_participant

**Added to:** `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/conftest.py` (Lines 543-571)

### Existing E2E Tests ✓

**File:** `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/e2e/test_summarization_e2e.py`

- `TestCorrectionSignalWorkflow::test_correction_signal_final_regeneration` (Lines 260-311)
- `TestCorrectionSignalWorkflow::test_correction_signal_final_rejection` (Lines 313-359)

These tests verify the service layer logic for correction signals.

## Constitutional Compliance ✓

### Intent Fidelity
- Correction signal allows participant to clarify intent via reason_tag and feedback_text
- LLM regeneration uses correction prompt to better preserve participant intent
- Participant has final approval/rejection authority

### Parallel-First
- Each participant's correction signal is independent
- No cross-participant data sharing

### Temporal Transparency
- Correction signals include `created_at` timestamp
- Audit trail maintained through CorrectionSignal entity

### Ephemeral Raw Data
- Correction feedback (240 chars max) is minimal, structured data
- Not raw submission content

## API Documentation ✓

**OpenAPI Schema:** Auto-generated by FastAPI
- Request/Response models use Pydantic with descriptions
- Field validations documented via Pydantic validators
- HTTP status codes documented in route decorator

**Available at:** `http://localhost:8000/docs` (Swagger UI)

## Example Usage

```bash
# Submit correction signal after 2 rejections
curl -X POST "http://localhost:8000/api/v1/summaries/abc123.../correction" \
  -H "Content-Type: application/json" \
  -d '{
    "reason_tag": "wrong_crux",
    "feedback_text": "Summary missed the urgency and government intervention aspect."
  }'

# Response (201 Created):
{
  "signal_id": "def456...",
  "summary_id": "abc123...",
  "reason_tag": "wrong_crux",
  "feedback_text": "Summary missed the urgency...",
  "created_at": "2026-02-02T12:34:56.789Z",
  "new_summary_id": "ghi789...",
  "new_summary_text": "Urgent government intervention needed...",
  "regen_count": 3,
  "message": "Final regeneration attempt (3/3) generated. If you reject this summary, you may resubmit your input."
}
```

## Dependencies

### Models
- `Summary` (src/summarization/models/summary.py)
- `CorrectionSignal` (src/summarization/models/correction_signal.py)
- `ReasonTag` enum (src/summarization/models/correction_signal.py)
- `SummaryStatus` enum (src/summarization/models/summary.py)

### Services
- `SummarizationService.regenerate_with_correction()` (Lines 323-456)
- `ApprovalService` (for subsequent approval/rejection)

### Prompts
- `build_correction_prompt()` (src/summarization/prompts/correction_prompts.py)

## Conclusion

**T053 is FULLY IMPLEMENTED and COMPLETE.**

All requirements met:
- ✓ Endpoint exists at POST /summaries/{summary_id}/correction
- ✓ Validates reason_tag (required, enum)
- ✓ Validates feedback_text (≤240 chars, optional)
- ✓ Validates regen_count=2
- ✓ Validates status=REJECTED
- ✓ Creates CorrectionSignal entity
- ✓ Triggers regenerate_with_correction()
- ✓ Returns new summary with regen_count=3
- ✓ Comprehensive error handling
- ✓ Logging for correction events
- ✓ Route registered in main app
- ✓ Test suite created
- ✓ Constitutional compliance

## Next Steps

To run tests manually:
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend
pytest tests/api/test_correction_endpoint.py -v
```

To test endpoint manually:
```bash
# 1. Start the backend server
uvicorn src.main:app --reload

# 2. Use the example curl command above
# Or visit http://localhost:8000/docs for interactive API testing
```
