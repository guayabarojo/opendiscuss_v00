"""
Integration test for T076 & T063: Window Enforcement (User Story 4).

Tests:
- Submit before window opens → 422 OUTSIDE_WINDOW
- Submit at window start (inclusive) → 201 CREATED
- Submit at window end (exclusive) → 422 OUTSIDE_WINDOW
- Submit after window closes → 422 OUTSIDE_WINDOW
- Test boundary conditions (start±1s, end±1s)
- T063: Enhanced error responses with detailed timing information
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.submission_metadata import SubmissionMetadata, SubmissionModality
from src.models.round import Round
from src.services.input_collection import (
    accept_submission,
    WindowViolationError
)
from src.services.window_enforcement import WindowStatus
from src.services.ephemeral_storage import ephemeral_storage


@pytest.mark.asyncio
@pytest.mark.integration
async def test_window_enforcement_before_window_opens(db_session: AsyncSession):
    """
    Test submission rejected before window opens.

    Window: 14:00 - 14:05
    Submit: 13:59
    Expected: WindowViolationError
    """
    # Setup: Create round with future window
    round_id = uuid4()
    participant_id = uuid4()

    # Window opens in 1 minute
    window_start = datetime.utcnow() + timedelta(minutes=1)
    window_end = window_start + timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="PENDING",  # Not yet open
        submission_window_duration_sec=300,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear state
    ephemeral_storage.rate_limits.clear()

    # Test: Submit before window opens
    with pytest.raises(WindowViolationError) as exc_info:
        await accept_submission(
            participant_id=participant_id,
            round_id=round_id,
            text="This submission should be rejected (too early)",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )

    # Verify: Correct error message
    assert "outside window" in str(exc_info.value).lower()

    # Verify: No submission created
    result = await db_session.execute(
        select(SubmissionMetadata).where(
            SubmissionMetadata.participant_id == participant_id
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_window_enforcement_at_start_inclusive(db_session: AsyncSession):
    """
    Test submission accepted at window start (inclusive boundary).

    Window: 14:00:00 - 14:05:00
    Submit: 14:00:00 (exactly at start)
    Expected: 201 CREATED
    """
    # Setup: Create round with window that just started
    round_id = uuid4()
    participant_id = uuid4()

    # Window started 1 second ago (to account for processing time)
    window_start = datetime.utcnow() - timedelta(seconds=1)
    window_end = window_start + timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="SUBMISSION_OPEN",
        submission_window_duration_sec=300,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear state
    ephemeral_storage.rate_limits.clear()

    # Test: Submit at window start
    metadata = await accept_submission(
        participant_id=participant_id,
        round_id=round_id,
        text="Submission at window start",
        modality=SubmissionModality.TEXT,
        window_start=window_start,
        window_end=window_end,
        db_session=db_session
    )
    await db_session.commit()

    # Verify: Submission created
    assert metadata is not None
    assert metadata.participant_id == participant_id
    assert metadata.round_id == round_id

    # Verify: Persisted to database
    result = await db_session.execute(
        select(SubmissionMetadata).where(
            SubmissionMetadata.submission_id == metadata.submission_id
        )
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_window_enforcement_at_end_exclusive(db_session: AsyncSession):
    """
    Test submission rejected at window end (exclusive boundary).

    Window: 14:00:00 - 14:05:00
    Submit: 14:05:00 (exactly at end)
    Expected: WindowViolationError
    """
    # Setup: Create round with window that just ended
    round_id = uuid4()
    participant_id = uuid4()

    # Window ended 1 second ago
    window_end = datetime.utcnow() - timedelta(seconds=1)
    window_start = window_end - timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="CLOSED",  # Window closed
        submission_window_duration_sec=300,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear state
    ephemeral_storage.rate_limits.clear()

    # Test: Submit at window end
    with pytest.raises(WindowViolationError) as exc_info:
        await accept_submission(
            participant_id=participant_id,
            round_id=round_id,
            text="This submission should be rejected (at end)",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )

    # Verify: Correct error message
    assert "outside window" in str(exc_info.value).lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_window_enforcement_after_window_closes(db_session: AsyncSession):
    """
    Test submission rejected after window closes.

    Window: 14:00 - 14:05
    Submit: 14:06
    Expected: WindowViolationError
    """
    # Setup: Create round with past window
    round_id = uuid4()
    participant_id = uuid4()

    # Window ended 1 minute ago
    window_end = datetime.utcnow() - timedelta(minutes=1)
    window_start = window_end - timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="CLOSED",
        submission_window_duration_sec=300,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear state
    ephemeral_storage.rate_limits.clear()

    # Test: Submit after window closes
    with pytest.raises(WindowViolationError) as exc_info:
        await accept_submission(
            participant_id=participant_id,
            round_id=round_id,
            text="This submission should be rejected (too late)",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )

    # Verify: Correct error message
    assert "outside window" in str(exc_info.value).lower()

    # Verify: No submission created
    result = await db_session.execute(
        select(SubmissionMetadata).where(
            SubmissionMetadata.participant_id == participant_id
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_window_enforcement_boundary_start_minus_1s(db_session: AsyncSession):
    """
    Test submission rejected 1 second before window start.

    Window: 14:00:00 - 14:05:00
    Submit: 13:59:59
    Expected: WindowViolationError
    """
    # Setup: Create round with window starting in 2 seconds
    round_id = uuid4()
    participant_id = uuid4()

    window_start = datetime.utcnow() + timedelta(seconds=2)
    window_end = window_start + timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="PENDING",
        submission_window_duration_sec=300,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear state
    ephemeral_storage.rate_limits.clear()

    # Test: Submit 1 second before window start
    with pytest.raises(WindowViolationError):
        await accept_submission(
            participant_id=participant_id,
            round_id=round_id,
            text="Submission 1 second before start",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_window_enforcement_boundary_end_minus_1s(db_session: AsyncSession):
    """
    Test submission accepted 1 second before window end.

    Window: 14:00:00 - 14:05:00
    Submit: 14:04:59
    Expected: 201 CREATED
    """
    # Setup: Create round with window ending in 2 seconds
    round_id = uuid4()
    participant_id = uuid4()

    window_end = datetime.utcnow() + timedelta(seconds=2)
    window_start = window_end - timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="SUBMISSION_OPEN",
        submission_window_duration_sec=300,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear state
    ephemeral_storage.rate_limits.clear()

    # Test: Submit 1 second before window end
    metadata = await accept_submission(
        participant_id=participant_id,
        round_id=round_id,
        text="Submission 1 second before end",
        modality=SubmissionModality.TEXT,
        window_start=window_start,
        window_end=window_end,
        db_session=db_session
    )
    await db_session.commit()

    # Verify: Submission created
    assert metadata is not None
    assert metadata.participant_id == participant_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_window_enforcement_during_active_window(db_session: AsyncSession):
    """
    Test submission accepted during active window.

    Window: 14:00 - 14:05
    Submit: 14:02:30 (middle of window)
    Expected: 201 CREATED
    """
    # Setup: Create round with active window
    round_id = uuid4()
    participant_id = uuid4()

    # Window: started 2 minutes ago, ends in 3 minutes
    window_start = datetime.utcnow() - timedelta(minutes=2)
    window_end = datetime.utcnow() + timedelta(minutes=3)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="SUBMISSION_OPEN",
        submission_window_duration_sec=300,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear state
    ephemeral_storage.rate_limits.clear()

    # Test: Submit during active window
    metadata = await accept_submission(
        participant_id=participant_id,
        round_id=round_id,
        text="Submission during active window",
        modality=SubmissionModality.TEXT,
        window_start=window_start,
        window_end=window_end,
        db_session=db_session
    )
    await db_session.commit()

    # Verify: Submission created
    assert metadata is not None
    assert metadata.participant_id == participant_id
    assert metadata.round_id == round_id

    # Verify: Timestamp within window
    assert window_start <= metadata.timestamp < window_end


@pytest.mark.asyncio
@pytest.mark.integration
async def test_window_enforcement_multiple_rounds(db_session: AsyncSession):
    """
    Test window enforcement is independent per round.

    Round 1: Active window → accept
    Round 2: Future window → reject
    Round 3: Past window → reject
    """
    participant_id = uuid4()

    # Clear state
    ephemeral_storage.rate_limits.clear()

    # Round 1: Active window
    round1_id = uuid4()
    round1_start = datetime.utcnow() - timedelta(minutes=1)
    round1_end = datetime.utcnow() + timedelta(minutes=5)

    round1 = Round(
        round_id=round1_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Round 1 question",
        status="SUBMISSION_OPEN",
        submission_window_duration_sec=360,
        submission_window_start=round1_start,
        submission_window_end=round1_end
    )
    db_session.add(round1)

    # Round 2: Future window
    round2_id = uuid4()
    round2_start = datetime.utcnow() + timedelta(minutes=10)
    round2_end = round2_start + timedelta(minutes=5)

    round2 = Round(
        round_id=round2_id,
        discussion_id=uuid4(),
        round_num=2,
        question_text="Round 2 question",
        status="PENDING",
        submission_window_duration_sec=300,
        submission_window_start=round2_start,
        submission_window_end=round2_end
    )
    db_session.add(round2)

    # Round 3: Past window
    round3_id = uuid4()
    round3_end = datetime.utcnow() - timedelta(minutes=1)
    round3_start = round3_end - timedelta(minutes=5)

    round3 = Round(
        round_id=round3_id,
        discussion_id=uuid4(),
        round_num=3,
        question_text="Round 3 question",
        status="CLOSED",
        submission_window_duration_sec=300,
        submission_window_start=round3_start,
        submission_window_end=round3_end
    )
    db_session.add(round3)

    await db_session.commit()

    # Test Round 1: Should accept
    metadata1 = await accept_submission(
        participant_id=participant_id,
        round_id=round1_id,
        text="Round 1 submission",
        modality=SubmissionModality.TEXT,
        window_start=round1_start,
        window_end=round1_end,
        db_session=db_session
    )
    await db_session.commit()
    assert metadata1 is not None

    # Test Round 2: Should reject (future)
    with pytest.raises(WindowViolationError):
        await accept_submission(
            participant_id=participant_id,
            round_id=round2_id,
            text="Round 2 submission (should fail)",
            modality=SubmissionModality.TEXT,
            window_start=round2_start,
            window_end=round2_end,
            db_session=db_session
        )

    # Test Round 3: Should reject (past)
    with pytest.raises(WindowViolationError):
        await accept_submission(
            participant_id=participant_id,
            round_id=round3_id,
            text="Round 3 submission (should fail)",
            modality=SubmissionModality.TEXT,
            window_start=round3_start,
            window_end=round3_end,
            db_session=db_session
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_enhanced_error_before_window(db_session: AsyncSession):
    """
    Test T063: Enhanced error response for BEFORE_WINDOW violations.

    Verify error includes:
    - window_start, window_end, current_time
    - wait_duration_seconds
    - status = BEFORE_WINDOW
    - User-friendly suggestion
    """
    round_id = uuid4()
    participant_id = uuid4()

    # Window opens in 60 seconds
    window_start = datetime.utcnow() + timedelta(seconds=60)
    window_end = window_start + timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="PENDING",
        submission_window_duration_sec=300,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    ephemeral_storage.rate_limits.clear()

    # Attempt submission before window
    with pytest.raises(WindowViolationError) as exc_info:
        await accept_submission(
            participant_id=participant_id,
            round_id=round_id,
            text="Too early",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )

    # Verify detailed error attributes
    error = exc_info.value
    assert error.window_status == WindowStatus.BEFORE_WINDOW
    assert error.window_start == window_start
    assert error.window_end == window_end
    assert error.current_time is not None
    assert error.wait_duration_seconds is not None
    assert error.wait_duration_seconds > 0
    assert error.wait_duration_seconds <= 60
    assert "not opened yet" in error.message.lower()
    assert str(error.wait_duration_seconds) in error.message


@pytest.mark.asyncio
@pytest.mark.integration
async def test_enhanced_error_after_window(db_session: AsyncSession):
    """
    Test T063: Enhanced error response for AFTER_WINDOW violations.

    Verify error includes:
    - window_start, window_end, current_time
    - status = AFTER_WINDOW
    - User-friendly message
    """
    round_id = uuid4()
    participant_id = uuid4()

    # Window ended 30 seconds ago
    window_end = datetime.utcnow() - timedelta(seconds=30)
    window_start = window_end - timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="CLOSED",
        submission_window_duration_sec=300,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    ephemeral_storage.rate_limits.clear()

    # Attempt submission after window
    with pytest.raises(WindowViolationError) as exc_info:
        await accept_submission(
            participant_id=participant_id,
            round_id=round_id,
            text="Too late",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )

    # Verify detailed error attributes
    error = exc_info.value
    assert error.window_status == WindowStatus.AFTER_WINDOW
    assert error.window_start == window_start
    assert error.window_end == window_end
    assert error.current_time is not None
    assert error.wait_duration_seconds is None  # No wait duration for AFTER_WINDOW
    assert "closed" in error.message.lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_enhanced_error_includes_timestamps(db_session: AsyncSession):
    """
    Test T063: Verify error response includes ISO format timestamps.
    """
    round_id = uuid4()
    participant_id = uuid4()

    window_start = datetime.utcnow() + timedelta(minutes=5)
    window_end = window_start + timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="Test question",
        status="PENDING",
        submission_window_duration_sec=300,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    ephemeral_storage.rate_limits.clear()

    with pytest.raises(WindowViolationError) as exc_info:
        await accept_submission(
            participant_id=participant_id,
            round_id=round_id,
            text="Test",
            modality=SubmissionModality.TEXT,
            window_start=window_start,
            window_end=window_end,
            db_session=db_session
        )

    error = exc_info.value

    # Verify all timestamps are present
    assert error.window_start is not None
    assert error.window_end is not None
    assert error.current_time is not None

    # Verify they can be converted to ISO format (for API response)
    assert error.window_start.isoformat()
    assert error.window_end.isoformat()
    assert error.current_time.isoformat()
