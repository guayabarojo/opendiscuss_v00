"""
Participant API routes for OpenDiscuss Discussion Protocol.

Implements participant-related endpoints:
- GET /discussions/{id}/participants - List participants with dropout status
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models.discussion import Discussion
from ..models.participant import Participant
from .error_handlers import DiscussionNotFoundException
from .schemas import ParticipantResponse, ParticipantListResponse

# Create router
router = APIRouter(prefix="/discussions", tags=["participants"])


# ============================================================================
# T055: GET /discussions/{discussion_id}/participants - List Participants
# ============================================================================


@router.get(
    "/{discussion_id}/participants",
    response_model=ParticipantListResponse,
    summary="List discussion participants",
    description="Get all participants for a discussion with dropout status and filter options",
)
async def get_discussion_participants(
    discussion_id: UUID,
    include_dropouts: bool = Query(
        default=True,
        description="Include participants who have dropped out (default: true)",
    ),
    db: AsyncSession = Depends(get_db),
) -> ParticipantListResponse:
    """
    List all participants for a discussion (T055).

    Returns participant information including:
    - participant_id (discussion-scoped identity)
    - user_id (user account identity)
    - first_round (round they joined)
    - last_round (round they dropped out, NULL if still active)
    - dropout_reason (reason for dropout, NULL if still active)
    - is_active (derived from last_round == NULL)

    Query Parameters:
    - include_dropouts: Whether to include participants who have dropped out (default: true)

    Returns:
        200: List of participants with metadata
        404: Discussion not found

    Response includes:
    - participants: Array of ParticipantResponse
    - total: Total number of participants (respecting include_dropouts filter)
    - active_count: Number of currently active participants
    - dropout_count: Number of participants who have dropped out
    """
    # Verify discussion exists
    discussion_stmt = select(Discussion).where(
        Discussion.discussion_id == discussion_id
    )
    discussion_result = await db.execute(discussion_stmt)
    discussion = discussion_result.scalar_one_or_none()

    if discussion is None:
        raise DiscussionNotFoundException(discussion_id=str(discussion_id))

    # Query participants
    stmt = (
        select(Participant)
        .where(Participant.discussion_id == discussion_id)
        .order_by(Participant.first_round.asc())
    )

    # Filter by dropout status if requested
    if not include_dropouts:
        stmt = stmt.where(Participant.last_round.is_(None))

    result = await db.execute(stmt)
    participants = result.scalars().all()

    # Calculate statistics
    all_participants_stmt = select(Participant).where(
        Participant.discussion_id == discussion_id
    )
    all_participants_result = await db.execute(all_participants_stmt)
    all_participants = list(all_participants_result.scalars().all())

    active_count = sum(1 for p in all_participants if p.is_active())
    dropout_count = len(all_participants) - active_count

    # Build response
    participant_responses = []
    for participant in participants:
        participant_responses.append(
            ParticipantResponse(
                participant_id=participant.participant_id,
                discussion_id=participant.discussion_id,
                user_id=participant.user_id,
                first_round=participant.first_round,
                last_round=participant.last_round,
                dropout_reason=participant.dropout_reason.value
                if participant.dropout_reason
                else None,
                is_active=participant.is_active(),
                created_at=participant.created_at,
            )
        )

    return ParticipantListResponse(
        participants=participant_responses,
        total=len(participant_responses),
        active_count=active_count,
        dropout_count=dropout_count,
    )
