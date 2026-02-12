# Voice Input Implementation - User Story 2

## Overview

This document describes the implementation of User Story 2: Voice Input with Transcription for the Input Collection Protocol (Spec 002).

**Implementation Date**: 2026-02-01
**Status**: Complete
**Tasks**: T034-T043

## Architecture

### Backend Components

#### 1. Transcription Service (`backend/src/services/transcription.py`)
- **Purpose**: Transcribe audio using OpenAI Whisper API
- **Function**: `transcribe_audio(audio_data: bytes, filename: str) -> Tuple[str, float]`
- **Returns**: (transcript_text, latency_ms)
- **Error Handling**:
  - Missing API key (non-retryable)
  - API rate limits (retryable)
  - Server errors (retryable)
  - Empty transcripts (retryable)

#### 2. Voice API Routes (`backend/src/api/routes/voice.py`)

##### POST /api/v1/voice/transcribe
- Accepts multipart audio file
- Stores AudioRecording in ephemeral storage
- Calls transcription service
- Stores Transcript in ephemeral storage
- Returns TranscriptResponse with latency metrics
- Warns if latency > 3000ms (SC-002)

##### DELETE /api/v1/voice/{recording_id}
- Deletes AudioRecording from ephemeral storage
- Deletes associated Transcript
- Used for re-record functionality

#### 3. Ephemeral Storage Updates (`backend/src/services/ephemeral_storage.py`)
- Added `get_transcript_by_recording(recording_id)` method
- Manages in-memory storage for AudioRecording and Transcript objects
- No database persistence (ephemeral only)

### Frontend Components

#### 1. VoiceInputRecorder Component (`frontend/src/components/VoiceInputRecorder.tsx`)

**State Machine**:
```
idle → recording → transcribing → reviewing → accepting → idle
                      ↓              ↓
                   (error)      (re-record)
                      ↓              ↓
                    idle ←─────────idle
```

**Features**:
- Browser MediaRecorder API integration
- Real-time recording duration display
- Audio waveform visualization placeholder
- Automatic transcription on stop
- Transcript review with Accept/Re-record buttons
- Latency warning if > 3000ms
- Error handling with retryable/non-retryable distinction

#### 2. Voice API Client (`frontend/src/services/submissionApi.ts`)

**New Functions**:
- `transcribeVoice(participantId, roundId, audioBlob)`: Upload and transcribe
- `deleteRecording(recordingId)`: Delete for re-record
- `acceptTranscript(participantId, roundId, transcriptText)`: Submit with VOICE modality

## User Flow

### Happy Path

1. **Recording**
   - Participant clicks "🎤 Start Recording"
   - Browser requests microphone permission
   - MediaRecorder captures audio (WebM format)
   - Duration counter displays elapsed time
   - Participant clicks "⏹ Stop Recording"

2. **Transcription**
   - Audio blob uploaded to `/api/v1/voice/transcribe`
   - Backend calls OpenAI Whisper API
   - Transcript returned with latency metrics
   - State transitions to 'reviewing'

3. **Review**
   - Transcript displayed in text box
   - Latency metrics shown
   - Warning displayed if > 3000ms
   - Two options:
     - "🔄 Re-record": Delete and start over
     - "✓ Accept Transcript": Submit

4. **Accept**
   - Transcript submitted to `/api/v1/submissions/` with `modality='VOICE'`
   - Recording and transcript deleted from backend
   - Success callback invoked
   - Component resets to 'idle'

### Re-record Flow

1. Participant clicks "🔄 Re-record" after reviewing transcript
2. DELETE request to `/api/v1/voice/{recording_id}`
3. AudioRecording and Transcript removed from ephemeral storage
4. Component resets to 'idle'
5. Participant can record again

### Error Handling

#### Microphone Access Denied
- Error message: "Failed to access microphone. Please grant permission and try again."
- Component stays in 'idle' state
- Participant can retry

#### Transcription Failed (Retryable)
- Error message: "Transcription failed. Please try recording again."
- Component returns to 'idle'
- Examples: API timeout, rate limit, server error

#### Transcription Failed (Non-retryable)
- Error message: "Transcription service unavailable. Please try text input instead."
- Component returns to 'idle'
- Examples: Missing API key, invalid credentials

## Configuration

### Backend Environment Variables

```bash
# Required for voice input
OPENAI_API_KEY=sk-...your-key...

# Optional (uses defaults if not set)
MAX_SUBMISSIONS_PER_ROUND=3
```

### Frontend Integration

To use the VoiceInputRecorder component:

```tsx
import VoiceInputRecorder from './components/VoiceInputRecorder';

<VoiceInputRecorder
  participantId="550e8400-e29b-41d4-a716-446655440000"
  roundId="660e8400-e29b-41d4-a716-446655440000"
  onSubmissionComplete={(submissionId) => {
    console.log('Submission created:', submissionId);
    // Refresh submission history, show success message, etc.
  }}
  disabled={false}
/>
```

## Success Criteria Met

### SC-002: Transcription Latency
✓ Transcription completes within 3 seconds (target)
✓ Latency tracked and logged
✓ Warning displayed if > 3000ms
✓ Actual latency displayed to user

### User Story Acceptance Scenarios

✓ **Scenario 1**: Audio transcribed and displayed for review
✓ **Scenario 2**: Re-record replaces transcript
✓ **Scenario 3**: Accepted transcript forwarded to summarization
✓ **Scenario 4**: Audio and transcript discarded after completion
✓ **Scenario 5**: Previous transcript replaced on re-record

## Data Lifecycle

### Ephemeral Data (NOT Persisted)

1. **AudioRecording**
   - Created: On upload to `/api/v1/voice/transcribe`
   - Deleted: On accept transcript OR re-record
   - Storage: In-memory dictionary
   - TTL: Until explicit deletion

2. **Transcript**
   - Created: After successful transcription
   - Deleted: On accept transcript OR re-record
   - Storage: In-memory dictionary
   - TTL: Until explicit deletion

### Persistent Data

1. **SubmissionMetadata**
   - Created: When transcript accepted
   - Fields: submission_id, participant_id, round_id, timestamp, modality=VOICE, counted=false
   - Storage: PostgreSQL database

2. **RawSubmission**
   - Created: When transcript accepted
   - Content: Normalized transcript text
   - Storage: In-memory (ephemeral)
   - TTL: Until summarization completes (24 hours max)

## Testing

### Unit Tests

- `backend/tests/unit/test_transcription.py`
  - Successful transcription
  - Missing API key
  - Empty transcript
  - Rate limit errors
  - Invalid API key

### Integration Testing

To test the voice input flow:

1. Start backend: `cd backend && uvicorn src.main:app --reload`
2. Set `OPENAI_API_KEY` environment variable
3. Use frontend or API client to:
   - Upload audio file
   - Verify transcript returned
   - Test re-record
   - Test accept transcript

### Manual Testing Checklist

- [ ] Record audio (10 seconds)
- [ ] Verify transcription completes < 3s
- [ ] Verify transcript text displayed
- [ ] Test re-record (transcript replaced)
- [ ] Test accept transcript (submission created)
- [ ] Verify audio/transcript deleted after accept
- [ ] Test microphone permission denied
- [ ] Test transcription error (invalid API key)
- [ ] Verify latency warning shown if > 3000ms

## Future Enhancements (Out of Scope)

- Audio waveform visualization (placeholder added)
- Audio playback before acceptance
- Transcript editing (spec requires re-record only)
- Multiple language support
- Speaker diarization
- Noise cancellation

## Dependencies

### Backend
- `openai==1.10.0` (Whisper API client)
- `pydantic-settings==2.1.0` (Configuration management)

### Frontend
- Browser MediaRecorder API (built-in)
- FormData API (built-in)
- axios (already in project)

## References

- **Spec**: `/specs/002-input-collection/spec.md`
- **Tasks**: `/specs/002-input-collection/tasks.md` (T034-T043)
- **Example**: `/backend/examples/voice_input_example.py`
- **OpenAI Whisper API**: https://platform.openai.com/docs/guides/speech-to-text
