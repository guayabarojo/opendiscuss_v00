"""
Submission API endpoints for Input Collection Protocol.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import List, Optional
import time

from src.api.schemas import (
    SubmissionRequest,
    InputCollectionSubmissionResponse,
    SubmissionListResponse,
    ErrorResponse
)
from src.database import get_db_session
from src.models.submission_metadata import SubmissionMetadata
from src.models.round import Round
from src.services.input_collection import (
    accept_submission,
    WindowViolationError,
    ValidationError,
    RateLimitExceeded
)
from src.config import settings
from src.utils.logger import get_logger, log_error, log_performance

logger = get_logger(__name__)

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("/", response_model=InputCollectionSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    request: SubmissionRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Submit text input for a round.

    Validates window timing, normalizes text, stores metadata and raw content.
    """
    start_time = time.time()

    logger.info("Received submission request", extra={
        "context": {
            "participant_id": str(request.participant_id),
            "round_id": str(request.round_id),
            "modality": request.modality.value
        }
    })

    try:
        # Get round to check window
        result = await db.execute(
            select(Round).where(Round.round_id == request.round_id)
        )
        round_obj = result.scalar_one_or_none()

        if not round_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Round {request.round_id} not found"
            )

        # Accept submission
        metadata = await accept_submission(
            participant_id=request.participant_id,
            round_id=request.round_id,
            text=request.text,
            modality=request.modality,
            window_start=round_obj.submission_window_start,
            window_end=round_obj.submission_window_end,
            db_session=db
        )

        await db.commit()

        # Log successful submission API call performance
        duration_ms = (time.time() - start_time) * 1000
        log_performance(
            logger,
            "submission_api_call",
            duration_ms,
            submission_id=str(metadata.submission_id),
            participant_id=str(request.participant_id),
            round_id=str(request.round_id),
            status="success"
        )

        return InputCollectionSubmissionResponse(
            submission_id=metadata.submission_id,
            participant_id=metadata.participant_id,
            round_id=metadata.round_id,
            timestamp=metadata.timestamp,
            modality=metadata.modality,
            counted=metadata.counted
        )

    except WindowViolationError as e:
        log_error(logger, e, "Window violation error",
                 participant_id=str(request.participant_id),
                 round_id=str(request.round_id))

        # Build detailed error response with timing information
        error_detail = {
            "error_code": e.window_status.value,
            "message": e.message,
            "window_start": e.window_start.isoformat(),
            "window_end": e.window_end.isoformat(),
            "current_time": e.current_time.isoformat(),
            "status": e.window_status.value
        }

        # Add wait duration for BEFORE_WINDOW case
        if e.wait_duration_seconds is not None:
            error_detail["wait_duration_seconds"] = e.wait_duration_seconds
            error_detail["suggestion"] = (
                f"The submission window will open in {e.wait_duration_seconds} seconds. "
                f"Please try again after {e.window_start.isoformat()}."
            )
        elif e.window_status.value == "AFTER_WINDOW":
            error_detail["suggestion"] = (
                "The submission window for this round has closed. "
                "Please wait for the next round to submit."
            )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_detail
        )

    except ValidationError as e:
        log_error(logger, e, "Validation error",
                 participant_id=str(request.participant_id),
                 round_id=str(request.round_id))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "VALIDATION_FAILED",
                "message": str(e)
            }
        )

    except RateLimitExceeded as e:
        log_error(logger, e, "Rate limit exceeded",
                 participant_id=str(request.participant_id),
                 round_id=str(request.round_id))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "TOO_MANY_REQUESTS",
                "message": "Rate limit exceeded",
                "details": str(e)
            }
        )

    except Exception as e:
        # Catch-all for unexpected errors
        log_error(logger, e, "Unexpected error in submission endpoint",
                 participant_id=str(request.participant_id),
                 round_id=str(request.round_id))
        raise


@router.get("/{submission_id}", response_model=InputCollectionSubmissionResponse)
async def get_submission(
    submission_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get submission metadata by ID.

    Returns metadata only (not raw text, which is ephemeral).
    """
    result = await db.execute(
        select(SubmissionMetadata).where(SubmissionMetadata.submission_id == submission_id)
    )
    metadata = result.scalar_one_or_none()

    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found"
        )

    return InputCollectionSubmissionResponse(
        submission_id=metadata.submission_id,
        participant_id=metadata.participant_id,
        round_id=metadata.round_id,
        timestamp=metadata.timestamp,
        modality=metadata.modality,
        counted=metadata.counted
    )


@router.get("/participant/{participant_id}/round/{round_id}", response_model=SubmissionListResponse)
async def get_participant_submissions(
    participant_id: UUID,
    round_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all submissions for a participant in a round (T047-T048).

    Returns submissions ordered by timestamp DESC (most recent first).
    Includes total count, max allowed, and whether more submissions can be made.
    """
    # Query all submissions for this participant in this round
    result = await db.execute(
        select(SubmissionMetadata)
        .where(
            SubmissionMetadata.participant_id == participant_id,
            SubmissionMetadata.round_id == round_id
        )
        .order_by(SubmissionMetadata.timestamp.desc())
    )
    submissions = result.scalars().all()

    # Get max allowed from config
    max_allowed = settings.max_submissions_per_round

    # Calculate if can submit more
    total_count = len(submissions)
    can_submit_more = total_count < max_allowed

    # Convert to response models
    submission_responses = [
        InputCollectionSubmissionResponse(
            submission_id=sub.submission_id,
            participant_id=sub.participant_id,
            round_id=sub.round_id,
            timestamp=sub.timestamp,
            modality=sub.modality,
            counted=sub.counted
        )
        for sub in submissions
    ]

    return SubmissionListResponse(
        submissions=submission_responses,
        total_count=total_count,
        max_allowed=max_allowed,
        can_submit_more=can_submit_more
    )
