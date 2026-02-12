# Phase 3 Quick Reference: Host-Defined Question Sequence

**Last Updated**: 2026-01-30

---

## Quick Start

### Create a Host-Defined Discussion

```python
import httpx

# 1. Create sequence via API
response = await client.post(
    "/api/v1/questions/sequences",
    json={
        "discussion_id": "550e8400-e29b-41d4-a716-446655440000",
        "mode": "HOST_DEFINED",
        "questions": [
            "What are the main challenges?",
            "How can we improve accessibility?",
            "What resources are needed?"
        ]
    }
)
# Returns: sequence with sequence_id, questions[]

# 2. Get sequence details
response = await client.get(
    "/api/v1/questions/sequences/{sequence_id}"
)
# Returns: full sequence with current_index, completion_status

# 3. Advance through rounds
# Host manually advances via Discussion API
await client.post(
    "/api/v1/discussions/{discussion_id}/advance"
)
```

---

## Service Layer Usage

### Create a Sequence (Python)

```python
from src.question_progression.services.sequence import QuestionSequenceService

service = QuestionSequenceService(db_session)

# Create host-defined sequence
sequence = await service.create_host_sequence(
    discussion_id=discussion_id,
    questions=[
        "What are the main challenges?",
        "How can we improve accessibility?",
        "What resources are needed?"
    ]
)

# Returns: QuestionSequence with questions[]
# Raises: ValidationError if any question fails validation
```

### Get Next Question

```python
# Get next question in sequence
question = await service.get_next_question(sequence_id)

if question:
    print(f"Order: {question.order}, Text: {question.question_text}")
else:
    print("All questions exhausted")
```

### Check Completion

```python
# Check if sequence is complete
was_completed = await service.check_and_mark_completion(sequence_id)

if was_completed:
    print("Discussion complete!")
```

---

## Validation Rules

### Valid Questions ✅

```python
# Must start with What or How
"What are the main challenges?"
"How can we improve accessibility?"
"What resources are needed?"
"How do participants feel about the proposal?"

# Length: 10-200 characters
"What now?"  # 9 chars - TOO SHORT ❌
"What is the current situation?"  # 35 chars - VALID ✅
```

### Invalid Questions ❌

```python
# Cannot start with Why, Do you, Should we, Would you
"Why is this important?"  # REJECTED - CONTAINS_PROHIBITED_WORD
"Do you agree with this?"  # REJECTED - CONTAINS_PROHIBITED_WORD
"Should we vote on this?"  # REJECTED - CONTAINS_PROHIBITED_WORD

# Cannot contain ranking/voting keywords
"What is the best option?"  # REJECTED - CONTAINS_RANKING_KEYWORD
"How should we rank the proposals?"  # REJECTED - CONTAINS_RANKING_KEYWORD
"What should we choose?"  # REJECTED - CONTAINS_RANKING_KEYWORD

# Cannot be binary choice
"What do you agree or disagree?"  # REJECTED - BINARY_CHOICE
```

---

## Error Codes Reference

| Error Code | Description | Example |
|------------|-------------|---------|
| `INVALID_LENGTH` | Question too short (<10) or too long (>200) | "What?" |
| `INVALID_START` | Must start with What or How | "Tell me about X" |
| `CONTAINS_PROHIBITED_WORD` | Starts with Why, Do you, Should, Would | "Why is this important?" |
| `CONTAINS_RANKING_KEYWORD` | Contains vote, rank, best, worst, etc. | "What is the best option?" |
| `BINARY_CHOICE` | Yes/no or agree/disagree question | "Do you agree?" |

---

## API Endpoints

### POST /api/v1/questions/sequences

**Request**:
```json
{
  "discussion_id": "uuid",
  "mode": "HOST_DEFINED",
  "questions": ["What...", "How..."]
}
```

**Response** (201):
```json
{
  "sequence_id": "uuid",
  "discussion_id": "uuid",
  "mode": "HOST_DEFINED",
  "total_questions": 2,
  "current_index": 0,
  "completion_status": "IN_PROGRESS",
  "questions": [...]
}
```

**Errors**:
- 400: Validation error
- 409: Sequence already exists

### GET /api/v1/questions/sequences/{sequence_id}

**Response** (200):
Same as POST response

**Errors**:
- 404: Sequence not found

### GET /api/v1/questions/discussions/{discussion_id}/questions

**Response** (200):
Returns sequence for discussion

**Errors**:
- 404: No sequence found

### POST /api/v1/questions/validate

**Query Params**: `?question_text="What..."`

**Response** (200):
```json
{
  "valid": true,
  "validated_text": "What are the challenges?",
  "error": null,
  "error_code": null
}
```

---

## Testing

### Run Unit Tests

```bash
# All unit tests
pytest backend/tests/spec6/unit/test_sequence_service.py -v

# Specific test class
pytest backend/tests/spec6/unit/test_sequence_service.py::TestCreateHostSequence -v

# Single test
pytest backend/tests/spec6/unit/test_sequence_service.py::TestCreateHostSequence::test_create_valid_sequence -v
```

### Run Integration Tests

```bash
# All integration tests
pytest backend/tests/spec6/integration/test_sequence_api.py -v

# Specific endpoint tests
pytest backend/tests/spec6/integration/test_sequence_api.py::TestCreateSequenceEndpoint -v
```

### Run All Phase 3 Tests

```bash
pytest backend/tests/spec6/ -v -k "sequence"
```

---

## Database Queries

### Get Sequence for Discussion

```sql
SELECT * FROM question_sequences WHERE discussion_id = 'uuid';
```

### Get All Questions in Sequence

```sql
SELECT * FROM questions
WHERE sequence_id = 'uuid'
ORDER BY "order" ASC;
```

### Get Current Question

```sql
SELECT q.*
FROM questions q
JOIN question_sequences qs ON q.sequence_id = qs.sequence_id
WHERE qs.discussion_id = 'uuid'
  AND q."order" = qs.current_index + 1;
```

### Get Immutable Questions

```sql
SELECT * FROM questions
WHERE immutable_since IS NOT NULL
ORDER BY immutable_since DESC;
```

---

## Logging Examples

### Successful Creation

```json
{
  "level": "INFO",
  "message": "Creating host-defined question sequence",
  "sequence_id": "uuid",
  "discussion_id": "uuid",
  "question_count": 3
}
```

### Validation Failure

```json
{
  "level": "WARNING",
  "message": "Question validation failed",
  "sequence_id": "uuid",
  "question_index": 2,
  "error_code": "CONTAINS_RANKING_KEYWORD",
  "error_message": "Question cannot contain ranking/voting keyword: 'best'"
}
```

### Question Marked Immutable

```json
{
  "level": "INFO",
  "message": "Marked question as immutable",
  "question_id": "uuid",
  "immutable_since": "2026-01-30T12:00:00Z"
}
```

---

## Common Patterns

### Create Discussion with Questions

```python
from src.question_progression.services.sequence import QuestionSequenceService
from src.models.discussion import Discussion, DiscussionMode

# 1. Create discussion
discussion = Discussion(
    community_id=community_id,
    host_user_id=host_user_id,
    mode=DiscussionMode.HOST_DEFINED,
    total_rounds=3,
)
db.add(discussion)
await db.flush()

# 2. Create question sequence
service = QuestionSequenceService(db)
try:
    sequence = await service.create_host_sequence(
        discussion_id=discussion.discussion_id,
        questions=["What...", "How...", "What..."],
    )
    await db.commit()
except ValidationError as e:
    await db.rollback()
    raise HTTPException(400, detail=str(e))
```

### Advance Through Questions

```python
# Get next question
question = await service.get_next_question(sequence.sequence_id)

if question:
    # Link question to round
    round.question_id = question.question_id

    # Open round (marks question immutable)
    round.open_submission_window()

    await db.commit()
else:
    # All questions exhausted, mark complete
    await service.check_and_mark_completion(sequence.sequence_id)
```

### Handle Validation Errors

```python
from src.question_progression.services.sequence import ValidationError
from src.question_progression.validators import ValidationErrorCode

try:
    sequence = await service.create_host_sequence(...)
except ValidationError as e:
    if e.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD:
        print("Remove ranking keywords (best, worst, etc.)")
    elif e.error_code == ValidationErrorCode.INVALID_START:
        print("Question must start with 'What' or 'How'")
    else:
        print(f"Validation error: {e.message}")
```

---

## Troubleshooting

### Issue: 409 Conflict - Sequence Already Exists

**Cause**: Attempting to create a second sequence for the same discussion

**Solution**: Each discussion can only have one sequence. Use GET endpoint to retrieve existing sequence.

```python
# Check if sequence exists first
sequence = await service.get_sequence_by_discussion(discussion_id)
if sequence:
    print("Sequence already exists")
else:
    sequence = await service.create_host_sequence(...)
```

### Issue: 400 Bad Request - Validation Error

**Cause**: Question violates constitutional constraints

**Solution**: Check error_code and rephrase question

```python
# Use validation endpoint to check before creation
response = await client.post(
    "/api/v1/questions/validate",
    params={"question_text": "Why is this important?"}
)
# Returns: valid=False, error_code="CONTAINS_PROHIBITED_WORD"
```

### Issue: Question Immutability Violation

**Cause**: Attempting to edit question after round started

**Solution**: Questions cannot be edited once immutable_since is set. Create a new question or terminate the round.

```python
# Check if question is immutable
if question.is_immutable():
    print("Cannot edit: question is immutable")
else:
    # Can still edit
    question.question_text = "Updated text"
```

---

## Performance Tips

1. **Use eager loading**: Service layer uses `selectinload()` for questions
2. **Cache sequences**: Sequences rarely change after creation
3. **Batch question creation**: All questions created in single transaction
4. **Index optimization**: Queries use indexed columns (discussion_id, sequence_id, order)

---

## Related Documentation

- **Full Implementation Summary**: `/PHASE3_IMPLEMENTATION_SUMMARY.md`
- **Spec 006 Plan**: `/specs/006-question-progression/plan.md`
- **Data Model**: `/specs/006-question-progression/data-model.md`
- **API Contracts**: `/specs/006-question-progression/contracts/question-api.yaml`
- **Tasks**: `/specs/006-question-progression/tasks.md`

---

## Next Steps

**Phase 4**: Auto-Generated Question Flow (User Story 2)
- Claude API integration for question generation
- Sankey pattern analysis
- Provenance tracking
- QUESTION_READY state

See `/specs/006-question-progression/tasks.md` for T039-T056.
