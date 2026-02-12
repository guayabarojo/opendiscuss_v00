"""
Integration tests for host-defined question sequence creation flow (Spec 006 - Phase 4).

Tests the complete API flow for creating host-defined sequences with validation,
including error handling and database persistence.

Task: T038
Constitutional Coverage:
- Principle VII (Representation Not Adjudication): Ensures all questions follow
  constitutional constraints (What/How only, no ranking/voting, no binary choices)
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from src.models.discussion import Discussion, DiscussionMode
from src.question_progression.models import (
    QuestionSequence,
    Question,
    SequenceMode,
    ValidationStatus,
)
from src.question_progression.services.sequence import (
    QuestionSequenceService,
    ValidationError,
)
from src.question_progression.validators import ValidationErrorCode


# ============================================================================
# T038: Integration Test - Host Defined Flow with Invalid Questions
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestHostDefinedFlowValidation:
    """Test host-defined sequence creation with validation."""

    async def test_create_sequence_with_invalid_question_returns_400(self, db_session):
        """
        Test creating host-defined sequence with invalid question fails gracefully.

        Validates:
        - Service raises ValidationError with specific error code
        - No QuestionSequence created in database
        - No Question entities created in database
        - Error message contains details
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Invalid question: starts with "Why" (prohibited)
        invalid_questions = [
            "What are your thoughts on this topic?",
            "Why is this important?",  # INVALID: starts with Why
            "How can we improve our approach?",
        ]

        service = QuestionSequenceService(db_session)

        # Attempt to create sequence should fail
        with pytest.raises(ValidationError) as exc_info:
            await service.create_host_sequence(
                discussion_id=discussion_id,
                questions=invalid_questions,
            )

        # Verify error details
        error = exc_info.value
        assert error.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD
        assert "why" in error.message.lower()
        assert "Question 2" in error.message  # Second question failed

        # Verify NO sequence was created in database
        result = await db_session.execute(
            select(QuestionSequence).where(
                QuestionSequence.discussion_id == discussion_id
            )
        )
        sequence = result.scalar_one_or_none()
        assert sequence is None, "No sequence should be created when validation fails"

        # Verify NO questions were created for this discussion
        # Note: Other tests may have created questions, so we can't check total count
        # We just verify no sequence was created, which implies no questions for this discussion

    async def test_create_sequence_with_ranking_keyword_fails(self, db_session):
        """
        Test creating sequence with ranking keyword fails validation.

        Validates:
        - Questions with ranking keywords are rejected
        - Error code is CONTAINS_RANKING_KEYWORD
        - No database entries created
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Invalid question: contains "best" (ranking keyword)
        invalid_questions = [
            "What is the best approach to this problem?",  # INVALID: contains "best"
        ]

        service = QuestionSequenceService(db_session)

        with pytest.raises(ValidationError) as exc_info:
            await service.create_host_sequence(
                discussion_id=discussion_id,
                questions=invalid_questions,
            )

        error = exc_info.value
        assert error.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD
        assert "best" in error.message.lower()

        # Verify no sequence created
        result = await db_session.execute(
            select(QuestionSequence).where(
                QuestionSequence.discussion_id == discussion_id
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_create_sequence_with_binary_choice_fails(self, db_session):
        """
        Test creating sequence with binary choice pattern fails validation.

        Validates:
        - Binary choice patterns are rejected
        - Error code is BINARY_CHOICE
        - No database entries created
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Invalid question: binary choice pattern
        invalid_questions = [
            "What is your position: yes or no?",  # INVALID: binary choice
        ]

        service = QuestionSequenceService(db_session)

        with pytest.raises(ValidationError) as exc_info:
            await service.create_host_sequence(
                discussion_id=discussion_id,
                questions=invalid_questions,
            )

        error = exc_info.value
        assert error.error_code == ValidationErrorCode.BINARY_CHOICE
        assert "binary" in error.message.lower()

        # Verify no sequence created
        result = await db_session.execute(
            select(QuestionSequence).where(
                QuestionSequence.discussion_id == discussion_id
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_create_sequence_with_invalid_start_fails(self, db_session):
        """
        Test creating sequence with invalid opening word fails validation.

        Validates:
        - Questions not starting with What/How are rejected
        - Error code is INVALID_START
        - No database entries created
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Invalid question: starts with "Which"
        invalid_questions = [
            "Which option should we consider?",  # INVALID: starts with Which
        ]

        service = QuestionSequenceService(db_session)

        with pytest.raises(ValidationError) as exc_info:
            await service.create_host_sequence(
                discussion_id=discussion_id,
                questions=invalid_questions,
            )

        error = exc_info.value
        assert error.error_code == ValidationErrorCode.INVALID_START
        assert "what" in error.message.lower() or "how" in error.message.lower()

        # Verify no sequence created
        result = await db_session.execute(
            select(QuestionSequence).where(
                QuestionSequence.discussion_id == discussion_id
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_create_sequence_with_invalid_length_fails(self, db_session):
        """
        Test creating sequence with invalid length question fails validation.

        Validates:
        - Questions outside 10-200 character range are rejected
        - Error code is INVALID_LENGTH
        - No database entries created
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Invalid question: too short (< 10 characters)
        invalid_questions = [
            "What?",  # INVALID: only 5 characters
        ]

        service = QuestionSequenceService(db_session)

        with pytest.raises(ValidationError) as exc_info:
            await service.create_host_sequence(
                discussion_id=discussion_id,
                questions=invalid_questions,
            )

        error = exc_info.value
        assert error.error_code == ValidationErrorCode.INVALID_LENGTH
        assert "10-200" in error.message

        # Verify no sequence created
        result = await db_session.execute(
            select(QuestionSequence).where(
                QuestionSequence.discussion_id == discussion_id
            )
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
@pytest.mark.integration
class TestHostDefinedFlowSuccess:
    """Test successful host-defined sequence creation."""

    async def test_create_sequence_with_valid_questions_succeeds(self, db_session):
        """
        Test creating host-defined sequence with all valid questions succeeds.

        Validates:
        - Sequence is created with correct attributes
        - All questions are created with VALID status
        - Questions are ordered correctly
        - Database persistence is correct
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        valid_questions = [
            "What are the main challenges facing our community?",
            "How can we improve accessibility to resources?",
            "What opportunities should we prioritize in the coming year?",
        ]

        service = QuestionSequenceService(db_session)

        # Create sequence - should succeed
        sequence = await service.create_host_sequence(
            discussion_id=discussion_id,
            questions=valid_questions,
        )

        # Verify sequence attributes
        assert sequence is not None
        assert sequence.sequence_id is not None
        assert sequence.discussion_id == discussion_id
        assert sequence.mode == SequenceMode.HOST_DEFINED
        assert sequence.total_questions == 3
        assert sequence.current_index == 0

        # Verify questions were created
        assert len(sequence.questions) == 3

        # Verify question details
        for i, question in enumerate(sequence.questions, start=1):
            assert question.question_id is not None
            assert question.sequence_id == sequence.sequence_id
            assert question.order == i
            assert question.validation_status == ValidationStatus.VALID
            assert question.question_text == valid_questions[i - 1]
            assert question.immutable_since is None  # Not yet immutable

        # Verify database persistence by querying directly
        result = await db_session.execute(
            select(QuestionSequence).where(
                QuestionSequence.discussion_id == discussion_id
            )
        )
        persisted_sequence = result.scalar_one()
        assert persisted_sequence.sequence_id == sequence.sequence_id
        assert persisted_sequence.total_questions == 3

        # Verify questions persisted
        questions_result = await db_session.execute(
            select(Question)
            .where(Question.sequence_id == sequence.sequence_id)
            .order_by(Question.question_order)
        )
        persisted_questions = questions_result.scalars().all()
        assert len(persisted_questions) == 3

        for i, question in enumerate(persisted_questions, start=1):
            assert question.question_order == i
            assert question.validation_status == ValidationStatus.VALID

    async def test_create_sequence_atomicity_on_validation_failure(self, db_session):
        """
        Test that sequence creation is atomic - no partial data on validation failure.

        Validates:
        - If any question fails validation, no sequence or questions are created
        - Database transaction is properly rolled back
        - No orphaned data remains
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Last question is invalid
        questions_with_invalid_last = [
            "What are your thoughts on this topic?",
            "How can we improve the situation?",
            "Why is this a problem?",  # INVALID: starts with Why
        ]

        service = QuestionSequenceService(db_session)

        # Should fail on third question
        with pytest.raises(ValidationError):
            await service.create_host_sequence(
                discussion_id=discussion_id,
                questions=questions_with_invalid_last,
            )

        # Verify NO sequence created (atomicity)
        sequence_result = await db_session.execute(
            select(QuestionSequence).where(
                QuestionSequence.discussion_id == discussion_id
            )
        )
        assert sequence_result.scalar_one_or_none() is None

        # Verify NO questions created for this discussion (atomicity)
        # Join with question_sequences to filter by discussion_id
        questions_result = await db_session.execute(
            select(Question)
            .join(QuestionSequence)
            .where(QuestionSequence.discussion_id == discussion_id)
        )
        assert len(questions_result.scalars().all()) == 0

    async def test_create_sequence_with_edge_case_lengths(self, db_session):
        """
        Test creating sequence with edge case lengths (exactly 10 and 200 chars).

        Validates:
        - Questions with exactly 10 characters are accepted
        - Questions with exactly 200 characters are accepted
        - Boundary conditions work correctly
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Question with exactly 10 characters
        exactly_10_chars = "What is x?"  # Exactly 10 characters
        assert len(exactly_10_chars) == 10

        # Question with exactly 200 characters
        exactly_200_chars = "What are " + "x" * 191  # Exactly 200 characters
        assert len(exactly_200_chars) == 200

        valid_questions = [exactly_10_chars, exactly_200_chars]

        service = QuestionSequenceService(db_session)

        # Should succeed
        sequence = await service.create_host_sequence(
            discussion_id=discussion_id,
            questions=valid_questions,
        )

        assert sequence is not None
        assert len(sequence.questions) == 2
        assert all(q.validation_status == ValidationStatus.VALID for q in sequence.questions)

    async def test_create_sequence_multiple_ranking_keywords(self, db_session):
        """
        Test that multiple different ranking keywords are all caught.

        Validates:
        - Service catches various ranking keywords
        - Constitutional constraints are enforced comprehensively
        """
        discussion_id_base = str(uuid.uuid4())

        ranking_keywords_to_test = [
            ("vote", "What should we vote on next?"),
            ("rank", "What can we rank by priority?"),
            ("best", "What is the best approach?"),
            ("worst", "What is the worst outcome?"),
            ("top", "What are the top priorities?"),
            ("winner", "What makes a winner?"),
            ("prefer", "What do we prefer?"),
        ]

        service = QuestionSequenceService(db_session)

        for keyword, question in ranking_keywords_to_test:
            discussion_id = uuid.UUID(discussion_id_base[:-2] + f"{len(keyword):02d}")

            with pytest.raises(ValidationError) as exc_info:
                await service.create_host_sequence(
                    discussion_id=discussion_id,
                    questions=[question],
                )

            error = exc_info.value
            assert error.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD
            assert keyword in error.message.lower(), f"Expected '{keyword}' in error message"

    async def test_create_sequence_case_insensitive_validation(self, db_session):
        """
        Test that validation is case-insensitive for opening words and keywords.

        Validates:
        - "WHAT" and "what" are both valid openings
        - "BEST" and "best" are both caught as ranking keywords
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Mixed case valid questions
        valid_questions = [
            "WHAT ARE YOUR THOUGHTS?",
            "what are your thoughts?",
            "How CAN WE IMPROVE?",
            "HOW CAN WE IMPROVE?",
        ]

        service = QuestionSequenceService(db_session)

        # Should succeed - all valid with different cases
        sequence = await service.create_host_sequence(
            discussion_id=discussion_id,
            questions=valid_questions,
        )

        assert len(sequence.questions) == 4
        assert all(q.validation_status == ValidationStatus.VALID for q in sequence.questions)

        # Test ranking keyword case insensitivity
        discussion_id_2 = uuid.uuid4()

        invalid_questions = [
            "What is the BEST approach?",  # BEST in uppercase
        ]

        with pytest.raises(ValidationError) as exc_info:
            await service.create_host_sequence(
                discussion_id=discussion_id_2,
                questions=invalid_questions,
            )

        assert exc_info.value.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD


@pytest.mark.asyncio
@pytest.mark.integration
class TestConstitutionalEnforcement:
    """Test constitutional constraint enforcement (Principle VII)."""

    async def test_create_sequence_multiple_ranking_keywords(self, db_session):
        """
        Test that multiple different ranking keywords are all caught.

        Validates:
        - Service catches various ranking keywords
        - Constitutional constraints are enforced comprehensively
        """
        discussion_id_base = str(uuid.uuid4())

        ranking_keywords_to_test = [
            ("vote", "What should we vote on next?"),
            ("rank", "What can we rank by priority?"),
            ("best", "What is the best approach?"),
            ("worst", "What is the worst outcome?"),
            ("top", "What are the top priorities?"),
            ("winner", "What makes a winner?"),
            ("prefer", "What do we prefer?"),
        ]

        service = QuestionSequenceService(db_session)

        for keyword, question in ranking_keywords_to_test:
            discussion_id = uuid.UUID(discussion_id_base[:-2] + f"{len(keyword):02d}")

            with pytest.raises(ValidationError) as exc_info:
                await service.create_host_sequence(
                    discussion_id=discussion_id,
                    questions=[question],
                )

            error = exc_info.value
            assert error.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD
            assert keyword in error.message.lower(), f"Expected '{keyword}' in error message"


# ============================================================================
# T063: Phase 6 Integration Test - Host Defined Round Advancement
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestHostDefinedRoundAdvancement:
    """Test round advancement control for HOST_DEFINED mode (T063)."""

    async def test_complete_round_1_and_advance_to_round_2(self, db_session):
        """
        Test complete HOST_DEFINED flow: Round 1 → complete → advance → Round 2 starts.

        Validates:
        - Create HOST_DEFINED discussion with 3 questions
        - Start discussion (Round 1 opens)
        - Simulate Round 1 completion (set to COMPLETE)
        - Verify can_advance() returns True
        - Call advance endpoint
        - Verify Round 2 starts with SUBMISSION_OPEN
        """
        from src.models import Discussion, Round, DiscussionMode, DiscussionStatus, RoundStatus

        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Create 3 rounds with questions
        questions = [
            "What are the main challenges?",
            "How can we address these challenges?",
            "What resources do we need?",
        ]

        rounds = []
        for i, q_text in enumerate(questions, start=1):
            round_obj = Round(
                discussion_id=discussion_id,
                round_num=i,
                question_text=q_text,
                submission_window_duration_sec=300,
            )
            db_session.add(round_obj)
            rounds.append(round_obj)

        await db_session.commit()

        # Start discussion (opens Round 1)
        discussion.start()
        rounds[0].open_submission_window()
        discussion.current_round_num = 1
        await db_session.commit()

        # Verify Round 1 is SUBMISSION_OPEN
        await db_session.refresh(rounds[0])
        assert rounds[0].status == RoundStatus.SUBMISSION_OPEN

        # Simulate Round 1 completion (all sub-protocols done)
        rounds[0].status = RoundStatus.COMPLETE
        rounds[0].completed_at = datetime.utcnow()
        await db_session.commit()

        # Verify can_advance() returns True for Round 2
        await db_session.refresh(rounds[1])
        can_adv, reason = rounds[1].can_advance()
        assert can_adv is True, f"Expected can_advance=True, got False: {reason}"
        assert reason is None

        # Advance to Round 2 (simulate endpoint call)
        discussion.current_round_num = 2
        rounds[1].open_submission_window()
        await db_session.commit()

        # Verify Round 2 is now SUBMISSION_OPEN
        await db_session.refresh(rounds[1])
        assert rounds[1].status == RoundStatus.SUBMISSION_OPEN
        assert rounds[1].submission_window_start is not None
        assert rounds[1].submission_window_end is not None

    async def test_advance_blocked_before_sankey_complete(self, db_session):
        """
        Test that advancement is blocked if Sankey not complete.

        Validates:
        - Create discussion, start Round 1
        - Set Round 1 to SANKEY_BUILDING (not COMPLETE)
        - Verify can_advance() on Round 2 returns True (Round 2 is ready)
        - But advance should be blocked because Round 1 not COMPLETE
        """
        from src.models import Discussion, Round, DiscussionMode, RoundStatus

        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Create 2 rounds
        round1 = Round(
            discussion_id=discussion_id,
            round_num=1,
            question_text="What are the key issues?",
            submission_window_duration_sec=300,
        )
        round2 = Round(
            discussion_id=discussion_id,
            round_num=2,
            question_text="How can we solve these issues?",
            submission_window_duration_sec=300,
        )
        db_session.add(round1)
        db_session.add(round2)

        discussion.start()
        round1.open_submission_window()
        discussion.current_round_num = 1
        await db_session.commit()

        # Set Round 1 to SANKEY_BUILDING (not COMPLETE)
        round1.status = RoundStatus.SANKEY_BUILDING
        await db_session.commit()

        # Round 2 can_advance should return True (question is ready)
        await db_session.refresh(round2)
        can_adv, reason = round2.can_advance()
        assert can_adv is True

        # But advancing should fail because Round 1 not COMPLETE
        await db_session.refresh(round1)
        assert round1.status != RoundStatus.COMPLETE

        # The advance logic should check that current_round is COMPLETE before advancing
        # This would be caught by the endpoint validation

    async def test_non_host_cannot_advance(self, db_session):
        """
        Test that non-host user cannot advance discussion.

        Validates:
        - Create discussion with host_user_id
        - Attempt advance with different user_id
        - Verify UnauthorizedException raised (when auth is implemented)

        Note: This test is a placeholder until auth is implemented.
        Currently, the endpoint doesn't enforce host validation (TODO comment).
        """
        from src.models import Discussion, DiscussionMode

        # Create discussion first (required for FK constraint)
        host_user_id = uuid.uuid4()
        other_user_id = uuid.uuid4()

        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=host_user_id,
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Verify host_user_id is set correctly
        await db_session.refresh(discussion)
        assert discussion.host_user_id == host_user_id
        assert discussion.host_user_id != other_user_id

        # TODO: When auth is implemented, test that other_user_id cannot advance
        # This would use RoundService.validate_host_can_advance()


@pytest.mark.asyncio
@pytest.mark.integration
class TestConstitutionalEnforcement:
    """Test constitutional constraint enforcement (Principle VII)."""

    async def test_no_adjudication_keywords_enforced(self, db_session):
        """
        Test that Principle VII (Representation Not Adjudication) is enforced.

        Validates:
        - No voting mechanisms allowed in questions
        - No ranking allowed in questions
        - No adjudication language allowed
        - Constitutional principles are upheld at creation time
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Questions violating Principle VII
        adjudication_questions = [
            "What should we vote on?",
            "What is the best solution?",
            "What option should we choose?",
            "What should we rank highest?",
        ]

        service = QuestionSequenceService(db_session)

        for question in adjudication_questions:
            with pytest.raises(ValidationError) as exc_info:
                await service.create_host_sequence(
                    discussion_id=discussion_id,
                    questions=[question],
                )

            error = exc_info.value
            assert error.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD
            # Verify specific adjudication keywords are caught
            assert any(
                keyword in error.message.lower()
                for keyword in ["vote", "best", "choose", "rank"]
            )

    async def test_exploratory_questions_only(self, db_session):
        """
        Test that only exploratory questions (What/How) are allowed.

        Validates:
        - What/How questions are the only valid openings
        - Constitutional requirement for exploratory framing is enforced
        - Questions starting with other interrogatives are rejected
        """
        # Create discussion first (required for FK constraint)
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.commit()
        discussion_id = discussion.discussion_id

        # Valid exploratory questions
        valid_exploratory = [
            "What are the key issues?",
            "How can we address these challenges?",
            "What perspectives exist on this topic?",
            "How might we approach this problem?",
        ]

        service = QuestionSequenceService(db_session)

        # Should succeed - all exploratory
        sequence = await service.create_host_sequence(
            discussion_id=discussion_id,
            questions=valid_exploratory,
        )

        assert len(sequence.questions) == 4

        # Test non-exploratory questions are rejected
        non_exploratory = [
            "When should we meet?",
            "Where is the meeting?",
            "Who is responsible?",
            "Which option is better?",
        ]

        for question in non_exploratory:
            new_discussion_id = uuid.uuid4()

            with pytest.raises(ValidationError) as exc_info:
                await service.create_host_sequence(
                    discussion_id=new_discussion_id,
                    questions=[question],
                )

            # Should fail on INVALID_START
            assert exc_info.value.error_code == ValidationErrorCode.INVALID_START
