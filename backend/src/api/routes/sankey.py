"""
Sankey API Routes - Endpoints for Sankey diagram construction and retrieval

This module provides FastAPI routes for constructing and retrieving Sankey diagrams.
Implements Spec 005 (Sankey Construction) API endpoints per contracts/api-spec.yaml.

Constitutional Compliance:
- Temporal Transparency: Sankey shows honest participant movement across rounds
- Semantic Accuracy: All clusters preserved as nodes (100% coverage)
- Representation Not Adjudication: Pure visualization without rankings

API Endpoints:
- POST /api/v1/sankey/construct: Trigger Sankey construction for a discussion
- GET /api/v1/sankey/{discussion_id}: Retrieve constructed Sankey diagram
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db as get_session
from ...models.sankey_graph import SankeyGraph
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sankey",
    tags=["sankey"],
    responses={
        404: {"description": "Sankey diagram not found"},
        400: {"description": "Invalid request parameters"},
        500: {"description": "Internal server error during construction"}
    }
)


# Request/Response Schemas

class SankeyConstructRequest(BaseModel):
    """
    Request to construct a Sankey diagram for a discussion.

    Attributes:
        discussion_id: Discussion UUID from Spec 001
        include_alignment: Whether to include alignment metadata (optional, default True)
    """

    discussion_id: UUID = Field(
        ...,
        description="Discussion UUID for which to construct Sankey diagram"
    )

    include_alignment: bool = Field(
        default=True,
        description="Include alignment metadata for visual continuity (optional)"
    )


class SankeyConstructResponse(BaseModel):
    """
    Response from Sankey construction endpoint.

    Attributes:
        sankey_graph: The constructed SankeyGraph entity
        construction_time_ms: Time taken to construct (for monitoring)
        message: Success message
    """

    sankey_graph: SankeyGraph = Field(
        ...,
        description="Constructed Sankey diagram with columns, nodes, and edges"
    )

    construction_time_ms: int = Field(
        ...,
        ge=0,
        description="Construction time in milliseconds"
    )

    message: str = Field(
        default="Sankey diagram constructed successfully",
        description="Success message"
    )


class SankeyRetrievalResponse(BaseModel):
    """
    Response from Sankey retrieval endpoint.

    Attributes:
        sankey_graph: The retrieved SankeyGraph entity
        cached: Whether result was from cache (not fresh construction)
        round_questions: Mapping of round_id to question_text for visualization
    """

    sankey_graph: SankeyGraph = Field(
        ...,
        description="Sankey diagram for the requested discussion"
    )

    cached: bool = Field(
        default=True,
        description="True if retrieved from database, False if freshly constructed"
    )

    round_questions: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of round_id (UUID string) to question_text for each round"
    )


# Endpoints

@router.post(
    "/construct",
    response_model=SankeyConstructResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Construct Sankey diagram for a discussion",
    description="""
    Trigger construction of a Sankey diagram for a discussion.

    **Process**:
    1. Fetch cluster data from Spec 004 for all rounds
    2. Build nodes (thought spaces) with participant counts
    3. Compute edges based on actual participant movement
    4. Validate all invariants (percentage sums, coverage, edge totals)
    5. Persist to database as JSONB

    **Idempotency**: Returns existing Sankey if already constructed for this discussion.

    **Performance**: Target <3s for 100 participants across 5 rounds (SC-001).

    **Constitutional Compliance**:
    - All clusters preserved as nodes (Semantic Accuracy, SC-003)
    - Edges computed from actual movement (Temporal Transparency, SC-002)
    - No synthetic "dropout" nodes (Representation Not Adjudication, SC-011)
    """,
    responses={
        201: {
            "description": "Sankey diagram constructed successfully",
            "model": SankeyConstructResponse
        },
        200: {
            "description": "Sankey diagram already exists (idempotent)",
            "model": SankeyConstructResponse
        },
        400: {
            "description": "Invalid discussion_id or no cluster data available"
        },
        500: {
            "description": "Construction failed due to internal error"
        }
    }
)
async def construct_sankey(
    request: SankeyConstructRequest,
    session: AsyncSession = Depends(get_session)
) -> SankeyConstructResponse:
    """
    Construct Sankey diagram for a discussion.

    Args:
        request: Construction request with discussion_id
        session: Database session

    Returns:
        SankeyConstructResponse with constructed diagram and metadata

    Raises:
        HTTPException: 400 if discussion_id invalid, 500 if construction fails
    """
    import time
    from ...services.sankey_builder import SankeyBuilder
    from ...models.discussion import Discussion

    start_time = time.time()

    logger.info(
        f"Sankey construction requested for discussion {request.discussion_id}, "
        f"include_alignment={request.include_alignment}"
    )

    try:
        # Initialize builder
        builder = SankeyBuilder(session)

        # Check idempotency: Return existing if already constructed
        existing = await builder.load_from_database(request.discussion_id)
        if existing:
            construction_time_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Returning existing Sankey for discussion {request.discussion_id} "
                f"(idempotent, retrieved in {construction_time_ms}ms)"
            )
            return SankeyConstructResponse(
                sankey_graph=existing,
                construction_time_ms=construction_time_ms,
                message="Sankey diagram already exists (retrieved from cache)"
            )

        # Fetch discussion to get rounds
        from sqlalchemy import select
        stmt = select(Discussion).where(Discussion.discussion_id == request.discussion_id)
        result = await session.execute(stmt)
        discussion = result.scalar_one_or_none()

        if not discussion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Discussion {request.discussion_id} not found"
            )

        # Get rounds for this discussion (assumes Discussion has rounds relationship)
        # Note: This needs to be adjusted based on actual Discussion model structure
        if not hasattr(discussion, 'rounds') or not discussion.rounds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Discussion {request.discussion_id} has no rounds"
            )

        rounds = [round.round_id for round in discussion.rounds]

        # Build Sankey graph
        sankey_graph = await builder.build_sankey_graph(
            discussion_id=request.discussion_id,
            rounds=rounds,
            include_alignment=request.include_alignment
        )

        # Persist to database
        await builder.save_to_database(sankey_graph)

        construction_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Sankey construction completed for discussion {request.discussion_id} "
            f"in {construction_time_ms}ms"
        )

        return SankeyConstructResponse(
            sankey_graph=sankey_graph,
            construction_time_ms=construction_time_ms,
            message="Sankey diagram constructed successfully"
        )

    except ValueError as e:
        # Validation or business logic error
        logger.error(f"Sankey construction validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Internal server error
        logger.exception(f"Sankey construction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sankey construction failed: {str(e)}"
        )


@router.get(
    "/{discussion_id}",
    response_model=SankeyRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Sankey diagram for a discussion",
    description="""
    Retrieve a previously constructed Sankey diagram from the database.

    **Query Parameters**: None (uses path parameter only)

    **Returns**: Complete SankeyGraph with columns, nodes, edges, and metadata.

    **Caching**: Results are persisted in database as JSONB. No TTL - diagrams
    are immutable once discussion is complete.

    **Performance**: Target <100ms for retrieval (database query only).
    """,
    responses={
        200: {
            "description": "Sankey diagram retrieved successfully",
            "model": SankeyRetrievalResponse
        },
        404: {
            "description": "Sankey diagram not found for this discussion"
        }
    }
)
async def get_sankey(
    discussion_id: UUID,
    session: AsyncSession = Depends(get_session)
) -> SankeyRetrievalResponse:
    """
    Retrieve Sankey diagram for a discussion.

    Args:
        discussion_id: Discussion UUID from path parameter
        session: Database session

    Returns:
        SankeyRetrievalResponse with cached diagram and round questions

    Raises:
        HTTPException: 404 if diagram not found
    """
    from ...services.sankey_builder import SankeyBuilder
    from ...models.round import Round
    from sqlalchemy import select

    logger.info(f"Sankey retrieval requested for discussion {discussion_id}")

    try:
        # Initialize builder
        builder = SankeyBuilder(session)

        # Load from database
        sankey_graph = await builder.load_from_database(discussion_id)

        if not sankey_graph:
            logger.warning(f"Sankey not found for discussion {discussion_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sankey diagram not found for discussion {discussion_id}"
            )

        # Fetch round questions for the discussion
        rounds_query = select(Round).where(Round.discussion_id == discussion_id).order_by(Round.round_num)
        rounds_result = await session.execute(rounds_query)
        rounds = rounds_result.scalars().all()

        # Build round_questions dictionary: round_id -> question_text
        round_questions = {str(r.round_id): r.question_text for r in rounds}

        # Add cluster size metadata to support frontend filtering
        cluster_sizes = {}
        for column in sankey_graph.columns:
            for node in column.nodes:
                cluster_sizes[node.cluster_id] = node.user_count

        # Calculate cluster size distribution
        if cluster_sizes:
            sorted_sizes = sorted(cluster_sizes.values())
            total_participants = sum(cluster_sizes.values()) / len(sankey_graph.columns) if cluster_sizes else 0

            # Initialize metadata if not present
            if not sankey_graph.metadata:
                sankey_graph.metadata = {}

            sankey_graph.metadata['cluster_size_distribution'] = {
                'min': min(sorted_sizes),
                'max': max(sorted_sizes),
                'median': sorted_sizes[len(sorted_sizes) // 2],
                'total_clusters': len(cluster_sizes)
            }

            # Add suggested thresholds for UI slider
            sankey_graph.metadata['cluster_granularity_suggestions'] = {
                'high_detail': 2,  # Show all clusters (current)
                'medium_detail': max(2, int(total_participants * 0.05)),  # 5% of participants
                'low_detail': max(5, int(total_participants * 0.10)),  # 10% of participants
            }

        logger.info(
            f"Sankey retrieved for discussion {discussion_id}: "
            f"{len(sankey_graph.columns)} columns, {len(sankey_graph.edges)} edges, "
            f"{len(round_questions)} round questions"
        )

        return SankeyRetrievalResponse(
            sankey_graph=sankey_graph,
            cached=True,
            round_questions=round_questions
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Internal server error
        logger.exception(f"Sankey retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sankey retrieval failed: {str(e)}"
        )


@router.delete(
    "/{discussion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Sankey diagram (admin only)",
    description="""
    Delete a Sankey diagram from the database.

    **Use Case**: Recompute Sankey after fixing cluster data or alignment.

    **Authorization**: Admin only (not implemented yet).

    **Idempotency**: Returns 204 even if diagram doesn't exist.
    """,
    responses={
        204: {
            "description": "Sankey diagram deleted successfully"
        }
    }
)
async def delete_sankey(
    discussion_id: UUID,
    session: AsyncSession = Depends(get_session)
) -> None:
    """
    Delete Sankey diagram for a discussion.

    Args:
        discussion_id: Discussion UUID from path parameter
        session: Database session

    Returns:
        None (204 No Content)
    """
    # This endpoint is optional - not part of core MVP
    logger.warning(
        f"delete_sankey endpoint called but not yet implemented: {discussion_id}"
    )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Sankey deletion not yet implemented (optional feature)"
    )
