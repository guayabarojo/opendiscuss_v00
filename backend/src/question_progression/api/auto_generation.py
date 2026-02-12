"""
API endpoints for auto-generation testing and debugging.

Provides manual triggers and status queries for question auto-generation.
Includes rate limiting to prevent accidental DoS (T104).
"""

import time
from datetime import datetime
from typing import Optional, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database import get_db_session
from src.models import Discussion, Round, RoundStatus
from src.question_progression.models import QuestionSequence, Question, QuestionProvenance
from src.question_progression.services.generation import (
    QuestionGenerationService,
    QuestionGenerationError,
    QuestionValidationExhausted
)
from src.question_progression.services.provenance import ProvenanceTracker
from src.events.event_types import SankeyGraph
from src.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auto-generation", tags=["Auto-Generation"])


# Rate limiting (T104) - 10 generation requests per minute per discussion
class RateLimiter:
    """
    Simple in-memory rate limiter for question generation API.

    Limits: 10 requests per minute per discussion to prevent accidental DoS.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}  # discussion_id -> [timestamps]

    def check_rate_limit(self, discussion_id: str) -> tuple[bool, Optional[int]]:
        """
        Check if request is within rate limit.

        Returns:
            Tuple of (allowed, retry_after_seconds)
            - allowed: True if request should be allowed
            - retry_after_seconds: Seconds until next request allowed (if denied)
        """
        now = time.time()
        key = str(discussion_id)

        # Initialize or clean old requests
        if key not in self.requests:
            self.requests[key] = []
        else:
            # Remove requests outside window
            cutoff = now - self.window_seconds
            self.requests[key] = [ts for ts in self.requests[key] if ts > cutoff]

        # Check limit
        if len(self.requests[key]) >= self.max_requests:
            # Calculate retry-after (time until oldest request expires)
            oldest = self.requests[key][0]
            retry_after = int(self.window_seconds - (now - oldest)) + 1
            return False, retry_after

        # Allow request and record timestamp
        self.requests[key].append(now)
        return True, None


# Global rate limiter instance
rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


# Request/Response Models

class GenerateQuestionRequest(BaseModel):
    """Request to manually trigger question generation."""
    discussion_id: UUID = Field(description="Discussion ID")
    round_id: UUID = Field(description="Round ID that completed")


class GenerateQuestionResponse(BaseModel):
    """Response from question generation."""
    question_id: UUID = Field(description="Generated question ID")
    question_text: str = Field(description="Generated question text")
    provenance: dict = Field(description="Provenance metadata")
    latency_ms: float = Field(description="Generation latency in milliseconds")


class GenerationStatusResponse(BaseModel):
    """Status of question generation for a discussion."""
    discussion_id: UUID
    current_round_num: int
    next_round_status: Optional[str] = Field(default=None, description="Status of next round")
    generation_status: str = Field(description="SUCCESS | FAILED | IN_PROGRESS")
    question_ready: bool = Field(description="Whether question is ready for next round")
    manual_entry_required: bool = Field(default=False, description="Whether manual question entry is required")
    generation_timestamp: Optional[datetime] = Field(default=None)
    latency_ms: Optional[float] = Field(default=None)
    retry_count: Optional[int] = Field(default=None)
    validation_attempts: Optional[int] = Field(default=None)
    error_message: Optional[str] = Field(default=None)


# Endpoints

@router.post("/generate", response_model=GenerateQuestionResponse, status_code=status.HTTP_201_CREATED)
async def generate_question(
    request: GenerateQuestionRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Manually trigger question generation for testing/debugging.

    This endpoint bypasses the event bus and directly calls the generation service.
    Intended for development and debugging purposes.

    Rate limit: 10 requests per minute per discussion.

    Args:
        request: Generation request with discussion_id and round_id
        response: Response object for setting headers
        db: Database session

    Returns:
        Generated question with provenance metadata

    Raises:
        HTTPException 404: If discussion or round not found
        HTTPException 400: If discussion is not AUTO_GENERATED mode
        HTTPException 429: If rate limit exceeded
        HTTPException 500: If generation fails
    """
    # Check rate limit (T104)
    allowed, retry_after = rate_limiter.check_rate_limit(str(request.discussion_id))
    if not allowed:
        logger.warning(
            "Rate limit exceeded for question generation",
            extra={
                "discussion_id": str(request.discussion_id),
                "retry_after": retry_after
            }
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum 10 generation requests per minute per discussion. "
                   f"Retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )

    logger.info(
        "Manual question generation requested",
        extra={
            "discussion_id": str(request.discussion_id),
            "round_id": str(request.round_id)
        }
    )

    try:
        # Fetch discussion
        result = await db.execute(
            select(Discussion)
            .where(Discussion.discussion_id == request.discussion_id)
            .options(selectinload(Discussion.question_sequence))
        )
        discussion = result.scalar_one_or_none()

        if not discussion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Discussion {request.discussion_id} not found"
            )

        # Check mode
        if discussion.mode != "AUTO_GENERATED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Discussion mode is {discussion.mode}, expected AUTO_GENERATED"
            )

        # Fetch round
        result = await db.execute(
            select(Round).where(Round.round_id == request.round_id)
        )
        round_obj = result.scalar_one_or_none()

        if not round_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Round {request.round_id} not found"
            )

        # Get previous questions
        sequence = discussion.question_sequence
        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question sequence not found"
            )

        previous_questions = [
            q.question_text
            for q in sorted(sequence.questions, key=lambda x: x.question_order)
        ]

        # Prepare mock Sankey data (for manual testing)
        # In production, this would come from the actual Sankey service
        sankey_data = {
            "nodes": [
                {
                    "label_summary": "Funding constraints",
                    "member_count": 12,
                    "member_pct": 0.40
                },
                {
                    "label_summary": "Staff capacity",
                    "member_count": 8,
                    "member_pct": 0.27
                }
            ],
            "flows": [
                {
                    "source_label": "Funding constraints",
                    "target_label": "Staff capacity",
                    "participant_count": 5
                }
            ],
            "dropout_count": 0,
            "total_participants": 30
        }

        # Generate question
        generation_service = QuestionGenerationService()
        result = await generation_service.generate_from_sankey(
            round_num=round_obj.round_num,
            previous_questions=previous_questions,
            sankey_data=sankey_data,
            input_round_id=request.round_id
        )

        question_text = result["question_text"]
        provenance_data = result["provenance"]

        # Create Question entity
        next_order = len(sequence.questions) + 1
        question = Question(
            sequence_id=sequence.sequence_id,
            order=next_order,
            question_text=question_text,
            mode="AUTO_GENERATED",
            validation_status="VALID"
        )

        db.add(question)
        await db.flush()

        # Create provenance record
        provenance_tracker = ProvenanceTracker(db)
        await provenance_tracker.record(
            question_id=question.question_id,
            provenance_data=provenance_data
        )

        await db.commit()
        await db.refresh(question)

        logger.info(
            "Manual question generation successful",
            extra={
                "question_id": str(question.question_id),
                "question_text": question_text,
                "latency_ms": provenance_data["generation_latency_ms"]
            }
        )

        return GenerateQuestionResponse(
            question_id=question.question_id,
            question_text=question_text,
            provenance=provenance_data,
            latency_ms=provenance_data["generation_latency_ms"]
        )

    except (QuestionGenerationError, QuestionValidationExhausted) as e:
        logger.error(
            "Question generation failed",
            extra={"error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Question generation failed: {str(e)}"
        )

    except Exception as e:
        logger.error(
            "Unexpected error in manual generation",
            extra={"error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/status/{discussion_id}", response_model=GenerationStatusResponse)
async def get_generation_status(
    discussion_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get auto-generation status for a discussion.

    Returns the status of the next round (if any) and provenance metadata
    for auto-generated questions.

    Args:
        discussion_id: Discussion ID
        db: Database session

    Returns:
        Generation status with provenance metadata

    Raises:
        HTTPException 404: If discussion not found
    """
    try:
        # Fetch discussion with rounds
        result = await db.execute(
            select(Discussion)
            .where(Discussion.discussion_id == discussion_id)
            .options(selectinload(Discussion.rounds))
        )
        discussion = result.scalar_one_or_none()

        if not discussion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Discussion {discussion_id} not found"
            )

        # Get current round (highest round_num)
        rounds = sorted(discussion.rounds, key=lambda r: r.round_num, reverse=True)
        if not rounds:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No rounds found for discussion"
            )

        current_round = rounds[0]

        # Check for next round
        next_round = None
        for r in rounds:
            if r.round_num == current_round.round_num + 1:
                next_round = r
                break

        # Build response
        response = GenerationStatusResponse(
            discussion_id=discussion_id,
            current_round_num=current_round.round_num,
            generation_status="IN_PROGRESS",
            question_ready=False,
            manual_entry_required=False
        )

        if next_round:
            response.next_round_status = next_round.status.value
            response.question_ready = next_round.status == RoundStatus.QUESTION_READY

            # Determine generation_status
            if next_round.status == RoundStatus.QUESTION_READY:
                response.generation_status = "SUCCESS"
            elif next_round.status == RoundStatus.QUESTION_GENERATION_FAILED:
                response.generation_status = "FAILED"
                response.manual_entry_required = True
                response.error_message = (
                    "Question generation failed after maximum retries. "
                    "Please provide a question manually to continue the discussion."
                )
            else:
                response.generation_status = "IN_PROGRESS"

            # Get provenance if question exists
            if next_round.question_id:
                result = await db.execute(
                    select(QuestionProvenance)
                    .where(QuestionProvenance.question_id == next_round.question_id)
                )
                provenance = result.scalar_one_or_none()

                if provenance:
                    response.generation_timestamp = provenance.generation_timestamp
                    response.latency_ms = provenance.generation_latency_ms
                    response.retry_count = provenance.retry_count
                    response.validation_attempts = provenance.validation_attempts

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error fetching generation status",
            extra={"discussion_id": str(discussion_id), "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
