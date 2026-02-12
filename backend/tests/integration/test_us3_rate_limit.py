"""
Integration test for T070: Rate limit enforcement (max 3 submissions per round).

Tests that participants cannot exceed the rate limit of 3 submissions per round,
and that the error response is clear and actionable.

Constitutional Principles:
- Intent Fidelity (Principle II): Rate limits prevent spam while allowing iteration
- Parallel-First (Principle I): Rate limits per participant don't affect others
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.discussion import Discussion, DiscussionStatus, DiscussionMode
from src.models.round import Round, RoundStatus
from src.models.participant import Participant
from src.services.submission_service import SubmissionService, MAX_SUBMISSIONS_PER_ROUND
from src.api.error_handlers import RateLimitExceededException


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rate_limit_enforcement(db_session: AsyncSession):
    """
    Test T070: Participant cannot exceed 3 submissions per round.

    Flow:
    1. Participant submits 3 times successfully
    2. Attempt 4th submission
    3. Verify RateLimitExceededException raised
    4. Verify error message includes clear rate limit details
    5. Verify remaining_submissions decrements correctly

    Expected:
    - First 3 submissions succeed with remaining_submissions = 2, 1, 0
    - 4th submission raises RateLimitExceededException with HTTP 429
    - Error message: "Rate limit exceeded. Maximum 3 submissions per round."
    """
    # Setup: Create discussion, round, and participant
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=1,
        status=DiscussionStatus.ACTIVE,
    )
    db_session.add(discussion)
    await db_session.flush()

    round_entity = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What improvements would you suggest?",
        submission_window_duration_sec=300,
    )
    # Manually set to SUBMISSION_OPEN for testing
    round_entity.status = RoundStatus.SUBMISSION_OPEN
    round_entity.submission_window_start = datetime.utcnow()
    round_entity.submission_window_end = datetime.utcnow() + timedelta(minutes=5)
    db_session.add(round_entity)
    await db_session.flush()

    participant = Participant(
        discussion_id=discussion.discussion_id,
        user_id=uuid4(),
        first_round=1,
    )
    db_session.add(participant)
    await db_session.flush()

    submission_service = SubmissionService(db=db_session)

    # ============================================================================
    # Step 1: Submit 3 times successfully
    # ============================================================================

    # First submission
    sub1, remaining1 = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="First submission",
    )
    await db_session.commit()

    assert remaining1 == 2, "After 1st submission, should have 2 remaining"
    assert sub1.submission_id is not None

    # Second submission
    sub2, remaining2 = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Second submission",
    )
    await db_session.commit()

    assert remaining2 == 1, "After 2nd submission, should have 1 remaining"
    assert sub2.submission_id is not None

    # Third submission
    sub3, remaining3 = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Third submission",
    )
    await db_session.commit()

    assert remaining3 == 0, "After 3rd submission, should have 0 remaining"
    assert sub3.submission_id is not None

    # ============================================================================
    # Step 2: Attempt 4th submission - should raise RateLimitExceededException
    # ============================================================================

    with pytest.raises(RateLimitExceededException) as exc_info:
        await submission_service.handle_multiple_submissions(
            participant_id=participant.participant_id,
            round_id=round_entity.round_id,
            submission_text="Fourth submission - should be rejected",
        )

    # ============================================================================
    # Step 3: Verify exception details
    # ============================================================================

    exception = exc_info.value

    # Verify exception attributes
    assert exception.resource == f"submissions for round {round_entity.round_id}"
    assert exception.limit == MAX_SUBMISSIONS_PER_ROUND
    assert exception.current == 3
    assert exception.reset_at == round_entity.submission_window_end

    # Verify error message format
    error_message = str(exception)
    assert "Rate limit exceeded" in error_message
    assert f"{exception.current}/{exception.limit}" in error_message
    assert "resets at" in error_message

    # ============================================================================
    # Step 4: Verify get_remaining_submissions returns 0
    # ============================================================================

    remaining = await submission_service.get_remaining_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
    )
    assert remaining == 0, "Should have 0 submissions remaining after hitting limit"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rate_limit_per_participant(db_session: AsyncSession):
    """
    Test that rate limits are enforced per participant (isolation).

    Flow:
    1. Participant 1 exhausts their 3 submissions
    2. Participant 2 can still submit 3 times
    3. Verify P1's limit doesn't affect P2

    Validates Parallel-First principle.
    """
    # Setup
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=1,
        status=DiscussionStatus.ACTIVE,
    )
    db_session.add(discussion)
    await db_session.flush()

    round_entity = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are your thoughts?",
        submission_window_duration_sec=300,
    )
    round_entity.status = RoundStatus.SUBMISSION_OPEN
    round_entity.submission_window_start = datetime.utcnow()
    round_entity.submission_window_end = datetime.utcnow() + timedelta(minutes=5)
    db_session.add(round_entity)
    await db_session.flush()

    participant1 = Participant(
        discussion_id=discussion.discussion_id,
        user_id=uuid4(),
        first_round=1,
    )
    participant2 = Participant(
        discussion_id=discussion.discussion_id,
        user_id=uuid4(),
        first_round=1,
    )
    db_session.add_all([participant1, participant2])
    await db_session.flush()

    submission_service = SubmissionService(db=db_session)

    # Participant 1 exhausts limit
    for i in range(3):
        await submission_service.handle_multiple_submissions(
            participant_id=participant1.participant_id,
            round_id=round_entity.round_id,
            submission_text=f"P1 submission {i+1}",
        )
        await db_session.commit()

    # Verify P1 cannot submit again
    with pytest.raises(RateLimitExceededException):
        await submission_service.handle_multiple_submissions(
            participant_id=participant1.participant_id,
            round_id=round_entity.round_id,
            submission_text="P1 submission 4 - should fail",
        )

    # Participant 2 can still submit 3 times
    for i in range(3):
        _, remaining = await submission_service.handle_multiple_submissions(
            participant_id=participant2.participant_id,
            round_id=round_entity.round_id,
            submission_text=f"P2 submission {i+1}",
        )
        await db_session.commit()
        assert remaining == 2 - i

    # Verify P2 cannot submit again
    with pytest.raises(RateLimitExceededException):
        await submission_service.handle_multiple_submissions(
            participant_id=participant2.participant_id,
            round_id=round_entity.round_id,
            submission_text="P2 submission 4 - should fail",
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rate_limit_per_round(db_session: AsyncSession):
    """
    Test that rate limits are reset per round.

    Flow:
    1. Participant exhausts 3 submissions in Round 1
    2. Round 2 opens
    3. Participant can submit 3 more times in Round 2

    Validates that rate limits are scoped to rounds.
    """
    # Setup
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=2,
        status=DiscussionStatus.ACTIVE,
    )
    db_session.add(discussion)
    await db_session.flush()

    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are your thoughts on topic 1?",
        submission_window_duration_sec=300,
    )
    round1.status = RoundStatus.SUBMISSION_OPEN
    round1.submission_window_start = datetime.utcnow()
    round1.submission_window_end = datetime.utcnow() + timedelta(minutes=5)
    db_session.add(round1)

    round2 = Round(
        discussion_id=discussion.discussion_id,
        round_num=2,
        question_text="What are your thoughts on topic 2?",
        submission_window_duration_sec=300,
    )
    round2.status = RoundStatus.SUBMISSION_OPEN
    round2.submission_window_start = datetime.utcnow()
    round2.submission_window_end = datetime.utcnow() + timedelta(minutes=5)
    db_session.add(round2)
    await db_session.flush()

    participant = Participant(
        discussion_id=discussion.discussion_id,
        user_id=uuid4(),
        first_round=1,
    )
    db_session.add(participant)
    await db_session.flush()

    submission_service = SubmissionService(db=db_session)

    # Exhaust Round 1 limit
    for i in range(3):
        await submission_service.handle_multiple_submissions(
            participant_id=participant.participant_id,
            round_id=round1.round_id,
            submission_text=f"Round 1 submission {i+1}",
        )
        await db_session.commit()

    # Verify Round 1 limit reached
    with pytest.raises(RateLimitExceededException):
        await submission_service.handle_multiple_submissions(
            participant_id=participant.participant_id,
            round_id=round1.round_id,
            submission_text="Round 1 submission 4 - should fail",
        )

    # Round 2 submissions should succeed (fresh limit)
    for i in range(3):
        _, remaining = await submission_service.handle_multiple_submissions(
            participant_id=participant.participant_id,
            round_id=round2.round_id,
            submission_text=f"Round 2 submission {i+1}",
        )
        await db_session.commit()
        assert remaining == 2 - i

    # Verify Round 2 limit reached
    with pytest.raises(RateLimitExceededException):
        await submission_service.handle_multiple_submissions(
            participant_id=participant.participant_id,
            round_id=round2.round_id,
            submission_text="Round 2 submission 4 - should fail",
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_remaining_submissions(db_session: AsyncSession):
    """
    Test get_remaining_submissions method returns correct counts.

    Validates that participants can query how many submissions they have left.
    """
    # Setup
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=1,
        status=DiscussionStatus.ACTIVE,
    )
    db_session.add(discussion)
    await db_session.flush()

    round_entity = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What improvements would you suggest?",
        submission_window_duration_sec=300,
    )
    round_entity.status = RoundStatus.SUBMISSION_OPEN
    round_entity.submission_window_start = datetime.utcnow()
    round_entity.submission_window_end = datetime.utcnow() + timedelta(minutes=5)
    db_session.add(round_entity)
    await db_session.flush()

    participant = Participant(
        discussion_id=discussion.discussion_id,
        user_id=uuid4(),
        first_round=1,
    )
    db_session.add(participant)
    await db_session.flush()

    submission_service = SubmissionService(db=db_session)

    # Check remaining before any submissions
    remaining = await submission_service.get_remaining_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
    )
    assert remaining == 3

    # After 1 submission
    await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="First submission",
    )
    await db_session.commit()

    remaining = await submission_service.get_remaining_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
    )
    assert remaining == 2

    # After 2 submissions
    await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Second submission",
    )
    await db_session.commit()

    remaining = await submission_service.get_remaining_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
    )
    assert remaining == 1

    # After 3 submissions
    await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Third submission",
    )
    await db_session.commit()

    remaining = await submission_service.get_remaining_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
    )
    assert remaining == 0
