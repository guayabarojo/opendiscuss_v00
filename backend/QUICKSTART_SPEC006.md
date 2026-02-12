# Quick Start Guide - Question Progression Protocol (Spec 006)

## Overview
The Question Progression Protocol manages question sequencing in discussions with two modes:
- **Host-defined**: Questions provided upfront at discussion creation
- **Auto-generated**: Questions generated autonomously after Sankey analysis

## Setup (5 minutes)

### 1. Install Dependencies
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend
poetry install
```

### 2. Configure Environment
```bash
# Copy example configuration
cp .env.example .env

# Edit .env and add your Claude API key
# Get key from: https://console.anthropic.com/
CLAUDE_API_KEY=your-actual-api-key-here
```

### 3. Verify Setup
```bash
# Check dependencies
poetry show anthropic pytest-mock

# Check module structure
ls -la src/question_progression/

# Check test structure
ls -la tests/spec6/
```

## Module Structure

```
src/question_progression/
├── __init__.py              # Module version and docs
├── models.py                # SQLAlchemy entities (Phase 2)
├── validators.py            # 5-check validation pipeline (Phase 2-4)
├── prompts.py               # LLM prompt templates (Phase 5)
├── event_handlers.py        # Event subscription/emission (Phase 5)
├── services/                # Business logic layer
│   └── __init__.py
├── api/                     # FastAPI endpoints
│   └── __init__.py
└── workers/                 # Background workers
    └── __init__.py
```

## Test Structure

```
tests/spec6/
├── unit/                    # Fast, isolated component tests
├── integration/             # Workflow tests with database
├── contract/                # API/event schema validation
└── e2e/                     # Real Claude API tests (--e2e flag)
```

## Configuration

### Environment Variables
```bash
# Required for auto-generation
CLAUDE_API_KEY=your-key                    # Anthropic Claude API key
CLAUDE_MODEL=claude-3-5-sonnet-20241022    # Model to use

# Optional tuning
QUESTION_GENERATION_TIMEOUT_SECONDS=30     # Generation timeout
QUESTION_GENERATION_MAX_RETRIES=3          # Max retry attempts
```

### Access in Code
```python
from src.config import settings

api_key = settings.claude_api_key
model = settings.claude_model
timeout = settings.question_generation_timeout_seconds
retries = settings.question_generation_max_retries
```

## Logging

### Using Question Context
```python
from src.logging_config import get_logger, set_question_id, set_sequence_id

logger = get_logger(__name__)

# Set context for automatic inclusion in all logs
set_question_id("q-12345")
set_sequence_id("seq-67890")

# All logs will now include question_id and sequence_id
logger.info("Processing question", extra={"status": "validating"})
```

### Log Output Format
```json
{
  "timestamp": "2026-01-30T12:00:00Z",
  "level": "INFO",
  "service": "opendiscuss-backend",
  "trace_id": "uuid-here",
  "discussion_id": "d-123",
  "round_id": "r-456",
  "question_id": "q-789",
  "sequence_id": "seq-abc",
  "message": "Processing question",
  "context": {
    "status": "validating"
  }
}
```

## Testing

### Run Tests
```bash
# All tests
pytest tests/spec6/

# By type
pytest tests/spec6/unit/          # Unit tests
pytest tests/spec6/integration/   # Integration tests
pytest tests/spec6/contract/      # Contract tests

# E2E tests (requires CLAUDE_API_KEY)
pytest tests/spec6/e2e/ --e2e

# With coverage
pytest tests/spec6/ --cov=src/question_progression --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Test Organization
- **Unit**: Mock all external dependencies (database, Redis, Claude API)
- **Integration**: Use real database, mock Claude API
- **Contract**: Validate OpenAPI/AsyncAPI schemas
- **E2E**: Use real Claude API (slow, requires API key)

## Development Workflow

### Phase 2: Next Steps (Foundational)
1. Create database migrations (T007-T010)
2. Implement SQLAlchemy models (T011-T013)
3. Setup Redis event bus (T014-T015)
4. Create validation pipeline (T016-T017)

### Phase 3: MVP (Host-Defined Mode)
1. Implement QuestionSequenceService (T018-T019)
2. Add API endpoints (T020-T021)
3. Add question retrieval logic (T022-T024)
4. Integrate with Discussion creation (T025-T028)

### Testing Strategy
1. Write unit tests for each component
2. Write integration tests for workflows
3. Test independently before moving to next phase
4. Use contract tests to ensure API compliance

## Common Tasks

### Create a New Service
```python
# src/question_progression/services/example_service.py
from src.logging_config import get_logger

logger = get_logger(__name__)

class ExampleService:
    """Service description."""

    async def do_something(self) -> None:
        """Method description."""
        logger.info("Doing something")
        # Implementation
```

### Add a New Validator
```python
# src/question_progression/validators.py
def validate_example(question: str) -> bool:
    """Validator description."""
    # Validation logic
    return True
```

### Add a New API Endpoint
```python
# src/question_progression/api/example_endpoint.py
from fastapi import APIRouter
from src.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.get("/example")
async def example_endpoint():
    """Endpoint description."""
    logger.info("Example endpoint called")
    return {"status": "ok"}
```

## Constitutional Constraints

All questions MUST follow these constraints:
1. ✅ Start with "What" or "How"
2. ❌ No "Why", "Do you", "Should we", "Would you"
3. ❌ No voting/ranking keywords (vote, rank, best, worst, choose)
4. ❌ No binary yes/no questions
5. ✅ Length: 10-200 characters

### Valid Examples
- "What are the main challenges in this area?"
- "How can we improve the current process?"
- "What factors should we consider?"

### Invalid Examples
- "Why is this important?" ❌ (starts with Why)
- "Should we implement this?" ❌ (yes/no question)
- "Which option is best?" ❌ (ranking/voting)
- "Do you agree?" ❌ (starts with Do you)

## Resources

- **Spec**: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/specs/006-question-progression/spec.md`
- **Tasks**: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/specs/006-question-progression/tasks.md`
- **Plan**: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/specs/006-question-progression/plan.md`
- **Phase 1 Report**: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/PHASE1_SETUP_SPEC006.md`

## Support

- Claude API Docs: https://docs.anthropic.com/
- FastAPI Docs: https://fastapi.tiangolo.com/
- SQLAlchemy Docs: https://docs.sqlalchemy.org/
- Pydantic Docs: https://docs.pydantic.dev/

---

**Status**: Phase 1 Complete ✅
**Next**: Phase 2 - Foundational (T007-T017)
