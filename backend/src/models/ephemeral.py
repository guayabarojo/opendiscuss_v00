"""
Ephemeral (in-memory) dataclasses for Input Collection Protocol.
These are NOT persisted to database - only stored in-memory with TTL.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID
import enum


class AudioStatus(str, enum.Enum):
    PENDING = "PENDING"
    TRANSCRIBING = "TRANSCRIBING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class RawSubmission:
    """Ephemeral raw submission text (deleted after summarization)."""
    submission_id: UUID
    submission_text: str
    ttl_expires_at: datetime


@dataclass
class AudioRecording:
    """Ephemeral audio recording (deleted after transcription)."""
    recording_id: UUID
    participant_id: UUID
    audio_data: bytes
    created_at: datetime
    status: AudioStatus = AudioStatus.PENDING


@dataclass
class Transcript:
    """Ephemeral transcript (deleted after participant accepts)."""
    transcript_id: UUID
    recording_id: UUID
    transcript_text: str
    reviewed: bool = False
    accepted: bool = False
