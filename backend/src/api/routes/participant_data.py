"""
Participant Data API Routes - Endpoints for fetching participant submission data

This module provides FastAPI routes for retrieving participant data including
raw submissions, summaries, and cluster assignments for a discussion.

Used for debugging, transparency, and detailed data inspection in the UI.
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...database import get_db as get_session
from ...models.submission import Submission
from ...models.approved_summary import ApprovedSummary
from ...models.thought_space import ThoughtSpace
from ...models.round import Round
from ...models.participant import Participant
from ...summarization.models.summary import Summary
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/participant-data",
    tags=["participant-data"],
    responses={
        404: {"description": "Discussion or data not found"},
        400: {"description": "Invalid request parameters"},
    }
)


# Response Schemas

class ParticipantDataRow(BaseModel):
    """
    Single row of participant data for a specific round.

    Attributes:
        round_num: Round number (1-indexed)
        round_id: Round UUID
        participant_id: Participant UUID
        submission_id: Submission UUID (may be None if deleted)
        raw_input: Raw submission text (may be truncated or None if deleted)
        summary: Approved summary text
        cluster_id: Cluster UUID assignment
        cluster_label: Cluster label (medoid text)
        cluster_size: Number of participants in cluster
    """
    round_num: int = Field(..., description="Round number (1-indexed)")
    round_id: str = Field(..., description="Round UUID")
    participant_id: str = Field(..., description="Participant UUID")
    submission_id: Optional[str] = Field(None, description="Submission UUID (may be None if deleted)")
    raw_input: Optional[str] = Field(None, description="Raw submission text (may be None if ephemeral deletion)")
    summary: str = Field(..., description="Approved summary text")
    cluster_id: str = Field(..., description="Cluster UUID")
    cluster_label: str = Field(..., description="Cluster label (medoid summary)")
    cluster_size: int = Field(..., description="Number of participants in cluster")

    class Config:
        from_attributes = True


class ParticipantDataResponse(BaseModel):
    """
    Response containing participant data for a discussion.

    Attributes:
        data: List of participant data rows
        total: Total number of rows (for pagination)
        discussion_id: Discussion UUID
        rounds: Total number of rounds in discussion
    """
    data: List[ParticipantDataRow] = Field(
        ...,
        description="List of participant data rows"
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of rows available (for pagination)"
    )
    discussion_id: str = Field(
        ...,
        description="Discussion UUID"
    )
    rounds: int = Field(
        ...,
        ge=0,
        description="Total number of rounds in discussion"
    )


# Endpoints

@router.get(
    "/{discussion_id}",
    response_model=ParticipantDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve participant data for a discussion",
    description="""
    Retrieve participant submission data for a discussion including:
    - Raw submission text (if not yet deleted)
    - Approved summary
    - Cluster assignment and label

    **Query Parameters**:
    - round_num: Filter by specific round number (optional)
    - search: Search in raw input, summary, or cluster label (optional)
    - limit: Number of rows per page (default 20, max 100)
    - offset: Pagination offset (default 0)

    **Performance**: Uses efficient joins and indexed queries.

    **Privacy Note**: Returns participant_id (not user_id) to preserve privacy.
    """
)
async def get_participant_data(
    discussion_id: UUID,
    round_num: Optional[int] = Query(None, description="Filter by round number", ge=1),
    search: Optional[str] = Query(None, description="Search in raw input, summary, or cluster label"),
    limit: int = Query(20, description="Number of rows per page", ge=1, le=100),
    offset: int = Query(0, description="Pagination offset", ge=0),
    session: AsyncSession = Depends(get_session)
) -> ParticipantDataResponse:
    """
    Retrieve participant data for a discussion.

    Args:
        discussion_id: Discussion UUID from path parameter
        round_num: Optional round number filter
        search: Optional search query
        limit: Number of rows per page
        offset: Pagination offset
        session: Database session

    Returns:
        ParticipantDataResponse with participant data rows and metadata

    Raises:
        HTTPException: 404 if discussion not found
    """
    from ...models.discussion import Discussion

    logger.info(
        f"Participant data requested for discussion {discussion_id}, "
        f"round_num={round_num}, search={search}, limit={limit}, offset={offset}"
    )

    try:
        # Verify discussion exists and get round count
        discussion_query = select(Discussion).where(Discussion.discussion_id == discussion_id)
        discussion_result = await session.execute(discussion_query)
        discussion = discussion_result.scalar_one_or_none()

        if not discussion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Discussion {discussion_id} not found"
            )

        # Get total rounds for this discussion
        rounds_count_query = select(func.count(Round.round_id)).where(
            Round.discussion_id == discussion_id
        )
        rounds_count_result = await session.execute(rounds_count_query)
        total_rounds = rounds_count_result.scalar() or 0

        # Build base query joining all necessary tables
        # We query from ApprovedSummary as the anchor since it's persisted
        base_query = (
            select(
                Round.round_num,
                Round.round_id,
                ApprovedSummary.participant_id,
                ApprovedSummary.submission_id,
                ApprovedSummary.summary_text,
                ApprovedSummary.cluster_id,
                ThoughtSpace.label_summary,
                ThoughtSpace.member_count,
                Submission.submission_text,
            )
            .select_from(ApprovedSummary)
            .join(Round, ApprovedSummary.round_id == Round.round_id)
            .join(ThoughtSpace, ApprovedSummary.cluster_id == ThoughtSpace.cluster_id)
            .outerjoin(Submission, ApprovedSummary.submission_id == Submission.submission_id)
            .where(Round.discussion_id == discussion_id)
        )

        # Apply round filter if specified
        if round_num is not None:
            base_query = base_query.where(Round.round_num == round_num)

        # Apply search filter if specified
        if search and len(search.strip()) > 0:
            search_term = f"%{search.strip()}%"
            base_query = base_query.where(
                (ApprovedSummary.summary_text.ilike(search_term)) |
                (ThoughtSpace.label_summary.ilike(search_term)) |
                (Submission.submission_text.ilike(search_term))
            )

        # Get total count for pagination
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await session.execute(count_query)
        total_count = count_result.scalar() or 0

        # Apply ordering and pagination
        final_query = (
            base_query
            .order_by(Round.round_num.asc(), ApprovedSummary.participant_id.asc())
            .limit(limit)
            .offset(offset)
        )

        # Execute query
        result = await session.execute(final_query)
        rows = result.all()

        # Build response data
        data_rows = []
        for row in rows:
            data_rows.append(
                ParticipantDataRow(
                    round_num=row.round_num,
                    round_id=str(row.round_id),
                    participant_id=str(row.participant_id),
                    submission_id=str(row.submission_id) if row.submission_id else None,
                    raw_input=row.submission_text if row.submission_text else None,
                    summary=row.summary_text,
                    cluster_id=str(row.cluster_id),
                    cluster_label=row.label_summary,
                    cluster_size=row.member_count,
                )
            )

        logger.info(
            f"Retrieved {len(data_rows)} participant data rows for discussion {discussion_id} "
            f"(total: {total_count}, rounds: {total_rounds})"
        )

        return ParticipantDataResponse(
            data=data_rows,
            total=total_count,
            discussion_id=str(discussion_id),
            rounds=total_rounds,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve participant data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve participant data: {str(e)}"
        )
