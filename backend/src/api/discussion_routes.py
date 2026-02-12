"""
Discussion API routes for OpenDiscuss Discussion Protocol.

Implements Phase 3 API endpoints (T032-T034):
- POST /discussions - Create new discussion
- GET /discussions/{id} - Get discussion details
- POST /discussions/{id}/start - Start discussion and open Round 1
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models.discussion import Discussion
from ..models.participant import Participant
from ..models.protocol_state import DiscussionMode, DiscussionStatus, RoundStatus
from ..models.round import Round
from ..models.cluster import Cluster
from ..models.flow import Flow
from .error_handlers import DiscussionNotFoundException, InvalidStateTransitionException
from .schemas import (
    CreateDiscussionRequest,
    DiscussionResponse,
    AdvancementResponse,
    DiscussionReportResponse,
    SankeyDiagramResponse,
    SankeyColumnResponse,
    ThoughtSpaceResponse,
    FlowResponse,
)
from src.question_progression.services.sequence import (
    QuestionSequenceService,
    ValidationError as QValidationError,
    SequenceAlreadyExistsError,
)

# Create router
router = APIRouter(prefix="/discussions", tags=["discussions"])


# ============================================================================
# T032: POST /discussions - Create Discussion
# ============================================================================


@router.post(
    "",
    response_model=DiscussionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new discussion",
    description="Create a new discussion with specified mode, rounds, and questions (if HOST_DEFINED)",
)
async def create_discussion(
    request_data: CreateDiscussionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> DiscussionResponse:
    """
    Create a new discussion (T032).

    Validates:
    - Community membership (TODO: when auth is implemented)
    - Questions provided for HOST_DEFINED mode
    - Question format (10-200 chars, starts with What/How)

    Returns:
        201: Discussion created with CREATED status
        400: Validation error
        401: Unauthorized (when auth implemented)
        403: Not a community member (when auth implemented)
    """
    import uuid
    import logging
    from ..middleware.auth import get_jwt_claims_from_request

    logger = logging.getLogger(__name__)

    # Extract user_id from JWT claims if available
    jwt_claims = get_jwt_claims_from_request(request)
    logger.info(f"JWT claims in create_discussion: {jwt_claims}")

    if jwt_claims and "user_id" in jwt_claims:
        host_user_id = UUID(jwt_claims["user_id"])
        logger.info(f"Using host_user_id from JWT: {host_user_id}")
    else:
        # Fallback to placeholder for testing/demo
        host_user_id = uuid.uuid4()
        logger.info(f"No JWT claims, using placeholder host_user_id: {host_user_id}")

    # Validate mode-specific requirements
    if request_data.mode == "HOST_DEFINED":
        if not request_data.questions or len(request_data.questions) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="questions are required for HOST_DEFINED mode",
            )
        if len(request_data.questions) != request_data.total_rounds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Number of questions ({len(request_data.questions)}) must match total_rounds ({request_data.total_rounds})",
            )
    elif request_data.mode == "AUTO_GENERATED":
        if not request_data.seed_question:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="seed_question is required for AUTO_GENERATED mode",
            )

    # Import DiscussionTimingMode
    from ..models.protocol_state import DiscussionTimingMode

    # Create discussion entity
    try:
        discussion = Discussion(
            community_id=request_data.community_id,
            host_user_id=host_user_id,
            mode=DiscussionMode(request_data.mode),
            total_rounds=request_data.total_rounds,
            timing_mode=DiscussionTimingMode(request_data.timing_mode),
            round_duration_hours=request_data.round_duration_hours,
            min_submissions_for_advance=request_data.min_submissions_for_advance,
            auto_advance_enabled=request_data.auto_advance_enabled,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Save discussion first to get discussion_id
    db.add(discussion)
    await db.flush()

    # Create QuestionSequence for HOST_DEFINED mode (Phase 3 - Spec 006 integration)
    if request_data.mode == "HOST_DEFINED" and request_data.questions:
        try:
            sequence_service = QuestionSequenceService(db)
            await sequence_service.create_host_sequence(
                discussion_id=discussion.discussion_id,
                questions=request_data.questions,
            )
        except QValidationError as e:
            # Rollback discussion creation if sequence creation fails
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "VALIDATION_ERROR",
                    "message": e.message,
                    "details": {"error_code": e.error_code.value},
                },
            )
        except SequenceAlreadyExistsError as e:
            # Should not happen in normal flow
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )

    # Create rounds for HOST_DEFINED mode
    if request_data.mode == "HOST_DEFINED" and request_data.questions:
        for round_num, question_text in enumerate(request_data.questions, start=1):
            try:
                round_obj = Round(
                    discussion_id=discussion.discussion_id,
                    round_num=round_num,
                    question_text=question_text,
                    submission_window_duration_sec=300,  # Default 5 minutes
                )
                db.add(round_obj)  # SQLAlchemy will handle the relationship via FK
            except ValueError as e:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid question {round_num}: {str(e)}",
                )

    # For AUTO_GENERATED mode, create only Round 1 with seed question
    elif request_data.mode == "AUTO_GENERATED" and request_data.seed_question:
        try:
            round_obj = Round(
                discussion_id=discussion.discussion_id,
                round_num=1,
                question_text=request_data.seed_question,
                submission_window_duration_sec=300,  # Default 5 minutes
            )
            db.add(round_obj)  # SQLAlchemy will handle the relationship via FK
        except ValueError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid seed question: {str(e)}",
            )

    # Commit all changes
    await db.commit()
    await db.refresh(discussion)

    # Convert to response model
    return DiscussionResponse.model_validate(discussion)


# ============================================================================
# T033: GET /discussions/{discussion_id} - Get Discussion
# ============================================================================


@router.get(
    "/{discussion_id}",
    response_model=DiscussionResponse,
    summary="Get discussion details",
    description="Fetch discussion by ID with current round status, participant count, and advancement status (T062)",
)
async def get_discussion(
    discussion_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DiscussionResponse:
    """
    Get discussion details (T033, enhanced in T062).

    Includes:
    - Full discussion details
    - Current round status
    - Participant count
    - Timing information
    - Advancement status (Phase 6 - T062)

    Returns:
        200: Discussion found
        404: Discussion not found
    """
    # Query discussion with relationships
    stmt = (
        select(Discussion)
        .options(
            selectinload(Discussion.rounds),
            selectinload(Discussion.participants),
        )
        .where(Discussion.discussion_id == discussion_id)
    )

    result = await db.execute(stmt)
    discussion = result.scalar_one_or_none()

    if discussion is None:
        raise DiscussionNotFoundException(discussion_id=str(discussion_id))

    # Convert to response model
    response_data = DiscussionResponse.model_validate(discussion)

    # Add advancement status (T062)
    advancement_status = "NOT_APPLICABLE"
    can_advance = False
    blockers = []

    if discussion.status == DiscussionStatus.ACTIVE:
        # Check if at final round
        if discussion.current_round_num >= discussion.total_rounds:
            advancement_status = "NOT_APPLICABLE"
            blockers = ["Already at final round"]
        else:
            # Get current round
            current_round = next(
                (r for r in discussion.rounds if r.round_num == discussion.current_round_num),
                None,
            )

            if current_round:
                # Check if current round is complete (ready for advancement)
                if current_round.status == RoundStatus.COMPLETE:
                    # Get next round to check if question is ready
                    next_round = next(
                        (r for r in discussion.rounds if r.round_num == discussion.current_round_num + 1),
                        None,
                    )

                    if next_round:
                        # Check if next round can advance
                        can_adv, reason = next_round.can_advance()
                        if can_adv:
                            advancement_status = "READY"
                            can_advance = True
                        else:
                            # Determine specific blocker type
                            if "generation" in reason.lower():
                                advancement_status = "WAITING_GENERATION"
                            elif "question" in reason.lower():
                                advancement_status = "BLOCKED_QUESTION"
                            else:
                                advancement_status = "BLOCKED_QUESTION"
                            blockers = [reason]
                    else:
                        advancement_status = "BLOCKED_QUESTION"
                        blockers = ["Next round not yet created"]
                else:
                    # Current round not complete yet
                    if current_round.status == RoundStatus.SANKEY_BUILDING:
                        advancement_status = "BLOCKED_SANKEY"
                        blockers = ["Sankey diagram generation in progress"]
                    elif current_round.status in (RoundStatus.CLUSTERING, RoundStatus.APPROVING, RoundStatus.SUMMARIZING):
                        advancement_status = "BLOCKED_SANKEY"
                        blockers = [f"Round in {current_round.status.value} state - waiting for completion"]
                    else:
                        advancement_status = "BLOCKED_SANKEY"
                        blockers = [f"Current round not complete (status: {current_round.status.value})"]

    # Set advancement fields
    response_data.advancement_status = advancement_status
    response_data.can_advance = can_advance
    response_data.blockers = blockers

    return response_data


# ============================================================================
# T034: POST /discussions/{discussion_id}/start - Start Discussion
# ============================================================================


@router.post(
    "/{discussion_id}/start",
    response_model=DiscussionResponse,
    summary="Start discussion (begin Round 1)",
    description="Start discussion, transition CREATED → ACTIVE, open Round 1 submission window, emit discussion.started event",
)
async def start_discussion(
    discussion_id: UUID,
    db: AsyncSession = Depends(get_db),
    # TODO: Add authentication dependency to verify host
    # current_user: User = Depends(get_current_user)
) -> DiscussionResponse:
    """
    Start discussion (T034).

    Validates:
    - Discussion exists
    - Status is CREATED
    - User is the host (TODO: when auth implemented)

    Actions:
    - Transition discussion CREATED → ACTIVE
    - Open Round 1 submission window
    - Set submission_window_start, submission_window_end, approval_deadline
    - Emit discussion.started event (TODO: T037 when event bus is integrated)

    Returns:
        200: Discussion started with ACTIVE status
        400: Invalid state transition (not in CREATED status)
        403: Only host can start discussion (when auth implemented)
        404: Discussion not found
    """
    # Query discussion with relationships
    stmt = (
        select(Discussion)
        .options(
            selectinload(Discussion.rounds),
            selectinload(Discussion.participants),
        )
        .where(Discussion.discussion_id == discussion_id)
    )

    result = await db.execute(stmt)
    discussion = result.scalar_one_or_none()

    if discussion is None:
        raise DiscussionNotFoundException(discussion_id=str(discussion_id))

    # TODO: Validate user is host when auth is implemented
    # if current_user.user_id != discussion.host_user_id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Only the discussion host can start the discussion"
    #     )

    # Validate status is CREATED
    if discussion.status != DiscussionStatus.CREATED:
        raise InvalidStateTransitionException(
            entity_type="Discussion",
            entity_id=str(discussion_id),
            from_state=discussion.status.value,
            to_state="ACTIVE",
            reason="Discussion must be in CREATED status to start. Use POST /discussions/{id}/advance to continue an active discussion.",
        )

    # Validate at least one round exists
    if not discussion.rounds or len(discussion.rounds) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot start discussion without rounds. This should not happen.",
        )

    # Start the discussion (transition CREATED → ACTIVE)
    try:
        discussion.start()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Get Round 1
    round_1 = next((r for r in discussion.rounds if r.round_num == 1), None)
    if round_1 is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Round 1 not found. This should not happen.",
        )

    # Open Round 1 submission window
    try:
        round_1.open_submission_window()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to open Round 1 submission window: {str(e)}",
        )

    # Update discussion current_round_num
    discussion.current_round_num = 1

    # Save changes
    await db.commit()
    await db.refresh(discussion)

    # TODO: Emit discussion.started event via event bus (T037)
    # await event_bus.emit(
    #     "discussion.started",
    #     {
    #         "discussion_id": str(discussion.discussion_id),
    #         "round_id": str(round_1.round_id),
    #         "submission_window_end": round_1.submission_window_end.isoformat(),
    #     }
    # )

    # TODO: Schedule submission window closure via TimingService (T014)
    # await timing_service.schedule_closure(
    #     round_id=round_1.round_id,
    #     closure_time=round_1.submission_window_end,
    # )

    # Convert to response model
    return DiscussionResponse.model_validate(discussion)


# ============================================================================
# T036: GET /discussions/{discussion_id}/report - Get Discussion Report
# ============================================================================


@router.get(
    "/{discussion_id}/report",
    response_model=DiscussionReportResponse,
    summary="Get final discussion report (includes Sankey diagram)",
    description="Fetch final discussion report with Sankey diagram. Requires status=COMPLETED.",
)
async def get_discussion_report(
    discussion_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DiscussionReportResponse:
    """
    Get final discussion report with Sankey diagram (T036).

    **Requirements**:
    - Discussion must be COMPLETED
    - Returns 400 if discussion not completed

    **Response includes**:
    - Discussion metadata (total rounds, participants, duration)
    - All rounds with questions
    - Final Sankey diagram from last round
    - Participant movement summary across all rounds
    - Dropout statistics

    **Performance**:
    - Large payload for multi-round discussions
    - Future: Consider pagination for very large discussions (100+ participants, 5+ rounds)

    Args:
        discussion_id: Discussion unique identifier
        db: Database session

    Returns:
        200: Final report with Sankey diagram
        400: Discussion not yet completed
        404: Discussion not found

    Raises:
        HTTPException: 400 if not completed, 404 if not found
    """
    # Query discussion with all relationships for report generation
    stmt = (
        select(Discussion)
        .options(
            selectinload(Discussion.rounds).selectinload(Round.thought_spaces),
            selectinload(Discussion.participants),
        )
        .where(Discussion.discussion_id == discussion_id)
    )

    result = await db.execute(stmt)
    discussion = result.scalar_one_or_none()

    if discussion is None:
        raise DiscussionNotFoundException(discussion_id=str(discussion_id))

    # Validate discussion is completed
    if discussion.status != DiscussionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_state",
                "message": f"Discussion report only available for COMPLETED discussions. Current status: {discussion.status.value}",
                "details": {
                    "discussion_id": str(discussion_id),
                    "current_status": discussion.status.value,
                    "required_status": "COMPLETED",
                },
            },
        )

    # Build Sankey diagram from all rounds
    sankey_columns = []
    all_flows = []

    # Sort rounds by round_num
    sorted_rounds = sorted(discussion.rounds, key=lambda r: r.round_num)

    for round_obj in sorted_rounds:
        # Build thought spaces (clusters) for this round
        thought_spaces = []
        for cluster in round_obj.clusters:
            thought_spaces.append(
                ThoughtSpaceResponse(
                    cluster_id=cluster.cluster_id,
                    label=cluster.label_summary,
                    member_count=cluster.user_count,
                    member_pct=cluster.user_pct,
                )
            )

        # Add column for this round
        sankey_columns.append(
            SankeyColumnResponse(
                round_num=round_obj.round_num,
                thought_spaces=thought_spaces,
            )
        )

        # Fetch flows from this round's thought spaces to next round
        if round_obj.round_num < len(sorted_rounds):
            # Get all flows originating from this round's clusters
            flows_stmt = (
                select(Flow)
                .join(Cluster, Flow.source_cluster_id == Cluster.cluster_id)
                .where(Cluster.round_id == round_obj.round_id)
            )
            flows_result = await db.execute(flows_stmt)
            flows = flows_result.scalars().all()

            for flow in flows:
                all_flows.append(
                    FlowResponse(
                        flow_id=flow.flow_id,
                        source_cluster_id=flow.source_cluster_id,
                        target_cluster_id=flow.target_cluster_id,
                        participant_count=flow.participant_count,
                    )
                )

    # Build Sankey diagram
    sankey_diagram = SankeyDiagramResponse(
        columns=sankey_columns,
        flows=all_flows,
    )

    # Calculate metadata
    total_participants = len(discussion.participants)
    active_participants = sum(1 for p in discussion.participants if p.is_active())
    dropout_count = total_participants - active_participants

    # Calculate duration in minutes
    duration_minutes = 0.0
    if discussion.started_at and discussion.completed_at:
        duration_seconds = (discussion.completed_at - discussion.started_at).total_seconds()
        duration_minutes = duration_seconds / 60.0

    # Collect all questions
    questions = [r.question_text for r in sorted_rounds]

    # Build metadata
    metadata = {
        "total_rounds": len(sorted_rounds),
        "total_participants": total_participants,
        "active_participants": active_participants,
        "dropout_count": dropout_count,
        "duration_minutes": round(duration_minutes, 2),
        "questions": questions,
        "started_at": discussion.started_at.isoformat() if discussion.started_at else None,
        "completed_at": discussion.completed_at.isoformat() if discussion.completed_at else None,
    }

    # Return report
    return DiscussionReportResponse(
        discussion_id=discussion.discussion_id,
        sankey_diagram=sankey_diagram,
        metadata=metadata,
    )


# ============================================================================
# T076: GET /discussions/{discussion_id}/timing - Get Timing Metrics
# ============================================================================


@router.get(
    "/{discussion_id}/timing",
    response_model=dict,
    summary="Get discussion timing metrics",
    description="Fetch timing metrics: round durations, total elapsed time, remaining time to 60-minute target",
)
async def get_discussion_timing(
    discussion_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get discussion timing metrics (T076).

    **Returns**:
    - round_durations: Array of durations for each round (in seconds)
    - total_elapsed_time: Total time since discussion started (in seconds)
    - remaining_time: Time remaining to 60-minute target (in seconds, can be negative)
    - started_at: Discussion start timestamp
    - current_time: Current server time

    **Requirements**:
    - Discussion must be ACTIVE or COMPLETED
    - Returns 400 if discussion not yet started

    Args:
        discussion_id: Discussion unique identifier
        db: Database session

    Returns:
        200: Timing metrics
        400: Discussion not started
        404: Discussion not found

    Raises:
        HTTPException: 400 if not started, 404 if not found
    """
    # Query discussion with relationships
    stmt = (
        select(Discussion)
        .options(
            selectinload(Discussion.rounds),
        )
        .where(Discussion.discussion_id == discussion_id)
    )

    result = await db.execute(stmt)
    discussion = result.scalar_one_or_none()

    if discussion is None:
        raise DiscussionNotFoundException(discussion_id=str(discussion_id))

    # Validate discussion has been started
    if discussion.status == DiscussionStatus.CREATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_state",
                "message": "Timing metrics only available for started discussions. Current status: CREATED",
                "details": {
                    "discussion_id": str(discussion_id),
                    "current_status": "CREATED",
                },
            },
        )

    if discussion.started_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discussion has not been started yet",
        )

    # Calculate timing metrics
    now = datetime.now(timezone.utc)
    total_elapsed_seconds = (now - discussion.started_at).total_seconds()

    # Target: 60 minutes (3600 seconds)
    target_duration_seconds = 3600
    remaining_seconds = target_duration_seconds - total_elapsed_seconds

    # Calculate per-round durations
    round_durations = []
    sorted_rounds = sorted(discussion.rounds, key=lambda r: r.round_num)

    for round_obj in sorted_rounds:
        round_duration = None

        if round_obj.submission_window_start is not None:
            # Round has started
            if round_obj.completed_at is not None:
                # Round completed: measure from start to completion
                round_duration = (
                    round_obj.completed_at - round_obj.submission_window_start
                ).total_seconds()
            elif round_obj.status != RoundStatus.PENDING:
                # Round in progress: measure from start to now
                round_duration = (now - round_obj.submission_window_start).total_seconds()

        round_durations.append({
            "round_num": round_obj.round_num,
            "duration_seconds": round_duration,
            "status": round_obj.status.value,
        })

    # Return timing metrics
    return {
        "discussion_id": str(discussion_id),
        "round_durations": round_durations,
        "total_elapsed_time_seconds": total_elapsed_seconds,
        "remaining_time_seconds": remaining_seconds,
        "target_duration_seconds": target_duration_seconds,
        "started_at": discussion.started_at.isoformat(),
        "current_time": now.isoformat(),
        "status": discussion.status.value,
    }


# ============================================================================
# T054: POST /discussions/{discussion_id}/advance - Advance to Next Round
# ============================================================================


@router.post(
    "/{discussion_id}/advance",
    response_model=AdvancementResponse,
    summary="Advance discussion to next round (T058)",
    description="Host advances discussion to next round after Sankey complete and question ready",
)
async def advance_discussion(
    discussion_id: UUID,
    db: AsyncSession = Depends(get_db),
    # TODO: Add authentication dependency to verify host
    # current_user: User = Depends(get_current_user)
) -> AdvancementResponse:
    """
    Advance discussion to the next round (T054, enhanced in T058).

    Validates:
    - Discussion exists
    - Discussion is ACTIVE
    - Current round is COMPLETE (Sankey finished)
    - Next round question is ready (HOST_DEFINED: question_id set, AUTO_GENERATED: status QUESTION_READY)
    - Not already at final round
    - User is the host (TODO: when auth implemented)

    Actions:
    - Checks can_advance() on next round
    - Transitions next round to SUBMISSION_OPEN
    - Starts submission timer
    - Increments Discussion.current_round_num
    - Returns advancement details

    Returns:
        200: Discussion advanced to next round
        400: Invalid state or blocked by Sankey/question readiness
        403: Only host can advance discussion (when auth implemented)
        404: Discussion not found

    Raises:
        HTTPException: 400 if invalid state, 404 if not found
    """
    # Query discussion with relationships
    stmt = (
        select(Discussion)
        .options(
            selectinload(Discussion.rounds),
            selectinload(Discussion.participants),
        )
        .where(Discussion.discussion_id == discussion_id)
    )

    result = await db.execute(stmt)
    discussion = result.scalar_one_or_none()

    if discussion is None:
        raise DiscussionNotFoundException(discussion_id=str(discussion_id))

    # TODO: Validate user is host when auth is implemented (T061)
    # if current_user.user_id != discussion.host_user_id:
    #     raise UnauthorizedException(
    #         operation="advance_discussion",
    #         reason="Only the discussion host can advance to the next round"
    #     )

    # Validate discussion is ACTIVE
    if discussion.status != DiscussionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot advance round: discussion must be ACTIVE. Current status: {discussion.status.value}",
        )

    # Validate not at final round
    if discussion.current_round_num >= discussion.total_rounds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot advance: already at final round ({discussion.total_rounds})",
        )

    # Get current round to validate it's complete
    current_round = next(
        (r for r in discussion.rounds if r.round_num == discussion.current_round_num),
        None,
    )

    if current_round is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Current round {discussion.current_round_num} not found. This should not happen.",
        )

    # Validate current round is COMPLETE (includes Sankey completion)
    if current_round.status != RoundStatus.COMPLETE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot advance: current round must be COMPLETE. Current round status: {current_round.status.value}",
        )

    # Get next round
    next_round_num = discussion.current_round_num + 1
    next_round = next(
        (r for r in discussion.rounds if r.round_num == next_round_num),
        None,
    )

    if next_round is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Round {next_round_num} not found. This should not happen.",
        )

    # T058: Check if next round can advance (Sankey complete AND question ready)
    can_adv, reason = next_round.can_advance()
    if not can_adv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "advancement_blocked",
                "message": f"Cannot advance to Round {next_round_num}: {reason}",
                "details": {
                    "discussion_id": str(discussion_id),
                    "current_round_num": discussion.current_round_num,
                    "next_round_num": next_round_num,
                    "next_round_status": next_round.status.value,
                    "blocker": reason,
                },
            },
        )

    # Increment to next round
    discussion.current_round_num = next_round_num

    # Open next round submission window (T058: transition to SUBMISSION_OPEN, start timer)
    try:
        next_round.open_submission_window()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to open Round {next_round_num} submission window: {str(e)}",
        )

    # Save changes
    await db.commit()
    await db.refresh(discussion)
    await db.refresh(next_round)

    # TODO: Emit round.started event via event bus (T037)
    # await event_bus.emit(
    #     "round.started",
    #     {
    #         "discussion_id": str(discussion.discussion_id),
    #         "round_id": str(next_round.round_id),
    #         "round_num": next_round_num,
    #         "submission_window_end": next_round.submission_window_end.isoformat(),
    #     }
    # )

    # TODO: Schedule submission window closure via TimingService (T014)
    # await timing_service.schedule_closure(
    #     round_id=next_round.round_id,
    #     closure_time=next_round.submission_window_end,
    # )

    # Return advancement response (T058)
    return AdvancementResponse(
        discussion_id=discussion.discussion_id,
        previous_round_num=current_round.round_num,
        current_round_num=next_round.round_num,
        new_round_status=next_round.status.value,
        submission_window_end=next_round.submission_window_end,
        message=f"Successfully advanced to Round {next_round.round_num}. Submission window now open.",
    )


# ============================================================================
# T068: POST /discussions/{discussion_id}/terminate - Terminate Discussion
# ============================================================================


@router.post(
    "/{discussion_id}/terminate",
    response_model=DiscussionResponse,
    summary="Terminate discussion manually",
    description="Host terminates discussion before all rounds complete. Marks status as TERMINATED.",
)
async def terminate_discussion(
    discussion_id: UUID,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    # TODO: Add authentication dependency to verify host
    # current_user: User = Depends(get_current_user)
) -> DiscussionResponse:
    """
    Terminate discussion manually (T068).

    Validates:
    - Discussion exists
    - Discussion is ACTIVE
    - User is the host (TODO: when auth implemented)
    - No active input collection (submission window closed)

    Actions:
    - Transition discussion ACTIVE → TERMINATED
    - Set termination_timestamp and termination_reason
    - Generate final report with last completed round

    Returns:
        200: Discussion terminated successfully
        400: Invalid state (not ACTIVE) or active input collection
        403: Only host can terminate (when auth implemented)
        404: Discussion not found

    Raises:
        HTTPException: 400 if invalid state, 404 if not found
    """
    # Query discussion with relationships
    stmt = (
        select(Discussion)
        .options(
            selectinload(Discussion.rounds),
            selectinload(Discussion.participants),
        )
        .where(Discussion.discussion_id == discussion_id)
    )

    result = await db.execute(stmt)
    discussion = result.scalar_one_or_none()

    if discussion is None:
        raise DiscussionNotFoundException(discussion_id=str(discussion_id))

    # TODO: Validate user is host when auth is implemented
    # if current_user.user_id != discussion.host_user_id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Only the discussion host can terminate the discussion"
    #     )

    # Validate discussion is ACTIVE
    if discussion.status != DiscussionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot terminate discussion: must be ACTIVE. Current status: {discussion.status.value}",
        )

    # Check if there's an active submission window (T069)
    if discussion.current_round_num > 0:
        current_round = next(
            (r for r in discussion.rounds if r.round_num == discussion.current_round_num),
            None,
        )

        if current_round and current_round.status == RoundStatus.SUBMISSION_OPEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "active_input_collection",
                    "message": "Cannot terminate during active input collection. Wait for submission window to close.",
                    "details": {
                        "round_id": str(current_round.round_id),
                        "round_num": current_round.round_num,
                        "submission_window_end": current_round.submission_window_end.isoformat()
                        if current_round.submission_window_end
                        else None,
                    },
                },
            )

    # Terminate the discussion
    termination_reason = reason or "Host terminated discussion manually"

    try:
        discussion.terminate(termination_reason)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Save changes
    await db.commit()
    await db.refresh(discussion)

    # TODO: Generate final report (T071)
    # await report_service.generate_final_report(discussion_id)

    # Convert to response model
    return DiscussionResponse.model_validate(discussion)
