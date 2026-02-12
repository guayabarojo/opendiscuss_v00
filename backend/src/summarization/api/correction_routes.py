"""
Correction signal API routes for Spec 003 (User Story 3).

Endpoints:
- POST /summaries/{summary_id}/correction - Submit correction signal and trigger final regeneration (T053)
"""

from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...logging_config import logger
from ..models.summary import SummaryStatus
from ..models.correction_signal import ReasonTag, CorrectionSignal
from ..services.summarization_service import SummarizationService
from ..services.approval_service import ApprovalService


# Router
router = APIRouter(prefix="/summaries", tags=["correction"])


# Request/Response Models
class CorrectionSignalRequest(BaseModel):
    """Request to submit correction signal (Task T053, T059-T060)."""

    reason_tag: str = Field(
        ...,
        description="Structured reason for rejection (WRONG_CRUX, TOO_VAGUE, etc.)"
    )
    feedback_text: Optional[str] = Field(
        default=None,
        description="Optional participant feedback (max 240 chars)"
    )

    @field_validator("feedback_text")
    @classmethod
    def validate_feedback_length(cls, v: Optional[str]) -> Optional[str]:
        """Validate feedback_text max 240 chars (T059)."""
        if v and len(v) > 240:
            raise ValueError("feedback_text must be 240 characters or less")
        return v

    @field_validator("reason_tag")
    @classmethod
    def validate_reason_tag(cls, v: str) -> str:
        """Validate reason_tag is valid ReasonTag enum value (T060)."""
        valid_tags = [tag.value for tag in ReasonTag]
        if v not in valid_tags:
            raise ValueError(
                f"Invalid reason_tag. Must be one of: {', '.join(valid_tags)}"
            )
        return v


class CorrectionSignalResponse(BaseModel):
    """Response for correction signal submission."""

    signal_id: UUID
    summary_id: UUID
    reason_tag: str
    feedback_text: Optional[str]
    created_at: str  # ISO 8601 timestamp
    new_summary_id: UUID
    new_summary_text: str
    regen_count: int
    message: str


# Endpoints

@router.post("/{summary_id}/correction", response_model=CorrectionSignalResponse, status_code=status.HTTP_201_CREATED)
async def submit_correction_signal(
    summary_id: UUID,
    request: CorrectionSignalRequest,
    db: AsyncSession = Depends(get_db),
) -> CorrectionSignalResponse:
    """
    Submit correction signal and trigger final regeneration (Task T053).

    Workflow:
    1. Validate summary exists and is in correct state (regen_count=2)
    2. Create CorrectionSignal entity
    3. Trigger final regeneration (regen_count=3) using correction prompt
    4. Return new summary for review

    If the participant rejects this final summary, it will be marked REJECTED_FINAL.

    Args:
        summary_id: UUID of rejected summary (should have regen_count=2)
        request: Correction signal with reason_tag and optional feedback_text
        db: Database session

    Returns:
        CorrectionSignalResponse: Created correction signal and new summary

    Raises:
        404: Summary not found
        422: Invalid state (not regen_count=2, not REJECTED status)
        500: Database or LLM error
    """
    try:
        # Fetch summary
        summarization_service = SummarizationService(db)
        summary = await summarization_service.get_summary(summary_id)

        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Summary {summary_id} not found"
            )

        # Validate state: must be regen_count=2 and REJECTED
        if summary.regen_count != 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Correction signals can only be submitted after 2 rejections. "
                    f"This summary has regen_count={summary.regen_count}."
                )
            )

        if summary.status != SummaryStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Summary must be in REJECTED state. "
                    f"Current status: {summary.status.value}"
                )
            )

        # Convert reason_tag string to enum
        reason_tag_enum = ReasonTag(request.reason_tag)

        # Create CorrectionSignal entity
        correction_signal = CorrectionSignal(
            signal_id=uuid4(),
            summary_id=summary_id,
            reason_tag=reason_tag_enum,
            feedback_text=request.feedback_text,
        )

        db.add(correction_signal)
        await db.commit()
        await db.refresh(correction_signal)

        # Logging (T061)
        logger.info(
            f"Correction signal {correction_signal.signal_id} submitted for summary {summary_id}: "
            f"reason_tag={reason_tag_enum.value}, "
            f"participant_id={summary.participant_id}, "
            f"has_feedback={bool(request.feedback_text)}"
        )

        # Trigger final regeneration with correction signal (T052)
        new_summary = await summarization_service.regenerate_with_correction(
            previous_summary_id=summary_id,
            use_fallback_model=False,
        )

        # Return response
        return CorrectionSignalResponse(
            signal_id=correction_signal.signal_id,
            summary_id=summary_id,
            reason_tag=correction_signal.reason_tag.value,
            feedback_text=correction_signal.feedback_text,
            created_at=correction_signal.created_at.isoformat(),
            new_summary_id=new_summary.summary_id,
            new_summary_text=new_summary.summary_text,
            regen_count=new_summary.regen_count,
            message=(
                f"Final regeneration attempt ({new_summary.regen_count}/3) generated. "
                "If you reject this summary, you may resubmit your input."
            ),
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error submitting correction signal: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error submitting correction signal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process correction signal"
        )
