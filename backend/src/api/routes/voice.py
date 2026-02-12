"""
Voice input API routes for Input Collection Protocol.
Handles audio recording, transcription, and cleanup.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
import logging

from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import TranscriptResponse, ErrorResponse
from src.models.ephemeral import AudioRecording, Transcript, AudioStatus
from src.services.ephemeral_storage import ephemeral_storage
from src.services.transcription import transcribe_audio, TranscriptionError
from src.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post(
    "/transcribe",
    response_model=TranscriptResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Transcription failed"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
    }
)
async def transcribe_voice_input(
    audio: UploadFile = File(..., description="Audio file (WebM, MP3, WAV, etc.)"),
    participant_id: UUID = Form(..., description="Participant UUID"),
    round_id: UUID = Form(..., description="Round UUID"),
    db: AsyncSession = Depends(get_db)
) -> TranscriptResponse:
    """
    Transcribe audio to text using OpenAI Whisper API.

    Process:
    1. Store AudioRecording in ephemeral storage
    2. Call transcription service
    3. Store Transcript in ephemeral storage
    4. Return transcript with latency metrics

    Args:
        audio: Uploaded audio file
        participant_id: Participant submitting the recording
        round_id: Round for the submission
        db: Database session

    Returns:
        TranscriptResponse with transcript text and latency

    Raises:
        HTTPException: 400 if invalid audio, 500 if transcription fails
    """
    recording_id = uuid4()
    transcript_id = uuid4()

    try:
        # Read audio data
        audio_data = await audio.read()

        if not audio_data:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_AUDIO",
                    "message": "Audio file is empty",
                    "retryable": False
                }
            )

        # Store AudioRecording in ephemeral storage
        audio_recording = AudioRecording(
            recording_id=recording_id,
            participant_id=participant_id,
            audio_data=audio_data,
            created_at=datetime.utcnow(),
            status=AudioStatus.TRANSCRIBING
        )
        ephemeral_storage.store_audio_recording(audio_recording)

        logger.info(f"Stored audio recording {recording_id} for participant {participant_id}")

        # Transcribe audio
        try:
            transcript_text, latency_ms = await transcribe_audio(
                audio_data,
                filename=audio.filename or "audio.webm"
            )
        except TranscriptionError as e:
            # Update recording status to FAILED
            audio_recording.status = AudioStatus.FAILED
            ephemeral_storage.store_audio_recording(audio_recording)

            raise HTTPException(
                status_code=500,
                detail={
                    "error": "TRANSCRIPTION_FAILED",
                    "message": str(e),
                    "retryable": e.retryable,
                    "recording_id": str(recording_id)
                }
            )

        # Update recording status to COMPLETED
        audio_recording.status = AudioStatus.COMPLETED
        ephemeral_storage.store_audio_recording(audio_recording)

        # Store Transcript in ephemeral storage
        transcript = Transcript(
            transcript_id=transcript_id,
            recording_id=recording_id,
            transcript_text=transcript_text,
            reviewed=True,  # Displayed to user for review
            accepted=False  # Not yet accepted
        )
        ephemeral_storage.store_transcript(transcript)

        logger.info(
            f"Transcription completed for recording {recording_id} in {latency_ms:.2f}ms"
        )

        # Warn if latency exceeds target (SC-002: < 3 seconds)
        if latency_ms > 3000:
            logger.warning(
                f"Transcription latency {latency_ms:.2f}ms exceeds target of 3000ms "
                f"(recording_id={recording_id})"
            )

        return TranscriptResponse(
            transcript_id=transcript_id,
            recording_id=recording_id,
            transcript_text=transcript_text,
            latency_ms=latency_ms
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error during transcription: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "TRANSCRIPTION_FAILED",
                "message": "An unexpected error occurred during transcription",
                "retryable": True,
                "recording_id": str(recording_id)
            }
        )


@router.delete(
    "/{recording_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Recording not found"},
    }
)
async def delete_recording(
    recording_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete audio recording and associated transcript (for re-record).

    Used when participant wants to re-record their voice input.
    Deletes both AudioRecording and Transcript from ephemeral storage.

    Args:
        recording_id: UUID of the recording to delete
        db: Database session

    Raises:
        HTTPException: 404 if recording not found
    """
    # Delete transcript first (if exists)
    transcript = ephemeral_storage.get_transcript_by_recording(recording_id)
    if transcript:
        ephemeral_storage.delete_transcript(transcript.transcript_id)
        logger.info(f"Deleted transcript {transcript.transcript_id} for recording {recording_id}")

    # Delete audio recording
    recording = ephemeral_storage.get_audio_recording(recording_id)
    if not recording:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "RECORDING_NOT_FOUND",
                "message": f"Audio recording {recording_id} not found",
            }
        )

    ephemeral_storage.delete_audio_recording(recording_id)
    logger.info(f"Deleted audio recording {recording_id}")

    # Return 204 No Content (no response body)
