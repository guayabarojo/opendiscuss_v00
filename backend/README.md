# OpenDiscuss Backend

Discussion Protocol implementation serving as the system spine for OpenDiscuss.

## Prerequisites

- Python 3.11+
- Poetry 1.7+
- Docker & Docker Compose (for PostgreSQL and Redis)

## Quick Start

### 1. Install Dependencies

```bash
cd backend
poetry install
```

### 2. Start Infrastructure Services

```bash
# From project root
docker-compose up -d
```

This starts:
- PostgreSQL 14+ on port 5432
- Redis 7+ on port 6379

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
# Required: DATABASE_URL, REDIS_URL, SECRET_KEY
```

### 4. Run Database Migrations

```bash
poetry run alembic upgrade head
```

### 5. Start Development Server

```bash
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at http://localhost:8000

API documentation at http://localhost:8000/docs

## Development

### Run Tests

```bash
# All tests with coverage
poetry run pytest

# Specific test type
poetry run pytest tests/unit
poetry run pytest tests/integration
poetry run pytest tests/contract

# Watch mode
poetry run pytest-watch
```

### Code Quality

```bash
# Format code
poetry run black src tests

# Lint code
poetry run ruff check src tests

# Type checking
poetry run mypy src
```

### Database Migrations

```bash
# Create new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1

# Show migration history
poetry run alembic history
```

## Project Structure

```
backend/
├── src/
│   ├── models/          # SQLAlchemy models (Discussion, Round, Participant)
│   ├── services/        # Business logic (DiscussionService, RoundService, TimingService)
│   ├── api/             # FastAPI routes (discussion, round, participant endpoints)
│   ├── events/          # Event bus and handlers (sub-protocol coordination)
│   ├── config.py        # Application configuration
│   ├── database.py      # Database connection and session management
│   └── main.py          # FastAPI application entry point
├── tests/
│   ├── unit/            # Unit tests for services and models
│   ├── integration/     # End-to-end discussion flow tests
│   └── contract/        # Sub-protocol integration contract tests
├── alembic/             # Database migration scripts
└── pyproject.toml       # Poetry dependencies and tool configuration
```

## Architecture

The Discussion Protocol serves as the system spine, orchestrating:

1. **Input Collection** (Spec 2) - Parallel participant submissions
2. **Summarization** (Spec 3) - Participant approval gate
3. **Clustering** (Spec 4) - Thought space generation
4. **Sankey Construction** (Spec 5) - Visualization with participant movement
5. **Question Progression** (Spec 6) - Multi-round coordination

### Key Components

- **State Machine**: Discussion and Round lifecycle management
- **Timing Service**: Submission window enforcement (±100ms precision)
- **Event Bus**: Sub-protocol coordination via typed events
- **Invariant Validator**: Constitutional compliance verification

## Performance Requirements

- State queries: <200ms p95
- Round state transitions: <500ms
- Submission window closure: ±100ms precision
- Support 100 concurrent participants per discussion

## Contributing

See `/specs/001-discussion-protocol/` for:
- `spec.md` - Feature specification
- `plan.md` - Implementation plan
- `tasks.md` - Task breakdown
- `contracts/` - API contracts

## License

[License information]
