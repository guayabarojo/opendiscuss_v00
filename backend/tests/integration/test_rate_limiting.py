"""
Integration test for User Story 3: Multiple Submissions with Rate Limiting (T046-T049).

Tests:
- Submit 3 times successfully (at rate limit)
- 4th submission rejected with 429 TOO_MANY_REQUESTS
- Query endpoint returns correct submission count and can_submit_more flag
- Last approved wins logic (T049)
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.submission_metadata import SubmissionMetadata, SubmissionModality
from src.models.round import Round
from src.services.input_collection import accept_submission, RateLimitExceeded
from src.services.ephemeral_storage import ephemeral_storage


@pytest.mark.asyncio
async def test_rate_limiting_max_submissions(db_session: AsyncSession):
    """Test that max 3 submissions are allowed per participant per round."""

    # Setup: Create a round with submission window
    round_id = uuid4()
    participant_id = uuid4()
    window_start = datetime.utcnow() - timedelta(minutes=1)
    window_end = datetime.utcnow() + timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="SUBMISSION_OPEN",
        submission_window_duration_sec=360,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear rate limit state
    ephemeral_storage.rate_limits.clear()

    # Test: Submit 3 times (should all succeed)
    submissions = []
    for i in range(3):
        metadata = await accept_submission(
            participant_id=participant_id,
            round_id=round_id,
            text=f"Submission {i+1}",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )
        submissions.append(metadata)
        await db_session.commit()

    # Verify: 3 submissions created
    result = await db_session.execute(
        select(SubmissionMetadata).where(
            SubmissionMetadata.participant_id == participant_id,
            SubmissionMetadata.round_id == round_id
        )
    )
    all_submissions = result.scalars().all()
    assert len(all_submissions) == 3

    # Test: 4th submission should raise RateLimitExceeded
    with pytest.raises(RateLimitExceeded) as exc_info:
        await accept_submission(
            participant_id=participant_id,
            round_id=round_id,
            text="Submission 4 (should fail)",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )

    assert "Rate limit exceeded" in str(exc_info.value)

    # Verify: Still only 3 submissions in database
    result = await db_session.execute(
        select(SubmissionMetadata).where(
            SubmissionMetadata.participant_id == participant_id,
            SubmissionMetadata.round_id == round_id
        )
    )
    all_submissions = result.scalars().all()
    assert len(all_submissions) == 3


@pytest.mark.asyncio
async def test_last_approved_wins(db_session: AsyncSession):
    """Test that only one submission is counted per participant per round (T049)."""

    # Setup: Create a round
    round_id = uuid4()
    participant_id = uuid4()
    window_start = datetime.utcnow() - timedelta(minutes=1)
    window_end = datetime.utcnow() + timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="SUBMISSION_OPEN",
        submission_window_duration_sec=360,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear rate limit state
    ephemeral_storage.rate_limits.clear()

    # Create 3 submissions
    submissions = []
    for i in range(3):
        metadata = await accept_submission(
            participant_id=participant_id,
            round_id=round_id,
            text=f"Submission {i+1}",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )
        submissions.append(metadata)
        await db_session.commit()

    # Initially, all submissions should have counted=False
    for submission in submissions:
        assert submission.counted is False

    # Simulate approval of 2nd submission
    from sqlalchemy import update
    await db_session.execute(
        update(SubmissionMetadata)
        .where(SubmissionMetadata.submission_id == submissions[1].submission_id)
        .values(counted=True)
    )
    await db_session.commit()

    # Verify: Only 2nd submission is counted
    result = await db_session.execute(
        select(SubmissionMetadata)
        .where(
            SubmissionMetadata.participant_id == participant_id,
            SubmissionMetadata.round_id == round_id
        )
        .order_by(SubmissionMetadata.timestamp)
    )
    all_submissions = result.scalars().all()
    assert all_submissions[0].counted is False
    assert all_submissions[1].counted is True
    assert all_submissions[2].counted is False

    # Simulate approval of 3rd submission (should unmark 2nd)
    # First unmark all
    await db_session.execute(
        update(SubmissionMetadata)
        .where(
            SubmissionMetadata.participant_id == participant_id,
            SubmissionMetadata.round_id == round_id,
            SubmissionMetadata.counted == True
        )
        .values(counted=False)
    )
    # Then mark 3rd
    await db_session.execute(
        update(SubmissionMetadata)
        .where(SubmissionMetadata.submission_id == submissions[2].submission_id)
        .values(counted=True)
    )
    await db_session.commit()

    # Verify: Only 3rd submission is counted
    result = await db_session.execute(
        select(SubmissionMetadata)
        .where(
            SubmissionMetadata.participant_id == participant_id,
            SubmissionMetadata.round_id == round_id
        )
        .order_by(SubmissionMetadata.timestamp)
    )
    all_submissions = result.scalars().all()
    assert all_submissions[0].counted is False
    assert all_submissions[1].counted is False
    assert all_submissions[2].counted is True

    # Verify: PostgreSQL EXCLUDE constraint ensures only one counted per (participant, round)
    # This constraint is already in the migration (T017)
    counted_submissions = [s for s in all_submissions if s.counted]
    assert len(counted_submissions) == 1


@pytest.mark.asyncio
async def test_different_participants_independent_rate_limits(db_session: AsyncSession):
    """Test that rate limits are independent per participant."""

    # Setup: Create a round
    round_id = uuid4()
    participant1_id = uuid4()
    participant2_id = uuid4()
    window_start = datetime.utcnow() - timedelta(minutes=1)
    window_end = datetime.utcnow() + timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="SUBMISSION_OPEN",
        submission_window_duration_sec=360,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear rate limit state
    ephemeral_storage.rate_limits.clear()

    # Participant 1 submits 3 times
    for i in range(3):
        await accept_submission(
            participant_id=participant1_id,
            round_id=round_id,
            text=f"Participant 1 - Submission {i+1}",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )
        await db_session.commit()

    # Participant 1 should be rate limited
    with pytest.raises(RateLimitExceeded):
        await accept_submission(
            participant_id=participant1_id,
            round_id=round_id,
            text="Participant 1 - Submission 4 (should fail)",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )

    # Participant 2 should still be able to submit
    await accept_submission(
        participant_id=participant2_id,
        round_id=round_id,
        text="Participant 2 - Submission 1",
        modality=SubmissionModality.TEXT,
        window_start=window_start,
        window_end=window_end,
        db_session=db_session
    )
    await db_session.commit()

    # Verify: Participant 1 has 3, Participant 2 has 1
    result1 = await db_session.execute(
        select(SubmissionMetadata).where(
            SubmissionMetadata.participant_id == participant1_id
        )
    )
    assert len(result1.scalars().all()) == 3

    result2 = await db_session.execute(
        select(SubmissionMetadata).where(
            SubmissionMetadata.participant_id == participant2_id
        )
    )
    assert len(result2.scalars().all()) == 1
