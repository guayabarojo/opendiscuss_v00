# Voice Input Quick Start Guide

Get voice input working in 5 minutes.

## Prerequisites

- OpenAI API key
- Backend running
- Frontend running

## Setup

### 1. Configure Backend

```bash
cd backend

# Set API key
export OPENAI_API_KEY=sk-...your-key...

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Start server
uvicorn src.main:app --reload
```

Backend should start on http://localhost:8000

### 2. Configure Frontend

```bash
cd frontend

# Create .env.local (if not exists)
echo "VITE_API_URL=http://localhost:8000" > .env.local

# Install dependencies (if not already installed)
npm install

# Start dev server
npm run dev
```

Frontend should start on http://localhost:5173

## Usage

### Using the Component

```tsx
import VoiceInputRecorder from './components/VoiceInputRecorder';

function MyPage() {
  return (
    <VoiceInputRecorder
      participantId="your-participant-uuid"
      roundId="your-round-uuid"
      onSubmissionComplete={(submissionId) => {
        console.log('Submitted!', submissionId);
      }}
    />
  );
}
```

### User Flow

1. Click "🎤 Start Recording"
2. Grant microphone permission (first time)
3. Speak your input
4. Click "⏹ Stop Recording"
5. Wait ~1-2 seconds for transcription
6. Review transcript
7. Click "✓ Accept Transcript" or "🔄 Re-record"

## Testing the API Directly

### Transcribe Audio

```bash
# Record audio (or use existing audio file)
curl -X POST http://localhost:8000/api/v1/voice/transcribe \
  -F "audio=@test-audio.webm" \
  -F "participant_id=550e8400-e29b-41d4-a716-446655440000" \
  -F "round_id=660e8400-e29b-41d4-a716-446655440000"
```

Response:
```json
{
  "transcript_id": "770e8400-e29b-41d4-a716-446655440000",
  "recording_id": "880e8400-e29b-41d4-a716-446655440000",
  "transcript_text": "This is the transcribed text",
  "latency_ms": 1250.5
}
```

### Delete Recording (Re-record)

```bash
curl -X DELETE http://localhost:8000/api/v1/voice/880e8400-e29b-41d4-a716-446655440000
```

Response: 204 No Content

### Accept Transcript (Submit)

```bash
curl -X POST http://localhost:8000/api/v1/submissions/ \
  -H "Content-Type: application/json" \
  -d '{
    "participant_id": "550e8400-e29b-41d4-a716-446655440000",
    "round_id": "660e8400-e29b-41d4-a716-446655440000",
    "text": "This is the transcribed text",
    "modality": "VOICE"
  }'
```

Response:
```json
{
  "submission_id": "990e8400-e29b-41d4-a716-446655440000",
  "participant_id": "550e8400-e29b-41d4-a716-446655440000",
  "round_id": "660e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-02-01T20:30:00Z",
  "modality": "VOICE",
  "counted": false
}
```

## Troubleshooting

### "OpenAI API key not configured"

```bash
# Check if environment variable is set
echo $OPENAI_API_KEY

# Set it if missing
export OPENAI_API_KEY=sk-...
```

### "Failed to access microphone"

- Grant microphone permission in browser
- Check if other apps are using the microphone
- Try a different browser (Chrome recommended)

### "Transcription failed"

Check backend logs:
```bash
# Backend should show detailed error
tail -f backend.log
```

Common issues:
- Invalid API key → Check `OPENAI_API_KEY`
- Rate limit → Wait a minute and retry
- Audio format → Use WebM, MP3, or WAV

### Latency > 3 seconds

- Check network connection
- Check OpenAI API status
- Audio file may be too large (keep under 25MB)

## Browser Compatibility

| Browser | MediaRecorder | Status |
|---------|---------------|--------|
| Chrome 49+ | ✅ WebM | Supported |
| Firefox 25+ | ✅ WebM | Supported |
| Edge 79+ | ✅ WebM | Supported |
| Safari 14.1+ | ⚠️ Limited | Partial |

For Safari, you may need to use a polyfill or alternative format.

## Performance Tips

1. **Audio Quality**: Use default settings (good enough for speech)
2. **Duration**: Keep recordings under 60 seconds for best results
3. **Format**: WebM with Opus codec (default) is optimal
4. **Network**: Ensure stable connection (audio uploaded to OpenAI)

## Next Steps

- Integrate into your discussion flow
- Add custom styling
- Monitor latency metrics
- Test with real users

## Support

- **Spec**: `/specs/002-input-collection/spec.md`
- **Implementation Details**: `/specs/002-input-collection/VOICE_INPUT_IMPLEMENTATION.md`
- **Tasks**: `/specs/002-input-collection/tasks.md`
- **Example Code**: `/backend/examples/voice_input_example.py`
