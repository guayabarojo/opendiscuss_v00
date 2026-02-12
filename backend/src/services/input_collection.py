"""
Input collection service for Input Collection Protocol.
Main service for accepting and processing submissions.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4
import time

from src.models.submission_metadata import SubmissionMetadata, SubmissionModality
from src.models.ephemeral import RawSubmission
from src.services.ephemeral_storage import ephemeral_storage
from src.services.window_enforcement import (
    is_within_window,
    get_window_status,
    get_wait_duration_seconds,
    WindowStatus
)
from src.services.validation import validate_text_input
from src.services.normalization import normalize_text
from src.events.bus import event_bus, EVENT_SUBMISSION_CREATED
from src.config import settings
from src.utils.logger import get_logger, log_performance, log_error, log_audit

logger = get_logger(__name__)


class WindowViolationError(Exception):
    """
    Raised when submission is outside window.

    Attributes:
        message: Human-readable error message
        window_status: Status of the window (BEFORE_WINDOW/AFTER_WINDOW)
        window_start: Window start time
        window_end: Window end time
        current_time: Time of submission attempt
        wait_duration_seconds: Seconds to wait (only for BEFORE_WINDOW)
    """
    def __init__(
        self,
        message: str,
        window_status: WindowStatus,
        window_start: datetime,
        window_end: datetime,
        current_time: datetime,
        wait_duration_seconds: Optional[int] = None
    ):
        super().__init__(message)
        self.message = message
        self.window_status = window_status
        self.window_start = window_start
        self.window_end = window_end
        self.current_time = current_time
        self.wait_duration_seconds = wait_duration_seconds


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


async def accept_submission(
    participant_id: UUID,
    round_id: UUID,
    text: str,
    modality: SubmissionModality,
    window_start: datetime,
    window_end: datetime,
    db_session
) -> SubmissionMetadata:
    """
    Accept a submission from a participant.

    Process:
    1. Validate window
    2. Validate text
    3. Normalize text
    4. Create SubmissionMetadata (persistent)
    5. Store RawSubmission (ephemeral)
    6. Publish submission.created event

    Args:
        participant_id: Participant UUID
        round_id: Round UUID
        text: Raw text input
        modality: TEXT or VOICE
        window_start: Window start time
        window_end: Window end time
        db_session: Database session

    Returns:
        Created SubmissionMetadata

    Raises:
        WindowViolationError: If outside window
        ValidationError: If validation fails
    """
    start_time = time.time()
    now = datetime.utcnow()

    logger.info("Processing submission", extra={
        "context": {
            "participant_id": str(participant_id),
            "round_id": str(round_id),
            "modality": modality.value,
            "text_length": len(text)
        }
    })

    # 1. Check rate limit (T046: max 3 submissions per participant per round)
    max_submissions = settings.max_submissions_per_round
    rate_limit_window_minutes = settings.submission_window_duration_minutes

    can_submit = ephemeral_storage.check_rate_limit(
        participant_id,
        max_submissions,
        rate_limit_window_minutes
    )

    if not can_submit:
        logger.warning("Rate limit exceeded", extra={
            "context": {
                "participant_id": str(participant_id),
                "round_id": str(round_id),
                "max_submissions": max_submissions
            }
        })
        raise RateLimitExceeded(
            f"Rate limit exceeded: maximum {max_submissions} submissions per round"
        )

    # 2. Validate window (inclusive start, exclusive end)
    if not is_within_window(now, window_start, window_end):
        # Determine specific window status for detailed error
        status = get_window_status(now, window_start, window_end)

        # Calculate wait duration for BEFORE_WINDOW case
        wait_duration = None
        if status == WindowStatus.BEFORE_WINDOW:
            wait_duration = get_wait_duration_seconds(now, window_start)

        # Create detailed error message with user-friendly suggestion
        if status == WindowStatus.BEFORE_WINDOW:
            message = (
                f"Submission window has not opened yet. "
                f"Please wait {wait_duration} seconds until {window_start.isoformat()}."
            )
        elif status == WindowStatus.AFTER_WINDOW:
            message = (
                f"Submission window has closed. "
                f"The window closed at {window_end.isoformat()}."
            )
        else:
            message = "Submission is outside the active window."

        logger.warning("Window violation", extra={
            "context": {
                "participant_id": str(participant_id),
                "round_id": str(round_id),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "current_time": now.isoformat(),
                "window_status": status.value,
                "wait_duration_seconds": wait_duration
            }
        })

        raise WindowViolationError(
            message=message,
            window_status=status,
            window_start=window_start,
            window_end=window_end,
            current_time=now,
            wait_duration_seconds=wait_duration
        )

    # 3. Validate text
    is_valid, error_msg = validate_text_input(text)
    if not is_valid:
        raise ValidationError(error_msg)

    # 4. Normalize text
    normalized_text = normalize_text(text)

    # 5. Create SubmissionMetadata (persistent to DB)
    submission_id = uuid4()
    metadata = SubmissionMetadata(
        submission_id=submission_id,
        participant_id=participant_id,
        round_id=round_id,
        timestamp=now,
        modality=modality,
        counted=False  # Will be set to True when participant approves their summary
    )

    db_session.add(metadata)
    await db_session.flush()

    # 6. Store RawSubmission (ephemeral in-memory, TTL = 24 hours)
    ttl_expires_at = now + timedelta(hours=24)
    raw_submission = RawSubmission(
        submission_id=submission_id,
        submission_text=normalized_text,
        ttl_expires_at=ttl_expires_at
    )
    ephemeral_storage.store_raw_submission(raw_submission)

    # 7. Publish submission.created event (for Spec 3 summarization)
    await event_bus.publish(EVENT_SUBMISSION_CREATED, {
        "submission_id": str(submission_id),
        "participant_id": str(participant_id),
        "round_id": str(round_id),
        "modality": modality.value,
        "timestamp": now.isoformat()
    })

    # Log performance metrics
    duration_ms = (time.time() - start_time) * 1000
    log_performance(
        logger,
        "submission_accepted",
        duration_ms,
        submission_id=str(submission_id),
        participant_id=str(participant_id),
        round_id=str(round_id),
        modality=modality.value
    )

    # Audit log for important state change
    log_audit(
        logger,
        "submission_created",
        submission_id=str(submission_id),
        participant_id=str(participant_id),
        round_id=str(round_id),
        modality=modality.value,
        counted=False
    )

    return metadata
