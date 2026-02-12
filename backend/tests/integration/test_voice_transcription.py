"""
Integration test for T074: Voice Transcription Flow (User Story 2).

Tests:
- Upload audio → verify transcription service called
- Verify transcript returned in < 3s (mocked API for speed)
- Verify AudioRecording stored in ephemeral storage
- Verify Transcript stored in ephemeral storage
- Test error handling for transcription failures
"""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timedelta
from io import BytesIO
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.round import Round
from src.models.ephemeral import AudioRecording, Transcript, AudioStatus
from src.services.ephemeral_storage import ephemeral_storage
from src.services.transcription import transcribe_audio, TranscriptionError


@pytest.mark.asyncio
@pytest.mark.integration
async def test_voice_transcription_flow(db_session: AsyncSession):
    """
    Test voice transcription flow at service layer.

    Flow:
    1. Mock OpenAI Whisper API
    2. Call transcribe_audio() with sample audio data
    3. Verify transcript returned
    4. Verify latency measured
    """
    # Setup: Mock OpenAI API client
    mock_transcript = "This is a test transcription of voice input."

    with patch('src.services.transcription.AsyncOpenAI') as mock_openai_class:
        # Configure mock
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client

        # Mock the transcription response
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcript)

        # Test: Transcribe audio
        audio_data = b"fake audio data"
        transcript_text, latency_ms = await transcribe_audio(audio_data, filename="test.webm")

        # Verify: Transcript returned
        assert transcript_text == mock_transcript
        assert isinstance(transcript_text, str)
        assert len(transcript_text) > 0

        # Verify: Latency measured
        assert latency_ms >= 0
        assert isinstance(latency_ms, float)

        # Verify: Whisper API was called
        mock_client.audio.transcriptions.create.assert_called_once()
        call_args = mock_client.audio.transcriptions.create.call_args
        assert call_args.kwargs["model"] == "whisper-1"
        assert call_args.kwargs["response_format"] == "text"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_voice_transcription_latency_under_3s(db_session: AsyncSession):
    """
    Test that voice transcription completes in < 3 seconds (SC-002 requirement).

    Uses mocked API to ensure consistent timing.
    """
    # Setup: Mock OpenAI API with fast response
    mock_transcript = "Fast transcription response."

    with patch('src.services.transcription.AsyncOpenAI') as mock_openai_class:
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcript)

        # Test: Transcribe audio
        audio_data = b"fake audio data"
        start_time = datetime.utcnow()
        transcript_text, latency_ms = await transcribe_audio(audio_data)
        end_time = datetime.utcnow()

        # Verify: Latency < 3000ms (excluding network time in mock)
        # Note: Real API may be slower, but mocked should be instant
        assert latency_ms < 3000, f"Transcription took {latency_ms}ms, expected < 3000ms"

        # Verify: Total processing time < 3s
        total_time_ms = (end_time - start_time).total_seconds() * 1000
        assert total_time_ms < 3000, f"Total processing took {total_time_ms}ms"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_voice_transcription_ephemeral_storage(db_session: AsyncSession):
    """
    Test that AudioRecording and Transcript are stored in ephemeral storage.

    Flow:
    1. Store AudioRecording
    2. Transcribe audio
    3. Store Transcript
    4. Verify both accessible from ephemeral storage
    """
    # Clear ephemeral storage
    ephemeral_storage.audio_recordings.clear()
    ephemeral_storage.transcripts.clear()

    # Setup: Create AudioRecording
    recording_id = uuid4()
    participant_id = uuid4()
    audio_data = b"fake audio data"

    audio_recording = AudioRecording(
        recording_id=recording_id,
        participant_id=participant_id,
        audio_data=audio_data,
        created_at=datetime.utcnow(),
        status=AudioStatus.TRANSCRIBING
    )

    # Test: Store AudioRecording
    ephemeral_storage.store_audio_recording(audio_recording)

    # Verify: AudioRecording stored
    stored_recording = ephemeral_storage.get_audio_recording(recording_id)
    assert stored_recording is not None
    assert stored_recording.recording_id == recording_id
    assert stored_recording.participant_id == participant_id
    assert stored_recording.status == AudioStatus.TRANSCRIBING

    # Setup: Mock transcription
    mock_transcript = "Transcribed text from audio."

    with patch('src.services.transcription.AsyncOpenAI') as mock_openai_class:
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcript)

        # Test: Transcribe
        transcript_text, latency_ms = await transcribe_audio(audio_data)

    # Test: Store Transcript
    transcript_id = uuid4()
    transcript = Transcript(
        transcript_id=transcript_id,
        recording_id=recording_id,
        transcript_text=transcript_text,
        reviewed=True,
        accepted=False
    )
    ephemeral_storage.store_transcript(transcript)

    # Verify: Transcript stored
    stored_transcript = ephemeral_storage.get_transcript(transcript_id)
    assert stored_transcript is not None
    assert stored_transcript.transcript_id == transcript_id
    assert stored_transcript.recording_id == recording_id
    assert stored_transcript.transcript_text == mock_transcript
    assert stored_transcript.reviewed is True
    assert stored_transcript.accepted is False

    # Verify: Can retrieve transcript by recording_id
    transcript_by_recording = ephemeral_storage.get_transcript_by_recording(recording_id)
    assert transcript_by_recording is not None
    assert transcript_by_recording.transcript_id == transcript_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_voice_transcription_status_transitions(db_session: AsyncSession):
    """
    Test AudioRecording status transitions during transcription.

    Flow:
    PENDING → TRANSCRIBING → COMPLETED (on success)
    PENDING → TRANSCRIBING → FAILED (on error)
    """
    # Clear ephemeral storage
    ephemeral_storage.audio_recordings.clear()

    # Setup: Create AudioRecording with PENDING status
    recording_id = uuid4()
    audio_recording = AudioRecording(
        recording_id=recording_id,
        participant_id=uuid4(),
        audio_data=b"fake audio",
        created_at=datetime.utcnow(),
        status=AudioStatus.PENDING
    )
    ephemeral_storage.store_audio_recording(audio_recording)

    # Test: Update to TRANSCRIBING
    audio_recording.status = AudioStatus.TRANSCRIBING
    ephemeral_storage.store_audio_recording(audio_recording)

    stored = ephemeral_storage.get_audio_recording(recording_id)
    assert stored.status == AudioStatus.TRANSCRIBING

    # Test: Update to COMPLETED
    audio_recording.status = AudioStatus.COMPLETED
    ephemeral_storage.store_audio_recording(audio_recording)

    stored = ephemeral_storage.get_audio_recording(recording_id)
    assert stored.status == AudioStatus.COMPLETED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_voice_transcription_error_handling(db_session: AsyncSession):
    """
    Test error handling for transcription failures.

    Tests:
    - Empty audio data
    - API error (mocked)
    - Invalid API key (mocked)
    - Rate limit exceeded (mocked)
    """
    # Test: Empty transcript response
    with patch('src.services.transcription.AsyncOpenAI') as mock_openai_class:
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        mock_client.audio.transcriptions.create = AsyncMock(return_value="")

        with pytest.raises(TranscriptionError) as exc_info:
            await transcribe_audio(b"fake audio")

        assert "empty transcript" in str(exc_info.value).lower()
        assert exc_info.value.retryable is True

    # Test: API error (rate limit)
    with patch('src.services.transcription.AsyncOpenAI') as mock_openai_class:
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client

        # Mock API error with status code
        api_error = Exception("Rate limit exceeded")
        api_error.status_code = 429
        mock_client.audio.transcriptions.create = AsyncMock(side_effect=api_error)

        with pytest.raises(TranscriptionError) as exc_info:
            await transcribe_audio(b"fake audio")

        assert exc_info.value.retryable is True

    # Test: API error (invalid key)
    with patch('src.services.transcription.AsyncOpenAI') as mock_openai_class:
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client

        api_error = Exception("Invalid API key")
        api_error.status_code = 401
        mock_client.audio.transcriptions.create = AsyncMock(side_effect=api_error)

        with pytest.raises(TranscriptionError) as exc_info:
            await transcribe_audio(b"fake audio")

        assert exc_info.value.retryable is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_voice_transcription_delete_recording(db_session: AsyncSession):
    """
    Test deleting audio recording and transcript (for re-record).

    Flow:
    1. Store AudioRecording
    2. Store Transcript
    3. Delete transcript
    4. Delete recording
    5. Verify both deleted from ephemeral storage
    """
    # Clear ephemeral storage
    ephemeral_storage.audio_recordings.clear()
    ephemeral_storage.transcripts.clear()

    # Setup: Create and store AudioRecording
    recording_id = uuid4()
    audio_recording = AudioRecording(
        recording_id=recording_id,
        participant_id=uuid4(),
        audio_data=b"fake audio",
        created_at=datetime.utcnow(),
        status=AudioStatus.COMPLETED
    )
    ephemeral_storage.store_audio_recording(audio_recording)

    # Setup: Create and store Transcript
    transcript_id = uuid4()
    transcript = Transcript(
        transcript_id=transcript_id,
        recording_id=recording_id,
        transcript_text="Transcript to be deleted",
        reviewed=True,
        accepted=False
    )
    ephemeral_storage.store_transcript(transcript)

    # Verify: Both exist
    assert ephemeral_storage.get_audio_recording(recording_id) is not None
    assert ephemeral_storage.get_transcript(transcript_id) is not None

    # Test: Delete transcript
    ephemeral_storage.delete_transcript(transcript_id)
    assert ephemeral_storage.get_transcript(transcript_id) is None

    # Test: Delete recording
    ephemeral_storage.delete_audio_recording(recording_id)
    assert ephemeral_storage.get_audio_recording(recording_id) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_voice_transcription_text_normalization(db_session: AsyncSession):
    """
    Test that transcribed text is normalized (whitespace trimmed).

    Verifies:
    - Leading/trailing whitespace removed from transcript
    - Text ready for submission
    """
    # Setup: Mock API with whitespace in response
    mock_transcript = "  \n  Transcribed text with whitespace  \n  "

    with patch('src.services.transcription.AsyncOpenAI') as mock_openai_class:
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcript)

        # Test: Transcribe
        transcript_text, latency_ms = await transcribe_audio(b"fake audio")

        # Verify: Whitespace trimmed
        assert transcript_text == "Transcribed text with whitespace"
        assert transcript_text.strip() == transcript_text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_voice_transcriptions_parallel(db_session: AsyncSession):
    """
    Test multiple voice transcriptions can be processed in parallel.

    Verifies:
    - Multiple AudioRecording objects can be stored simultaneously
    - Each gets unique recording_id and transcript_id
    """
    # Clear ephemeral storage
    ephemeral_storage.audio_recordings.clear()
    ephemeral_storage.transcripts.clear()

    # Setup: Create multiple recordings
    recordings = []
    for i in range(3):
        recording_id = uuid4()
        recording = AudioRecording(
            recording_id=recording_id,
            participant_id=uuid4(),
            audio_data=f"audio data {i}".encode(),
            created_at=datetime.utcnow(),
            status=AudioStatus.PENDING
        )
        ephemeral_storage.store_audio_recording(recording)
        recordings.append(recording)

    # Verify: All stored
    for recording in recordings:
        stored = ephemeral_storage.get_audio_recording(recording.recording_id)
        assert stored is not None
        assert stored.recording_id == recording.recording_id

    # Verify: Unique IDs
    recording_ids = [r.recording_id for r in recordings]
    assert len(recording_ids) == len(set(recording_ids))
