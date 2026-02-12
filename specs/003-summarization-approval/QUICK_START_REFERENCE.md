# Quick Start Reference: Spec 003 Implementation

**Status**: Phase 1 & 2 COMPLETE ✅ | Ready for User Story Implementation
**Last Updated**: 2026-02-01

---

## TL;DR - What's Ready

All foundational infrastructure (Phase 1 & 2, Tasks T001-T014) is complete. You can now implement any user story in parallel.

**Foundation Complete:**
- ✅ Backend: FastAPI + OpenAI SDK + Redis + PostgreSQL
- ✅ Frontend: React + TypeScript + TanStack Query
- ✅ Database: Summary & CorrectionSignal tables with FSM
- ✅ Event Bus: Spec 2 → Spec 3 → Spec 4 handoffs
- ✅ Linting: Ruff (backend) + ESLint/Prettier (frontend)

---

## Project Locations

### Backend Root
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/
```

### Frontend Root
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend/
```

### Spec 003 Docs
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/specs/003-summarization-approval/
```

---

## Backend Quick Commands

### Start Backend Server
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Migrations
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/
poetry run alembic upgrade head
```

### Run Tests
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/
poetry run pytest
```

### Run Linting
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/
poetry run ruff check .
```

### Format Code
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/
poetry run ruff format .
```

---

## Frontend Quick Commands

### Start Frontend Dev Server
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend/
npm run dev
```

### Run Unit Tests
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend/
npm run test:unit
```

### Run E2E Tests
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend/
npm run test:e2e
```

### Run Linting
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend/
npm run lint
```

### Format Code
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend/
npm run format
```

---

## Key File Locations

### Backend Structure
```
backend/src/
├── summarization/
│   ├── models/
│   │   ├── summary.py                    # Summary model with FSM
│   │   └── correction_signal.py          # CorrectionSignal model
│   ├── services/
│   │   ├── summarization_service.py      # LLM generation
│   │   ├── approval_service.py           # Approve/reject logic
│   │   ├── regeneration_service.py       # Bounded retry
│   │   ├── safety_filter_service.py      # Profanity/threat detection
│   │   ├── llm_cache_service.py          # Redis caching
│   │   └── cleanup_service.py            # Ephemeral data cleanup
│   ├── api/
│   │   ├── summary_routes.py             # POST /summaries/*, GET /summaries/{id}
│   │   └── correction_routes.py          # POST /summaries/{id}/correction
│   ├── prompts/
│   │   ├── base_summary_prompt.py        # Base summarization prompt
│   │   └── correction_prompts.py         # Correction-aware prompts
│   └── events/
│       └── handlers/                     # Event handlers
├── cache/redis_client.py                 # Redis connection
├── llm/openai_client.py                  # OpenAI SDK client
├── config.py                             # Environment config
├── main.py                               # FastAPI app
├── events/bus.py                         # Event bus
└── logging_config.py                     # Logging setup
```

### Frontend Structure
```
frontend/src/
├── components/
│   ├── SummaryReview/
│   │   ├── SummaryReview.tsx             # Approve/reject buttons
│   │   └── SummaryReview.css
│   ├── CorrectionSignalForm/
│   │   ├── CorrectionSignalForm.tsx      # Reason tags + feedback
│   │   └── CorrectionSignalForm.css
│   └── SafetyNotice/
│       ├── SafetyNotice.tsx              # Safety warnings
│       └── SafetyNotice.css
├── pages/
│   └── ApprovalInterface/
│       ├── ApprovalInterface.tsx         # Main approval page
│       └── ApprovalInterface.css
└── services/
    └── summaryApi.ts                     # API client
```

---

## API Endpoints (Available)

### Summarization Endpoints
```
POST   /api/v1/summaries/generate          # Generate summary from submission
GET    /api/v1/summaries/{summary_id}      # Get summary by ID
POST   /api/v1/summaries/{summary_id}/approve    # Approve summary
POST   /api/v1/summaries/{summary_id}/reject     # Reject summary
POST   /api/v1/summaries/{summary_id}/correction # Submit correction signal
```

### Health & Documentation
```
GET    /health                             # Health check
GET    /docs                               # Swagger UI
GET    /redoc                              # ReDoc UI
```

---

## Database Schema (Available)

### Summaries Table
```sql
CREATE TABLE summaries (
    summary_id UUID PRIMARY KEY,
    submission_id UUID REFERENCES submissions(submission_id),
    participant_id UUID REFERENCES participants(participant_id),
    round_id UUID REFERENCES rounds(round_id),
    summary_text VARCHAR(500) NOT NULL,
    status summarystatus NOT NULL DEFAULT 'pending_review',
    regen_count INTEGER NOT NULL DEFAULT 0,
    safety_flags VARCHAR[],
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP
);
```

**Status Enum:**
- `pending_review` - Initial state after generation
- `approved` - Participant approved, forward to clustering
- `rejected` - Rejected, regeneration triggered
- `rejected_final` - Final rejection after correction
- `disallowed_content` - Safety filter blocked
- `approval_timeout` - Deadline exceeded
- `superseded` - Replaced by newer approved summary

### Correction_Signals Table
```sql
CREATE TABLE correction_signals (
    signal_id UUID PRIMARY KEY,
    summary_id UUID REFERENCES summaries(summary_id),
    reason_tag reasontag NOT NULL,
    feedback_text VARCHAR(240),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Reason Tag Enum:**
- `wrong_crux` - Missed the main point
- `too_vague` - Not specific enough
- `misrepresents_me` - Inaccurate representation
- `missed_constraint` - Overlooked important constraint
- `missed_solution` - Overlooked proposed solution
- `other` - Other reason

---

## Environment Variables (Required)

### Backend (.env)
```bash
# Database
DATABASE_URL=postgresql+asyncpg://opendiscuss:opendiscuss_dev@localhost:5432/opendiscuss

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI (Spec 003)
OPENAI_API_KEY=sk-your-key-here
OPENAI_ORG_ID=org-your-org-id  # Optional
OPENAI_DEFAULT_MODEL=gpt-4-turbo
OPENAI_FALLBACK_MODEL=gpt-3.5-turbo
LLM_CACHE_TTL_SECONDS=3600

# Application
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO

# Approval Settings
ENABLE_APPROVAL_TIMEOUT=True
APPROVAL_TIMEOUT_MINUTES=10
SUBMISSION_TTL_MINUTES=5
```

### Frontend (.env)
```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

---

## Event Types (Available)

### Spec 2 → Spec 3 Handoff
```python
EVENT_SUBMISSION_CREATED = "submission.created"
```

### Spec 3 Internal Events
```python
EVENT_SUMMARY_GENERATED = "summary.generated"
EVENT_SUMMARY_REJECTED = "summary.rejected"
EVENT_CORRECTION_SIGNAL = "correction_signal.provided"
EVENT_APPROVAL_TIMEOUT = "approval.timeout"
```

### Spec 3 → Spec 4 Handoff
```python
EVENT_SUMMARY_APPROVED_FINAL = "summary.approved"
EVENT_SUMMARY_REJECTED_FINAL = "summary.rejected_final"
```

---

## Services (Available)

### Backend Services
1. **SummarizationService** - LLM generation with caching
   - `generate_summary()` - Generate summary from submission
   - Model selection (GPT-4-turbo default, GPT-3.5 fallback)

2. **ApprovalService** - Approve/reject workflow
   - `approve_summary()` - Approve summary, forward to clustering
   - `reject_summary()` - Reject summary, trigger regeneration
   - Last-approved-wins logic

3. **RegenerationService** - Bounded retry logic
   - `regenerate_summary()` - Regenerate with varied prompts
   - Max 2 automatic retries (regen_count 0-2)

4. **SafetyFilterService** - Profanity and threat detection
   - `filter_submission()` - Profanity neutralization
   - `check_threats()` - OpenAI Moderation API
   - DISALLOWED_CONTENT status on threats

5. **LLMCacheService** - Redis caching for LLM responses
   - `get_cached_response()` - Check cache before LLM call
   - `set_cached_response()` - Store with TTL=3600s

6. **CleanupService** - Ephemeral data cleanup
   - `cleanup_submissions()` - Delete raw submissions after approval
   - TTL=5 min grace period

### Frontend Services
1. **summaryApi.ts** - API client for summary endpoints
   - `generateSummary()` - POST /summaries/generate
   - `getSummary()` - GET /summaries/{id}
   - `approveSummary()` - POST /summaries/{id}/approve
   - `rejectSummary()` - POST /summaries/{id}/reject
   - `submitCorrection()` - POST /summaries/{id}/correction

---

## Testing Infrastructure

### Backend Tests
```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run specific test file
poetry run pytest tests/unit/test_summarization_service.py

# Run integration tests
poetry run pytest tests/integration/
```

### Frontend Tests
```bash
# Run unit tests
npm run test:unit

# Run unit tests in watch mode
npm run test:unit:watch

# Run E2E tests
npm run test:e2e

# Run E2E tests with UI
npm run test:e2e:ui

# Run E2E tests in debug mode
npm run test:e2e:debug
```

---

## User Story Status

### Phase 3: User Story 1 - Generate and Approve (P1) ✅ COMPLETED
- Generate summary from submission
- Approve/reject workflow
- Forward approved summaries to clustering

### Phase 4: User Story 2 - Reject and Regenerate (P2) ✅ COMPLETED
- Bounded retry (max 2 automatic regenerations)
- Regeneration prompt templates
- Rejection workflow

### Phase 5: User Story 3 - Correction Signal (P3) ⏳ IN PROGRESS
- Correction signal after 2 rejections
- Reason tags + feedback text
- Final regeneration with correction
- REJECTED_FINAL status

### Phase 6: User Story 4 - Safety Filtering (P4) ✅ COMPLETED
- Profanity neutralization
- Threat detection
- DISALLOWED_CONTENT status

### Phase 7: User Story 5 - Multiple Submissions (P5) ⏳ PENDING
- Last-approved-wins selection
- SUPERSEDED status
- Multiple submission handling

### Phase 8: Additional Features ✅ COMPLETED
- LLM caching
- Approval timeout
- Ephemeral cleanup
- Integration tests

### Phase 9: Polish ✅ COMPLETED
- Rate limiting
- Performance monitoring
- Analytics
- Unit tests

---

## Constitutional Principles

### Intent Fidelity (This spec IS the approval gate)
- Only `status=approved` summaries forwarded to clustering
- Status FSM enforces explicit approval
- No unapproved content propagation

### Parallel-First Architecture
- Independent summary generation per participant
- No reactive dependencies
- Async LLM calls with caching

### Temporal Transparency
- `approved_at` timestamp for movement tracking
- Last-approved-wins selection logic
- Stable participant tracking

### Ephemeral Raw Data
- Submission TTL after approval (5 min grace period)
- Raw text retained only during summarization
- Approved summaries persist indefinitely

---

## Common Tasks

### Add a New API Endpoint
1. Define route in `backend/src/summarization/api/summary_routes.py`
2. Add Pydantic request/response models
3. Implement business logic in service layer
4. Add tests in `backend/tests/`
5. Update OpenAPI documentation

### Add a New Frontend Component
1. Create component in `frontend/src/components/`
2. Add TypeScript types in component file
3. Add CSS styles
4. Export from `index.ts`
5. Add tests in `frontend/tests/`

### Add a New Event Type
1. Define constant in `backend/src/events/bus.py`
2. Create event handler in `backend/src/summarization/events/handlers/`
3. Subscribe handler in service or main.py
4. Publish event from service layer
5. Add tests for event flow

### Add a New Database Migration
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/
poetry run alembic revision -m "description of change"
# Edit generated migration file
poetry run alembic upgrade head
```

---

## Troubleshooting

### Backend Issues

**Problem**: `ModuleNotFoundError: No module named 'fastapi'`
**Solution**: Ensure you're using poetry environment
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/
poetry install
poetry run uvicorn src.main:app --reload
```

**Problem**: `redis.ConnectionError`
**Solution**: Ensure Redis is running
```bash
# Start Redis with Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or check if Redis is running
redis-cli ping  # Should return PONG
```

**Problem**: `sqlalchemy.exc.OperationalError`
**Solution**: Ensure PostgreSQL is running and migrations are applied
```bash
# Check PostgreSQL
psql -h localhost -U opendiscuss -d opendiscuss

# Run migrations
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/
poetry run alembic upgrade head
```

### Frontend Issues

**Problem**: `Module not found` errors
**Solution**: Ensure dependencies are installed
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend/
npm install
```

**Problem**: CORS errors in browser
**Solution**: Check CORS configuration in backend
```python
# backend/src/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Resources

### Documentation
- **Full Completion Report**: `/specs/003-summarization-approval/PHASE1_PHASE2_COMPLETION_REPORT.md`
- **Tasks List**: `/specs/003-summarization-approval/tasks.md`
- **Spec Document**: `/specs/003-summarization-approval/spec.md`
- **Plan Document**: `/specs/003-summarization-approval/plan.md`
- **API Documentation**: `http://localhost:8000/docs` (when backend running)

### Key Dependencies Documentation
- FastAPI: https://fastapi.tiangolo.com/
- OpenAI SDK: https://platform.openai.com/docs/api-reference
- Pydantic: https://docs.pydantic.dev/
- SQLAlchemy: https://docs.sqlalchemy.org/
- Redis: https://redis.io/docs/
- React: https://react.dev/
- TypeScript: https://www.typescriptlang.org/docs/
- TanStack Query: https://tanstack.com/query/latest

---

**Last Updated**: 2026-02-01
**Phase Status**: Phase 1 & 2 COMPLETE ✅
**Next Action**: Implement remaining user stories (US3, US5) or start new feature
