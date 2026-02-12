"""
Alignment API routes for cross-round cluster alignment.

Provides endpoints to trigger alignment between adjacent rounds
and retrieve alignment maps for Sankey visualization.
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from src.database import get_db
from src.services.alignment_service import (
    compute_similarity_matrix,
    greedy_matching,
    assign_display_groups,
    persist_alignment,
    update_cluster_display_groups,
    validate_alignment_invariance,
    get_cluster_member_counts,
    AlignmentServiceError,
    AlignmentResult,
)
from src.services.centroid_service import load_centroids, CentroidServiceError
from src.events.bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alignments", tags=["alignment"])


# ============================================================================
# Request/Response Models
# ============================================================================


class AlignmentRequest(BaseModel):
    """Request model for triggering cross-round alignment."""

    discussion_id: UUID = Field(..., description="Discussion to align clusters for")
    round_r: int = Field(..., ge=1, description="Earlier round number")
    round_r1: int = Field(..., ge=2, description="Later round number (must be r+1)")
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity for alignment",
    )
    force_realign: bool = Field(
        default=False,
        description="Force realignment if already computed",
    )


class AlignmentResponse(BaseModel):
    """Response model for alignment trigger."""

    job_id: UUID
    discussion_id: UUID
    round_r: int
    round_r1: int
    status: str
    estimated_completion_ms: int


class Alignment(BaseModel):
    """Single alignment mapping between clusters."""

    alignment_id: UUID
    round_r: int
    round_r1: int
    cluster_r_id: UUID
    cluster_r1_id: UUID
    similarity_score: float
    display_group_id: Optional[UUID]
    alignment_type: str


class AlignmentList(BaseModel):
    """List of alignments for a discussion."""

    discussion_id: UUID
    alignment_count: int
    alignments: list[Alignment]


# ============================================================================
# T055-T057: POST /api/v1/alignments/trigger - Trigger Cross-Round Alignment
# ============================================================================


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_alignment(
    request: AlignmentRequest,
    session: AsyncSession = Depends(get_db),
) -> AlignmentResponse:
    """
    Trigger cross-round alignment between adjacent rounds.

    Workflow:
    1. Validate rounds are adjacent (r+1)
    2. Verify both rounds are clustered
    3. Load centroids for both rounds
    4. Compute similarity matrix
    5. Perform greedy matching
    6. Assign display groups
    7. Persist alignment and update clusters
    8. Publish alignment.completed event

    Requirements:
        - T055: POST /api/v1/alignments/trigger endpoint
        - T056: Validate adjacent rounds
        - T057: Validate rounds are clustered
        - FR-029: Support alignment between adjacent rounds
        - FR-037: Alignment does NOT change membership
    """
    start_time = datetime.utcnow()

    try:
        # T056: Validate rounds are adjacent
        if request.round_r1 != request.round_r + 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "NON_ADJACENT_ROUNDS",
                    "message": f"Alignment requires adjacent rounds (r+1). "
                    f"Provided: r={request.round_r}, r+1={request.round_r1}",
                    "details": {
                        "round_r": request.round_r,
                        "round_r1": request.round_r1,
                    },
                },
            )

        # T057: Verify both rounds are clustered
        rounds_query = text("""
            SELECT r.round_id, r.round_number,
                   COUNT(DISTINCT c.cluster_id) as cluster_count
            FROM rounds r
            LEFT JOIN clusters c ON r.round_id = c.round_id
            WHERE r.discussion_id = :discussion_id
              AND r.round_number IN (:round_r, :round_r1)
            GROUP BY r.round_id, r.round_number
        """)

        result = await session.execute(
            rounds_query,
            {
                "discussion_id": str(request.discussion_id),
                "round_r": request.round_r,
                "round_r1": request.round_r1,
            },
        )

        rounds_info = {row.round_number: row for row in result}

        if request.round_r not in rounds_info or request.round_r1 not in rounds_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ROUNDS_NOT_FOUND",
                    "message": "One or both rounds not found in discussion",
                    "details": {
                        "discussion_id": str(request.discussion_id),
                        "round_r": request.round_r,
                        "round_r1": request.round_r1,
                    },
                },
            )

        round_r_info = rounds_info[request.round_r]
        round_r1_info = rounds_info[request.round_r1]

        if round_r_info.cluster_count == 0 or round_r1_info.cluster_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "ROUNDS_NOT_CLUSTERED",
                    "message": "Both rounds must be clustered before alignment.",
                    "details": {
                        "round_r_clustered": round_r_info.cluster_count > 0,
                        "round_r1_clustered": round_r1_info.cluster_count > 0,
                    },
                },
            )

        round_r_id = UUID(round_r_info.round_id)
        round_r1_id = UUID(round_r1_info.round_id)

        # Check if alignment already exists
        existing_query = text("""
            SELECT COUNT(*) as count
            FROM alignment_maps
            WHERE discussion_id = :discussion_id
              AND round_r = :round_r
              AND round_r1 = :round_r1
        """)

        existing_result = await session.execute(
            existing_query,
            {
                "discussion_id": str(request.discussion_id),
                "round_r": request.round_r,
                "round_r1": request.round_r1,
            },
        )

        existing_count = existing_result.scalar()

        if existing_count > 0 and not request.force_realign:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "ALIGNMENT_EXISTS",
                    "message": "Alignment already computed for these rounds. "
                    "Use force_realign=true to override.",
                    "details": {
                        "discussion_id": str(request.discussion_id),
                        "round_r": request.round_r,
                        "round_r1": request.round_r1,
                        "alignment_count": existing_count,
                    },
                },
            )

        # If force_realign, delete existing alignments
        if existing_count > 0 and request.force_realign:
            await session.execute(
                text("""
                    DELETE FROM alignment_maps
                    WHERE discussion_id = :discussion_id
                      AND round_r = :round_r
                      AND round_r1 = :round_r1
                """),
                {
                    "discussion_id": str(request.discussion_id),
                    "round_r": request.round_r,
                    "round_r1": request.round_r1,
                },
            )
            await session.commit()
            logger.info(f"Deleted {existing_count} existing alignments for force_realign")

        # Get member counts before alignment (for invariance validation)
        member_counts_before = await get_cluster_member_counts(
            session, [round_r_id, round_r1_id]
        )

        # Load centroids
        logger.info(
            f"Loading centroids for rounds {request.round_r} and {request.round_r1}"
        )

        centroids_map = await load_centroids(session, [round_r_id, round_r1_id])
        centroids_r = centroids_map[round_r_id]
        centroids_r1 = centroids_map[round_r1_id]

        logger.info(
            f"Loaded {len(centroids_r)} centroids for round {request.round_r}, "
            f"{len(centroids_r1)} centroids for round {request.round_r1}"
        )

        # Compute similarity matrix
        similarity_matrix = await compute_similarity_matrix(centroids_r, centroids_r1)

        # Greedy matching
        matches = await greedy_matching(
            similarity_matrix, threshold=request.similarity_threshold
        )

        # Assign display groups
        display_groups = await assign_display_groups(matches)

        # Persist alignment
        await persist_alignment(
            session,
            request.discussion_id,
            request.round_r,
            request.round_r1,
            matches,
            display_groups,
        )

        # Update cluster display groups
        await update_cluster_display_groups(session, display_groups)

        # Validate alignment invariance
        invariant_holds = await validate_alignment_invariance(
            session, [round_r_id, round_r1_id], member_counts_before
        )

        if not invariant_holds:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "ALIGNMENT_INVARIANCE_VIOLATED",
                    "message": "Alignment changed cluster membership (invariant violation)",
                },
            )

        await session.commit()

        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # T059: Publish alignment.completed event
        await event_bus.publish(
            "alignment.completed",
            {
                "discussion_id": str(request.discussion_id),
                "round_r": request.round_r,
                "round_r1": request.round_r1,
                "match_count": len(matches),
                "similarity_threshold": request.similarity_threshold,
                "processing_time_ms": processing_time_ms,
                "display_group_count": len(set(display_groups.values())),
            },
        )

        logger.info(
            f"Alignment completed: {len(matches)} matches, "
            f"{len(set(display_groups.values()))} display groups, "
            f"{processing_time_ms}ms"
        )

        # Return async job response
        job_id = UUID(int=0)  # Placeholder - could implement async jobs later
        return AlignmentResponse(
            job_id=job_id,
            discussion_id=request.discussion_id,
            round_r=request.round_r,
            round_r1=request.round_r1,
            status="COMPLETED",
            estimated_completion_ms=processing_time_ms,
        )

    except HTTPException:
        raise
    except (CentroidServiceError, AlignmentServiceError) as e:
        logger.error(f"Alignment service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ALIGNMENT_FAILED",
                "message": str(e),
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error during alignment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ALIGNMENT_FAILED",
                "message": "An unexpected error occurred during alignment",
            },
        )


# ============================================================================
# T058: GET /api/v1/alignments - Retrieve Alignment Maps
# ============================================================================


@router.get("", response_model=AlignmentList)
async def get_alignments(
    discussion_id: UUID,
    round_r: Optional[int] = None,
    session: AsyncSession = Depends(get_db),
) -> AlignmentList:
    """
    Get alignment maps for a discussion.

    Returns alignment mappings between clusters across adjacent rounds
    for use in Sankey visualization (color/label continuity).

    Requirements:
        - T058: GET /api/v1/alignments endpoint
        - FR-036: Provide alignment maps for visualization
    """
    try:
        # Build query
        query = text("""
            SELECT
                alignment_id,
                round_r,
                round_r1,
                cluster_r_id,
                cluster_r1_id,
                similarity_score,
                display_group_id
            FROM alignment_maps
            WHERE discussion_id = :discussion_id
        """ + (" AND round_r = :round_r" if round_r is not None else "") + """
            ORDER BY round_r, round_r1, similarity_score DESC
        """)

        params = {"discussion_id": str(discussion_id)}
        if round_r is not None:
            params["round_r"] = round_r

        result = await session.execute(query, params)

        # Convert to response models
        alignments = []
        for row in result:
            # Determine alignment type (1-to-1, 1-to-many, many-to-1)
            # This is a simplification - could be computed more accurately
            alignment_type = "1-to-1"  # Default

            alignments.append(
                Alignment(
                    alignment_id=UUID(row.alignment_id)
                    if isinstance(row.alignment_id, str)
                    else row.alignment_id,
                    round_r=row.round_r,
                    round_r1=row.round_r1,
                    cluster_r_id=UUID(row.cluster_r_id)
                    if isinstance(row.cluster_r_id, str)
                    else row.cluster_r_id,
                    cluster_r1_id=UUID(row.cluster_r1_id)
                    if isinstance(row.cluster_r1_id, str)
                    else row.cluster_r1_id,
                    similarity_score=float(row.similarity_score),
                    display_group_id=UUID(row.display_group_id)
                    if row.display_group_id and isinstance(row.display_group_id, str)
                    else row.display_group_id,
                    alignment_type=alignment_type,
                )
            )

        return AlignmentList(
            discussion_id=discussion_id,
            alignment_count=len(alignments),
            alignments=alignments,
        )

    except Exception as e:
        logger.error(f"Failed to retrieve alignments: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ALIGNMENT_RETRIEVAL_FAILED",
                "message": "Failed to retrieve alignment maps",
            },
        )
