# Developer Quickstart: OpenDiscuss Discussion Protocol

**Feature**: 001-discussion-protocol
**Date**: 2026-01-29
**Audience**: Backend developers implementing the Discussion Protocol system spine

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Docker (optional, for local development)
- Git

## Local Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/opendiscuss/opendiscuss.git
cd opendiscuss
git checkout 001-discussion-protocol
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies (pytest, mypy, black, ruff)
pip install -r requirements-dev.txt
```

### 3. Start Dependencies (Docker Compose)

```bash
# Start PostgreSQL + Redis
docker-compose up -d postgres redis

# Verify services
docker-compose ps
# Should show postgres:5432 and redis:6379 running
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# Key variables:
#   DATABASE_URL=postgresql://user:pass@localhost:5432/opendiscuss
#   REDIS_URL=redis://localhost:6379/0
#   SECRET_KEY=<generate with: openssl rand -hex 32>
```

### 5. Run Database Migrations

```bash
# Apply schema migrations
alembic upgrade head

# Verify tables created
psql $DATABASE_URL -c "\dt"
# Should show: discussions, rounds, participants, submissions, approved_summaries, thought_spaces, flows
```

### 6. Run Tests

```bash
# Run full test suite
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run only Discussion Protocol tests
pytest tests/unit/test_discussion_lifecycle.py
pytest tests/integration/test_single_round_discussion.py
```

### 7. Start Development Server

```bash
# Start FastAPI with hot reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# API docs available at:
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

---

## Project Structure

```
backend/
├── src/
│   ├── main.py                        # FastAPI app entry point
│   ├── config.py                      # Configuration from environment
│   ├── database.py                    # SQLAlchemy session management
│   ├── models/
│   │   ├── __init__.py
│   │   ├── discussion.py              # Discussion entity
│   │   ├── round.py                   # Round entity with state machine
│   │   ├── participant.py             # Participant entity
│   │   ├── submission.py              # Submission entity (ephemeral)
│   │   ├── approved_summary.py        # ApprovedSummary entity
│   │   ├── thought_space.py           # ThoughtSpace entity
│   │   ├── flow.py                    # Flow entity
│   │   └── protocol_state.py          # Enums (DiscussionStatus, RoundStatus, etc.)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── discussion_service.py      # Discussion lifecycle management
│   │   ├── round_service.py           # Round state machine coordination
│   │   ├── timing_service.py          # Redis-backed timing enforcement
│   │   ├── protocol_coordinator.py    # Event bus coordination
│   │   └── invariant_validator.py     # Constitutional compliance checks
│   ├── api/
│   │   ├── __init__.py
│   │   ├── discussion_routes.py       # /discussions endpoints
│   │   ├── round_routes.py            # /rounds endpoints
│   │   └── participant_routes.py      # /participants endpoints
│   └── events/
│       ├── __init__.py
│       ├── event_bus.py               # Event emitter/subscriber
│       ├── event_types.py             # Pydantic event schemas
│       └── handlers/
│           ├── submission_complete.py      # Spec 2 → Spec 3
│           ├── summarization_complete.py   # Spec 3 → Spec 4
│           ├── clustering_complete.py      # Spec 4 → Spec 5
│           └── sankey_complete.py          # Spec 5 → Spec 6
├── tests/
│   ├── conftest.py                    # Pytest fixtures
│   ├── unit/
│   │   ├── test_discussion_lifecycle.py
│   │   ├── test_round_state_machine.py
│   │   └── test_invariant_validator.py
│   ├── integration/
│   │   ├── test_single_round_discussion.py
│   │   ├── test_multi_round_movement.py
│   │   └── test_timing_enforcement.py
│   └── contract/
│       ├── test_submission_to_summary.py
│       ├── test_summary_to_clustering.py
│       ├── test_clustering_to_sankey.py
│       └── test_sankey_to_question.py
├── alembic/                           # Database migrations
│   ├── versions/
│   └── env.py
├── requirements.txt                   # Production dependencies
├── requirements-dev.txt               # Dev/test dependencies
├── docker-compose.yml                 # Local services (Postgres, Redis)
└── pyproject.toml                     # Project config (black, ruff, mypy)
```

---

## Key Files to Start With

### 1. `src/models/protocol_state.py` - State Enums

```python
from enum import Enum

class DiscussionStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"

class RoundStatus(str, Enum):
    PENDING = "PENDING"
    QUESTION_READY = "QUESTION_READY"  # AUTO mode only
    SUBMISSION_OPEN = "SUBMISSION_OPEN"
    SUBMISSION_CLOSED = "SUBMISSION_CLOSED"
    SUMMARIZING = "SUMMARIZING"
    APPROVING = "APPROVING"
    CLUSTERING = "CLUSTERING"
    SANKEY_BUILDING = "SANKEY_BUILDING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"

class DropoutReason(str, Enum):
    APPROVAL_TIMEOUT = "APPROVAL_TIMEOUT"
    NO_SUBMISSION = "NO_SUBMISSION"
    VOLUNTARY = "VOLUNTARY"
```

### 2. `src/models/discussion.py` - Discussion Entity

```python
from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.database import Base
from src.models.protocol_state import DiscussionStatus, DiscussionMode

class Discussion(Base):
    __tablename__ = "discussions"

    discussion_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    community_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    mode = Column(SQLEnum(DiscussionMode), nullable=False)
    total_rounds = Column(Integer, nullable=False)
    status = Column(SQLEnum(DiscussionStatus), nullable=False, default=DiscussionStatus.CREATED)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    terminated_reason = Column(String, nullable=True)
    host_user_id = Column(UUID(as_uuid=True), nullable=False)

    # Relationships
    rounds = relationship("Round", back_populates="discussion", cascade="all, delete-orphan")
    participants = relationship("Participant", back_populates="discussion", cascade="all, delete-orphan")

    def start(self):
        """Transition to ACTIVE state and open Round 1"""
        if self.status != DiscussionStatus.CREATED:
            raise ValueError(f"Cannot start discussion in {self.status} state")

        self.status = DiscussionStatus.ACTIVE
        self.started_at = datetime.utcnow()

        # Start first round
        first_round = self.rounds[0]
        first_round.status = RoundStatus.SUBMISSION_OPEN
        first_round.submission_window_start = datetime.utcnow()

    def complete(self):
        """Mark discussion as completed after final report generation"""
        if self.status != DiscussionStatus.ACTIVE:
            raise ValueError(f"Cannot complete discussion in {self.status} state")

        # Verify all rounds complete
        if not all(r.status == RoundStatus.COMPLETE for r in self.rounds):
            raise ValueError("Cannot complete: not all rounds are complete")

        self.status = DiscussionStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    @property
    def current_round(self):
        """Get currently active round"""
        for round in sorted(self.rounds, key=lambda r: r.round_num):
            if round.status != RoundStatus.COMPLETE:
                return round
        return None
```

### 3. `src/services/discussion_service.py` - Core Logic

```python
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from src.models.discussion import Discussion, DiscussionMode, DiscussionStatus
from src.models.round import Round, RoundStatus
from src.events.event_bus import event_bus
from src.services.timing_service import timing_service

class DiscussionService:
    def __init__(self, db: Session):
        self.db = db

    def create_discussion(
        self,
        community_id: UUID,
        host_user_id: UUID,
        mode: DiscussionMode,
        total_rounds: int,
        questions: Optional[List[str]] = None,
        seed_question: Optional[str] = None
    ) -> Discussion:
        """Create new discussion with rounds"""

        # Validate mode-specific requirements
        if mode == DiscussionMode.HOST_DEFINED:
            if not questions or len(questions) != total_rounds:
                raise ValueError("HOST_DEFINED mode requires questions for all rounds")
        elif mode == DiscussionMode.AUTO_GENERATED:
            if not seed_question:
                raise ValueError("AUTO_GENERATED mode requires seed_question")

        # Create discussion
        discussion = Discussion(
            community_id=community_id,
            host_user_id=host_user_id,
            mode=mode,
            total_rounds=total_rounds,
            status=DiscussionStatus.CREATED
        )

        # Create rounds
        for round_num in range(1, total_rounds + 1):
            question_text = None
            if mode == DiscussionMode.HOST_DEFINED:
                question_text = questions[round_num - 1]
            elif mode == DiscussionMode.AUTO_GENERATED and round_num == 1:
                question_text = seed_question

            round = Round(
                discussion=discussion,
                round_num=round_num,
                question_text=question_text,
                status=RoundStatus.PENDING,
                submission_window_duration_sec=300  # 5 minutes default
            )
            discussion.rounds.append(round)

        self.db.add(discussion)
        self.db.commit()
        self.db.refresh(discussion)

        return discussion

    def start_discussion(self, discussion_id: UUID) -> Discussion:
        """Start discussion and open Round 1 submission window"""
        discussion = self.db.query(Discussion).filter_by(discussion_id=discussion_id).first()

        if not discussion:
            raise ValueError("Discussion not found")

        discussion.start()

        # Schedule submission window closure
        first_round = discussion.current_round
        await timing_service.schedule_window_close(
            round_id=first_round.round_id,
            duration_sec=first_round.submission_window_duration_sec
        )

        self.db.commit()
        self.db.refresh(discussion)

        # Emit event for UI notification
        await event_bus.emit("discussion.started", {
            "discussion_id": discussion_id,
            "round_num": 1
        })

        return discussion

    def advance_round(self, discussion_id: UUID) -> Round:
        """Advance to next round (host trigger)"""
        discussion = self.db.query(Discussion).filter_by(discussion_id=discussion_id).first()

        if not discussion:
            raise ValueError("Discussion not found")

        current_round = discussion.current_round

        if not current_round:
            raise ValueError("No active round to advance from")

        if current_round.status not in [RoundStatus.COMPLETE, RoundStatus.QUESTION_READY]:
            raise ValueError(f"Current round not ready to advance (status: {current_round.status})")

        # Get next round
        next_round_num = current_round.round_num + 1
        next_round = next(r for r in discussion.rounds if r.round_num == next_round_num)

        # Validate question exists
        if not next_round.question_text:
            raise ValueError("Next round question not defined")

        # Open submission window
        next_round.status = RoundStatus.SUBMISSION_OPEN
        next_round.submission_window_start = datetime.utcnow()
        next_round.submission_window_end = datetime.utcnow() + timedelta(
            seconds=next_round.submission_window_duration_sec
        )

        # Schedule window close
        await timing_service.schedule_window_close(
            round_id=next_round.round_id,
            duration_sec=next_round.submission_window_duration_sec
        )

        self.db.commit()
        self.db.refresh(next_round)

        # Emit event
        await event_bus.emit("round.started", {
            "discussion_id": discussion_id,
            "round_id": next_round.round_id,
            "round_num": next_round_num
        })

        return next_round
```

---

## Common Development Tasks

### Add a New State Transition

1. Update `RoundStatus` enum in `src/models/protocol_state.py`
2. Add transition logic to `src/models/round.py`
3. Update state machine diagram in `data-model.md`
4. Add test case in `tests/unit/test_round_state_machine.py`

### Add a New Event Handler

1. Define event schema in `src/events/event_types.py`:
```python
class MyEventPayload(BaseModel):
    round_id: str
    data: dict
```

2. Create handler in `src/events/handlers/my_handler.py`:
```python
@event_bus.subscribe("my.event")
async def on_my_event(payload: MyEventPayload):
    # Handle event
    pass
```

3. Register handler in `src/main.py`:
```python
from src.events.handlers import my_handler
```

### Run Specific Test Suite

```bash
# Unit tests only
pytest tests/unit/

# Integration tests (requires running Postgres/Redis)
pytest tests/integration/

# Contract tests (validates sub-protocol integration)
pytest tests/contract/

# Specific test file
pytest tests/unit/test_discussion_lifecycle.py

# Specific test function
pytest tests/unit/test_discussion_lifecycle.py::test_start_discussion
```

### Database Operations

```bash
# Create new migration
alembic revision -m "Add new field to Round"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Reset database (development only!)
alembic downgrade base && alembic upgrade head

# Inspect current schema
psql $DATABASE_URL -c "\d discussions"
psql $DATABASE_URL -c "\d rounds"
```

### Code Quality Checks

```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/

# Run all checks
./scripts/check_quality.sh
```

---

## Testing Strategies

### Unit Tests (Fast, No External Dependencies)

```python
# tests/unit/test_discussion_lifecycle.py
import pytest
from src.models.discussion import Discussion, DiscussionStatus

def test_start_discussion():
    """Test discussion transitions to ACTIVE on start"""
    discussion = Discussion(
        community_id=uuid.uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=3,
        host_user_id=uuid.uuid4()
    )

    assert discussion.status == DiscussionStatus.CREATED

    discussion.start()

    assert discussion.status == DiscussionStatus.ACTIVE
    assert discussion.started_at is not None
```

### Integration Tests (Require Database)

```python
# tests/integration/test_single_round_discussion.py
import pytest
from src.services.discussion_service import DiscussionService

@pytest.mark.asyncio
async def test_complete_single_round(db_session):
    """Test full single-round discussion lifecycle"""
    service = DiscussionService(db_session)

    # Create discussion
    discussion = service.create_discussion(
        community_id=uuid.uuid4(),
        host_user_id=uuid.uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=1,
        questions=["What should we prioritize?"]
    )

    assert discussion.status == DiscussionStatus.CREATED

    # Start discussion (opens Round 1)
    discussion = await service.start_discussion(discussion.discussion_id)
    assert discussion.status == DiscussionStatus.ACTIVE
    assert discussion.current_round.status == RoundStatus.SUBMISSION_OPEN

    # ... continue through full lifecycle
```

### Contract Tests (Validate Sub-Protocol Integration)

```python
# tests/contract/test_submission_to_summary.py
import pytest
from src.events.event_bus import event_bus

@pytest.mark.asyncio
async def test_submission_complete_triggers_summarization():
    """Verify Spec 2 → Spec 3 contract"""
    # Setup: Create round in SUBMISSION_OPEN state
    # ...

    # Emit submission.complete event (from Spec 2)
    await event_bus.emit("submission_window.closed", {
        "round_id": round.round_id,
        "submissions": [...]
    })

    # Assert: Round transitions to SUMMARIZING
    await asyncio.sleep(0.1)  # Allow event processing
    assert round.status == RoundStatus.SUMMARIZING
```

---

## Debugging Tips

### Enable Detailed Logging

```bash
# .env
LOG_LEVEL=DEBUG
LOG_SQL=true  # Log all SQL queries
```

### Inspect Event Bus

```python
# Add logging to event handlers
@event_bus.subscribe("my.event")
async def on_my_event(payload):
    logger.info(f"Received event: {payload}")
    # ...
```

### Check Redis Timers

```bash
# Connect to Redis CLI
docker exec -it opendiscuss_redis redis-cli

# List scheduled timers
ZRANGE submission_windows 0 -1 WITHSCORES

# Check specific timer
ZSCORE submission_windows <round_id>
```

### Query Database State

```sql
-- Find active discussions
SELECT discussion_id, status, started_at
FROM discussions
WHERE status = 'ACTIVE';

-- Check round states
SELECT round_id, round_num, status, submission_window_end
FROM rounds
WHERE discussion_id = '<discussion_id>'
ORDER BY round_num;

-- Count participants per round
SELECT r.round_num, COUNT(DISTINCT p.participant_id) as participant_count
FROM rounds r
LEFT JOIN approved_summaries s ON r.round_id = s.round_id
LEFT JOIN participants p ON s.participant_id = p.participant_id
WHERE r.discussion_id = '<discussion_id>'
GROUP BY r.round_num
ORDER BY r.round_num;
```

---

## Next Steps

1. **Read Architecture Docs**:
   - [research.md](./research.md) - Key design decisions
   - [data-model.md](./data-model.md) - Entity relationships
   - [contracts/](./contracts/) - API specifications

2. **Implement First Feature**:
   - Start with `discussion_service.py` (core lifecycle)
   - Add tests as you go (TDD approach)
   - Run `/speckit.tasks` to generate implementation task breakdown

3. **Integrate with Sub-Protocols**:
   - Implement event handlers for Spec 2 → 3 → 4 → 5 → 6
   - Write contract tests to validate integration
   - See `tests/contract/` for examples

4. **Run MVP Acceptance Tests**:
   - See `../../../MVP_ACCEPTANCE_TEST_PLAN.md`
   - Verify all constitutional compliance tests pass
   - Benchmark performance (100 participants, <45 minutes)

---

## Support

- **Documentation**: `specs/001-discussion-protocol/`
- **Issues**: GitHub Issues (tag: `001-discussion-protocol`)
- **Questions**: Team Slack #opendiscuss-dev

**Last Updated**: 2026-01-29
**Maintainer**: OpenDiscuss Backend Team
