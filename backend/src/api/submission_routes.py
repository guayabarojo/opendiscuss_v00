"""
Submission API routes for OpenDiscuss Discussion Protocol.

Implements submission-related endpoints:
- POST /submissions - Submit with rate limiting
- GET /submissions/history - View submission history
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.submission import Submission
from ..models.approved_summary import ApprovedSummary
from ..services.submission_service import SubmissionService
from ..api.error_handlers import (
    RateLimitExceededException,
    TimingViolationException,
    RoundNotFoundException,
    ParticipantNotFoundException,
)
from .schemas import (
    SubmitRequest,
    SubmissionResponse,
    SubmissionHistoryResponse,
    SubmissionHistoryItem,
)

# Create router
router = APIRouter(prefix="/submissions", tags=["submissions"])


# ============================================================================
# T067: POST /submissions - Submit with Rate Limiting
# ============================================================================


@router.post(
    "",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a participant response to a round",
    description="Create a submission with rate limit enforcement (max 3 per round)",
    responses={
        201: {"description": "Submission created successfully"},
        400: {"description": "Submission window not open"},
        404: {"description": "Round or participant not found"},
        429: {"description": "Rate limit exceeded (max 3 submissions per round)"},
    },
)
async def create_submission(
    request: SubmitRequest,
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
    """
    Create a new submission for a round (T067).

    Rate Limiting:
    - Maximum 3 submissions per participant per round
    - Returns 429 (Too Many Requests) if limit exceeded
    - Response includes remaining_submissions field

    Validation:
    - Submission window must be OPEN
    - Participant must exist and be active
    - submission_text must be 1-2000 characters

    Args:
        request: SubmitRequest with participant_id, round_id, submission_text, modality
        db: Database session (injected)

    Returns:
        201: SubmissionResponse with submission details and remaining_submissions
        400: Submission window not open
        404: Round or participant not found
        429: Rate limit exceeded

    Error Messages:
    - 429: "Rate limit exceeded. Maximum 3 submissions per round."
    """
    # Initialize submission service
    submission_service = SubmissionService(db)

    try:
        # Create submission with rate limit check
        submission, remaining_submissions = await submission_service.handle_multiple_submissions(
            participant_id=request.participant_id,
            round_id=request.round_id,
            submission_text=request.submission_text,
            modality=request.modality,
        )

        # Build response
        return SubmissionResponse(
            submission_id=submission.submission_id,
            participant_id=submission.participant_id,
            round_id=submission.round_id,
            submission_text=submission.submission_text,
            modality=submission.modality.value if hasattr(submission.modality, 'value') else str(submission.modality),
            submitted_at=submission.submitted_at,
            summary_status=submission.summary_status.value if hasattr(submission.summary_status, 'value') else str(submission.summary_status),
            remaining_submissions=remaining_submissions,
        )

    except RateLimitExceededException:
        # Re-raise with proper error message for T067
        raise RateLimitExceededException(
            resource=f"submissions for round {request.round_id}",
            limit=3,
            current=3,
            reset_at=None,
        )
    except TimingViolationException as e:
        # Re-raise timing violations as-is
        raise e
    except ValueError as e:
        # Handle validation errors from service
        if "not found" in str(e).lower():
            if "round" in str(e).lower():
                raise RoundNotFoundException(str(request.round_id))
            elif "participant" in str(e).lower():
                raise ParticipantNotFoundException(str(request.participant_id))
        raise e


# ============================================================================
# T068: GET /submissions/history - View Submission History
# ============================================================================


@router.get(
    "/history",
    response_model=SubmissionHistoryResponse,
    summary="Get participant's submission history for a round",
    description="View all submissions with approval status (APPROVED, SUPERSEDED, PENDING)",
    responses={
        200: {"description": "Submission history retrieved successfully"},
        404: {"description": "Round or participant not found"},
    },
)
async def get_submission_history(
    participant_id: UUID = Query(..., description="UUID of the participant"),
    round_id: UUID = Query(..., description="UUID of the round"),
    db: AsyncSession = Depends(get_db),
) -> SubmissionHistoryResponse:
    """
    Get submission history for a participant in a round (T068).

    Returns:
    - All submissions ordered by submitted_at DESC (most recent first)
    - Each submission includes summary_status (APPROVED, SUPERSEDED, PENDING, etc.)
    - Indicates which submission is currently approved (is_currently_approved)
    - Includes remaining_submissions count
    - Returns empty array if no submissions yet

    Args:
        participant_id: UUID of the participant
        round_id: UUID of the round
        db: Database session (injected)

    Returns:
        200: SubmissionHistoryResponse with submissions list
        404: Round or participant not found

    Status Values:
    - APPROVED: Summary approved and used for clustering
    - SUPERSEDED: Previously approved but replaced by newer submission
    - PENDING: Awaiting summary generation and approval
    - REJECTED: Summary rejected by participant
    - APPROVAL_TIMEOUT: Approval deadline expired
    """
    # Initialize submission service
    submission_service = SubmissionService(db)

    try:
        # Get submissions from service
        submissions = await submission_service.get_participant_submissions(
            participant_id=participant_id,
            round_id=round_id,
        )

        # Get remaining submissions count
        remaining_submissions = await submission_service.get_remaining_submissions(
            participant_id=participant_id,
            round_id=round_id,
        )

        # Find currently approved submission (if any)
        approved_summary_result = await db.execute(
            select(ApprovedSummary).where(
                and_(
                    ApprovedSummary.participant_id == participant_id,
                    ApprovedSummary.round_id == round_id,
                )
            )
        )
        approved_summary = approved_summary_result.scalar_one_or_none()
        currently_approved_id = (
            approved_summary.submission_id if approved_summary else None
        )

        # Build submission history items
        history_items: List[SubmissionHistoryItem] = []
        for submission in submissions:
            history_items.append(
                SubmissionHistoryItem(
                    submission_id=submission.submission_id,
                    submission_text=submission.submission_text,
                    modality=submission.modality.value,
                    submitted_at=submission.submitted_at,
                    summary_status=submission.summary_status.value,
                    is_currently_approved=(
                        submission.submission_id == currently_approved_id
                        if currently_approved_id
                        else False
                    ),
                )
            )

        # Build response
        return SubmissionHistoryResponse(
            participant_id=participant_id,
            round_id=round_id,
            submissions=history_items,
            total_submissions=len(history_items),
            remaining_submissions=remaining_submissions,
        )

    except ValueError as e:
        # Handle not found errors from service
        if "not found" in str(e).lower():
            if "round" in str(e).lower():
                raise RoundNotFoundException(str(round_id))
            elif "participant" in str(e).lower():
                raise ParticipantNotFoundException(str(participant_id))
        raise e
