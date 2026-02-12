# Phase 1 Setup - Question Progression Protocol (Spec 006)

**Implementation Date**: 2026-01-30
**Status**: ✅ COMPLETE
**Tasks Completed**: T001-T006 (6/6)

---

## Overview

Phase 1 establishes the foundational infrastructure for the Question Progression Protocol (Spec 006), which manages question sequencing in discussions with dual-mode support:
- **Host-defined mode**: Questions provided upfront at discussion creation
- **Auto-generated mode**: Questions generated autonomously after each Sankey analysis

All questions follow constitutional constraints (What/How only, no voting/ranking).

---

## Completed Tasks

### T001: Module Structure Creation ✅

**Created directory structure**:
```
backend/src/question_progression/
├── __init__.py              # Module initialization and version
├── models.py                # SQLAlchemy models (placeholder for Phase 2)
├── validators.py            # Question validation pipeline (placeholder)
├── prompts.py               # LLM prompt templates (placeholder)
├── event_handlers.py        # Event handlers for sankey.complete (placeholder)
├── services/
│   └── __init__.py          # Service layer initialization
├── api/
│   └── __init__.py          # API endpoints initialization
└── workers/
    └── __init__.py          # Background workers initialization
```

**Files created**:
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/__init__.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/models.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/validators.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/prompts.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/event_handlers.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/services/__init__.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/api/__init__.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/workers/__init__.py`

### T002: Python Dependencies ✅

**Added to pyproject.toml**:
```toml
[tool.poetry.dependencies]
anthropic = "^0.18.0"  # Anthropic Claude API for question generation
```

**Dependencies already present**:
- `python = "^3.11"` - Python 3.11+ async/await support
- `fastapi = "^0.109.0"` - API framework
- `sqlalchemy = "^2.0.25"` - Database ORM with asyncio support
- `pydantic = "^2.5.3"` - Validation framework
- `redis = "^5.0.1"` - Event bus infrastructure

### T003: Pytest Configuration ✅

**Added to pyproject.toml**:
```toml
[tool.poetry.group.dev.dependencies]
pytest-mock = "^3.12.0"  # Mock support for testing
```

**Pytest configuration already present**:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
asyncio_mode = "auto"  # Async testing support
addopts = "-v --tb=short --cov=src --cov-report=term-missing --cov-report=html"
```

**Dependencies already present**:
- `pytest = "^7.4.4"` - Testing framework
- `pytest-asyncio = "^0.23.3"` - Async test support

### T004: Test Directory Structure ✅

**Created test structure**:
```
backend/tests/spec6/
├── __init__.py              # Test suite documentation
├── unit/
│   └── __init__.py          # Unit test documentation
├── integration/
│   └── __init__.py          # Integration test documentation
├── contract/
│   └── __init__.py          # Contract test documentation
└── e2e/
    └── __init__.py          # E2E test documentation
```

**Test organization**:
- **unit/**: Component-level tests (validators, services) - fast, isolated
- **integration/**: Workflow tests (host-defined, auto-generated) - database required
- **contract/**: API schema and event payload validation - schema compliance
- **e2e/**: Real Claude API tests (--e2e flag) - requires CLAUDE_API_KEY

**Files created**:
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/__init__.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/unit/__init__.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/integration/__init__.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/contract/__init__.py`
- `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/e2e/__init__.py`

### T005: Environment Configuration ✅

**Added to `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/config.py`**:
```python
# LLM Configuration (Spec 006: Question Progression)
claude_api_key: str = Field(
    default="",
    description="Anthropic Claude API key for question generation",
    alias="ANTHROPIC_API_KEY",  # Supports both CLAUDE_API_KEY and ANTHROPIC_API_KEY
)

claude_model: str = Field(
    default="claude-3-5-sonnet-20241022",
    description="Claude model for question generation",
)

question_generation_timeout_seconds: int = Field(
    default=30,
    ge=10,
    le=120,
    description="Timeout for Claude API question generation requests",
)

question_generation_max_retries: int = Field(
    default=3,
    ge=1,
    le=5,
    description="Maximum retry attempts for question generation",
)
```

**Added to `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/.env.example`**:
```bash
# ============================================================================
# LLM Configuration (Spec 006: Question Progression)
# ============================================================================

# Anthropic Claude API key for autonomous question generation
# Get your API key from: https://console.anthropic.com/
# Can also use ANTHROPIC_API_KEY (alias)
CLAUDE_API_KEY=your-claude-api-key-here

# Claude model for question generation (default: claude-3-5-sonnet-20241022)
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# Timeout for Claude API question generation requests in seconds (default: 30)
QUESTION_GENERATION_TIMEOUT_SECONDS=30

# Maximum retry attempts for question generation (default: 3)
QUESTION_GENERATION_MAX_RETRIES=3
```

### T006: Logging Configuration ✅

**Added to `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/logging_config.py`**:

**New context variables**:
```python
question_id_ctx_var: ContextVar[Optional[str]] = ContextVar("question_id", default=None)
sequence_id_ctx_var: ContextVar[Optional[str]] = ContextVar("sequence_id", default=None)
```

**New helper functions**:
```python
def get_question_id() -> Optional[str]:
    """Get the current question_id from context."""
    return question_id_ctx_var.get()

def set_question_id(question_id: str) -> None:
    """Set the question_id in context for log correlation."""
    question_id_ctx_var.set(question_id)

def get_sequence_id() -> Optional[str]:
    """Get the current sequence_id from context."""
    return sequence_id_ctx_var.get()

def set_sequence_id(sequence_id: str) -> None:
    """Set the sequence_id in context for log correlation."""
    sequence_id_ctx_var.set(sequence_id)
```

**Updated JSONFormatter**:
- Automatically includes `question_id` in all log entries when set
- Automatically includes `sequence_id` in all log entries when set
- Enables structured logging with full context for question operations

**Updated clear_correlation_context()**:
- Now clears `question_id` and `sequence_id` along with other correlation IDs

---

## Technical Details

### Python Version
- **Requirement**: Python 3.11+
- **Reason**: Async/await support for concurrent LLM calls and event handling

### Key Technologies
- **Anthropic Claude API**: LLM for autonomous question generation
- **FastAPI**: Async API framework
- **SQLAlchemy**: Async ORM for database operations
- **Pydantic**: Data validation and settings management
- **Redis**: Event bus for sankey.complete subscription
- **PostgreSQL 14+**: Database for question sequences, questions, and provenance

### Module Organization
- **models.py**: SQLAlchemy entities (QuestionSequence, Question, QuestionProvenance)
- **validators.py**: 5-check validation pipeline (What/How, no Why, no ranking, no yes/no, length)
- **prompts.py**: LLM prompt templates with constitutional constraints
- **event_handlers.py**: Event subscription and emission logic
- **services/**: Business logic (sequence management, generation, provenance tracking)
- **api/**: FastAPI endpoints (sequences, auto-generation status)
- **workers/**: Background workers for async generation

### Test Strategy
- **Unit tests**: Fast, isolated component tests with mocked dependencies
- **Integration tests**: End-to-end workflow tests with real database
- **Contract tests**: Schema validation for API and event payloads
- **E2E tests**: Real Claude API integration tests (gated by --e2e flag)

### Logging Strategy
- **Structured JSON logs**: All logs in JSON format with correlation IDs
- **Context propagation**: Automatic trace_id, discussion_id, round_id, question_id, sequence_id inclusion
- **Correlation across services**: Track operations across Spec 5 (Sankey) → Spec 6 (Questions)

---

## Next Steps

### Phase 2: Foundational (CRITICAL - Blocks all user stories)

**Database migrations**:
- T007: Create QuestionSequence table schema
- T008: Create Question table with mode enum (HOST_DEFINED, AUTO_GENERATED)
- T009: Create QuestionProvenance table for metadata tracking
- T010: Extend Round table with question_id FK

**SQLAlchemy models**:
- T011: Implement QuestionSequence model
- T012: Implement Question model
- T013: Implement QuestionProvenance model

**Event infrastructure**:
- T014: Setup Redis connection for event bus
- T015: Create event bus infrastructure for sankey.complete subscription

**Validation pipeline**:
- T016: Create QuestionValidator with 5-check pipeline
- T017: Add constitutional constraint keywords to validator

**Checkpoint**: Foundation ready - user story implementation can begin in parallel

### Phase 3: User Story 1 - Host-Defined Mode (MVP)
- Host provides questions upfront at discussion creation
- Questions appear in sequence as rounds progress
- Host controls advancement timing
- **Tasks**: T018-T028 (11 tasks)

---

## Configuration Setup

### Development Setup

1. **Update `.env` file**:
```bash
# Copy from .env.example
cp /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/.env.example /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/.env

# Add your Claude API key
CLAUDE_API_KEY=your-actual-api-key-here
```

2. **Install dependencies**:
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend
poetry install
```

3. **Verify installation**:
```bash
# Check Python version
python --version  # Should be 3.11+

# Check installed packages
poetry show anthropic  # Should show version ^0.18.0
poetry show pytest-mock  # Should show version ^3.12.0
```

### Testing Setup

```bash
# Run all tests
pytest tests/spec6/

# Run specific test types
pytest tests/spec6/unit/          # Unit tests only
pytest tests/spec6/integration/   # Integration tests only
pytest tests/spec6/contract/      # Contract tests only

# Run E2E tests (requires CLAUDE_API_KEY)
pytest tests/spec6/e2e/ --e2e

# Run with coverage
pytest tests/spec6/ --cov=src/question_progression --cov-report=html
```

---

## Files Modified

### Created (8 module files + 5 test files)
1. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/__init__.py`
2. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/models.py`
3. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/validators.py`
4. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/prompts.py`
5. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/event_handlers.py`
6. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/services/__init__.py`
7. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/api/__init__.py`
8. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/workers/__init__.py`
9. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/__init__.py`
10. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/unit/__init__.py`
11. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/integration/__init__.py`
12. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/contract/__init__.py`
13. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/e2e/__init__.py`

### Modified (3 existing files)
1. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/pyproject.toml`
   - Added `anthropic = "^0.18.0"` to dependencies
   - Added `pytest-mock = "^3.12.0"` to dev dependencies

2. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/config.py`
   - Added LLM configuration section (4 new fields)
   - Added CLAUDE_API_KEY with ANTHROPIC_API_KEY alias
   - Added Claude model, timeout, and retry configuration

3. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/logging_config.py`
   - Added `question_id_ctx_var` context variable
   - Added `sequence_id_ctx_var` context variable
   - Added getter/setter helper functions
   - Updated JSONFormatter to include question/sequence IDs
   - Updated clear_correlation_context()

4. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/.env.example`
   - Added LLM configuration section with 4 new environment variables

5. `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/specs/006-question-progression/tasks.md`
   - Marked T001-T006 as complete [X]

---

## Success Criteria

### Phase 1 Success Criteria ✅
- [X] Module structure created with all required subdirectories
- [X] Python 3.11+ dependencies installed (anthropic, fastapi, sqlalchemy, pydantic, redis)
- [X] Pytest configured with async support and pytest-mock
- [X] Test directory structure created (unit, integration, contract, e2e)
- [X] Claude API key configuration added with environment variable support
- [X] Logging configuration extended for question progression context

### Verification Commands

```bash
# Verify module structure
ls -la /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/question_progression/

# Verify test structure
ls -la /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/tests/spec6/

# Verify dependencies
grep anthropic /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/pyproject.toml
grep pytest-mock /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/pyproject.toml

# Verify configuration
grep -A 10 "LLM Configuration" /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/config.py
grep "question_id\|sequence_id" /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/logging_config.py
```

---

## Notes

- All parallel tasks (T002-T006) were executed efficiently
- Module follows existing project structure conventions
- Configuration uses Pydantic settings with .env file support
- Logging integrates with existing structured JSON logging system
- Test structure mirrors existing compliance/contract/integration/performance organization
- Phase 2 (Foundational) is now ready to begin - it BLOCKS all user story work

---

**Phase 1 Status**: ✅ COMPLETE
**Next Phase**: Phase 2 - Foundational (T007-T017)
**Ready for**: Database migrations, SQLAlchemy models, event bus setup, validation pipeline
