"""
QuestionSequenceService for managing host-defined and auto-generated question sequences.

Handles creation, retrieval, and progression of question sequences across
discussions. Integrates with QuestionValidator for constitutional constraint
enforcement.
"""

import uuid
from typing import List, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.question_progression.models import (
    QuestionSequence,
    Question,
    SequenceMode,
    QuestionMode,
    ValidationStatus,
    CompletionStatus,
)
from src.question_progression.validators import QuestionValidator, ValidationErrorCode
from src.models.discussion import Discussion, DiscussionStatus
from src.logging_config import get_logger, set_sequence_id, set_question_id

logger = get_logger(__name__)


class ValidationError(Exception):
    """Raised when question validation fails."""

    def __init__(self, message: str, error_code: ValidationErrorCode):
        """
        Initialize ValidationError.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class SequenceAlreadyExistsError(Exception):
    """Raised when attempting to create a duplicate sequence for a discussion."""

    pass


class SequenceNotFoundError(Exception):
    """Raised when sequence not found."""

    pass


class SequenceIntegrityError(Exception):
    """Raised when sequence integrity validation fails."""

    def __init__(self, message: str, violation: str):
        """
        Initialize SequenceIntegrityError.

        Args:
            message: Human-readable error message
            violation: Specific integrity violation type
        """
        super().__init__(message)
        self.message = message
        self.violation = violation


class QuestionSequenceService:
    """
    Service for managing question sequences in HOST_DEFINED and AUTO_GENERATED modes.

    Responsibilities:
    - Create host-defined sequences with upfront validation
    - Retrieve sequences and individual questions
    - Track sequence progression (current_index, completion_status)
    - Enforce immutability when rounds start
    - Detect sequence completion
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize QuestionSequenceService.

        Args:
            db_session: Database session for persistence operations
        """
        self.db_session = db_session
        self.validator = QuestionValidator()

    async def create_host_sequence(
        self,
        discussion_id: uuid.UUID,
        questions: List[str],
    ) -> QuestionSequence:
        """
        Create a host-defined question sequence with validated questions.

        Validates all questions upfront using QuestionValidator, creates
        QuestionSequence and Question entities atomically. Fail-fast on
        validation errors.

        Args:
            discussion_id: UUID of parent discussion
            questions: List of 1-10 question texts

        Returns:
            QuestionSequence with all Question entities created

        Raises:
            ValidationError: If any question fails validation (fail-fast)
            SequenceAlreadyExistsError: If sequence already exists for discussion
            ValueError: If question count not in range [1, 10]
        """
        # Validate question count
        if not questions:
            raise ValueError("Must provide at least one question")

        question_count = len(questions)
        if not (1 <= question_count <= 10):
            raise ValueError(
                f"HOST_DEFINED mode requires 1-10 questions, got {question_count}"
            )

        logger.info(
            "Creating host-defined question sequence",
            extra={
                "discussion_id": str(discussion_id),
                "question_count": question_count,
            },
        )

        # Check if sequence already exists
        existing_sequence_result = await self.db_session.execute(
            select(QuestionSequence).where(
                QuestionSequence.discussion_id == discussion_id
            )
        )
        existing_sequence = existing_sequence_result.scalar_one_or_none()

        if existing_sequence:
            raise SequenceAlreadyExistsError(
                f"Question sequence already exists for discussion {discussion_id}"
            )

        # Validate all questions (fail-fast)
        for i, question_text in enumerate(questions, start=1):
            validation_result = self.validator.validate(question_text)

            if not validation_result.valid:
                error_msg = (
                    f"Question {i} validation failed: {validation_result.error_message}"
                )
                logger.warning(
                    "Question validation failed",
                    extra={
                        "discussion_id": str(discussion_id),
                        "question_index": i,
                        "question_text": question_text[:50],
                        "error_code": validation_result.error_code.value,
                        "error_message": validation_result.error_message,
                    },
                )
                raise ValidationError(
                    message=error_msg,
                    error_code=validation_result.error_code,
                )

        # Create QuestionSequence entity
        sequence = QuestionSequence(
            discussion_id=discussion_id,
            mode=SequenceMode.HOST_DEFINED,
            total_questions=question_count,
        )

        self.db_session.add(sequence)
        await self.db_session.flush()  # Get sequence_id before creating questions

        set_sequence_id(str(sequence.sequence_id))

        logger.info(
            "Created question sequence",
            extra={
                "sequence_id": str(sequence.sequence_id),
                "mode": SequenceMode.HOST_DEFINED.value,
                "total_questions": question_count,
            },
        )

        # Create Question entities (all validated and VALID status)
        question_entities = []
        for order, question_text in enumerate(questions, start=1):
            # Use validated_text from validation result
            validation_result = self.validator.validate(question_text)
            validated_text = validation_result.validated_text

            question = Question(
                sequence_id=sequence.sequence_id,
                order=order,
                question_text=validated_text,
                mode=QuestionMode.HOST_DEFINED,
                validation_status=ValidationStatus.VALID,
            )

            self.db_session.add(question)
            question_entities.append(question)

            logger.debug(
                "Created question in sequence",
                extra={
                    "question_order": order,
                    "question_text_preview": validated_text[:50],
                },
            )

        # Commit all entities atomically
        await self.db_session.commit()
        await self.db_session.refresh(sequence)

        logger.info(
            "Successfully created host-defined question sequence",
            extra={
                "questions_created": len(question_entities),
            },
        )

        return sequence

    async def get_sequence(
        self, sequence_id: uuid.UUID
    ) -> Optional[QuestionSequence]:
        """
        Get a question sequence by ID with all questions loaded.

        Args:
            sequence_id: UUID of the sequence

        Returns:
            QuestionSequence with questions relationship loaded, or None if not found
        """
        result = await self.db_session.execute(
            select(QuestionSequence)
            .where(QuestionSequence.sequence_id == sequence_id)
            .options(selectinload(QuestionSequence.questions))
        )
        return result.scalar_one_or_none()

    async def validate_sequence_integrity(
        self, sequence_id: uuid.UUID
    ) -> None:
        """
        Validate linear sequence integrity.

        Checks:
        - No gaps in question order (1, 2, 3, ... no skips)
        - No duplicate order values
        - current_index <= total_questions count

        Args:
            sequence_id: UUID of the sequence to validate

        Raises:
            SequenceNotFoundError: If sequence not found
            SequenceIntegrityError: If integrity validation fails
        """
        sequence = await self.get_sequence(sequence_id)

        if not sequence:
            raise SequenceNotFoundError(f"Sequence {sequence_id} not found")

        questions = sorted(sequence.questions, key=lambda q: q.question_order)

        if not questions:
            # Empty sequence is valid (AUTO mode at start)
            return

        # Check for gaps and duplicates
        expected_order = 1
        seen_orders = set()

        for question in questions:
            order = question.question_order

            # Check for duplicates
            if order in seen_orders:
                raise SequenceIntegrityError(
                    f"Duplicate question order {order} found in sequence {sequence_id}",
                    violation="DUPLICATE_ORDER"
                )
            seen_orders.add(order)

            # Check for gaps
            if order != expected_order:
                raise SequenceIntegrityError(
                    f"Gap in question sequence at order {expected_order}. "
                    f"Found order {order} instead. Sequence must be linear (1, 2, 3, ...).",
                    violation="ORDER_GAP"
                )

            expected_order += 1

        # Validate current_index
        if sequence.current_index > len(questions):
            raise SequenceIntegrityError(
                f"current_index ({sequence.current_index}) exceeds question count ({len(questions)})",
                violation="INDEX_OUT_OF_BOUNDS"
            )

        logger.debug(
            "Sequence integrity validated",
            extra={
                "sequence_id": str(sequence_id),
                "question_count": len(questions),
                "current_index": sequence.current_index,
            },
        )

    async def get_sequence_by_discussion(
        self, discussion_id: uuid.UUID
    ) -> Optional[QuestionSequence]:
        """
        Get the question sequence for a discussion.

        Args:
            discussion_id: UUID of the discussion

        Returns:
            QuestionSequence with questions loaded, or None if not found
        """
        result = await self.db_session.execute(
            select(QuestionSequence)
            .where(QuestionSequence.discussion_id == discussion_id)
            .options(selectinload(QuestionSequence.questions))
        )
        return result.scalar_one_or_none()

    async def get_next_question(
        self, sequence_id: uuid.UUID
    ) -> Optional[Question]:
        """
        Get the next question in the sequence and increment current_index.

        Returns the question at current_index, then increments the index.
        Returns None if all questions have been exhausted.

        Args:
            sequence_id: UUID of the sequence

        Returns:
            Question at current_index, or None if exhausted

        Raises:
            SequenceNotFoundError: If sequence not found
        """
        # Fetch sequence with questions
        sequence = await self.get_sequence(sequence_id)

        if not sequence:
            raise SequenceNotFoundError(f"Sequence {sequence_id} not found")

        # Check if all questions exhausted
        if sequence.current_index >= len(sequence.questions):
            logger.info(
                "All questions exhausted in sequence",
                extra={
                    "sequence_id": str(sequence_id),
                    "current_index": sequence.current_index,
                    "total_questions": len(sequence.questions),
                },
            )
            return None

        # Get question at current index (0-based indexing)
        # Questions are ordered by the 'order' field (1-indexed)
        current_question = sequence.questions[sequence.current_index]

        # Increment current_index
        sequence.current_index += 1
        self.db_session.add(sequence)
        await self.db_session.commit()
        await self.db_session.refresh(sequence)

        logger.info(
            "Retrieved next question from sequence",
            extra={
                "sequence_id": str(sequence_id),
                "question_id": str(current_question.question_id),
                "question_order": current_question.question_order,
                "new_current_index": sequence.current_index,
            },
        )

        return current_question

    async def check_and_mark_completion(
        self, sequence_id: uuid.UUID
    ) -> bool:
        """
        Check if sequence is complete and mark it as COMPLETED if so.

        A sequence is complete when current_index >= total_questions (HOST mode)
        or when all created questions have been used.

        Args:
            sequence_id: UUID of the sequence

        Returns:
            True if sequence was marked complete, False otherwise

        Raises:
            SequenceNotFoundError: If sequence not found
        """
        sequence = await self.get_sequence(sequence_id)

        if not sequence:
            raise SequenceNotFoundError(f"Sequence {sequence_id} not found")

        # Already completed or terminated
        if sequence.completion_status != CompletionStatus.IN_PROGRESS:
            return False

        # Check completion criteria
        is_complete = False

        if sequence.mode == SequenceMode.HOST_DEFINED:
            # HOST mode: complete when current_index >= total_questions
            if sequence.current_index >= sequence.total_questions:
                is_complete = True
        else:
            # AUTO mode: complete when all created questions used
            # (termination is explicit via terminate_sequence)
            if sequence.current_index >= len(sequence.questions):
                is_complete = True

        if is_complete:
            sequence.completion_status = CompletionStatus.COMPLETED
            sequence.updated_at = datetime.utcnow()
            self.db_session.add(sequence)
            await self.db_session.commit()

            logger.info(
                "Marked question sequence as COMPLETED",
                extra={
                    "sequence_id": str(sequence_id),
                    "mode": sequence.mode.value,
                    "current_index": sequence.current_index,
                    "total_questions": sequence.total_questions,
                },
            )

            # Mark discussion as completed
            await self._mark_discussion_completed(sequence.discussion_id)

            return True

        return False

    async def terminate_sequence(
        self, sequence_id: uuid.UUID
    ) -> QuestionSequence:
        """
        Terminate a sequence early (AUTO mode only, typically).

        Sets completion_status to TERMINATED. Used when host decides to
        end an auto-generated discussion before natural completion.

        Args:
            sequence_id: UUID of the sequence

        Returns:
            Updated QuestionSequence

        Raises:
            SequenceNotFoundError: If sequence not found
        """
        sequence = await self.get_sequence(sequence_id)

        if not sequence:
            raise SequenceNotFoundError(f"Sequence {sequence_id} not found")

        sequence.completion_status = CompletionStatus.TERMINATED
        sequence.updated_at = datetime.utcnow()
        self.db_session.add(sequence)
        await self.db_session.commit()
        await self.db_session.refresh(sequence)

        logger.info(
            "Terminated question sequence",
            extra={
                "sequence_id": str(sequence_id),
                "mode": sequence.mode.value,
                "current_index": sequence.current_index,
            },
        )

        return sequence

    async def _mark_discussion_completed(
        self, discussion_id: uuid.UUID
    ) -> None:
        """
        Mark discussion as completed when sequence finishes.

        Internal helper for sequence completion detection.

        Args:
            discussion_id: UUID of the discussion
        """
        result = await self.db_session.execute(
            select(Discussion).where(Discussion.discussion_id == discussion_id)
        )
        discussion = result.scalar_one_or_none()

        if discussion and discussion.status == DiscussionStatus.ACTIVE:
            discussion.complete()
            self.db_session.add(discussion)
            await self.db_session.commit()

            logger.info(
                "Marked discussion as COMPLETED",
                extra={
                    "discussion_id": str(discussion_id),
                },
            )

    async def mark_question_immutable(
        self, question_id: uuid.UUID
    ) -> Question:
        """
        Mark a question as immutable (called when round starts).

        Sets immutable_since timestamp to prevent further edits.

        Args:
            question_id: UUID of the question

        Returns:
            Updated Question entity

        Raises:
            ValueError: If question not found
        """
        result = await self.db_session.execute(
            select(Question).where(Question.question_id == question_id)
        )
        question = result.scalar_one_or_none()

        if not question:
            raise ValueError(f"Question {question_id} not found")

        question.mark_immutable()
        self.db_session.add(question)
        await self.db_session.commit()
        await self.db_session.refresh(question)

        set_question_id(str(question_id))

        logger.info(
            "Marked question as immutable",
            extra={
                "question_id": str(question_id),
                "immutable_since": question.immutable_since.isoformat()
                if question.immutable_since
                else None,
            },
        )

        return question
