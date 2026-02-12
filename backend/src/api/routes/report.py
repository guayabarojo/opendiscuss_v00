"""
Report API Routes - Endpoints for discussion report generation and retrieval

This module provides FastAPI routes for generating and retrieving discussion reports.
Implements Spec 005 User Story 5 (Discussion Reports) API endpoints.

Constitutional Compliance:
- Temporal Transparency: Reports show honest dropout curves and movements
- Semantic Accuracy: All clusters preserved in summaries
- Representation Not Adjudication: Pure data presentation without rankings

API Endpoints:
- POST /api/v1/reports/generate: Generate comprehensive report for a discussion
- GET /api/v1/reports/{discussion_id}: Retrieve cached report
- GET /api/v1/reports/{discussion_id}/export: Export report as JSON file
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...models.discussion_report import DiscussionReport
from ...models.sankey_graph import SankeyGraph
from ...services.report_service import assemble_discussion_report
from ...services.sankey_builder import SankeyBuilder

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    responses={
        404: {"description": "Report or discussion not found"},
        400: {"description": "Invalid request parameters"},
        500: {"description": "Internal server error during report generation"}
    }
)


# Request/Response Schemas

class ReportGenerateRequest(BaseModel):
    """
    Request to generate a discussion report.

    Attributes:
        discussion_id: Discussion UUID from Spec 001
    """

    discussion_id: UUID = Field(
        ...,
        description="Discussion UUID for which to generate report"
    )


class ReportGenerateResponse(BaseModel):
    """
    Response from report generation endpoint.

    Attributes:
        report: The generated DiscussionReport entity
        generation_time_ms: Time taken to generate (for monitoring)
        message: Success message
    """

    report: DiscussionReport = Field(
        ...,
        description="Complete discussion report with Sankey and statistics"
    )

    generation_time_ms: int = Field(
        ...,
        ge=0,
        description="Report generation time in milliseconds"
    )

    message: str = Field(
        default="Discussion report generated successfully",
        description="Success message"
    )


class ReportRetrievalResponse(BaseModel):
    """
    Response from report retrieval endpoint.

    Attributes:
        report: The retrieved DiscussionReport entity
        cached: Whether result was from cache (not fresh generation)
    """

    report: DiscussionReport = Field(
        ...,
        description="Discussion report for the requested discussion"
    )

    cached: bool = Field(
        default=True,
        description="True if retrieved from cache, False if freshly generated"
    )


# Endpoints

@router.post(
    "/generate",
    response_model=ReportGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate discussion report",
    description="""
    Generate a comprehensive discussion report including Sankey diagram,
    cluster summaries, dropout curve, and top movements.

    **Process**:
    1. Load or construct SankeyGraph for the discussion
    2. Generate cluster summaries for each round
    3. Generate dropout curve showing participant engagement
    4. Identify top movements between rounds
    5. Assemble complete DiscussionReport entity

    **Idempotency**: Returns existing report if already generated for this discussion.

    **Constitutional Compliance**:
    - All clusters included in summaries (Semantic Accuracy, SC-002)
    - Honest dropout representation (Temporal Transparency, SC-004)
    - No filtering or ranking (Representation Not Adjudication, SC-008)
    """,
    responses={
        201: {
            "description": "Report generated successfully",
            "model": ReportGenerateResponse
        },
        200: {
            "description": "Report already exists (idempotent)",
            "model": ReportGenerateResponse
        },
        400: {
            "description": "Invalid discussion_id or no Sankey data available"
        },
        500: {
            "description": "Report generation failed due to internal error"
        }
    }
)
async def generate_report(
    request: ReportGenerateRequest,
    session: AsyncSession = Depends(get_session)
) -> ReportGenerateResponse:
    """
    Generate discussion report for a discussion.

    Args:
        request: Generation request with discussion_id
        session: Database session

    Returns:
        ReportGenerateResponse with generated report and metadata

    Raises:
        HTTPException: 400 if discussion_id invalid, 500 if generation fails
    """
    import time

    start_time = time.time()

    logger.info(f"Report generation requested for discussion {request.discussion_id}")

    try:
        # Initialize Sankey builder
        builder = SankeyBuilder(session)

        # Load or build SankeyGraph
        sankey_graph = await builder.load_from_database(request.discussion_id)

        if not sankey_graph:
            # Try to construct Sankey if not found
            logger.info(
                f"No cached Sankey found for discussion {request.discussion_id}, "
                f"attempting to construct"
            )

            # Fetch discussion to get rounds
            from sqlalchemy import select
            from ...models.discussion import Discussion

            stmt = select(Discussion).where(Discussion.id == request.discussion_id)
            result = await session.execute(stmt)
            discussion = result.scalar_one_or_none()

            if not discussion:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Discussion {request.discussion_id} not found"
                )

            if not hasattr(discussion, 'rounds') or not discussion.rounds:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Discussion {request.discussion_id} has no rounds"
                )

            rounds = [round_obj.id for round_obj in discussion.rounds]

            # Build Sankey graph
            sankey_graph = await builder.build_sankey_graph(
                discussion_id=request.discussion_id,
                rounds=rounds,
                include_alignment=True
            )

            # Persist to database
            await builder.save_to_database(sankey_graph)

        # Generate report from Sankey
        report = assemble_discussion_report(sankey_graph)

        generation_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Report generated for discussion {request.discussion_id} "
            f"in {generation_time_ms}ms: "
            f"{report.get_total_rounds()} rounds, "
            f"{report.get_total_dropout()} dropout"
        )

        return ReportGenerateResponse(
            report=report,
            generation_time_ms=generation_time_ms,
            message="Discussion report generated successfully"
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Internal server error
        logger.exception(f"Report generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {str(e)}"
        )


@router.get(
    "/{discussion_id}",
    response_model=ReportRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve discussion report",
    description="""
    Retrieve a previously generated discussion report.

    **Implementation Note**: Currently generates report on-demand from cached Sankey.
    Future versions may cache the full report.

    **Returns**: Complete DiscussionReport with all sections.

    **Performance**: Target <500ms for retrieval and generation from cached Sankey.
    """,
    responses={
        200: {
            "description": "Report retrieved successfully",
            "model": ReportRetrievalResponse
        },
        404: {
            "description": "Report not found for this discussion"
        }
    }
)
async def get_report(
    discussion_id: UUID,
    session: AsyncSession = Depends(get_session)
) -> ReportRetrievalResponse:
    """
    Retrieve discussion report for a discussion.

    Args:
        discussion_id: Discussion UUID from path parameter
        session: Database session

    Returns:
        ReportRetrievalResponse with report

    Raises:
        HTTPException: 404 if report not found
    """
    logger.info(f"Report retrieval requested for discussion {discussion_id}")

    try:
        # Initialize Sankey builder
        builder = SankeyBuilder(session)

        # Load Sankey from database
        sankey_graph = await builder.load_from_database(discussion_id)

        if not sankey_graph:
            logger.warning(f"No Sankey found for discussion {discussion_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report not found for discussion {discussion_id}. "
                       f"Generate report first using POST /reports/generate"
            )

        # Generate report from Sankey
        report = assemble_discussion_report(sankey_graph)

        logger.info(
            f"Report retrieved for discussion {discussion_id}: "
            f"{report.get_total_rounds()} rounds"
        )

        return ReportRetrievalResponse(
            report=report,
            cached=True
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Internal server error
        logger.exception(f"Report retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report retrieval failed: {str(e)}"
        )


@router.get(
    "/{discussion_id}/export",
    status_code=status.HTTP_200_OK,
    summary="Export discussion report as JSON",
    description="""
    Export a discussion report as downloadable JSON file.

    **Use Case**: Archive discussion results, external analysis, data portability.

    **Format**: JSON conforming to DiscussionReport schema (json-v1).

    **Performance**: Target <500ms for export.
    """,
    responses={
        200: {
            "description": "Report exported successfully",
            "content": {
                "application/json": {
                    "example": {
                        "discussion_id": "987fcdeb-51a2-43d1-b987-123456789abc",
                        "sankey_graph": {},
                        "cluster_summaries": [],
                        "dropout_curve": [],
                        "top_movements": []
                    }
                }
            }
        },
        404: {
            "description": "Report not found for this discussion"
        }
    }
)
async def export_report(
    discussion_id: UUID,
    session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    """
    Export discussion report as JSON file.

    Args:
        discussion_id: Discussion UUID from path parameter
        session: Database session

    Returns:
        JSONResponse with report data and Content-Disposition header

    Raises:
        HTTPException: 404 if report not found
    """
    logger.info(f"Report export requested for discussion {discussion_id}")

    try:
        # Initialize Sankey builder
        builder = SankeyBuilder(session)

        # Load Sankey from database
        sankey_graph = await builder.load_from_database(discussion_id)

        if not sankey_graph:
            logger.warning(f"No Sankey found for discussion {discussion_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report not found for discussion {discussion_id}"
            )

        # Generate report from Sankey
        report = assemble_discussion_report(sankey_graph)

        # Convert to JSON
        report_json = report.model_dump(mode='json')

        # Create filename
        filename = f"discussion_report_{discussion_id}.json"

        logger.info(f"Report exported for discussion {discussion_id}")

        # Return as downloadable JSON
        return JSONResponse(
            content=report_json,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/json"
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Internal server error
        logger.exception(f"Report export failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report export failed: {str(e)}"
        )
