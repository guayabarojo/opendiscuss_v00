# Question Validation Examples (Spec 006 - Phase 4)

This document provides quick reference examples for the Question Validation Pipeline implemented in Phase 4.

## Valid Questions ✅

### Exploratory Questions (What/How)

```python
# What questions
"What are the main challenges facing our community?"
"What opportunities should we prioritize in the coming year?"
"What perspectives exist on this topic?"
"What are your thoughts on climate change policies?"

# How questions
"How can we improve accessibility to resources?"
"How might we approach this problem differently?"
"How do you think we should allocate the budget?"
"How can we increase community engagement?"
```

### Edge Cases (Still Valid)

```python
# Minimum length (exactly 10 characters)
"What is x?"

# Maximum length (exactly 200 characters)
"What are your detailed thoughts on community participation and engagement with local initiatives, including feedback mechanisms and transparent decision-making processes?"  # 200 chars

# Case variations
"WHAT ARE YOUR THOUGHTS?"
"what are your thoughts?"
"How CAN WE IMPROVE?"
```

## Invalid Questions ❌

### 1. Invalid Opening Word (INVALID_START)

```python
# Rejected - don't start with What/How
"Which option should we consider?"
"When should we meet?"
"Where is the meeting?"
"Who is responsible for this?"
```

**Error Code**: `INVALID_START`
**Error Message**: "Question must start with 'What' or 'How'"

---

### 2. Prohibited Opening Words (CONTAINS_PROHIBITED_WORD)

```python
# Rejected - judgmental/leading questions
"Why is this important?"
"Do you agree with this proposal?"
"Should we implement this feature?"
"Would you support this initiative?"
"Would we benefit from this change?"
```

**Error Code**: `CONTAINS_PROHIBITED_WORD`
**Error Message**: "Question cannot start with 'why'" (or "do you", "should we", etc.)

---

### 3. Ranking/Voting Keywords (CONTAINS_RANKING_KEYWORD)

```python
# Rejected - adjudication/ranking language
"What is the best approach?"
"What is the worst outcome?"
"What should we vote on?"
"What can we rank by priority?"
"What is your top priority?"
"What is your favorite option?"
"What should we choose?"
"What should we select?"
"What do you prefer?"
"What makes a winner?"
"What is the better solution?"
```

**Rejected Keywords** (20+ total):
- vote, rank, order
- best, worst
- choose, select, pick, prefer
- favorite
- top, bottom, first, last
- winner, loser
- better, worse, superior, inferior

**Error Code**: `CONTAINS_RANKING_KEYWORD`
**Error Message**: "Question cannot contain ranking/voting keyword: 'best'"

---

### 4. Binary Choice Patterns (BINARY_CHOICE)

```python
# Rejected - binary choice questions
"What is your answer, yes or no?"
"What do you think, agree or disagree?"
"What is your stance, true or false?"
"What is your position: yes/no?"
"What do you think: agree vs disagree?"
```

**Rejected Patterns**:
- `yes or no`
- `agree or disagree`
- `true or false`
- `yes/no`, `agree/disagree` (with slash)

**Error Code**: `BINARY_CHOICE`
**Error Message**: "Question cannot be a binary choice (yes/no, agree/disagree)"

---

### 5. Invalid Length (INVALID_LENGTH)

```python
# Too short (< 10 characters)
"What?"        # 5 chars
"How are?"     # 8 chars

# Too long (> 200 characters)
"What are your extremely detailed thoughts on every single aspect of this incredibly complex topic including all the nuances, edge cases, contextual factors, historical precedents, potential future implications, and related considerations?" # 250 chars
```

**Error Code**: `INVALID_LENGTH`
**Error Message**: "Question must be 10-200 characters, got 5"

---

## Validation Flow

```
Input: "What is the best approach?"
         ↓
Step 1: Length check → PASS (24 chars, within 10-200)
         ↓
Step 2: Opening word → PASS (starts with "What")
         ↓
Step 3: Prohibited words → PASS (no Why/Do you/Should/Would)
         ↓
Step 4: Ranking keywords → FAIL (contains "best")
         ↓
Result: ValidationResult(
    valid=False,
    error_code="CONTAINS_RANKING_KEYWORD",
    error_message="Question cannot contain ranking/voting keyword: 'best'"
)
```

## API Usage

### Creating a Host-Defined Sequence

```http
POST /questions/sequences
Content-Type: application/json

{
  "discussion_id": "550e8400-e29b-41d4-a716-446655440000",
  "mode": "HOST_DEFINED",
  "questions": [
    "What are the main challenges?",
    "How can we address them?",
    "What opportunities exist?"
  ]
}
```

**Success Response (201)**:
```json
{
  "sequence_id": "...",
  "discussion_id": "...",
  "mode": "HOST_DEFINED",
  "total_questions": 3,
  "current_index": 0,
  "completion_status": "IN_PROGRESS",
  "questions": [...]
}
```

**Failure Response (400)** - Invalid Question:
```json
{
  "error": "VALIDATION_ERROR",
  "message": "Question 2 validation failed: Question cannot contain ranking/voting keyword: 'best'",
  "details": {
    "error_code": "CONTAINS_RANKING_KEYWORD"
  }
}
```

## Programmatic Usage

### Python Service Layer

```python
from src.question_progression.validators import validate_question

# Validate a question
result = validate_question("What are your thoughts?")

if result.valid:
    print(f"Valid: {result.validated_text}")
else:
    print(f"Invalid: {result.error_code} - {result.error_message}")
```

### Using QuestionSequenceService

```python
from src.question_progression.services.sequence import QuestionSequenceService

service = QuestionSequenceService(db_session)

try:
    sequence = await service.create_host_sequence(
        discussion_id=discussion_id,
        questions=["What are your thoughts?", "How can we improve?"]
    )
    print(f"Created sequence: {sequence.sequence_id}")
except ValidationError as e:
    print(f"Validation failed: {e.error_code} - {e.message}")
```

## Testing

### Unit Test Example

```python
from src.question_progression.validators import (
    QuestionValidator,
    ValidationErrorCode
)

def test_ranking_keyword_rejected():
    validator = QuestionValidator()
    result = validator.validate("What is the best approach?")

    assert result.valid is False
    assert result.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD
    assert "best" in result.error_message.lower()
```

### Integration Test Example

```python
import pytest
from src.question_progression.services.sequence import (
    QuestionSequenceService,
    ValidationError
)

@pytest.mark.asyncio
async def test_create_sequence_with_invalid_question(db_session):
    discussion_id = uuid.uuid4()
    service = QuestionSequenceService(db_session)

    with pytest.raises(ValidationError) as exc_info:
        await service.create_host_sequence(
            discussion_id=discussion_id,
            questions=["Why is this important?"]  # Invalid
        )

    assert exc_info.value.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD
```

## Constitutional Principle

**Principle VII: Representation Not Adjudication**

The validation rules enforce constitutional constraints:

1. ✅ **Exploratory framing**: Only What/How questions (no Why/Should)
2. ✅ **No voting**: Reject vote, rank, choose, select keywords
3. ✅ **No adjudication**: Reject best, worst, winner, loser keywords
4. ✅ **No binary choices**: Reject yes/no, agree/disagree patterns
5. ✅ **Clear boundaries**: 10-200 character range for clarity

These rules ensure the system **represents diverse perspectives** rather than **adjudicating "correct" answers**.

## Additional Notes

- **Case-insensitive**: Validation is case-insensitive ("BEST" and "best" both rejected)
- **Fail-fast**: Pipeline stops at first validation failure
- **Atomic**: If any question fails, no sequence/questions are created
- **Whitespace trimming**: Leading/trailing whitespace removed before validation
- **Immutability**: Once a round starts, questions cannot be edited

## References

- **Implementation**: `/backend/src/question_progression/validators.py`
- **Unit Tests**: `/backend/tests/spec6/unit/test_validation.py`
- **Integration Tests**: `/backend/tests/spec6/integration/test_host_defined_flow.py`
- **Constitution**: `/.specify/memory/constitution.md` (Principle VII)
