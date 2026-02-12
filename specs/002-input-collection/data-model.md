# Data Model: Input Collection Protocol

**Feature**: Input Collection Protocol (Spec 002)
**Date**: 2026-01-29
**Phase**: Phase 1 - Design

## Purpose

This document defines the data model for parallel input collection, including entities, fields, relationships, validation rules, and state transitions. Extracted from functional requirements in spec.md and informed by research.md technology decisions.

---

## Entity Relationship Diagram

```
┌─────────────────┐
│   Participant   │
│                 │
│  participant_id │◄─────┐
│  community_id   │      │
│  created_at     │      │
└─────────────────┘      │
                         │
                         │
┌─────────────────┐      │
│      Round      │      │
│                 │      │
│  round_id       │◄──┐  │
│  discussion_id  │   │  │
│  window_start   │   │  │
│  window_end     │   │  │
│  status         │   │  │
└─────────────────┘   │  │
                      │  │
                      │  │
┌──────────────────┐  │  │
│   RateLimit      │  │  │
│  (in-memory)     │  │  │
│                  │  │  │
│  participant_id  ├──┼──┘
│  round_id        ├──┘
│  count           │
│  max_allowed     │
└──────────────────┘


┌──────────────────────┐
│  SubmissionMetadata  │
│                      │
│  submission_id (PK)  │
│  participant_id (FK) ├──────┘
│  round_id (FK)       ├────────┐
│  timestamp           │        │
│  modality            │        │
│  counted             │        │
└──────────────────────┘        │
                                │
┌──────────────────────┐        │
│  RawSubmission       │        │
│  (ephemeral)         │        │
│                      │        │
│  submission_id       ├────────┘
│  submission_text     │
│  ttl_expires_at      │
└──────────────────────┘


┌──────────────────────┐
│  AudioRecording      │
│  (ephemeral)         │
│                      │
│  recording_id        │
│  participant_id      │
│  audio_data          │
│  created_at          │
│  status              │
└──────────────────────┘
         │
         ▼
┌──────────────────────┐
│  Transcript          │
│  (ephemeral)         │
│                      │
│  transcript_id       │
│  recording_id (FK)   │
│  transcript_text     │
│  reviewed            │
│  accepted            │
└──────────────────────┘
```

**Legend**:
- **Solid boxes**: Persistent entities (PostgreSQL)
- **Dashed boxes** (ephemeral): In-memory only, never persisted to database
- **FK**: Foreign key relationship

---

## Persistent Entities

### 1. Participant

**Purpose**: Tracks participants across rounds to enable movement tracking (Temporal Transparency)

**Schema**:
```sql
CREATE TABLE participants (
    participant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_community
        FOREIGN KEY (community_id)
        REFERENCES communities(community_id)
);

CREATE INDEX idx_participants_community
    ON participants(community_id);
```

**Fields**:

| Field | Type | Constraints | Description | Source Requirement |
|-------|------|-------------|-------------|-------------------|
| `participant_id` | UUID | PRIMARY KEY | Stable identifier across rounds | FR-031, FR-032 |
| `community_id` | UUID | NOT NULL, FK | Community context for discussion | Constitution Principle V |
| `created_at` | TIMESTAMP | NOT NULL | Participant registration time | Audit trail |

**Validation Rules**:
- `participant_id` must be globally unique
- `community_id` must reference valid community
- Participant cannot be deleted while active submissions exist (enforce via FK constraints)

**Lifecycle**:
- **Created**: When user joins a community (handled by community/auth layer)
- **Referenced**: By submissions during rounds
- **Never Deleted**: Persist for historical movement tracking across all rounds

---

### 2. Round

**Purpose**: Defines time-bounded submission windows for parallel input collection

**Schema**:
```sql
CREATE TABLE rounds (
    round_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discussion_id UUID NOT NULL,
    round_number INT NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    CONSTRAINT fk_discussion
        FOREIGN KEY (discussion_id)
        REFERENCES discussions(discussion_id),
    CONSTRAINT chk_window_order
        CHECK (window_end > window_start),
    CONSTRAINT chk_status
        CHECK (status IN ('PENDING', 'ACTIVE', 'CLOSED', 'COMPLETED'))
);

CREATE INDEX idx_rounds_discussion
    ON rounds(discussion_id);
CREATE INDEX idx_rounds_status
    ON rounds(status);
```

**Fields**:

| Field | Type | Constraints | Description | Source Requirement |
|-------|------|-------------|-------------|-------------------|
| `round_id` | UUID | PRIMARY KEY | Unique identifier for round | - |
| `discussion_id` | UUID | NOT NULL, FK | Parent discussion | Spec 1 dependency |
| `round_number` | INT | NOT NULL | Sequential round number (1, 2, 3...) | Temporal ordering |
| `window_start` | TIMESTAMP | NOT NULL | Inclusive start boundary | FR-009 |
| `window_end` | TIMESTAMP | NOT NULL | Exclusive end boundary | FR-009 |
| `status` | VARCHAR(20) | NOT NULL | Current round state | State management |

**Status Values**:
- `PENDING`: Scheduled but not started
- `ACTIVE`: Accepting submissions (`NOW() >= window_start AND NOW() < window_end`)
- `CLOSED`: Window expired, awaiting summarization completion
- `COMPLETED`: Summarization done, ephemeral data cleared

**Validation Rules**:
- `window_end` must be after `window_start` (enforced via CHECK constraint)
- `window_start` must be in future when created (application logic)
- Default window duration: 5 minutes (configurable, MVP range 3-6 minutes per FR-005)
- Status transitions must follow state machine (see State Transitions below)

**State Transitions**:
```
PENDING → ACTIVE (when NOW() >= window_start)
ACTIVE → CLOSED (when NOW() >= window_end)
CLOSED → COMPLETED (when all summarizations done AND ephemeral data cleared)
```

**Lifecycle**:
- **Created**: By discussion orchestration (Spec 1) when scheduling rounds
- **Updated**: Status transitions triggered by timer or events
- **Never Deleted**: Persist for historical analysis

---

### 3. SubmissionMetadata

**Purpose**: Tracks submission metadata WITHOUT storing raw content (ephemeral data separation)

**Schema**:
```sql
CREATE TABLE submission_metadata (
    submission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id UUID NOT NULL,
    round_id UUID NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    modality VARCHAR(10) NOT NULL,
    counted BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_participant
        FOREIGN KEY (participant_id)
        REFERENCES participants(participant_id),
    CONSTRAINT fk_round
        FOREIGN KEY (round_id)
        REFERENCES rounds(round_id),
    CONSTRAINT chk_modality
        CHECK (modality IN ('TEXT', 'VOICE')),
    CONSTRAINT uq_counted_per_participant_round
        EXCLUDE USING btree (participant_id WITH =, round_id WITH =)
        WHERE (counted = TRUE)
);

CREATE INDEX idx_submission_metadata_participant_round
    ON submission_metadata(participant_id, round_id);
CREATE INDEX idx_submission_metadata_counted
    ON submission_metadata(counted) WHERE counted = TRUE;
```

**Fields**:

| Field | Type | Constraints | Description | Source Requirement |
|-------|------|-------------|-------------|-------------------|
| `submission_id` | UUID | PRIMARY KEY | Unique identifier | - |
| `participant_id` | UUID | NOT NULL, FK | Submitting participant | FR-032 |
| `round_id` | UUID | NOT NULL, FK | Target round | FR-031 |
| `timestamp` | TIMESTAMP | NOT NULL | Server-side submission time | FR-009 (deterministic) |
| `modality` | VARCHAR(10) | NOT NULL | Input method (TEXT/VOICE) | FR-001, FR-002 |
| `counted` | BOOLEAN | NOT NULL | Is this the counted submission? | FR-013 (last-approved-wins) |

**Validation Rules**:
- `timestamp` must be within round window (enforced by application, logged if violation)
- `modality` must be one of: `TEXT`, `VOICE`
- **Exactly one** `counted = TRUE` per `(participant_id, round_id)` (enforced via EXCLUDE constraint)
- Submission cannot be modified after creation (immutability per FR-015)

**Invariants**:
- **Last-Approved-Wins**: When new submission approved, unmark previous `counted` submission:
  ```sql
  -- Atomic operation
  UPDATE submission_metadata
  SET counted = FALSE
  WHERE participant_id = ? AND round_id = ? AND counted = TRUE;

  UPDATE submission_metadata
  SET counted = TRUE
  WHERE submission_id = ?;
  ```

**Lifecycle**:
- **Created**: On submission acceptance (within window, under rate limit)
- **Updated**: `counted` flag toggled during approval (Spec 3 integration)
- **Never Deleted**: Persist for analytics (audit trail)

---

## Ephemeral Entities (In-Memory Only)

### 4. RawSubmission

**Purpose**: Temporary storage of submission text for forwarding to summarization

**Storage**: Python dict (in-memory), never written to PostgreSQL

**Schema** (conceptual):
```python
raw_submissions: Dict[UUID, RawSubmission] = {}

@dataclass
class RawSubmission:
    submission_id: UUID
    submission_text: str  # Normalized text (trimmed, no HTML)
    ttl_expires_at: datetime  # Auto-delete after this time
```

**Fields**:

| Field | Type | Description | Source Requirement |
|-------|------|-------------|-------------------|
| `submission_id` | UUID | Links to SubmissionMetadata | - |
| `submission_text` | str | Raw participant text (text input or transcript) | FR-003, FR-004 |
| `ttl_expires_at` | datetime | Expiration timestamp (30 min after creation) | FR-021, FR-022 |

**Validation Rules**:
- `submission_text` max length: 5000 characters (Assumption 7)
- `submission_text` must not be empty or whitespace-only (Edge Case)
- Text normalization applied:
  - Strip leading/trailing whitespace
  - Remove HTML tags (if any)
  - Preserve original meaning (no interpretation per FR-004)

**Lifecycle**:
- **Created**: When submission accepted (text input or voice transcript finalized)
- **Read**: When forwarding to summarization (Spec 3)
- **Deleted**: Explicit deletion after summarization completes OR TTL expires (whichever first)

**Deletion Trigger**:
```python
# Option 1: Event-driven (preferred)
on_event("summarization.completed", delete_raw_submission)

# Option 2: TTL fallback (safety net)
@scheduled(every="1 minute")
def cleanup_expired_raw_submissions():
    now = datetime.utcnow()
    expired = [sid for sid, sub in raw_submissions.items()
               if sub.ttl_expires_at < now]
    for sid in expired:
        del raw_submissions[sid]
```

**Compliance**: FR-021 (no long-term persistence), FR-022 (ephemeral only), SC-009 (0% persistence)

---

### 5. RateLimit

**Purpose**: Enforce max submissions per participant per round

**Storage**: Python dict with threading.Lock (in-memory), never written to PostgreSQL

**Schema** (conceptual):
```python
rate_limits: Dict[Tuple[UUID, UUID], int] = {}
rate_limit_locks: Dict[Tuple[UUID, UUID], threading.Lock] = {}

# Key: (participant_id, round_id)
# Value: count of submissions
```

**Fields**:

| Field | Type | Description | Source Requirement |
|-------|------|-------------|-------------------|
| `participant_id` | UUID | Participant identifier | - |
| `round_id` | UUID | Round identifier | - |
| `count` | int | Current submission count | FR-011 |
| `max_allowed` | int | Max submissions (default: 3) | FR-011 |

**Validation Rules**:
- `count` must be non-negative
- `max_allowed` configurable per round (default: 3 for MVP)

**Operations**:
```python
def check_and_increment_rate_limit(participant_id: UUID, round_id: UUID) -> bool:
    """
    Atomically check rate limit and increment counter.
    Returns True if submission allowed, False if rate limit exceeded.
    """
    key = (participant_id, round_id)

    # Get or create lock for this key
    if key not in rate_limit_locks:
        rate_limit_locks[key] = threading.Lock()

    with rate_limit_locks[key]:
        current_count = rate_limits.get(key, 0)

        if current_count >= MAX_SUBMISSIONS:
            # Rate limit exceeded
            return False

        # Increment and allow
        rate_limits[key] = current_count + 1
        return True
```

**Lifecycle**:
- **Created**: On first submission by participant in round
- **Updated**: Incremented on each subsequent submission
- **Deleted**: When round transitions to COMPLETED (reset for next round)

**Compliance**: FR-011 (rate limit enforcement), FR-012 (explicit feedback), SC-004 (100% accuracy)

---

### 6. AudioRecording

**Purpose**: Temporary storage of voice recording during transcription

**Storage**: Python dict (in-memory), never written to PostgreSQL

**Schema** (conceptual):
```python
audio_recordings: Dict[UUID, AudioRecording] = {}

@dataclass
class AudioRecording:
    recording_id: UUID
    participant_id: UUID
    audio_data: bytes  # Raw audio (WAV, MP3, etc.)
    created_at: datetime
    status: str  # 'PENDING', 'TRANSCRIBING', 'COMPLETED', 'FAILED'
```

**Fields**:

| Field | Type | Description | Source Requirement |
|-------|------|-------------|-------------------|
| `recording_id` | UUID | Unique identifier | - |
| `participant_id` | UUID | Recording participant | - |
| `audio_data` | bytes | Raw audio file | FR-002 |
| `created_at` | datetime | Recording timestamp | - |
| `status` | str | Transcription status | - |

**Status Values**:
- `PENDING`: Uploaded, awaiting transcription
- `TRANSCRIBING`: Sent to Whisper API
- `COMPLETED`: Transcript generated
- `FAILED`: Transcription error (user can retry)

**Lifecycle**:
- **Created**: When participant finishes voice recording
- **Updated**: Status changes during transcription
- **Deleted**: Immediately after transcript accepted OR participant re-records

**Compliance**: FR-023 (audio not persisted after transcription)

---

### 7. Transcript

**Purpose**: Temporary storage of transcribed text for participant review

**Storage**: Python dict (in-memory), never written to PostgreSQL

**Schema** (conceptual):
```python
transcripts: Dict[UUID, Transcript] = {}

@dataclass
class Transcript:
    transcript_id: UUID
    recording_id: UUID
    transcript_text: str
    reviewed: bool  # Has participant seen it?
    accepted: bool  # Has participant accepted it?
```

**Fields**:

| Field | Type | Description | Source Requirement |
|-------|------|-------------|-------------------|
| `transcript_id` | UUID | Unique identifier | - |
| `recording_id` | UUID | Source audio | Links to AudioRecording |
| `transcript_text` | str | Whisper API output | FR-017 |
| `reviewed` | bool | Displayed to participant | FR-017 |
| `accepted` | bool | Participant approved | FR-020 |

**Lifecycle**:
- **Created**: When Whisper API returns transcript
- **Updated**: `reviewed` set to TRUE on first display; `accepted` set to TRUE on approval
- **Deleted**: After participant accepts (transcript forwarded as RawSubmission) OR participant re-records (replaced)

**State Transitions**:
```
Created (reviewed=False, accepted=False)
   ↓
Displayed to participant (reviewed=True, accepted=False)
   ↓
Participant approves (reviewed=True, accepted=True) → Forward as RawSubmission
```

**Compliance**: FR-017 (display for review), FR-018 (re-record replaces), FR-019 (no direct editing), FR-020 (forward transcript not audio)

---

## State Transitions

### Round Status State Machine

```
┌─────────┐
│ PENDING │  Round scheduled but not started
└────┬────┘
     │
     │ (NOW() >= window_start)
     ▼
┌─────────┐
│ ACTIVE  │  Accepting submissions
└────┬────┘
     │
     │ (NOW() >= window_end)
     ▼
┌─────────┐
│ CLOSED  │  Window expired, summarization in progress
└────┬────┘
     │
     │ (Event: summarization_completed)
     ▼
┌───────────┐
│ COMPLETED │  Ephemeral data cleared, ready for next round
└───────────┘
```

**Triggers**:
- `PENDING → ACTIVE`: Timer service checks every second
- `ACTIVE → CLOSED`: Timer service checks every second
- `CLOSED → COMPLETED`: Event listener on summarization completion

---

### Submission Counted Status

```
┌─────────────────────────┐
│ New Submission Created  │
│  counted = FALSE        │
└───────────┬─────────────┘
            │
            │ (Forwarded to Spec 3 for summarization)
            ▼
┌─────────────────────────┐
│  Summary Generated      │
│  (awaiting approval)    │
└───────────┬─────────────┘
            │
            │ (Participant approves summary)
            ▼
┌─────────────────────────┐
│ Approval Received       │
│ 1. Unmark previous      │
│    counted submission   │
│ 2. Mark this submission │
│    as counted = TRUE    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Forwarded to Clustering │
│  (Spec 4)               │
└─────────────────────────┘
```

**Invariant**: Exactly one `counted = TRUE` per `(participant_id, round_id)` at all times after first approval

---

### Voice Input Flow

```
┌─────────────────────┐
│ User Records Voice  │
└──────────┬──────────┘
           │
           │ (Audio uploaded)
           ▼
┌─────────────────────┐
│ AudioRecording      │
│ status = PENDING    │
└──────────┬──────────┘
           │
           │ (Send to Whisper API)
           ▼
┌─────────────────────┐
│ status = TRANSCRIBING│
└──────────┬──────────┘
           │
           │ (API returns transcript)
           ▼
┌─────────────────────┐
│ status = COMPLETED  │
│ Transcript Created  │
│ reviewed = FALSE    │
└──────────┬──────────┘
           │
           │ (Display to user)
           ▼
┌─────────────────────┐
│ reviewed = TRUE     │
│ User sees transcript│
└──────────┬──────────┘
           │
           ├─────────────────────┐
           │ (Accept)            │ (Re-record)
           ▼                     ▼
┌─────────────────────┐   ┌─────────────────────┐
│ accepted = TRUE     │   │ Delete Audio +      │
│ Create RawSubmission│   │ Transcript          │
│ Delete Audio +      │   │ Start new recording │
│ Transcript          │   └─────────────────────┘
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│ Forward to Spec 3   │
│ for Summarization   │
└─────────────────────┘
```

**Compliance**: FR-017 to FR-020, SC-002 (< 3s transcription)

---

## Validation Rules Summary

### Submission Acceptance Criteria

A submission is accepted if ALL of the following are TRUE:

1. **Window Timing** (FR-006, FR-007, FR-009):
   - `submission_timestamp >= round.window_start` (inclusive)
   - `submission_timestamp < round.window_end` (exclusive)

2. **Rate Limit** (FR-011, FR-012):
   - `rate_limits[(participant_id, round_id)] < MAX_SUBMISSIONS`

3. **Content Validation**:
   - `submission_text` is not empty or whitespace-only
   - `submission_text` length <= 5000 characters

4. **Round Status**:
   - `round.status = 'ACTIVE'`

**Rejection Response** (FR-028):
```json
{
  "error": "SUBMISSION_REJECTED",
  "reason": "OUTSIDE_WINDOW" | "RATE_LIMIT_EXCEEDED" | "INVALID_CONTENT",
  "message": "Explicit user-visible feedback",
  "details": {
    "window_start": "2026-01-29T14:00:00Z",
    "window_end": "2026-01-29T14:05:00Z",
    "current_time": "2026-01-29T14:05:01Z",
    "submissions_count": 3,
    "max_allowed": 3
  }
}
```

---

### Last-Approved-Wins Implementation

**Algorithm** (FR-013, SC-007):
```sql
-- Step 1: Find previous counted submission (if any)
SELECT submission_id
FROM submission_metadata
WHERE participant_id = :participant_id
  AND round_id = :round_id
  AND counted = TRUE;

-- Step 2: Unmark previous (if exists)
UPDATE submission_metadata
SET counted = FALSE
WHERE participant_id = :participant_id
  AND round_id = :round_id
  AND counted = TRUE;

-- Step 3: Mark new submission as counted
UPDATE submission_metadata
SET counted = TRUE
WHERE submission_id = :new_submission_id;
```

**Database Guarantee**: EXCLUDE constraint prevents multiple `counted = TRUE` for same `(participant_id, round_id)`

---

### Ephemeral Data Cleanup

**Triggers**:

1. **Event-Driven** (primary):
   - Listen for `summarization.completed` event from Spec 3
   - Delete `raw_submissions[submission_id]` for all submissions in round

2. **TTL Fallback** (safety net):
   - Background job runs every 1 minute
   - Delete any `RawSubmission` where `ttl_expires_at < NOW()`

**Audit Log** (without content):
```json
{
  "event": "EPHEMERAL_DATA_DELETED",
  "submission_id": "uuid",
  "deleted_at": "2026-01-29T14:10:00Z",
  "reason": "SUMMARIZATION_COMPLETED" | "TTL_EXPIRED"
}
```

**Compliance**: FR-021 to FR-024, SC-009

---

## Data Flow Diagram

### Text Input Flow

```
┌───────────────┐
│  Participant  │
└───────┬───────┘
        │
        │ (Types text, clicks Submit)
        ▼
┌───────────────────────────────────────────────┐
│  Backend: POST /submissions                   │
│                                               │
│  1. Validate window timing                    │
│  2. Check rate limit                          │
│  3. Validate content                          │
│  4. Create SubmissionMetadata (persistent)    │
│  5. Store RawSubmission (ephemeral)           │
│  6. Increment rate limit counter              │
│  7. Return submission_id                      │
└───────────────┬───────────────────────────────┘
                │
                │ (Success)
                ▼
┌───────────────────────────────────────────────┐
│  Forward to Spec 3 (Summarization Protocol)   │
│                                               │
│  Input: submission_id, submission_text        │
│  Output: summary_id (generated by Spec 3)     │
└───────────────┬───────────────────────────────┘
                │
                │ (Summary generated)
                ▼
┌───────────────────────────────────────────────┐
│  Participant Reviews & Approves Summary       │
│  (handled by Spec 3)                          │
└───────────────┬───────────────────────────────┘
                │
                │ (Approval received)
                ▼
┌───────────────────────────────────────────────┐
│  Update SubmissionMetadata.counted = TRUE     │
│  (unmark previous counted submission)         │
└───────────────┬───────────────────────────────┘
                │
                │ (Summarization complete)
                ▼
┌───────────────────────────────────────────────┐
│  Delete RawSubmission (ephemeral cleanup)     │
└───────────────────────────────────────────────┘
```

---

### Voice Input Flow

```
┌───────────────┐
│  Participant  │
└───────┬───────┘
        │
        │ (Records voice, clicks Stop)
        ▼
┌───────────────────────────────────────────────┐
│  Backend: POST /voice/transcribe              │
│                                               │
│  1. Store AudioRecording (ephemeral)          │
│  2. Send to Whisper API                       │
│  3. Wait for transcript (< 3s target)         │
│  4. Store Transcript (ephemeral)              │
│  5. Return transcript_id, transcript_text     │
└───────────────┬───────────────────────────────┘
                │
                │ (Display transcript to participant)
                ▼
┌───────────────────────────────────────────────┐
│  Frontend: Show transcript with options       │
│  - Accept                                     │
│  - Re-record                                  │
└───────────────┬───────────────────────────────┘
                │
                ├─────────────────────┐
                │ (Accept)            │ (Re-record)
                ▼                     ▼
┌───────────────────────────┐   ┌───────────────────┐
│ POST /submissions         │   │ DELETE audio +    │
│  (same flow as text)      │   │ transcript, retry │
└───────────────────────────┘   └───────────────────┘
```

---

## Integration Contracts

### Contract 1: Submission → Summarization (Spec 2 → Spec 3)

**Interface**:
```python
class SubmissionForSummarization:
    submission_id: UUID
    user_id: UUID  # Same as participant_id
    round_id: UUID
    submission_text: str  # Normalized text
    timestamp: datetime
    modality: Literal["TEXT", "VOICE"]
```

**Endpoint** (Option A: Event Bus):
```python
# Publisher (Spec 2)
publish_event("submission.created", SubmissionForSummarization)

# Subscriber (Spec 3)
@on_event("submission.created")
def handle_new_submission(submission: SubmissionForSummarization):
    # Generate summary
    pass
```

**Endpoint** (Option B: Direct API):
```http
POST /api/v1/summarize
Content-Type: application/json

{
  "submission_id": "uuid",
  "user_id": "uuid",
  "round_id": "uuid",
  "submission_text": "Normalized text here",
  "timestamp": "2026-01-29T14:02:30Z",
  "modality": "TEXT"
}
```

**Guarantees**:
- Only counted submissions forwarded (after approval by participant)
- Text is normalized (trimmed, no HTML)
- Timestamp is server-authoritative (not client-provided)

---

### Contract 2: Summarization Completion → Cleanup (Spec 3 → Spec 2)

**Interface**:
```python
class SummarizationCompleted:
    round_id: UUID
    completed_at: datetime
```

**Endpoint** (Event Bus):
```python
# Publisher (Spec 3)
publish_event("summarization.completed", SummarizationCompleted)

# Subscriber (Spec 2)
@on_event("summarization.completed")
def cleanup_ephemeral_data(event: SummarizationCompleted):
    # Delete all RawSubmission for round_id
    for submission_id in get_submissions_for_round(event.round_id):
        if submission_id in raw_submissions:
            del raw_submissions[submission_id]

    # Update round status
    update_round_status(event.round_id, "COMPLETED")
```

**Guarantees**:
- Event fired only after ALL summaries in round approved or failed
- Spec 2 deletes ephemeral data within 1 minute of receiving event

---

## Schema Migration Strategy

### Initial Schema (MVP)

**Persistent Tables**:
1. `participants` (depends on `communities` from auth layer)
2. `rounds` (depends on `discussions` from Spec 1)
3. `submission_metadata`

**Indexes**:
- `idx_participants_community`
- `idx_rounds_discussion`
- `idx_rounds_status`
- `idx_submission_metadata_participant_round`
- `idx_submission_metadata_counted`

**Constraints**:
- Foreign keys (enforce referential integrity)
- CHECK constraints (modality, status enums)
- EXCLUDE constraint (one counted per participant per round)

### Post-MVP Enhancements

**Potential Additions** (deferred):
1. `submission_analytics` table (aggregated stats, no raw text)
2. Redis for distributed rate limiting (multi-server)
3. Audit log table for ephemeral data deletion (compliance tracking)

---

## Performance Considerations

### Expected Load (MVP)

- **Concurrent submissions**: 100 participants submitting within 5-second window
- **Submission rate**: 20 submissions/second (burst)
- **Voice transcription**: 50 concurrent requests (50% of participants use voice)
- **Database writes**: 20 inserts/second to `submission_metadata`
- **In-memory operations**: 20 dict inserts/second to `raw_submissions`, `rate_limits`

### Optimizations

1. **Batch Inserts**: Use batch insert for SubmissionMetadata if concurrent writes exceed 50/s
2. **Index Strategy**: Compound index on `(participant_id, round_id, counted)` for fast last-approved-wins queries
3. **Connection Pooling**: PostgreSQL connection pool (min: 5, max: 20)
4. **Rate Limit Locks**: Use fine-grained locks per `(participant_id, round_id)` to avoid global lock contention

---

## Summary

**Persistent Entities**: 3 (Participant, Round, SubmissionMetadata)
**Ephemeral Entities**: 4 (RawSubmission, RateLimit, AudioRecording, Transcript)
**State Machines**: 2 (Round Status, Voice Input Flow)
**Integration Contracts**: 2 (Submission → Summarization, Cleanup)

**Key Design Decisions**:
1. **Ephemeral/Persistent Separation**: Raw text never touches PostgreSQL (FR-021 compliance)
2. **Last-Approved-Wins**: Enforced via database constraint + atomic update (SC-007 accuracy)
3. **Voice Transcription**: Ephemeral audio/transcript lifecycle (FR-023 compliance)
4. **Rate Limiting**: In-memory with per-key locks (SC-004 accuracy)
5. **Cleanup Strategy**: Event-driven + TTL fallback (SC-009 compliance)

**Ready to proceed to**: API contract definition (contracts/)
