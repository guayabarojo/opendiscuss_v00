# Quickstart Guide: Input Collection Protocol

**Feature**: Input Collection Protocol (Spec 002)
**Date**: 2026-01-29
**Audience**: Developers implementing or integrating with Input Collection

## Overview

This guide helps you:
1. Set up the development environment for Input Collection
2. Run the protocol locally
3. Test core functionality (window enforcement, rate limiting, voice transcription)
4. Integrate with Spec 3 (Summarization & Approval Protocol)

**Estimated time**: 30 minutes

---

## Prerequisites

### Required

- **Python 3.11+**: Language runtime
- **PostgreSQL 15+**: Persistent storage
- **Node.js 18+**: Frontend development
- **OpenAI API Key**: For Whisper voice transcription

### Optional

- **Redis 7+**: For production event bus (can use in-memory pub/sub for MVP)
- **Docker**: For containerized PostgreSQL

---

## Setup

### 1. Clone Repository

```bash
git clone https://github.com/opendiscuss/opendiscuss.git
cd opendiscuss
```

### 2. Backend Setup

#### Install Dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**requirements.txt**:
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
openai==1.10.0
python-dotenv==1.0.0
pytest==7.4.4
pytest-asyncio==0.23.3
httpx==0.26.0
```

#### Configure Environment

Create `.env` file in `backend/` directory:

```bash
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/opendiscuss_dev

# OpenAI (for voice transcription)
OPENAI_API_KEY=sk-your-api-key-here

# Application
DEBUG=true
MAX_SUBMISSIONS_PER_ROUND=3
SUBMISSION_WINDOW_DURATION_MINUTES=5

# Event Bus (optional for MVP, defaults to in-memory)
REDIS_URL=redis://localhost:6379/0
```

#### Initialize Database

```bash
# Start PostgreSQL (Docker example)
docker run --name postgres-dev \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=opendiscuss_dev \
  -p 5432:5432 \
  -d postgres:15

# Run migrations
alembic upgrade head
```

**Migration creates tables**:
- `participants`
- `rounds`
- `submission_metadata`

#### Run Backend

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**Verify**:
```bash
curl http://localhost:8000/health
# {"status": "healthy", "spec": "input-collection"}
```

---

### 3. Frontend Setup

#### Install Dependencies

```bash
cd ../frontend
npm install
```

**package.json** (key dependencies):
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "typescript": "^5.0.0",
    "axios": "^1.6.5",
    "@types/react": "^18.2.48"
  }
}
```

#### Configure Environment

Create `.env` file in `frontend/` directory:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

#### Run Frontend

```bash
npm run dev
```

**Expected output**:
```
  VITE v5.0.11  ready in 500 ms

  ➜  Local:   http://localhost:5173/
```

**Verify**: Open http://localhost:5173/ in browser

---

## Basic Usage

### Scenario 1: Submit Text Input

#### Step 1: Create a Round (via Spec 1 API)

```bash
curl -X POST http://localhost:8000/api/v1/rounds \
  -H "Content-Type: application/json" \
  -d '{
    "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
    "round_number": 1,
    "window_start": "2026-01-29T14:00:00Z",
    "window_end": "2026-01-29T14:05:00Z"
  }'
```

**Response**:
```json
{
  "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
  "status": "PENDING"
}
```

#### Step 2: Get Window Status

```bash
curl http://localhost:8000/api/v1/rounds/r1234567-89ab-cdef-0123-456789abcdef/window
```

**Response** (if within window):
```json
{
  "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
  "window_start": "2026-01-29T14:00:00Z",
  "window_end": "2026-01-29T14:05:00Z",
  "current_time": "2026-01-29T14:02:30Z",
  "time_remaining_seconds": 150,
  "is_open": true,
  "status": "ACTIVE"
}
```

#### Step 3: Submit Text

```bash
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt-token>" \
  -d '{
    "participant_id": "p1234567-89ab-cdef-0123-456789abcdef",
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
    "submission_text": "I think we should prioritize accessibility features.",
    "modality": "TEXT"
  }'
```

**Response**:
```json
{
  "submission_id": "s1234567-89ab-cdef-0123-456789abcdef",
  "participant_id": "p1234567-89ab-cdef-0123-456789abcdef",
  "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
  "timestamp": "2026-01-29T14:02:30.123Z",
  "modality": "TEXT",
  "counted": false,
  "message": "Submission accepted. Awaiting summarization."
}
```

#### Step 4: Verify Event Published

Check logs for:
```
INFO: Published event: submission.created
INFO: Event ID: e1234567-89ab-cdef-0123-456789abcdef
INFO: Submission ID: s1234567-89ab-cdef-0123-456789abcdef
```

---

### Scenario 2: Submit Voice Input

#### Step 1: Record Audio (Frontend)

Use browser MediaRecorder API or upload existing audio file.

#### Step 2: Transcribe Audio

```bash
curl -X POST http://localhost:8000/api/v1/voice/transcribe \
  -H "Authorization: Bearer <jwt-token>" \
  -F "audio=@recording.wav" \
  -F "participant_id=p1234567-89ab-cdef-0123-456789abcdef" \
  -F "round_id=r1234567-89ab-cdef-0123-456789abcdef"
```

**Response** (typically < 3 seconds):
```json
{
  "transcript_id": "t1234567-89ab-cdef-0123-456789abcdef",
  "recording_id": "a1234567-89ab-cdef-0123-456789abcdef",
  "transcript_text": "We need to improve onboarding for new users.",
  "reviewed": false,
  "latency_ms": 1820
}
```

#### Step 3: Review Transcript (Frontend)

Display `transcript_text` to participant with options:
- **Accept**: Proceed to Step 4
- **Re-record**: DELETE recording and retry

```bash
# If re-recording
curl -X DELETE http://localhost:8000/api/v1/voice/a1234567-89ab-cdef-0123-456789abcdef
```

#### Step 4: Accept Transcript

Submit transcript as text (same as Scenario 1 Step 3):

```bash
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt-token>" \
  -d '{
    "participant_id": "p1234567-89ab-cdef-0123-456789abcdef",
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
    "submission_text": "We need to improve onboarding for new users.",
    "modality": "VOICE"
  }'
```

---

### Scenario 3: Test Window Enforcement

#### Submit Before Window Opens

```bash
# Assuming current time is 13:59:00, window opens at 14:00:00
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -d '{
    "participant_id": "p1234567-89ab-cdef-0123-456789abcdef",
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
    "submission_text": "Early submission attempt.",
    "modality": "TEXT"
  }'
```

**Expected Response** (422):
```json
{
  "error": "OUTSIDE_WINDOW",
  "message": "The submission window has not opened yet.",
  "details": {
    "window_start": "2026-01-29T14:00:00Z",
    "window_end": "2026-01-29T14:05:00Z",
    "current_time": "2026-01-29T13:59:00Z",
    "status": "BEFORE_WINDOW"
  }
}
```

#### Submit After Window Closes

```bash
# Assuming current time is 14:05:01, window closed at 14:05:00
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -d '{
    "participant_id": "p1234567-89ab-cdef-0123-456789abcdef",
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
    "submission_text": "Late submission attempt.",
    "modality": "TEXT"
  }'
```

**Expected Response** (422):
```json
{
  "error": "OUTSIDE_WINDOW",
  "message": "The submission window has closed.",
  "details": {
    "window_start": "2026-01-29T14:00:00Z",
    "window_end": "2026-01-29T14:05:00Z",
    "current_time": "2026-01-29T14:05:01Z",
    "status": "AFTER_WINDOW"
  }
}
```

---

### Scenario 4: Test Rate Limiting

```bash
# Assuming MAX_SUBMISSIONS_PER_ROUND=3

# Submission 1 (accepted)
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -d '{"participant_id": "p1234567-89ab-cdef-0123-456789abcdef", "round_id": "r1234567-89ab-cdef-0123-456789abcdef", "submission_text": "First attempt.", "modality": "TEXT"}'
# Response: 201 Created

# Submission 2 (accepted)
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -d '{"participant_id": "p1234567-89ab-cdef-0123-456789abcdef", "round_id": "r1234567-89ab-cdef-0123-456789abcdef", "submission_text": "Second attempt.", "modality": "TEXT"}'
# Response: 201 Created

# Submission 3 (accepted)
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -d '{"participant_id": "p1234567-89ab-cdef-0123-456789abcdef", "round_id": "r1234567-89ab-cdef-0123-456789abcdef", "submission_text": "Third attempt.", "modality": "TEXT"}'
# Response: 201 Created

# Submission 4 (rejected - rate limit exceeded)
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -d '{"participant_id": "p1234567-89ab-cdef-0123-456789abcdef", "round_id": "r1234567-89ab-cdef-0123-456789abcdef", "submission_text": "Fourth attempt.", "modality": "TEXT"}'
```

**Expected Response** (403):
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "You have reached the maximum of 3 submissions for this round.",
  "details": {
    "submissions_count": 3,
    "max_allowed": 3,
    "round_id": "r1234567-89ab-cdef-0123-456789abcdef"
  }
}
```

---

## Testing

### Run Unit Tests

```bash
cd backend
pytest tests/unit/ -v
```

**Key test files**:
- `test_window_enforcement.py`: Boundary conditions (inclusive start, exclusive end)
- `test_rate_limiter.py`: Concurrent submission race conditions
- `test_input_collection.py`: Text normalization, validation

**Example test**:
```python
# tests/unit/test_window_enforcement.py
import pytest
from datetime import datetime, timedelta
from src.services.window_enforcement import is_within_window

def test_inclusive_start_boundary():
    """FR-009: Submission at exact window start should be accepted"""
    window_start = datetime(2026, 1, 29, 14, 0, 0)
    window_end = datetime(2026, 1, 29, 14, 5, 0)
    submission_time = datetime(2026, 1, 29, 14, 0, 0)  # Exact start

    assert is_within_window(submission_time, window_start, window_end) == True

def test_exclusive_end_boundary():
    """FR-009: Submission at exact window end should be rejected"""
    window_start = datetime(2026, 1, 29, 14, 0, 0)
    window_end = datetime(2026, 1, 29, 14, 5, 0)
    submission_time = datetime(2026, 1, 29, 14, 5, 0)  # Exact end

    assert is_within_window(submission_time, window_start, window_end) == False
```

**Run**:
```bash
pytest tests/unit/test_window_enforcement.py -v
```

**Expected output**:
```
tests/unit/test_window_enforcement.py::test_inclusive_start_boundary PASSED
tests/unit/test_window_enforcement.py::test_exclusive_end_boundary PASSED
```

---

### Run Integration Tests

```bash
pytest tests/integration/ -v
```

**Key test files**:
- `test_submission_flow.py`: End-to-end submission acceptance
- `test_voice_transcription.py`: Whisper API integration
- `test_event_publishing.py`: Event bus integration with Spec 3

**Example test**:
```python
# tests/integration/test_submission_flow.py
import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_text_submission_full_flow():
    """Test complete text submission flow"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Create round
        round_response = await client.post("/api/v1/rounds", json={
            "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
            "round_number": 1,
            "window_start": "2026-01-29T14:00:00Z",
            "window_end": "2026-01-29T14:05:00Z"
        })
        assert round_response.status_code == 201
        round_id = round_response.json()["round_id"]

        # 2. Submit text
        submission_response = await client.post("/api/v1/submissions", json={
            "participant_id": "p1234567-89ab-cdef-0123-456789abcdef",
            "round_id": round_id,
            "submission_text": "Test submission",
            "modality": "TEXT"
        })
        assert submission_response.status_code == 201
        submission_data = submission_response.json()
        assert submission_data["counted"] == False

        # 3. Verify event published
        # (Check event bus mock or logs)
```

---

### Run Contract Tests

```bash
pytest tests/contract/ -v
```

**Purpose**: Verify Spec 2 → Spec 3 integration contract

**Example test**:
```python
# tests/contract/test_submission_to_summarization.py
import pytest
from src.events import publish_submission_created
from tests.mocks import MockSummarizationService

@pytest.mark.asyncio
async def test_submission_created_event_schema():
    """Verify submission.created event matches contract"""
    mock_subscriber = MockSummarizationService()

    # Publish event
    await publish_submission_created(
        submission_id="s1234567-89ab-cdef-0123-456789abcdef",
        user_id="p1234567-89ab-cdef-0123-456789abcdef",
        round_id="r1234567-89ab-cdef-0123-456789abcdef",
        submission_text="Test submission",
        timestamp="2026-01-29T14:02:30Z",
        modality="TEXT"
    )

    # Verify subscriber received correct schema
    received_event = mock_subscriber.last_received_event
    assert received_event["event_type"] == "submission.created"
    assert "submission_id" in received_event["data"]
    assert "submission_text" in received_event["data"]
    assert received_event["data"]["submission_text"] == "Test submission"
```

---

## Integration with Spec 3 (Summarization)

### Event Bus Setup

**Option A: In-Memory Pub/Sub (MVP)**

```python
# src/events/in_memory_bus.py
subscribers = {}

def subscribe(event_type, handler):
    """Register event handler"""
    if event_type not in subscribers:
        subscribers[event_type] = []
    subscribers[event_type].append(handler)

async def publish(event_type, payload):
    """Publish event to all subscribers"""
    if event_type in subscribers:
        for handler in subscribers[event_type]:
            await handler(payload)
```

**Option B: Redis Pub/Sub (Production)**

```python
# src/events/redis_bus.py
import redis.asyncio as redis

async def publish(event_type, payload):
    """Publish event to Redis channel"""
    r = await redis.from_url(REDIS_URL)
    await r.publish(f"opendiscuss.{event_type}", json.dumps(payload))
```

### Publish Submission Event

```python
# src/services/input_collection.py
from src.events import publish

async def accept_submission(submission_request):
    # 1. Validate window and rate limit
    # 2. Create SubmissionMetadata
    # 3. Store RawSubmission
    # 4. Publish event
    await publish("submission.created", {
        "event_id": str(uuid4()),
        "event_type": "submission.created",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "submission_id": submission.submission_id,
            "user_id": submission.participant_id,
            "round_id": submission.round_id,
            "submission_text": submission.submission_text,
            "timestamp": submission.timestamp.isoformat(),
            "modality": submission.modality
        }
    })
```

### Subscribe to Summarization Events

```python
# src/services/cleanup.py
from src.events import subscribe

@subscribe("summarization.completed")
async def cleanup_ephemeral_data(event):
    """Delete RawSubmission data when summarization completes"""
    round_id = event["data"]["round_id"]

    # Delete all raw submissions for round
    submissions = get_submissions_for_round(round_id)
    for submission_id in submissions:
        if submission_id in raw_submissions:
            del raw_submissions[submission_id]
            logger.info(f"Deleted ephemeral data for submission {submission_id}")

    # Update round status
    update_round_status(round_id, "COMPLETED")
```

---

## Troubleshooting

### Issue: Voice transcription times out

**Symptom**: `/voice/transcribe` returns 500 after 30 seconds

**Causes**:
1. Invalid OpenAI API key
2. Large audio file (> 25 MB)
3. Network issues

**Solutions**:
```bash
# Check API key
echo $OPENAI_API_KEY

# Test Whisper API directly
curl https://api.openai.com/v1/audio/transcriptions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F file=@test.wav \
  -F model=whisper-1

# Reduce audio file size (compress to MP3)
ffmpeg -i recording.wav -b:a 64k recording.mp3
```

---

### Issue: Submissions rejected with "OUTSIDE_WINDOW" despite timer showing time remaining

**Symptom**: Client sees 2:30 remaining, but submission rejected

**Cause**: Client clock skew

**Solution**: Use server-authoritative time from `/rounds/{id}/window` endpoint

```typescript
// Frontend: Calculate time remaining using server time
const serverTime = new Date(windowStatus.current_time);
const localTime = new Date();
const skew = serverTime.getTime() - localTime.getTime();

// Apply skew to countdown
const adjustedTimeRemaining = windowStatus.time_remaining_seconds - (skew / 1000);
```

---

### Issue: Rate limit shows 2 submissions, but 4th submission accepted

**Symptom**: Race condition in concurrent submissions

**Cause**: Missing lock in `check_and_increment_rate_limit`

**Solution**: Ensure per-key locking

```python
# src/services/rate_limiter.py
import threading

rate_limit_locks = {}

def check_and_increment_rate_limit(participant_id, round_id):
    key = (participant_id, round_id)

    # Get or create lock
    if key not in rate_limit_locks:
        rate_limit_locks[key] = threading.Lock()

    with rate_limit_locks[key]:
        # Atomic check and increment
        current = rate_limits.get(key, 0)
        if current >= MAX_SUBMISSIONS:
            return False
        rate_limits[key] = current + 1
        return True
```

---

## Next Steps

1. **Implement Spec 3 Integration**: Subscribe to `submission.created` events in Summarization service
2. **Add Frontend Timer**: WebSocket client for real-time countdown updates
3. **Deploy to Staging**: Test with 100 concurrent users (performance benchmark)
4. **Enable Analytics**: Log submission metadata for MVP analysis (without raw text)

---

## Resources

- **API Spec**: `contracts/api-spec.yaml`
- **Event Contract**: `contracts/events.yaml`
- **Data Model**: `data-model.md`
- **Research**: `research.md`

**Support**: Open an issue at https://github.com/opendiscuss/issues
