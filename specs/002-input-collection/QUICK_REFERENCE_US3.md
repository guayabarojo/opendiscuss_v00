# Quick Reference: User Story 3 Implementation

## API Endpoints

### Submit Text
```http
POST /api/v1/submissions/
Content-Type: application/json

{
  "participant_id": "uuid",
  "round_id": "uuid",
  "text": "Submission text (1-5000 chars)",
  "modality": "TEXT"
}

Response (201 Created):
{
  "submission_id": "uuid",
  "participant_id": "uuid",
  "round_id": "uuid",
  "timestamp": "2026-02-01T12:00:00Z",
  "modality": "TEXT",
  "counted": false
}

Response (429 Too Many Requests):
{
  "error_code": "TOO_MANY_REQUESTS",
  "message": "Rate limit exceeded",
  "details": "Rate limit exceeded: maximum 3 submissions per round"
}
```

### Get Participant Submissions
```http
GET /api/v1/submissions/participant/{participant_id}/round/{round_id}

Response (200 OK):
{
  "submissions": [
    {
      "submission_id": "uuid",
      "participant_id": "uuid",
      "round_id": "uuid",
      "timestamp": "2026-02-01T12:00:00Z",
      "modality": "TEXT",
      "counted": true
    }
  ],
  "total_count": 3,
  "max_allowed": 3,
  "can_submit_more": false
}
```

## Frontend Components

### InputCollectionHistory
```tsx
import { InputCollectionHistory } from '@/components/InputCollectionHistory';

<InputCollectionHistory
  participantId="uuid"
  roundId="uuid"
  onEdit={(submission) => {
    // Handle edit click
  }}
/>
```

### TextInputForm with Rate Limiting
```tsx
import { TextInputForm } from '@/components/TextInputForm';

<TextInputForm
  participantId="uuid"
  roundId="uuid"
  onSubmit={async (text) => {
    await submitText(participantId, roundId, text);
  }}
  disabled={false}
  initialText="" // For editing previous submissions
  remainingSubmissions={3} // Show remaining count
/>
```

### RoundInputPage (Complete Integration)
```tsx
import { RoundInputPage } from '@/pages/RoundInputPage';

<RoundInputPage
  participantId="uuid"
  roundId="uuid"
/>
```

## API Client Usage

```typescript
import {
  submitText,
  getParticipantSubmissions,
  SubmissionListResponse
} from '@/services/submissionApi';

// Submit text
try {
  const response = await submitText(participantId, roundId, "My response");
  console.log('Submission successful:', response.submission_id);
} catch (error) {
  if (error.response?.status === 429) {
    console.error('Rate limit exceeded');
  }
}

// Get submissions
const history: SubmissionListResponse = await getParticipantSubmissions(
  participantId,
  roundId
);

console.log(`${history.total_count}/${history.max_allowed} submissions`);
console.log('Can submit more:', history.can_submit_more);

// Find counted submission
const countedSubmission = history.submissions.find(s => s.counted);
```

## Backend Service Usage

```python
from src.services.input_collection import accept_submission, RateLimitExceeded
from src.models.submission_metadata import SubmissionModality

try:
    metadata = await accept_submission(
        participant_id=participant_id,
        round_id=round_id,
        text="Submission text",
        modality=SubmissionModality.TEXT,
        window_start=round.submission_window_start,
        window_end=round.submission_window_end,
        db_session=db
    )
    await db.commit()
except RateLimitExceeded as e:
    # Handle rate limit error (return 429)
    raise HTTPException(status_code=429, detail=str(e))
```

## Rate Limit Configuration

```python
# backend/src/config.py
max_submissions_per_round: int = 3  # Maximum submissions per participant
submission_window_duration_minutes: int = 5  # Window duration for rate tracking
```

## Event Handling

```python
# Listen for summary approval
from src.events.bus import event_bus, EVENT_SUMMARY_APPROVED

@event_handler
async def handle_summary_approved(event):
    submission_id = event.payload["submission_id"]
    participant_id = event.payload["participant_id"]
    round_id = event.payload["round_id"]

    # "Last approved wins" logic implemented in:
    # backend/src/events/approval_handler.py
```

## Testing

```bash
# Run integration tests
cd backend
pytest tests/integration/test_rate_limiting.py -v

# Test specific scenario
pytest tests/integration/test_rate_limiting.py::test_rate_limiting_max_submissions -v
```

## Common Scenarios

### Submit Multiple Times
```typescript
// Submit 3 times (all succeed)
for (let i = 1; i <= 3; i++) {
  await submitText(participantId, roundId, `Submission ${i}`);
}

// 4th submission fails with 429
try {
  await submitText(participantId, roundId, "Submission 4");
} catch (error) {
  console.error('Rate limit exceeded:', error.response?.status === 429);
}
```

### Check Submission Status
```typescript
const history = await getParticipantSubmissions(participantId, roundId);

if (!history.can_submit_more) {
  console.log('Rate limit reached');
}

// Show which submission is counted
const counted = history.submissions.find(s => s.counted);
if (counted) {
  console.log('Counted submission:', counted.submission_id);
}
```

### Display Rate Limit Status
```tsx
const [history, setHistory] = useState<SubmissionListResponse | null>(null);

useEffect(() => {
  const fetchHistory = async () => {
    const data = await getParticipantSubmissions(participantId, roundId);
    setHistory(data);
  };
  fetchHistory();
}, [participantId, roundId]);

return (
  <div>
    <p>
      {history?.total_count} / {history?.max_allowed} submissions
    </p>
    {!history?.can_submit_more && (
      <p>Rate limit reached</p>
    )}
  </div>
);
```

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `TOO_MANY_REQUESTS` | 429 | Exceeded max 3 submissions |
| `OUTSIDE_WINDOW` | 422 | Submission window closed |
| `VALIDATION_FAILED` | 400 | Invalid text input |

## Key Files

### Backend
- `backend/src/services/input_collection.py` - Rate limiting logic
- `backend/src/api/routes/submissions.py` - Endpoints
- `backend/src/events/approval_handler.py` - "Last approved wins"
- `backend/src/services/ephemeral_storage.py` - Rate limit tracking

### Frontend
- `frontend/src/components/InputCollectionHistory.tsx` - History display
- `frontend/src/components/TextInputForm.tsx` - Form with rate limit
- `frontend/src/pages/RoundInputPage.tsx` - Complete page
- `frontend/src/services/submissionApi.ts` - API client

## Database Schema

```sql
CREATE TABLE submission_metadata (
    submission_id UUID PRIMARY KEY,
    participant_id UUID NOT NULL,
    round_id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    modality VARCHAR(10) NOT NULL,
    counted BOOLEAN NOT NULL DEFAULT FALSE,

    -- Ensure only one counted per (participant, round)
    CONSTRAINT one_counted_submission_per_participant_round
    EXCLUDE USING btree (participant_id WITH =, round_id WITH =)
    WHERE (counted = true)
);

CREATE INDEX idx_submission_metadata_participant ON submission_metadata(participant_id);
CREATE INDEX idx_submission_metadata_round ON submission_metadata(round_id);
CREATE INDEX idx_submission_metadata_counted ON submission_metadata(counted);
```
