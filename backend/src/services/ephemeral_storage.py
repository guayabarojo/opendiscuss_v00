"""
Ephemeral storage manager for Input Collection Protocol.
Manages in-memory storage for raw submissions, rate limits, audio recordings, and transcripts.
All data is volatile and has TTL-based expiration.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from uuid import UUID

from src.models.ephemeral import RawSubmission, AudioRecording, Transcript


class EphemeralStorageManager:
    """Manages in-memory storage for ephemeral data."""

    def __init__(self):
        # Dictionary storage (UUID -> object)
        self.raw_submissions: Dict[UUID, RawSubmission] = {}
        self.audio_recordings: Dict[UUID, AudioRecording] = {}
        self.transcripts: Dict[UUID, Transcript] = {}

        # Rate limiting (participant_id -> list of submission timestamps)
        self.rate_limits: Dict[UUID, list[datetime]] = {}

    def store_raw_submission(self, submission: RawSubmission) -> None:
        """Store raw submission with TTL."""
        self.raw_submissions[submission.submission_id] = submission

    def get_raw_submission(self, submission_id: UUID) -> Optional[RawSubmission]:
        """Get raw submission if not expired."""
        submission = self.raw_submissions.get(submission_id)
        if submission and submission.ttl_expires_at > datetime.utcnow():
            return submission
        elif submission:
            # Expired - remove it
            del self.raw_submissions[submission_id]
        return None

    def delete_raw_submission(self, submission_id: UUID) -> None:
        """Delete raw submission (called after summarization)."""
        self.raw_submissions.pop(submission_id, None)

    def store_audio_recording(self, recording: AudioRecording) -> None:
        """Store audio recording."""
        self.audio_recordings[recording.recording_id] = recording

    def get_audio_recording(self, recording_id: UUID) -> Optional[AudioRecording]:
        """Get audio recording."""
        return self.audio_recordings.get(recording_id)

    def delete_audio_recording(self, recording_id: UUID) -> None:
        """Delete audio recording (for re-record)."""
        self.audio_recordings.pop(recording_id, None)

    def store_transcript(self, transcript: Transcript) -> None:
        """Store transcript."""
        self.transcripts[transcript.transcript_id] = transcript

    def get_transcript(self, transcript_id: UUID) -> Optional[Transcript]:
        """Get transcript."""
        return self.transcripts.get(transcript_id)

    def get_transcript_by_recording(self, recording_id: UUID) -> Optional[Transcript]:
        """Get transcript by recording ID."""
        for transcript in self.transcripts.values():
            if transcript.recording_id == recording_id:
                return transcript
        return None

    def delete_transcript(self, transcript_id: UUID) -> None:
        """Delete transcript."""
        self.transcripts.pop(transcript_id, None)

    def check_rate_limit(self, participant_id: UUID, max_submissions: int, window_minutes: int) -> bool:
        """
        Check if participant can submit (rate limit).

        CRITICAL LOGIC: Rate Limiter Locking Strategy
        -----------------------------------------------
        This implementation uses Python's GIL (Global Interpreter Lock) for thread safety.
        Since this is an in-memory dictionary operation with asyncio (single-threaded event loop),
        we don't need explicit threading.Lock.

        For production multi-process deployments:
        - Replace with Redis-based rate limiting (INCR + EXPIRE)
        - Or use database-level rate limit tracking with SELECT FOR UPDATE

        Race Condition Analysis:
        - WITHOUT locking: Two concurrent requests could both read count=2, both increment to 3
        - WITH GIL: Operations are atomic within single Python process
        - WITH Redis: INCR is atomic across processes

        Current approach is safe for single-process uvicorn deployment (MVP).
        For horizontal scaling, migrate to Redis-based implementation.

        Args:
            participant_id: Participant UUID
            max_submissions: Maximum allowed submissions (default: 3)
            window_minutes: Time window in minutes (matches submission window)

        Returns:
            True if submission allowed, False if rate limit exceeded

        Example:
            max_submissions=3, window=5 minutes
            - Submission 1 at 14:00 → allowed (count=1)
            - Submission 2 at 14:02 → allowed (count=2)
            - Submission 3 at 14:04 → allowed (count=3)
            - Submission 4 at 14:04:30 → REJECTED (count=3, limit reached)
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=window_minutes)

        # Get or create rate limit list for this participant
        if participant_id not in self.rate_limits:
            self.rate_limits[participant_id] = []

        # Clean old entries (submissions outside the time window)
        # This implements sliding window rate limiting
        # Example: If window is 5 minutes, only count submissions from last 5 minutes
        self.rate_limits[participant_id] = [
            ts for ts in self.rate_limits[participant_id] if ts > cutoff
        ]

        # Check limit: If already at max, reject new submission
        if len(self.rate_limits[participant_id]) >= max_submissions:
            return False

        # Record this submission timestamp
        # Note: This happens BEFORE the actual submission is created
        # If submission fails later, we don't decrement (simpler, acceptable for MVP)
        self.rate_limits[participant_id].append(now)
        return True

    def cleanup_expired(self) -> None:
        """Clean up expired TTL entries."""
        now = datetime.utcnow()
        expired_ids = [
            sid for sid, sub in self.raw_submissions.items()
            if sub.ttl_expires_at <= now
        ]
        for sid in expired_ids:
            del self.raw_submissions[sid]


# Global singleton instance
ephemeral_storage = EphemeralStorageManager()
