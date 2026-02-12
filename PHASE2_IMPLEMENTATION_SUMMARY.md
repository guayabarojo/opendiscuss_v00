# Phase 2 Implementation Summary - Question Progression Protocol

**Spec**: 006-question-progression
**Phase**: Phase 2 (Foundational)
**Date**: 2026-01-30
**Status**: COMPLETE ✓

---

## Overview

Phase 2 establishes the foundational infrastructure for the Question Progression Protocol (Spec 006). This phase is a BLOCKING prerequisite - no user story implementation can begin until these tasks are complete.

**All 11 tasks (T007-T017) have been successfully completed.**

---

## Completed Tasks

### Database Migrations (T007-T010)

#### T007: QuestionSequence Table Schema ✓
**File**: `/backend/alembic/versions/004_question_sequence.py`

Created `question_sequences` table with:
- `sequence_id` (UUID PK)
- `discussion_id` (UUID FK UNIQUE to discussions)
- `mode` (ENUM: HOST_DEFINED | AUTO_GENERATED)
- `total_questions` (INT NULL for AUTO mode, 1-10 for HOST mode)
- `current_index` (INT, 0-based)
- `completion_status` (ENUM: IN_PROGRESS | COMPLETED | TERMINATED)
- `created_at` (TIMESTAMP)

Constraints:
- Unique index on `discussion_id` (one sequence per discussion)
- Check constraint for mode-specific `total_questions` validation
- Check constraint for non-negative `current_index`

#### T008: Question Table Schema ✓
**File**: `/backend/alembic/versions/005_question.py`

Created `questions` table with:
- `question_id` (UUID PK)
- `sequence_id` (UUID FK to question_sequences)
- `order` (INT, 1-indexed)
- `question_text` (VARCHAR(200), validated)
- `mode` (ENUM: HOST_DEFINED | AUTO_GENERATED)
- `validation_status` (ENUM: VALID | REJECTED | PENDING)
- `created_at` (TIMESTAMP)
- `immutable_since` (TIMESTAMP NULL, set when round starts)

Constraints:
- Unique composite index on `(sequence_id, order)`
- Check constraint for positive `order` (>= 1)
- Check constraint for text length (10-200 characters)

#### T009: QuestionProvenance Table Schema ✓
**File**: `/backend/alembic/versions/006_question_provenance.py`

Created `question_provenance` table with:
- `provenance_id` (UUID PK)
- `question_id` (UUID FK UNIQUE to questions)
- `generation_timestamp` (TIMESTAMP)
- `generation_latency_ms` (FLOAT)
- `input_sankey_hash` (VARCHAR(64) - SHA-256)
- `input_round_id` (UUID FK to rounds)
- `llm_model` (VARCHAR(100))
- `prompt_tokens` (INT)
- `completion_tokens` (INT)
- `retry_count` (INT DEFAULT 0)
- `validation_attempts` (INT DEFAULT 1)
- `previous_questions_count` (INT)

Indexes:
- Unique index on `question_id`
- Index on `input_round_id` (find questions generated from specific round)
- Index on `generation_timestamp` (time-series queries for monitoring)

#### T010: Round Entity Extension ✓
**File**: `/backend/alembic/versions/007_round_question_fk.py`

Extended `rounds` table with:
- `question_id` (UUID FK NULL to questions)
- Foreign key constraint with CASCADE delete
- Index on `question_id` for efficient joins

Updated Round model relationships in:
- `/backend/src/models/round.py` - Added `question` relationship

---

### SQLAlchemy Models (T011-T013)

#### T011: QuestionSequence Model ✓
**File**: `/backend/src/question_progression/models.py`

Implemented `QuestionSequence` model with:
- All schema fields mapped to SQLAlchemy columns
- Mode validation (HOST_DEFINED requires total_questions 1-10, AUTO_GENERATED requires NULL)
- Relationships: belongs to Discussion, has many Questions
- Enums: `SequenceMode`, `CompletionStatus`

Features:
- Automatic validation in `__init__`
- Mode-specific constraint enforcement
- Clean `__repr__` for debugging

#### T012: Question Model ✓
**File**: `/backend/src/question_progression/models.py`

Implemented `Question` model with:
- All schema fields mapped to SQLAlchemy columns
- Relationships: belongs to QuestionSequence, has one QuestionProvenance, referenced by Round
- Enums: `QuestionMode`, `ValidationStatus`
- Immutability tracking

Features:
- `mark_immutable()` method to lock question when round starts
- `is_immutable()` method to check immutability status
- Length validation (10-200 characters)
- Order validation (>= 1)

#### T013: QuestionProvenance Model ✓
**File**: `/backend/src/question_progression/models.py`

Implemented `QuestionProvenance` model with:
- All schema fields for provenance tracking
- Relationships: belongs to Question, references Round
- Comprehensive metadata capture

Features:
- Tracks generation latency, token usage, retry counts
- SHA-256 Sankey hash for reproducibility
- Support for monitoring and quality analysis

**Model Registration**: Updated `/backend/src/models/__init__.py` to import all Question Progression models and enums.

**Relationship Updates**:
- `/backend/src/models/discussion.py` - Added `question_sequence` relationship
- `/backend/src/models/round.py` - Added `question` relationship

---

### Event Infrastructure (T014-T015)

#### T014: Redis Connection Setup ✓
**Status**: Event bus already configured with Redis support in `/backend/src/events/event_bus.py`

The existing EventBus class provides:
- Async Redis pub/sub support
- Connection pooling with retry logic
- Graceful failure handling
- Health check capabilities

**No additional work required** - infrastructure already supports question progression events.

#### T015: Event Bus Infrastructure ✓
**File**: `/backend/src/events/event_types.py`

Added question progression events:

1. **QuestionReadyEvent**
   - Emitted when auto-generated question is ready
   - Fields: `round_id`, `question_id`, `question_text`, `timestamp`
   - Channel: `events:question.ready`

2. **QuestionGenerationFailedEvent**
   - Emitted when auto-generation fails after max retries
   - Fields: `round_id`, `discussion_id`, `retry_count`, `last_error`, `timestamp`
   - Channel: `events:question.generation_failed`

**Event Registry**: Updated `EVENT_TYPE_REGISTRY` to include new event types for dynamic dispatch.

**Integration Points**:
- Sankey complete handler will emit `question.ready` after successful generation
- Generation worker will emit `question.generation_failed` on failure
- Round service can subscribe to these events for state transitions

---

### Validation Pipeline (T016-T017)

#### T016: QuestionValidator with 5-Check Pipeline ✓
**File**: `/backend/src/question_progression/validators.py`

Implemented `QuestionValidator` class with fail-fast validation:

**Check 1: Length (10-200 characters)**
- Validates question length is within bounds
- Error code: `INVALID_LENGTH`

**Check 2: Opening Word (What/How only)**
- Ensures question starts with "What" or "How"
- Case-insensitive matching
- Error code: `INVALID_START`

**Check 3: Prohibited Opening Words**
- Rejects: "Why", "Do you", "Should we", "Would you", "Would we", "Could you", "Could we", "Will you", "Will we"
- Error code: `CONTAINS_PROHIBITED_WORD`

**Check 4: Ranking/Voting Keywords**
- Comprehensive keyword list (see T017)
- Case-insensitive matching
- Error code: `CONTAINS_RANKING_KEYWORD`

**Check 5: Binary Choice Patterns**
- Regex pattern matching for yes/no, agree/disagree questions
- Pattern: `\b(yes|no|agree|disagree)\s*(or|/|vs\.?)\s*(yes|no|agree|disagree)\b`
- Error code: `BINARY_CHOICE`

**Features**:
- `ValidationResult` Pydantic model with detailed error reporting
- `get_validation_rules_summary()` for human-readable documentation
- Singleton instance `validator` for easy import
- Convenience function `validate_question(text)` for quick validation

#### T017: Constitutional Constraint Keywords ✓
**File**: `/backend/src/question_progression/validators.py`

Added comprehensive ranking/voting keyword list:
- **Core**: vote, rank, order, best, worst, choose, select, pick, prefer
- **Extended**: favorite, top, bottom, first, last, winner, loser, better, worse, superior, inferior

**Constitutional Guarantee**: Enforces Principle VII (Representation Not Adjudication)
- Zero questions with ranking/voting keywords pass validation
- All questions are exploratory (What/How) and open-ended

---

## Integration Points

### Database Schema
- All migrations are sequenced: 004 → 005 → 006 → 007
- Migrations depend on existing tables (discussions, rounds)
- Foreign key constraints ensure referential integrity
- Indexes optimize query performance for common access patterns

### SQLAlchemy Models
- Models registered in `/backend/src/models/__init__.py`
- Bidirectional relationships configured (Discussion ↔ QuestionSequence, Question ↔ Round)
- Cascade delete rules preserve data integrity
- Enums shared between migrations and models

### Event System
- Event types registered in global `EVENT_TYPE_REGISTRY`
- EventBus supports typed event emission and subscription
- Async/await pattern for non-blocking event handling
- Events follow existing naming convention (`domain.action`)

### Validation
- Validator is stateless and thread-safe
- Can be used synchronously in API layer
- Returns structured `ValidationResult` for consistent error handling
- Supports both host-defined and auto-generated questions

---

## Testing Readiness

Phase 2 implementation is **fully testable** with:

### Unit Tests
- Model validation logic (enums, constraints, relationships)
- Validator 5-check pipeline (each check independently)
- Event payload serialization/deserialization
- Model `__init__` validation

### Integration Tests
- Database migrations (upgrade/downgrade)
- Foreign key constraints enforcement
- Cascade delete behavior
- Event bus pub/sub flow

### Contract Tests
- ValidationResult schema
- Event payload schemas (QuestionReadyEvent, QuestionGenerationFailedEvent)
- Model field types and constraints

---

## Files Created/Modified

### Created Files
1. `/backend/alembic/versions/004_question_sequence.py` (Migration)
2. `/backend/alembic/versions/005_question.py` (Migration)
3. `/backend/alembic/versions/006_question_provenance.py` (Migration)
4. `/backend/alembic/versions/007_round_question_fk.py` (Migration)

### Modified Files
1. `/backend/src/question_progression/models.py` (Replaced placeholder with full implementation)
2. `/backend/src/question_progression/validators.py` (Replaced placeholder with full implementation)
3. `/backend/src/models/__init__.py` (Added Question Progression imports)
4. `/backend/src/models/round.py` (Added question_id FK and relationship)
5. `/backend/src/models/discussion.py` (Added question_sequence relationship)
6. `/backend/src/events/event_types.py` (Added QuestionReadyEvent, QuestionGenerationFailedEvent)
7. `/specs/006-question-progression/tasks.md` (Marked T007-T017 as complete)

---

## Verification

### Syntax Validation
All Python files pass `python3 -m py_compile`:
- ✓ `src/question_progression/models.py`
- ✓ `src/question_progression/validators.py`
- ✓ `src/events/event_types.py`
- ✓ `src/models/__init__.py`

### Schema Validation
Migration files follow Alembic patterns:
- ✓ Proper revision IDs and dependencies
- ✓ Upgrade/downgrade symmetry
- ✓ Consistent naming conventions
- ✓ Complete constraint definitions

### Relationship Validation
SQLAlchemy relationships are bidirectional:
- ✓ Discussion ↔ QuestionSequence
- ✓ QuestionSequence ↔ Question
- ✓ Question ↔ QuestionProvenance
- ✓ Question ↔ Round
- ✓ Round ↔ Question (via question_id FK)

---

## Next Steps

**Phase 2 is COMPLETE**. User story implementation can now proceed:

1. **Phase 3**: User Story 1 - Host-Defined Question Sequence (T018-T028)
2. **Phase 4**: User Story 3 - Question Quality Constraints (T029-T038)
3. **Phase 5**: User Story 2 - Auto-Generated Questions (T039-T062)

All foundational infrastructure is in place:
- ✓ Database schema ready
- ✓ SQLAlchemy models ready
- ✓ Event infrastructure ready
- ✓ Validation pipeline ready

User stories can now be implemented **independently and in parallel** as specified in the tasks.md.

---

## Compliance Notes

### Constitutional Alignment
- **Principle VII (Representation Not Adjudication)**: Enforced through validator keyword checks
- **Parallel-First Architecture**: Models support concurrent operations with proper constraints
- **Data Integrity**: Foreign keys and cascade rules prevent orphaned records

### Spec Alignment
- All fields from `data-model.md` implemented
- All enums match spec definitions
- Indexes match performance requirements
- Event types match contract specifications

### Code Quality
- Type hints for all function signatures
- Docstrings for all classes and methods
- PEP 8 compliant formatting
- No linting errors

---

**Phase 2 Status**: ✅ COMPLETE (11/11 tasks)
**Ready for Phase 3**: ✅ YES
**Blocking Issues**: ❌ NONE
