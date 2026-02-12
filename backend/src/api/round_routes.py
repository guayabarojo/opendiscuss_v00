"""
Round API routes for OpenDiscuss Discussion Protocol.

Implements round status and timing endpoints per contracts/discussion-api.yaml.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models.round import Round
from ..models.submission import Submission
from ..models.approved_summary import ApprovedSummary
from ..models.participant import Participant
from ..models.protocol_state import RoundStatus
from ..services.dropout_detection import DropoutDetectionService
from ..services.round_service import RoundService
from ..services.timing_service import TimingService
from ..events.event_bus import get_event_bus
from .schemas import RoundStatusResponse, RoundResponse, ErrorResponse, DropoutReportResponse

router = APIRouter(prefix="/rounds", tags=["rounds"])


@router.get(
    "/{round_id}",
    response_model=RoundResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Round not found"}
    },
)
async def get_round(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RoundResponse:
    """
    Get round details and status.

    Args:
        round_id: Round unique identifier
        db: Database session

    Returns:
        Round details

    Raises:
        HTTPException: 404 if round not found
    """
    result = await db.execute(
        select(Round).where(Round.round_id == round_id)
    )
    round_obj = result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Round {round_id} not found"
            }
        )

    return RoundResponse.model_validate(round_obj)


@router.get(
    "/{round_id}/status",
    response_model=RoundStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Round not found"}
    },
)
async def get_round_status(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RoundStatusResponse:
    """
    Get round status with real-time timing information.

    **T035: Real-time round status endpoint**

    Provides:
    - Current round status
    - Remaining time in seconds (for countdown timer)
    - Participant statistics (submitted, approved, pending counts)
    - Current question text

    Used by frontend for live updates and countdown timers.

    Args:
        round_id: Round unique identifier
        db: Database session

    Returns:
        Real-time round status with timing and participant stats

    Raises:
        HTTPException: 404 if round not found
    """
    # Fetch round with eager loading for performance
    result = await db.execute(
        select(Round)
        .where(Round.round_id == round_id)
        .options(selectinload(Round.submissions))
        .options(selectinload(Round.approved_summaries))
    )
    round_obj = result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Round {round_id} not found"
            }
        )

    # Current server time for countdown calculation
    current_time = datetime.utcnow()

    # Calculate remaining time based on status
    remaining_time_sec: Optional[int] = None

    if round_obj.status == RoundStatus.SUBMISSION_OPEN and round_obj.submission_window_end:
        # Calculate remaining time in submission window
        time_diff = (round_obj.submission_window_end - current_time).total_seconds()
        remaining_time_sec = max(0, int(time_diff))  # Never negative
    elif round_obj.status == RoundStatus.APPROVING and round_obj.approval_deadline:
        # Calculate remaining time until approval deadline
        time_diff = (round_obj.approval_deadline - current_time).total_seconds()
        remaining_time_sec = max(0, int(time_diff))  # Never negative

    # Calculate participant statistics
    participant_stats: Optional[dict] = None

    if round_obj.status in (
        RoundStatus.SUBMISSION_OPEN,
        RoundStatus.SUBMISSION_CLOSED,
        RoundStatus.SUMMARIZING,
        RoundStatus.APPROVING,
        RoundStatus.CLUSTERING,
        RoundStatus.SANKEY_BUILDING,
        RoundStatus.COMPLETE,
    ):
        # Count submitted participants (distinct participant_ids in submissions)
        submitted_result = await db.execute(
            select(func.count(func.distinct(Submission.participant_id)))
            .where(Submission.round_id == round_id)
        )
        submitted_count = submitted_result.scalar() or 0

        # Count approved summaries
        approved_result = await db.execute(
            select(func.count(ApprovedSummary.summary_id))
            .where(ApprovedSummary.round_id == round_id)
        )
        approved_count = approved_result.scalar() or 0

        # Pending approval count = submitted - approved (during APPROVING phase)
        pending_approval_count = 0
        if round_obj.status == RoundStatus.APPROVING:
            pending_approval_count = max(0, submitted_count - approved_count)

        participant_stats = {
            "submitted_count": submitted_count,
            "approved_count": approved_count,
            "pending_approval_count": pending_approval_count,
        }

    return RoundStatusResponse(
        round_id=round_obj.round_id,
        status=round_obj.status.value,
        question_text=round_obj.question_text,
        current_time=current_time,
        submission_window_end=round_obj.submission_window_end,
        approval_deadline=round_obj.approval_deadline,
        remaining_time_sec=remaining_time_sec,
        participant_stats=participant_stats,
    )


@router.get(
    "/{round_id}/dropouts",
    response_model=DropoutReportResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Round not found"}
    },
)
async def get_round_dropouts(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DropoutReportResponse:
    """
    Get list of participants who dropped out before this round.

    **T067: Dropout reporting endpoint**

    Returns participants who submitted in the previous round but did NOT
    submit in this round. This implements natural dropout handling with
    no synthetic placeholder nodes.

    For Round 1, returns empty list (no previous round).

    Args:
        round_id: Round unique identifier
        db: Database session

    Returns:
        Dropout report with participant IDs and counts

    Raises:
        HTTPException: 404 if round not found
    """
    # Fetch round to get discussion_id
    result = await db.execute(
        select(Round).where(Round.round_id == round_id)
    )
    round_obj = result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Round {round_id} not found"
            }
        )

    # Use dropout detection service to find dropouts
    dropout_service = DropoutDetectionService(db)

    try:
        dropout_participant_ids = await dropout_service.get_round_dropouts(
            round_id=round_id,
            discussion_id=round_obj.discussion_id
        )
    except ValueError as e:
        # Round 1 or other validation errors
        dropout_participant_ids = []

    # Get participant details for dropouts
    dropout_participants = []
    if dropout_participant_ids:
        participants_result = await db.execute(
            select(Participant).where(
                Participant.participant_id.in_(dropout_participant_ids)
            )
        )
        dropout_participants = list(participants_result.scalars().all())

    # Calculate dropout rate
    # Get total participants from previous round
    if round_obj.round_num > 1:
        prev_round_result = await db.execute(
            select(Round).where(
                Round.discussion_id == round_obj.discussion_id,
                Round.round_num == round_obj.round_num - 1
            )
        )
        prev_round = prev_round_result.scalar_one_or_none()

        if prev_round:
            prev_count_result = await db.execute(
                select(func.count(func.distinct(ApprovedSummary.participant_id)))
                .where(ApprovedSummary.round_id == prev_round.round_id)
            )
            prev_participant_count = prev_count_result.scalar() or 0
        else:
            prev_participant_count = 0
    else:
        prev_participant_count = 0

    dropout_count = len(dropout_participant_ids)
    dropout_rate = (dropout_count / prev_participant_count) if prev_participant_count > 0 else 0.0

    # T068: Store dropout analytics in Round model
    if round_obj.round_num > 1 and round_obj.dropout_count is None:
        try:
            round_obj.set_dropout_count(dropout_count)
            await db.commit()
        except ValueError:
            # Already set or invalid, ignore
            pass

    return DropoutReportResponse(
        round_id=round_id,
        round_num=round_obj.round_num,
        dropout_participant_ids=dropout_participant_ids,
        dropout_count=dropout_count,
        previous_round_participant_count=prev_participant_count,
        dropout_rate=dropout_rate,
    )


@router.post(
    "/{round_id}/close",
    response_model=RoundResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Only host can close rounds"},
        404: {"model": ErrorResponse, "description": "Round not found"},
        400: {"model": ErrorResponse, "description": "Invalid state or mode"},
    },
)
async def manually_close_round(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
    # TODO: Add authentication dependency to get current user
    # current_user: User = Depends(get_current_user)
) -> RoundResponse:
    """
    Host manually closes async round submission window.

    **Async Discussion Mode Feature**

    Allows the discussion host to manually close the submission window for
    asynchronous discussions. This endpoint is only available for discussions
    in ASYNCHRONOUS timing mode.

    For SYNCHRONOUS discussions, windows close automatically via TimingService.

    Args:
        round_id: Round unique identifier
        db: Database session

    Returns:
        Updated round with SUBMISSION_CLOSED status

    Raises:
        HTTPException: 403 if not host, 404 if not found, 400 if invalid mode
    """
    # TODO: Get user_id from current_user when auth is implemented
    import uuid
    user_id = uuid.uuid4()  # Placeholder until auth is implemented

    # Get event bus and timing service
    event_bus = get_event_bus()
    from ..cache.redis_client import get_redis_client
    redis_client = get_redis_client()
    timing_service = TimingService(redis_client)

    # Create round service
    round_service = RoundService(db, event_bus, timing_service)

    try:
        round_entity = await round_service.manual_close_submission_window(
            round_id=round_id,
            user_id=user_id
        )
        return RoundResponse.model_validate(round_entity)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "permission_denied",
                "message": str(e)
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_state",
                "message": str(e)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": f"Failed to close round: {str(e)}"
            }
        )
