"""
Transcription service for voice input using OpenAI Whisper API.
Converts audio recordings to text for Input Collection Protocol.
"""

import time
from typing import Tuple
import logging

from openai import AsyncOpenAI
from src.config import settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Raised when transcription fails."""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


async def transcribe_audio(audio_data: bytes, filename: str = "audio.webm") -> Tuple[str, float]:
    """
    Transcribe audio using OpenAI Whisper API.

    Args:
        audio_data: Raw audio bytes
        filename: Filename hint for the audio format (default: audio.webm)

    Returns:
        Tuple of (transcript_text, latency_ms)

    Raises:
        TranscriptionError: If transcription fails
    """
    if not settings.openai_api_key:
        raise TranscriptionError(
            "OpenAI API key not configured. Set OPENAI_API_KEY environment variable.",
            retryable=False
        )

    start_time = time.time()

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Create a file-like object from bytes
        # Whisper API expects a file with proper format extension
        from io import BytesIO
        audio_file = BytesIO(audio_data)
        audio_file.name = filename

        # Call Whisper API
        logger.info(f"Starting transcription for audio file: {filename}")
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

        latency_ms = (time.time() - start_time) * 1000

        # Response is just the text string when response_format="text"
        transcript_text = response.strip() if isinstance(response, str) else str(response).strip()

        logger.info(f"Transcription completed in {latency_ms:.2f}ms: {transcript_text[:50]}...")

        if not transcript_text:
            raise TranscriptionError(
                "Whisper API returned empty transcript",
                retryable=True
            )

        return transcript_text, latency_ms

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000

        # Check if it's an API error
        if hasattr(e, 'status_code'):
            if e.status_code == 401:
                raise TranscriptionError(
                    "Invalid OpenAI API key",
                    retryable=False
                )
            elif e.status_code == 429:
                raise TranscriptionError(
                    "OpenAI API rate limit exceeded",
                    retryable=True
                )
            elif e.status_code >= 500:
                raise TranscriptionError(
                    f"OpenAI API server error: {str(e)}",
                    retryable=True
                )

        # Generic error
        logger.error(f"Transcription failed after {latency_ms:.2f}ms: {str(e)}")
        raise TranscriptionError(
            f"Transcription failed: {str(e)}",
            retryable=True
        )
