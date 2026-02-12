"""
Summary API routes for Spec 003.

Endpoints:
- POST /summaries/generate - Generate summary from submission (T022)
- POST /summaries/{summary_id}/approve - Approve summary (T023)
- GET /summaries/{summary_id} - Get summary details (T024)
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...logging_config import logger
from ..models.summary import SummaryStatus
from ..services.summarization_service import SummarizationService
from ..services.approval_service import ApprovalService
from ..services.regeneration_service import RegenerationService


# Router
router = APIRouter(prefix="/summaries", tags=["summaries"])


# Request/Response Models
class GenerateSummaryRequest(BaseModel):
    """Request to generate summary from submission."""

    submission_id: UUID = Field(
        ...,
        description="UUID of submission to summarize"
    )
    use_fallback_model: bool = Field(
        default=False,
        description="If True, use GPT-3.5 instead of GPT-4-turbo"
    )


class SummaryResponse(BaseModel):
    """Summary response model."""

    summary_id: UUID
    submission_id: UUID
    participant_id: UUID
    round_id: UUID
    summary_text: str
    status: str  # Enum value as string
    regen_count: int
    safety_flags: Optional[List[str]] = None
    created_at: str  # ISO 8601 timestamp
    approved_at: Optional[str] = None  # ISO 8601 timestamp

    model_config = {"from_attributes": True}


class ApprovalResponse(BaseModel):
    """Response for approval/rejection actions."""

    summary_id: UUID
    status: str
    message: str
    approved_at: Optional[str] = None


class RejectResponse(BaseModel):
    """Response for rejection with automatic regeneration."""

    rejected_summary_id: UUID
    rejected_status: str
    new_summary: Optional[SummaryResponse] = None
    message: str
    needs_correction_signal: bool = False


# Endpoints

@router.post("/generate", response_model=SummaryResponse, status_code=status.HTTP_201_CREATED)
async def generate_summary(
    request: GenerateSummaryRequest,
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    """
    Generate summary from submission (Task T022).

    Creates initial summary with status=PENDING_REVIEW.

    Args:
        request: Generation request with submission_id
        db: Database session

    Returns:
        SummaryResponse: Created summary

    Raises:
        404: Submission not found
        422: Invalid submission (no text content)
        500: LLM generation failed
    """
    try:
        service = SummarizationService(db)
        summary = await service.generate_summary(
            submission_id=request.submission_id,
            use_fallback_model=request.use_fallback_model,
        )

        return SummaryResponse(
            summary_id=summary.summary_id,
            submission_id=summary.submission_id,
            participant_id=summary.participant_id,
            round_id=summary.round_id,
            summary_text=summary.summary_text,
            status=summary.status.value,
            regen_count=summary.regen_count,
            safety_flags=summary.safety_flags,
            created_at=summary.created_at.isoformat(),
            approved_at=summary.approved_at.isoformat() if summary.approved_at else None,
        )

    except ValueError as e:
        logger.error(f"Validation error generating summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate summary"
        )


@router.post("/{summary_id}/approve", response_model=ApprovalResponse)
async def approve_summary(
    summary_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    """
    Approve a summary (Task T023).

    Transitions status from PENDING_REVIEW to APPROVED.
    Sets approved_at timestamp.

    Args:
        summary_id: UUID of summary to approve
        db: Database session

    Returns:
        ApprovalResponse: Updated summary status

    Raises:
        404: Summary not found
        422: Invalid state transition (not PENDING_REVIEW)
        500: Database error
    """
    try:
        service = ApprovalService(db)
        summary = await service.approve_summary(summary_id)

        return ApprovalResponse(
            summary_id=summary.summary_id,
            status=summary.status.value,
            message="Summary approved successfully",
            approved_at=summary.approved_at.isoformat() if summary.approved_at else None,
        )

    except ValueError as e:
        logger.error(f"Validation error approving summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error approving summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve summary"
        )


@router.post("/{summary_id}/reject", response_model=RejectResponse)
async def reject_summary(
    summary_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RejectResponse:
    """
    Reject a summary and automatically regenerate (User Story 2, Task T040).

    Workflow:
    1. Reject the current summary (status → REJECTED)
    2. Check if automatic regeneration is allowed (regen_count < 2)
    3. If allowed: Generate new summary and return it
    4. If not allowed: Return message to prompt for correction signal (User Story 3)

    FSM Transitions:
    - Current summary: PENDING_REVIEW → REJECTED
    - New summary (if regen_count < 2): Created with status=PENDING_REVIEW, regen_count++
    - If regen_count >= 2: No new summary, needs_correction_signal=True

    Args:
        summary_id: UUID of summary to reject
        db: Database session

    Returns:
        RejectResponse: Rejected summary info + new summary (if auto-regen allowed)

    Raises:
        404: Summary not found
        422: Invalid state transition (not PENDING_REVIEW)
        500: Database error or LLM failure
    """
    try:
        # Step 1: Reject the current summary
        approval_service = ApprovalService(db)
        rejected_summary = await approval_service.reject_summary(summary_id)

        # Step 2: Check if automatic regeneration is allowed
        regen_service = RegenerationService(db)
        can_auto_regen = await regen_service.can_auto_regenerate(summary_id)

        if can_auto_regen:
            # Step 3a: Automatic regeneration (regen_count < 2)
            new_summary = await regen_service.regenerate_with_bounded_retry(
                rejected_summary_id=summary_id,
                use_fallback_model=False,
            )

            if new_summary:
                return RejectResponse(
                    rejected_summary_id=rejected_summary.summary_id,
                    rejected_status=rejected_summary.status.value,
                    new_summary=SummaryResponse(
                        summary_id=new_summary.summary_id,
                        submission_id=new_summary.submission_id,
                        participant_id=new_summary.participant_id,
                        round_id=new_summary.round_id,
                        summary_text=new_summary.summary_text,
                        status=new_summary.status.value,
                        regen_count=new_summary.regen_count,
                        safety_flags=new_summary.safety_flags,
                        created_at=new_summary.created_at.isoformat(),
                        approved_at=None,
                    ),
                    message=f"Summary rejected. New summary generated (Attempt {new_summary.regen_count + 1}/3).",
                    needs_correction_signal=False,
                )
            else:
                # Should not happen, but defensive
                return RejectResponse(
                    rejected_summary_id=rejected_summary.summary_id,
                    rejected_status=rejected_summary.status.value,
                    new_summary=None,
                    message="Summary rejected, but regeneration failed. Please provide correction signal.",
                    needs_correction_signal=True,
                )
        else:
            # Step 3b: Max auto-regenerations reached (regen_count >= 2)
            return RejectResponse(
                rejected_summary_id=rejected_summary.summary_id,
                rejected_status=rejected_summary.status.value,
                new_summary=None,
                message=f"Summary rejected (Attempt {rejected_summary.regen_count + 1}/3). Please provide correction signal to regenerate once more.",
                needs_correction_signal=True,
            )

    except ValueError as e:
        logger.error(f"Validation error rejecting summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error rejecting summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject summary"
        )


@router.get("/{summary_id}", response_model=SummaryResponse)
async def get_summary(
    summary_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    """
    Get summary details (Task T024).

    Args:
        summary_id: UUID of summary to retrieve
        db: Database session

    Returns:
        SummaryResponse: Summary details

    Raises:
        404: Summary not found
        500: Database error
    """
    try:
        service = SummarizationService(db)
        summary = await service.get_summary(summary_id)

        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Summary {summary_id} not found"
            )

        return SummaryResponse(
            summary_id=summary.summary_id,
            submission_id=summary.submission_id,
            participant_id=summary.participant_id,
            round_id=summary.round_id,
            summary_text=summary.summary_text,
            status=summary.status.value,
            regen_count=summary.regen_count,
            safety_flags=summary.safety_flags,
            created_at=summary.created_at.isoformat(),
            approved_at=summary.approved_at.isoformat() if summary.approved_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve summary"
        )


@router.get("/submission/{submission_id}", response_model=List[SummaryResponse])
async def get_summaries_for_submission(
    submission_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> List[SummaryResponse]:
    """
    Get all summaries for a submission (including regenerations).

    Args:
        submission_id: UUID of submission
        db: Database session

    Returns:
        List[SummaryResponse]: All summaries for submission

    Raises:
        500: Database error
    """
    try:
        service = SummarizationService(db)
        summaries = await service.get_summaries_for_submission(submission_id)

        return [
            SummaryResponse(
                summary_id=s.summary_id,
                submission_id=s.submission_id,
                participant_id=s.participant_id,
                round_id=s.round_id,
                summary_text=s.summary_text,
                status=s.status.value,
                regen_count=s.regen_count,
                safety_flags=s.safety_flags,
                created_at=s.created_at.isoformat(),
                approved_at=s.approved_at.isoformat() if s.approved_at else None,
            )
            for s in summaries
        ]

    except Exception as e:
        logger.error(f"Error retrieving summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve summaries"
        )


@router.get("/participant/{participant_id}/round/{round_id}", response_model=List[SummaryResponse])
async def get_summaries_for_participant_round(
    participant_id: UUID,
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> List[SummaryResponse]:
    """
    Get all summaries for a participant in a round (T083-T084).

    Supports User Story 5 - Multiple Submissions with Last-Approved-Wins.
    Returns all summaries ordered by approved_at (DESC) to show latest first.

    Args:
        participant_id: UUID of participant
        round_id: UUID of round
        db: Database session

    Returns:
        List[SummaryResponse]: All summaries for participant in round, sorted by approved_at DESC

    Raises:
        500: Database error
    """
    try:
        from sqlalchemy import select
        from ..models.summary import Summary

        # Query all summaries for participant in round, ordered by approved_at DESC
        result = await db.execute(
            select(Summary)
            .where(Summary.participant_id == participant_id)
            .where(Summary.round_id == round_id)
            .order_by(
                Summary.approved_at.desc().nullslast(),
                Summary.created_at.desc()
            )
        )
        summaries = list(result.scalars().all())

        return [
            SummaryResponse(
                summary_id=s.summary_id,
                submission_id=s.submission_id,
                participant_id=s.participant_id,
                round_id=s.round_id,
                summary_text=s.summary_text,
                status=s.status.value,
                regen_count=s.regen_count,
                safety_flags=s.safety_flags,
                created_at=s.created_at.isoformat(),
                approved_at=s.approved_at.isoformat() if s.approved_at else None,
            )
            for s in summaries
        ]

    except Exception as e:
        logger.error(f"Error retrieving summaries for participant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve summaries"
        )
