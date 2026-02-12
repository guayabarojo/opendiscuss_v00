"""
Unit tests for QuestionSequenceService (Phase 3 - Spec 006).

Tests T018-T024: Service layer for host-defined question sequences.
"""

import pytest
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.question_progression.services.sequence import (
    QuestionSequenceService,
    ValidationError,
    SequenceAlreadyExistsError,
    SequenceNotFoundError,
)
from src.question_progression.models import (
    QuestionSequence,
    Question,
    SequenceMode,
    QuestionMode,
    ValidationStatus,
    CompletionStatus,
)
from src.question_progression.validators import ValidationErrorCode
from src.models.discussion import Discussion, DiscussionMode, DiscussionStatus


@pytest.mark.asyncio
class TestCreateHostSequence:
    """Tests for T018: QuestionSequenceService.create_host_sequence()"""

    async def test_create_valid_sequence(
        self, async_session: AsyncSession
    ):
        """T018: Create sequence with valid questions"""
        # Create discussion
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        async_session.add(discussion)
        await async_session.commit()

        # Create sequence
        service = QuestionSequenceService(async_session)
        questions = [
            "What are the main challenges?",
            "How can we improve accessibility?",
            "What resources are needed?",
        ]

        sequence = await service.create_host_sequence(
            discussion_id=discussion.discussion_id,
            questions=questions,
        )

        # Verify sequence
        assert sequence.sequence_id is not None
        assert sequence.discussion_id == discussion.discussion_id
        assert sequence.mode == SequenceMode.HOST_DEFINED
        assert sequence.total_questions == 3
        assert sequence.current_index == 0
        assert sequence.completion_status == CompletionStatus.IN_PROGRESS

        # Verify questions created
        assert len(sequence.questions) == 3
        for i, question in enumerate(sequence.questions, start=1):
            assert question.order == i
            assert question.mode == QuestionMode.HOST_DEFINED
            assert question.validation_status == ValidationStatus.VALID
            assert question.immutable_since is None

    async def test_create_sequence_single_question(
        self, async_session: AsyncSession
    ):
        """T018: Create sequence with single question (min boundary)"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = ["What is the priority?"]

        sequence = await service.create_host_sequence(
            discussion_id=discussion.discussion_id,
            questions=questions,
        )

        assert sequence.total_questions == 1
        assert len(sequence.questions) == 1

    async def test_create_sequence_ten_questions(
        self, async_session: AsyncSession
    ):
        """T018: Create sequence with 10 questions (max boundary)"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=10,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = [
            f"What is challenge {i}?" for i in range(1, 11)
        ]

        sequence = await service.create_host_sequence(
            discussion_id=discussion.discussion_id,
            questions=questions,
        )

        assert sequence.total_questions == 10
        assert len(sequence.questions) == 10

    async def test_create_sequence_empty_list(
        self, async_session: AsyncSession
    ):
        """T018: Reject empty question list"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)

        with pytest.raises(ValueError, match="at least one question"):
            await service.create_host_sequence(
                discussion_id=discussion.discussion_id,
                questions=[],
            )

    async def test_create_sequence_too_many_questions(
        self, async_session: AsyncSession
    ):
        """T018: Reject more than 10 questions"""
        # Create discussion with valid total_rounds (10)
        # Test will verify that service rejects 11 questions
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=10,  # Valid value, but we'll try to create 11 questions
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = [f"What is question {i}?" for i in range(1, 12)]  # 11 questions

        with pytest.raises(ValueError, match="1-10 questions"):
            await service.create_host_sequence(
                discussion_id=discussion.discussion_id,
                questions=questions,
            )

    async def test_create_sequence_already_exists(
        self, async_session: AsyncSession
    ):
        """T018: Reject duplicate sequence for same discussion"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = ["What is A?", "What is B?"]

        # Create first sequence
        await service.create_host_sequence(
            discussion_id=discussion.discussion_id,
            questions=questions,
        )

        # Attempt to create duplicate
        with pytest.raises(SequenceAlreadyExistsError):
            await service.create_host_sequence(
                discussion_id=discussion.discussion_id,
                questions=questions,
            )


@pytest.mark.asyncio
class TestQuestionValidation:
    """Tests for T019: Question validation at creation"""

    async def test_validation_invalid_start(
        self, async_session: AsyncSession
    ):
        """T019: Reject question not starting with What/How"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = ["Why is this important?"]

        with pytest.raises(ValidationError) as exc_info:
            await service.create_host_sequence(
                discussion_id=discussion.discussion_id,
                questions=questions,
            )

        assert exc_info.value.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD

    async def test_validation_contains_ranking(
        self, async_session: AsyncSession
    ):
        """T019: Reject question with ranking keywords"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = ["What is the best option?"]

        with pytest.raises(ValidationError) as exc_info:
            await service.create_host_sequence(
                discussion_id=discussion.discussion_id,
                questions=questions,
            )

        assert exc_info.value.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD

    async def test_validation_too_short(
        self, async_session: AsyncSession
    ):
        """T019: Reject question shorter than 10 characters"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = ["What up?"]

        with pytest.raises(ValidationError) as exc_info:
            await service.create_host_sequence(
                discussion_id=discussion.discussion_id,
                questions=questions,
            )

        assert exc_info.value.error_code == ValidationErrorCode.INVALID_LENGTH

    async def test_validation_too_long(
        self, async_session: AsyncSession
    ):
        """T019: Reject question longer than 200 characters"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = ["What " + "x" * 200]

        with pytest.raises(ValidationError) as exc_info:
            await service.create_host_sequence(
                discussion_id=discussion.discussion_id,
                questions=questions,
            )

        assert exc_info.value.error_code == ValidationErrorCode.INVALID_LENGTH

    async def test_validation_fail_fast(
        self, async_session: AsyncSession
    ):
        """T019: Stop validation at first failure"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = [
            "What is valid?",
            "Why is invalid?",  # Should fail here
            "What is also valid?",
        ]

        with pytest.raises(ValidationError, match="Question 2"):
            await service.create_host_sequence(
                discussion_id=discussion.discussion_id,
                questions=questions,
            )


@pytest.mark.asyncio
class TestGetNextQuestion:
    """Tests for T022: QuestionSequenceService.get_next_question()"""

    async def test_get_next_question_increments_index(
        self, async_session: AsyncSession
    ):
        """T022: Get next question and increment current_index"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = [
            "What is question 1?",
            "What is question 2?",
            "What is question 3?",
        ]

        sequence = await service.create_host_sequence(
            discussion_id=discussion.discussion_id,
            questions=questions,
        )

        # Get first question
        question_1 = await service.get_next_question(sequence.sequence_id)
        assert question_1.order == 1
        assert question_1.question_text == "What is question 1?"

        # Verify index incremented
        updated_sequence = await service.get_sequence(sequence.sequence_id)
        assert updated_sequence.current_index == 1

        # Get second question
        question_2 = await service.get_next_question(sequence.sequence_id)
        assert question_2.order == 2

        # Verify index incremented again
        updated_sequence = await service.get_sequence(sequence.sequence_id)
        assert updated_sequence.current_index == 2

    async def test_get_next_question_exhausted(
        self, async_session: AsyncSession
    ):
        """T022: Return None when all questions exhausted"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = ["What is the only question?"]

        sequence = await service.create_host_sequence(
            discussion_id=discussion.discussion_id,
            questions=questions,
        )

        # Get first question
        question = await service.get_next_question(sequence.sequence_id)
        assert question is not None

        # Attempt to get second question
        none_result = await service.get_next_question(sequence.sequence_id)
        assert none_result is None


@pytest.mark.asyncio
class TestSequenceCompletion:
    """Tests for T024: Sequence completion detection"""

    async def test_check_completion_host_mode(
        self, async_session: AsyncSession
    ):
        """T024: Mark sequence complete when all questions used"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = ["What is A?", "What is B?"]

        sequence = await service.create_host_sequence(
            discussion_id=discussion.discussion_id,
            questions=questions,
        )

        # Use both questions
        await service.get_next_question(sequence.sequence_id)
        await service.get_next_question(sequence.sequence_id)

        # Check completion
        was_completed = await service.check_and_mark_completion(sequence.sequence_id)
        assert was_completed is True

        # Verify status
        updated_sequence = await service.get_sequence(sequence.sequence_id)
        assert updated_sequence.completion_status == CompletionStatus.COMPLETED

    async def test_check_completion_not_yet_complete(
        self, async_session: AsyncSession
    ):
        """T024: Don't mark complete if questions remain"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = ["What is A?", "What is B?", "What is C?"]

        sequence = await service.create_host_sequence(
            discussion_id=discussion.discussion_id,
            questions=questions,
        )

        # Use only one question
        await service.get_next_question(sequence.sequence_id)

        # Check completion
        was_completed = await service.check_and_mark_completion(sequence.sequence_id)
        assert was_completed is False

        # Verify status unchanged
        updated_sequence = await service.get_sequence(sequence.sequence_id)
        assert updated_sequence.completion_status == CompletionStatus.IN_PROGRESS


@pytest.mark.asyncio
class TestQuestionImmutability:
    """Tests for T023: Question immutability enforcement"""

    async def test_mark_question_immutable(
        self, async_session: AsyncSession
    ):
        """T023: Mark question immutable when round starts"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        questions = ["What is the question?"]

        sequence = await service.create_host_sequence(
            discussion_id=discussion.discussion_id,
            questions=questions,
        )

        question = sequence.questions[0]
        assert question.immutable_since is None

        # Mark immutable
        await service.mark_question_immutable(question.question_id)

        # Verify immutable
        from sqlalchemy import select
        result = await async_session.execute(
            select(Question).where(Question.question_id == question.question_id)
        )
        updated_question = result.scalar_one()
        assert updated_question.immutable_since is not None
        assert updated_question.is_immutable() is True
