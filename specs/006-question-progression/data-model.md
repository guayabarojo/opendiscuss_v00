# Data Model: Question Progression Protocol

**Feature**: 006-question-progression
**Date**: 2026-01-29
**Status**: Complete

## Overview

This document defines all entities, relationships, and validation rules for the Question Progression Protocol. The data model supports dual-mode question sequencing (host-defined + auto-generated), constraint validation, provenance tracking, and round advancement control.

---

## Entity Relationship Diagram

```
Discussion (1) ─────< (N) QuestionSequence
     │                      │
     │                      └─────< (N) Question
     │                               │
     │                               └────> (1) QuestionProvenance (AUTO mode only)
     │
     └─────< (N) Round (extends Spec 1 entity)
              │
              └────> (1) Question (FK to question_id)
```

---

## Core Entities

### 1. QuestionSequence

**Purpose**: Ordered collection of questions for a discussion. In HOST_DEFINED mode, all questions are created at discussion creation. In AUTO_GENERATED mode, questions are added incrementally after each Sankey completes.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `sequence_id` | UUID | PK, NOT NULL | Unique identifier |
| `discussion_id` | UUID | FK, NOT NULL, UNIQUE | One sequence per discussion |
| `mode` | Enum | NOT NULL | HOST_DEFINED \| AUTO_GENERATED |
| `total_questions` | Integer | NULL | Fixed count (HOST mode only), NULL in AUTO mode |
| `current_index` | Integer | NOT NULL, >= 0 | Index of current question (0-based) |
| `completion_status` | Enum | NOT NULL | IN_PROGRESS \| COMPLETED \| TERMINATED |
| `created_at` | Timestamp | NOT NULL | Sequence creation timestamp |

**Relationships**:
- Belongs to Discussion (`discussion_id`)
- Has many Questions (1:N)

**Mode-Specific Rules**:
- **HOST_DEFINED**: `total_questions` set at creation (1-10), all Questions created upfront
- **AUTO_GENERATED**: `total_questions` is NULL, Questions added incrementally

**Validation Rules**:
- `mode` cannot be changed after creation (immutable)
- `total_questions` MUST be 1-10 for HOST_DEFINED mode
- `total_questions` MUST be NULL for AUTO_GENERATED mode
- `current_index` MUST be < COUNT(Questions) in sequence
- `completion_status = COMPLETED` only when all rounds complete (HOST mode) or host terminates

**Indexes**:
- `(discussion_id)` - Unique constraint, one sequence per discussion

---

### 2. Question

**Purpose**: Individual question within a sequence. Represents the prompt displayed to participants during a round.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `question_id` | UUID | PK, NOT NULL | Unique identifier |
| `sequence_id` | UUID | FK, NOT NULL | Parent sequence |
| `order` | Integer | NOT NULL, >= 1 | Sequential order (1-indexed) |
| `question_text` | String | NOT NULL, 10-200 chars | Validated question text |
| `mode` | Enum | NOT NULL | HOST_DEFINED \| AUTO_GENERATED |
| `validation_status` | Enum | NOT NULL | VALID \| REJECTED \| PENDING |
| `created_at` | Timestamp | NOT NULL | Question creation timestamp |
| `immutable_since` | Timestamp | NULL | Set when round starts (SUBMISSION_OPEN) |

**Relationships**:
- Belongs to QuestionSequence (`sequence_id`)
- Has one QuestionProvenance (1:1, AUTO mode only)
- Referenced by Round (`round.question_id`)

**Validation Rules**:
- `question_text` MUST start with "What" or "How" (case-insensitive)
- `question_text` MUST NOT start with "Why", "Do you", "Should we", "Would you"
- `question_text` MUST NOT contain "vote", "rank", "best", "worst", "choose", "select", "pick"
- `question_text` MUST be 10-200 characters
- `question_text` is immutable once `immutable_since` is set (round started)
- `(sequence_id, order)` MUST be unique (no gaps in sequence)
- `validation_status = VALID` required before round can begin

**Constitutional Guarantee** (Representation Not Adjudication - Principle VII):
- Zero questions with ranking/voting keywords pass validation
- All questions are exploratory (What/How) and open-ended

**Indexes**:
- `(sequence_id, order)` - Unique constraint, ordered question lookup
- `(question_id)` - Fast lookups for round assignment

---

### 3. QuestionProvenance

**Purpose**: Metadata tracking for auto-generated questions. Supports audit, debugging, and quality monitoring.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `provenance_id` | UUID | PK, NOT NULL | Unique identifier |
| `question_id` | UUID | FK, NOT NULL, UNIQUE | One provenance per auto-generated question |
| `generation_timestamp` | Timestamp | NOT NULL | When question was generated |
| `generation_latency_ms` | Float | NOT NULL, >= 0 | Time from request to completion |
| `input_sankey_hash` | String(64) | NOT NULL | SHA-256 of Sankey JSON (reproducibility) |
| `input_round_id` | UUID | FK, NOT NULL | Round that triggered generation (N generates N+1 question) |
| `llm_model` | String(100) | NOT NULL | Model identifier (e.g., "claude-sonnet-4-5") |
| `prompt_tokens` | Integer | NOT NULL, >= 0 | Token count for prompt |
| `completion_tokens` | Integer | NOT NULL, >= 0 | Token count for response |
| `retry_count` | Integer | NOT NULL, >= 0, DEFAULT 0 | Number of retries (API failures) |
| `validation_attempts` | Integer | NOT NULL, >= 1, DEFAULT 1 | Number of validation attempts (constraint failures) |
| `previous_questions_count` | Integer | NOT NULL, >= 0 | Number of prior questions in context |

**Relationships**:
- Belongs to Question (`question_id`)
- References Round (`input_round_id` - the round whose Sankey triggered generation)

**Validation Rules**:
- Only AUTO_GENERATED questions have provenance records
- `retry_count` <= 3 (MAX_RETRIES exceeded triggers fallback)
- `validation_attempts` <= 3 (MAX_VALIDATION_ATTEMPTS exceeded triggers fallback)
- `generation_latency_ms` < 30000 (30-second timeout enforced)
- `input_sankey_hash` MUST match SHA-256 of actual Sankey JSON at `input_round_id`

**Monitoring Alerts**:
- Alert if AVG(`retry_count`) > 1 over 1 hour (API instability)
- Alert if AVG(`validation_attempts`) > 1.5 over 1 hour (prompt drift or model regression)
- Alert if p95(`generation_latency_ms`) > 10000 (10 seconds) (performance degradation)

**Indexes**:
- `(question_id)` - Unique constraint
- `(input_round_id)` - Find questions generated from specific round
- `(generation_timestamp)` - Time-series queries for monitoring

---

## Extended Entities (Spec 1 Extensions)

### 4. Round (Extended from Spec 1)

**New Fields for Question Progression**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `question_id` | UUID | FK, NULL | References Question entity (NULL until question assigned) |

**New State for AUTO Mode**:
```python
class RoundStatus(str, Enum):
    # ... existing states from Spec 1 ...
    QUESTION_READY = "QUESTION_READY"  # AUTO mode only: question generated, awaiting host trigger
    QUESTION_GENERATION_FAILED = "QUESTION_GENERATION_FAILED"  # Fallback to manual entry
```

**State Transitions (AUTO_GENERATED mode)**:
```
Round N: COMPLETE (Sankey built)
  ↓ (automatic, <30 seconds)
[Spec 6] Auto-generate question from Sankey
  ↓ (success)
Round N+1: QUESTION_READY (question_id set, awaiting host trigger)
  ↓ (manual, host POSTs /discussions/{id}/advance)
Round N+1: SUBMISSION_OPEN (timer starts)

OR

  ↓ (generation failure after 3 retries)
Round N+1: QUESTION_GENERATION_FAILED (question_id NULL, host must provide manual question)
```

**Validation Rules**:
- `question_id` MUST NOT be NULL when `status = SUBMISSION_OPEN`
- `question_id` MUST reference a Question with `validation_status = VALID`
- `question_id` is immutable once `status = SUBMISSION_OPEN` (question cannot be changed mid-round)

**Indexes**:
- `(question_id)` - Join to Question for round details

---

## State Machine Summary

### HOST_DEFINED Mode Lifecycle

```
1. Discussion creation:
   ├─ Create QuestionSequence (mode=HOST_DEFINED, total_questions=N)
   ├─ Validate all N questions (What/How, no voting/ranking)
   └─ Create N Question entities (order 1..N, validation_status=VALID)

2. Round advancement (repeated N times):
   ├─ Round created with question_id = Questions[current_index].question_id
   ├─ Host POSTs /discussions/{id}/advance
   ├─ Round.status → SUBMISSION_OPEN
   ├─ Question.immutable_since = now() (locked)
   └─ [Continue through Spec 1 round lifecycle]

3. Completion:
   ├─ Round N completes (all questions exhausted)
   └─ QuestionSequence.completion_status → COMPLETED
```

### AUTO_GENERATED Mode Lifecycle

```
1. Discussion creation:
   ├─ Create QuestionSequence (mode=AUTO_GENERATED, total_questions=NULL)
   ├─ Validate initial question (What/How, no voting/ranking)
   └─ Create Question (order=1, mode=HOST_DEFINED, validation_status=VALID)

2. Round 1:
   ├─ Round created with question_id = Questions[0].question_id
   ├─ Host POSTs /discussions/{id}/advance
   ├─ Round.status → SUBMISSION_OPEN
   └─ [Continue through Spec 1 round lifecycle until COMPLETE]

3. Auto-generation (after each Sankey completes):
   ├─ Spec 5 emits sankey.complete event
   ├─ Spec 6 subscribes and triggers generation:
   │   ├─ Build prompt (Sankey + previous questions)
   │   ├─ Call LLM API (Claude Sonnet 4.5, max 3 retries)
   │   ├─ Validate response (What/How, no voting/ranking, max 3 attempts)
   │   └─ Create Question + QuestionProvenance
   ├─ Round N+1.status → QUESTION_READY
   └─ Round N+1.question_id = newly generated Question

4. Continuation or termination:
   ├─ Host reviews auto-generated question in QUESTION_READY state
   ├─ Host POSTs /discussions/{id}/advance (continue)
   │   └─ Repeat step 2-3 for subsequent rounds
   └─ OR Host POSTs /discussions/{id}/terminate (end discussion)
       └─ QuestionSequence.completion_status → TERMINATED
```

---

## Validation Summary

### Question Validation Pipeline (5 Checks)

```python
def validate_question(text: str) -> ValidationResult:
    """Validate question against constitutional constraints"""

    # Check 1: Length
    if not (10 <= len(text) <= 200):
        return ValidationResult(valid=False, error="Length must be 10-200 characters")

    # Check 2: Opening word (What or How)
    if not text.lower().startswith(("what", "how")):
        return ValidationResult(valid=False, error="Must start with 'What' or 'How'")

    # Check 3: Prohibited openings
    prohibited = ["why", "do you", "should we", "would you", "would"]
    if any(text.lower().startswith(p) for p in prohibited):
        return ValidationResult(valid=False, error=f"Cannot start with prohibited word")

    # Check 4: Ranking/voting keywords
    keywords = ["vote", "rank", "best", "worst", "choose", "select", "pick"]
    if any(kw in text.lower() for kw in keywords):
        return ValidationResult(valid=False, error="Cannot contain ranking/voting keywords")

    # Check 5: Binary choice patterns
    if re.search(r"(yes|no|agree|disagree)\s*(or|/)\s*(yes|no|agree|disagree)\?$", text.lower()):
        return ValidationResult(valid=False, error="Cannot be yes/no or binary choice")

    return ValidationResult(valid=True, validated_text=text.strip())
```

**Validation Timing**:
- **HOST_DEFINED**: All questions validated at discussion creation (before DB commit)
- **AUTO_GENERATED**: Each question validated immediately after LLM generation

**Validation Failure Handling**:
- **HOST_DEFINED**: Reject discussion creation with specific error message
- **AUTO_GENERATED**: Retry generation with stricter prompt (up to 3 attempts), then fallback to QUESTION_GENERATION_FAILED

---

## Immutability and Integrity Guarantees

### Question Text Immutability

**Rule**: `question_text` is immutable once `Question.immutable_since` is set (when round transitions to SUBMISSION_OPEN)

**Enforcement**:
1. Database-level: `CHECK` constraint prevents updates when `immutable_since IS NOT NULL`
2. ORM-level: SQLAlchemy `__setattr__` override raises `ImmutabilityViolation`
3. API-level: PATCH endpoints reject requests with 400 error
4. UI-level: Edit controls disabled in frontend

**Exceptions**:
- **Before round starts**: Question can be edited if round is in PENDING or QUESTION_READY state
- **After termination**: Historical questions cannot be edited (audit integrity)

### Sequence Integrity

**Rule**: Questions in a sequence must be contiguous (no gaps in `order` values)

**Enforcement**:
- HOST_DEFINED: All questions created atomically at discussion creation (transaction ensures completeness)
- AUTO_GENERATED: Questions created sequentially; new question only created after previous round completes

**Validation Queries**:
```sql
-- Check for gaps in sequence
SELECT sequence_id, order
FROM questions
WHERE (sequence_id, order + 1) NOT IN (
    SELECT sequence_id, order FROM questions
)
AND order < (SELECT MAX(order) FROM questions q2 WHERE q2.sequence_id = questions.sequence_id);

-- Result should be empty (no gaps)
```

---

## Dropdown and Natural Mass Shrinkage

**Integration with Spec 1 Participant Tracking**:
- Participants who don't submit in Round N+1 generate NO outgoing flows from Round N
- Question Progression does NOT create synthetic "No Response" questions or states
- Dropout is visible through reduced flow mass in Sankey (Spec 5), not through question logic

**Implications**:
- Questions are independent of participant presence (same question shown regardless of dropout)
- Host can observe dropout in Sankey and choose to terminate or continue
- AUTO mode generation considers dropout patterns in Sankey (e.g., "How can we address the high dropout from funding constraints?")

---

## Performance Considerations

### Indexes

All foreign keys indexed for join performance:
- `QuestionSequence.discussion_id` (1:1 lookup)
- `Question.sequence_id` (ordered question fetch)
- `Question.question_id` (round assignment)
- `QuestionProvenance.question_id` (provenance lookup)
- `QuestionProvenance.input_round_id` (find questions generated from round)

### Caching (Redis)

Cache frequently accessed data:
- Current question for active round (TTL: 10 minutes)
- Question sequence for discussion (invalidate on termination)
- Validation results for host-defined questions (TTL: 24 hours)

### Query Optimization

**Common Query 1**: Get current question for active round
```sql
SELECT q.question_text, q.order, r.status
FROM rounds r
JOIN questions q ON r.question_id = q.question_id
WHERE r.discussion_id = :discussion_id
  AND r.status = 'SUBMISSION_OPEN'
LIMIT 1;
```
- Index: `(discussion_id, status)` on rounds + `(question_id)` on questions
- Expected: <5ms (indexed join on UUID keys)

**Common Query 2**: Get all questions for discussion (HOST mode, for display)
```sql
SELECT q.question_text, q.order, q.mode
FROM questions q
JOIN question_sequences qs ON q.sequence_id = qs.sequence_id
WHERE qs.discussion_id = :discussion_id
ORDER BY q.order ASC;
```
- Index: `(discussion_id)` on question_sequences + `(sequence_id, order)` on questions
- Expected: <10ms for 10 questions (max HOST mode)

**Common Query 3**: Get provenance for auto-generated questions (monitoring dashboard)
```sql
SELECT AVG(generation_latency_ms) as avg_latency,
       AVG(retry_count) as avg_retries,
       AVG(validation_attempts) as avg_validations,
       COUNT(*) as total_generated
FROM question_provenance
WHERE generation_timestamp > NOW() - INTERVAL '1 hour';
```
- Index: `(generation_timestamp)` for time-series queries
- Expected: <50ms for 1000 questions (aggregation on indexed timestamp)

---

## Testing Scenarios

### Host-Defined Mode

1. **Happy path**: Create discussion with 3 questions → advance through all rounds → auto-complete
2. **Validation failure**: Attempt to create discussion with "Why did you..." question → reject with error
3. **Early termination**: Create discussion with 5 questions → terminate after Round 2 → Questions 3-5 unused
4. **Immutability**: Attempt to edit question after round starts → reject with 400 error

### Auto-Generated Mode

1. **Happy path**: Create discussion with initial question → complete Round 1 → auto-generate Round 2 question → continue
2. **Generation success**: Verify question generated within 30 seconds, passes validation, transitions to QUESTION_READY
3. **Generation failure**: Mock LLM API failure → verify 3 retries with backoff → QUESTION_GENERATION_FAILED
4. **Validation failure**: Mock LLM returns "Why..." question → verify regeneration → eventual success or QUESTION_GENERATION_FAILED
5. **Host review**: Verify question visible in QUESTION_READY state before advancement
6. **Termination in QUESTION_READY**: Terminate before advancing → question discarded, round never starts

### Provenance Tracking

1. **Completeness**: Verify 100% of auto-generated questions have provenance records
2. **Reproducibility**: Replay Sankey hash → regenerate question → verify identical output (deterministic seed)
3. **Monitoring**: Query questions with `retry_count > 2` → verify alert trigger
4. **Latency tracking**: Verify `generation_latency_ms` matches actual elapsed time (±100ms)

---

## Migration Path (Existing Discussions)

**Backward Compatibility**: QuestionSequence is additive (does not modify existing Spec 1 tables)

**Migration Strategy**:
1. Add `question_id` column to `rounds` table (nullable initially)
2. Backfill `question_id` for existing discussions:
   - Create QuestionSequence (mode=HOST_DEFINED)
   - Extract `round.question_text` → create Question entities
   - Update `round.question_id` to reference new Question
3. Make `round.question_id` NOT NULL (after backfill completes)
4. Add foreign key constraint: `rounds.question_id → questions.question_id`

**Data Preservation**:
- Existing `round.question_text` column preserved for audit (read-only)
- New queries use `round.question_id → questions.question_text` join

---

**Last Updated**: 2026-01-29
**Schema Version**: 1.0.0
**Next Action**: Generate OpenAPI contracts
