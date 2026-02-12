"""
API endpoints for Question Progression Protocol.

Provides REST endpoints for:
- Creating and managing question sequences (host-defined mode)
- Retrieving sequence and question details
- Validating questions before creation
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.question_progression.services.sequence import (
    QuestionSequenceService,
    ValidationError as QValidationError,
    SequenceAlreadyExistsError,
    SequenceNotFoundError,
)
from src.question_progression.models import (
    SequenceMode,
    CompletionStatus,
    QuestionMode,
    ValidationStatus,
)
from src.question_progression.validators import validate_question, ValidationErrorCode
from src.logging_config import get_logger, set_discussion_id, set_sequence_id

logger = get_logger(__name__)

router = APIRouter(prefix="/questions", tags=["questions"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateSequenceRequest(BaseModel):
    """Request body for creating a host-defined question sequence."""

    discussion_id: UUID = Field(description="UUID of the discussion")
    mode: str = Field(
        default="HOST_DEFINED",
        description="Sequence mode (only HOST_DEFINED supported in Phase 3)",
    )
    questions: List[str] = Field(
        min_length=1,
        max_length=10,
        description="List of 1-10 question texts",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "discussion_id": "550e8400-e29b-41d4-a716-446655440000",
                "mode": "HOST_DEFINED",
                "questions": [
                    "What are the main challenges facing our community?",
                    "How can we improve accessibility to resources?",
                    "What opportunities should we prioritize?",
                ],
            }
        }
    }


class QuestionResponse(BaseModel):
    """Response model for a single question."""

    question_id: UUID
    sequence_id: UUID
    order: int
    question_text: str
    mode: str
    validation_status: str
    created_at: datetime
    immutable_since: Optional[datetime] = None

    model_config = {"from_attributes": True}


class QuestionSequenceResponse(BaseModel):
    """Response model for a question sequence."""

    sequence_id: UUID
    discussion_id: UUID
    mode: str
    total_questions: Optional[int]
    current_index: int
    completion_status: str
    created_at: datetime
    questions: List[QuestionResponse]

    model_config = {"from_attributes": True}


class ValidationResultResponse(BaseModel):
    """Response model for question validation."""

    valid: bool
    validated_text: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    details: Optional[dict] = None


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/sequences",
    response_model=QuestionSequenceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "Sequence already exists"},
    },
)
async def create_question_sequence(
    request: CreateSequenceRequest,
    db: AsyncSession = Depends(get_db),
) -> QuestionSequenceResponse:
    """
    Create a host-defined question sequence with validated questions.

    Creates a QuestionSequence with mode=HOST_DEFINED and all questions
    validated upfront. All questions must pass validation before the
    sequence is created (fail-fast validation).

    Args:
        request: Sequence creation request with discussion_id and questions
        db: Database session

    Returns:
        Created QuestionSequence with all Question entities

    Raises:
        HTTPException 400: If validation fails on any question
        HTTPException 409: If sequence already exists for discussion
    """
    set_discussion_id(str(request.discussion_id))

    # Validate mode (Phase 3 only supports HOST_DEFINED)
    if request.mode != "HOST_DEFINED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_MODE",
                "message": f"Only HOST_DEFINED mode supported in Phase 3, got {request.mode}",
            },
        )

    logger.info(
        "Creating host-defined question sequence",
        extra={
            "discussion_id": str(request.discussion_id),
            "question_count": len(request.questions),
        },
    )

    service = QuestionSequenceService(db)

    try:
        sequence = await service.create_host_sequence(
            discussion_id=request.discussion_id,
            questions=request.questions,
        )

        # Build response
        questions_response = [
            QuestionResponse(
                question_id=q.question_id,
                sequence_id=q.sequence_id,
                order=q.question_order,
                question_text=q.question_text,
                mode=q.mode.value,
                validation_status=q.validation_status.value,
                created_at=q.created_at,
                immutable_since=q.immutable_since,
            )
            for q in sequence.questions
        ]

        response = QuestionSequenceResponse(
            sequence_id=sequence.sequence_id,
            discussion_id=sequence.discussion_id,
            mode=sequence.mode.value,
            total_questions=sequence.total_questions,
            current_index=sequence.current_index,
            completion_status=sequence.completion_status.value,
            created_at=sequence.created_at,
            questions=questions_response,
        )

        logger.info(
            "Successfully created question sequence",
            extra={
                "sequence_id": str(sequence.sequence_id),
                "questions_created": len(questions_response),
            },
        )

        return response

    except QValidationError as e:
        logger.warning(
            "Question validation failed",
            extra={
                "error_code": e.error_code.value,
                "error_message": e.message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": e.message,
                "details": {"error_code": e.error_code.value},
            },
        )

    except SequenceAlreadyExistsError as e:
        logger.warning(
            "Sequence already exists for discussion",
            extra={"error_message": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "SEQUENCE_ALREADY_EXISTS",
                "message": str(e),
            },
        )

    except ValueError as e:
        logger.warning(
            "Invalid request parameters",
            extra={"error_message": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_REQUEST",
                "message": str(e),
            },
        )


@router.get(
    "/sequences/{sequence_id}",
    response_model=QuestionSequenceResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Sequence not found"},
    },
)
async def get_question_sequence(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> QuestionSequenceResponse:
    """
    Get a question sequence by ID with all questions.

    Returns the full sequence with all questions in order, including
    current_index and completion_status.

    Args:
        sequence_id: UUID of the sequence
        db: Database session

    Returns:
        QuestionSequence with all questions

    Raises:
        HTTPException 404: If sequence not found
    """
    set_sequence_id(str(sequence_id))

    service = QuestionSequenceService(db)
    sequence = await service.get_sequence(sequence_id)

    if not sequence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": f"Question sequence {sequence_id} not found",
            },
        )

    # Build response
    questions_response = [
        QuestionResponse(
            question_id=q.question_id,
            sequence_id=q.sequence_id,
            order=q.question_order,
            question_text=q.question_text,
            mode=q.mode.value,
            validation_status=q.validation_status.value,
            created_at=q.created_at,
            immutable_since=q.immutable_since,
        )
        for q in sequence.questions
    ]

    return QuestionSequenceResponse(
        sequence_id=sequence.sequence_id,
        discussion_id=sequence.discussion_id,
        mode=sequence.mode.value,
        total_questions=sequence.total_questions,
        current_index=sequence.current_index,
        completion_status=sequence.completion_status.value,
        created_at=sequence.created_at,
        questions=questions_response,
    )


@router.get(
    "/discussions/{discussion_id}/questions",
    response_model=QuestionSequenceResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Sequence not found"},
    },
)
async def get_discussion_questions(
    discussion_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> QuestionSequenceResponse:
    """
    Get all questions for a discussion.

    Returns the question sequence for the discussion with all questions
    in order.

    Args:
        discussion_id: UUID of the discussion
        db: Database session

    Returns:
        QuestionSequence with all questions

    Raises:
        HTTPException 404: If sequence not found
    """
    set_discussion_id(str(discussion_id))

    service = QuestionSequenceService(db)
    sequence = await service.get_sequence_by_discussion(discussion_id)

    if not sequence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": f"No question sequence found for discussion {discussion_id}",
            },
        )

    # Build response
    questions_response = [
        QuestionResponse(
            question_id=q.question_id,
            sequence_id=q.sequence_id,
            order=q.question_order,
            question_text=q.question_text,
            mode=q.mode.value,
            validation_status=q.validation_status.value,
            created_at=q.created_at,
            immutable_since=q.immutable_since,
        )
        for q in sequence.questions
    ]

    return QuestionSequenceResponse(
        sequence_id=sequence.sequence_id,
        discussion_id=sequence.discussion_id,
        mode=sequence.mode.value,
        total_questions=sequence.total_questions,
        current_index=sequence.current_index,
        completion_status=sequence.completion_status.value,
        created_at=sequence.created_at,
        questions=questions_response,
    )


class ValidateQuestionRequest(BaseModel):
    """Request model for question validation"""
    question_text: str = Field(..., description="Question text to validate")


class UpdateQuestionRequest(BaseModel):
    """Request model for updating a question."""
    question_text: str = Field(..., min_length=10, max_length=200, description="New question text")


@router.post(
    "/validate",
    response_model=ValidationResultResponse,
)
async def validate_question_text(
    request: ValidateQuestionRequest,
) -> ValidationResultResponse:
    """
    Validate question text against constitutional constraints.

    Pre-check endpoint for validating questions before creating a sequence.
    Returns validation result with specific error codes.

    Args:
        question_text: Question text to validate

    Returns:
        ValidationResult with valid=True/False and error details
    """
    logger.debug(
        "Validating question text",
        extra={"question_text_preview": request.question_text[:50]},
    )

    result = validate_question(request.question_text)

    return ValidationResultResponse(
        valid=result.valid,
        validated_text=result.validated_text,
        error=result.error_message,
        error_code=result.error_code.value if result.error_code else None,
    )


@router.patch(
    "/questions/{question_id}",
    response_model=QuestionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Question is immutable or validation error"},
        404: {"model": ErrorResponse, "description": "Question not found"},
    },
)
async def update_question(
    question_id: UUID,
    request: UpdateQuestionRequest,
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    """
    Update a question's text (only allowed before round starts).

    Questions become immutable once their associated round has started.
    This endpoint enforces immutability and validates the new question text.

    Args:
        question_id: UUID of the question to update
        request: New question text
        db: Database session

    Returns:
        Updated Question entity

    Raises:
        HTTPException 400: If question is immutable or validation fails
        HTTPException 404: If question not found
    """
    from sqlalchemy import select
    from src.question_progression.models import Question

    # Fetch question
    result = await db.execute(
        select(Question).where(Question.question_id == question_id)
    )
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": f"Question {question_id} not found",
            },
        )

    # Check immutability
    if question.immutable_since is not None:
        # Find associated round to get round number
        from src.models import Round
        round_result = await db.execute(
            select(Round).where(Round.question_id == question_id)
        )
        associated_round = round_result.scalar_one_or_none()

        round_info = ""
        if associated_round:
            round_info = f" (Round {associated_round.round_num})"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "IMMUTABLE_QUESTION",
                "message": (
                    f"Cannot modify question after round has started{round_info}. "
                    f"Question became immutable at {question.immutable_since.isoformat()}"
                ),
                "details": {
                    "immutable_since": question.immutable_since.isoformat(),
                    "round_num": associated_round.round_num if associated_round else None,
                },
            },
        )

    # Validate new question text
    validation_result = validate_question(request.question_text)

    if not validation_result.valid:
        logger.warning(
            "Question update validation failed",
            extra={
                "question_id": str(question_id),
                "error_code": validation_result.error_code.value,
                "error_message": validation_result.error_message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": validation_result.error_message,
                "details": {"error_code": validation_result.error_code.value},
            },
        )

    # Update question
    question.question_text = validation_result.validated_text
    question.validation_status = ValidationStatus.VALID
    question.updated_at = datetime.utcnow()

    db.add(question)
    await db.commit()
    await db.refresh(question)

    logger.info(
        "Question updated successfully",
        extra={
            "question_id": str(question_id),
            "new_text_preview": validation_result.validated_text[:50],
        },
    )

    return QuestionResponse(
        question_id=question.question_id,
        sequence_id=question.sequence_id,
        order=question.question_order,
        question_text=question.question_text,
        mode=question.mode.value,
        validation_status=question.validation_status.value,
        created_at=question.created_at,
        immutable_since=question.immutable_since,
    )
