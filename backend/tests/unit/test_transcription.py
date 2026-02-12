"""
Unit tests for transcription service (Spec 002 - User Story 2).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.transcription import transcribe_audio, TranscriptionError


@pytest.mark.asyncio
async def test_transcribe_audio_success():
    """Test successful audio transcription."""
    # Mock OpenAI client
    mock_client = AsyncMock()
    mock_response = "This is a test transcript"
    mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)

    with patch('src.services.transcription.AsyncOpenAI', return_value=mock_client):
        with patch('src.services.transcription.settings') as mock_settings:
            mock_settings.openai_api_key = "test-api-key"

            audio_data = b"fake audio data"
            transcript, latency_ms = await transcribe_audio(audio_data)

            assert transcript == "This is a test transcript"
            assert latency_ms > 0
            assert isinstance(latency_ms, float)


@pytest.mark.asyncio
async def test_transcribe_audio_missing_api_key():
    """Test transcription fails when API key is missing."""
    with patch('src.services.transcription.settings') as mock_settings:
        mock_settings.openai_api_key = ""

        audio_data = b"fake audio data"

        with pytest.raises(TranscriptionError) as exc_info:
            await transcribe_audio(audio_data)

        assert "API key not configured" in str(exc_info.value)
        assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_transcribe_audio_empty_transcript():
    """Test transcription fails when API returns empty transcript."""
    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value="   ")

    with patch('src.services.transcription.AsyncOpenAI', return_value=mock_client):
        with patch('src.services.transcription.settings') as mock_settings:
            mock_settings.openai_api_key = "test-api-key"

            audio_data = b"fake audio data"

            with pytest.raises(TranscriptionError) as exc_info:
                await transcribe_audio(audio_data)

            assert "empty transcript" in str(exc_info.value)
            assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_transcribe_audio_api_rate_limit():
    """Test transcription handles rate limit errors."""
    mock_client = AsyncMock()
    mock_error = Exception("Rate limit exceeded")
    mock_error.status_code = 429
    mock_client.audio.transcriptions.create = AsyncMock(side_effect=mock_error)

    with patch('src.services.transcription.AsyncOpenAI', return_value=mock_client):
        with patch('src.services.transcription.settings') as mock_settings:
            mock_settings.openai_api_key = "test-api-key"

            audio_data = b"fake audio data"

            with pytest.raises(TranscriptionError) as exc_info:
                await transcribe_audio(audio_data)

            assert "rate limit" in str(exc_info.value).lower()
            assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_transcribe_audio_invalid_api_key():
    """Test transcription handles invalid API key."""
    mock_client = AsyncMock()
    mock_error = Exception("Invalid API key")
    mock_error.status_code = 401
    mock_client.audio.transcriptions.create = AsyncMock(side_effect=mock_error)

    with patch('src.services.transcription.AsyncOpenAI', return_value=mock_client):
        with patch('src.services.transcription.settings') as mock_settings:
            mock_settings.openai_api_key = "invalid-key"

            audio_data = b"fake audio data"

            with pytest.raises(TranscriptionError) as exc_info:
                await transcribe_audio(audio_data)

            assert "Invalid OpenAI API key" in str(exc_info.value)
            assert exc_info.value.retryable is False
