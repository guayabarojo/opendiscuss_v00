# Testing Guide: Spec 003 User Story 1 - Generate and Approve Summary

**Last Updated**: 2026-02-01
**Status**: MVP Ready for Testing

## Prerequisites

1. **Database**: PostgreSQL 14+ running
2. **Redis**: Redis 6+ running  
3. **OpenAI API Key**: Required for GPT-4-turbo summarization
4. **Backend**: Python 3.11+ with Poetry
5. **Frontend**: Node.js 18+ with npm

## Setup

### 1. Database Migration

```bash
cd backend

# Run migrations to create tables
poetry run alembic upgrade head

# Verify tables created:
# - summaries
# - correction_signals
```

### 2. Environment Configuration

Create/update `backend/.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://opendiscuss:opendiscuss_dev@localhost:5432/opendiscuss

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI (REQUIRED for summarization)
OPENAI_API_KEY=sk-...your-key-here...
OPENAI_ORG_ID=org-...optional...
OPENAI_DEFAULT_MODEL=gpt-4-turbo
OPENAI_FALLBACK_MODEL=gpt-3.5-turbo

# LLM Cache
LLM_CACHE_TTL_SECONDS=3600
```

### 3. Start Services

**Terminal 1 - Backend**:
```bash
cd backend
poetry run uvicorn src.main:app --reload --port 8000
```

**Terminal 2 - Frontend**:
```bash
cd frontend
npm run dev
```

## End-to-End Test Flow

### Step 1: Submit Input (Spec 002)

```bash
# Submit text input
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -d '{
    "participant_id": "<participant_uuid>",
    "round_id": "<round_uuid>",
    "submission_text": "I believe climate change is one of the most pressing issues of our time. We need immediate action to reduce carbon emissions and transition to renewable energy sources.",
    "modality": "text"
  }'
```

### Step 2: Automatic Summary Generation (Spec 2 → 3)

When submission window closes, summaries are generated automatically.

**Check Logs**:
```
[Spec 2→3] Received submission_window.closed for round <uuid>
[Spec 2→3] Summary generation complete: 5 successful, 0 failed
```

### Step 3: Get Generated Summary

```bash
curl http://localhost:8000/api/v1/summaries/submission/<submission_id>
```

### Step 4: Review Summary (Frontend)

Navigate to: `http://localhost:5173/approval?summaryId=<summary_uuid>`

### Step 5: Approve Summary

```bash
curl -X POST http://localhost:8000/api/v1/summaries/<summary_id>/approve
```

### Step 6: Verify Handoff to Clustering (Spec 3 → 4)

**Check Logs**:
```
[Spec 3→4] Emitted summarization.complete event for round <uuid>
[Spec 3→4] Round transitioned: SUMMARIZING → CLUSTERING
```

## API Endpoints

- `POST /api/v1/summaries/generate` - Generate summary
- `POST /api/v1/summaries/{id}/approve` - Approve summary
- `POST /api/v1/summaries/{id}/reject` - Reject summary
- `GET /api/v1/summaries/{id}` - Get summary
- `GET /api/v1/summaries/submission/{id}` - Get all summaries

## Verification Checklist

- [ ] Summary generated with status=PENDING_REVIEW
- [ ] Summary text <= 500 characters
- [ ] Approval sets approved_at timestamp
- [ ] Event logs show Spec 2→3 handoff
- [ ] Event logs show Spec 3→4 handoff
- [ ] Only approved summaries forwarded to clustering

## Troubleshooting

**No summary generated**: Check OpenAI API key and backend logs  
**Approval fails**: Verify summary status is PENDING_REVIEW  
**Event handler not firing**: Check Redis connection and event bus initialization

---

See `IMPLEMENTATION_SUMMARY_US1.md` for detailed documentation.
