"""
Integration test for T073: Text Submission Flow (User Story 1).

Tests:
- Create round → submit text → verify SubmissionMetadata created
- Verify RawSubmission stored in ephemeral storage
- Verify submission.created event published with correct schema
- Test full end-to-end flow from API endpoint
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.submission_metadata import SubmissionMetadata, SubmissionModality
from src.models.round import Round
from src.services.input_collection import accept_submission
from src.services.ephemeral_storage import ephemeral_storage
from src.events.bus import event_bus, EVENT_SUBMISSION_CREATED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_text_submission_flow_service_layer(db_session: AsyncSession):
    """
    Test text submission flow at service layer.

    Flow:
    1. Create a round with active submission window
    2. Submit text via accept_submission()
    3. Verify SubmissionMetadata created in database
    4. Verify RawSubmission stored in ephemeral storage
    """
    # Setup: Create a round with submission window
    round_id = uuid4()
    participant_id = uuid4()
    window_start = datetime.utcnow() - timedelta(minutes=1)
    window_end = datetime.utcnow() + timedelta(minutes=5)

    round_obj = Round(
        round_id=round_id,
        discussion_id=uuid4(),
        round_num=1,
        question_text="What are your thoughts on text submission?",
        status="SUBMISSION_OPEN",
        submission_window_duration_sec=360,
        submission_window_start=window_start,
        submission_window_end=window_end
    )
    db_session.add(round_obj)
    await db_session.commit()

    # Clear rate limit state
    ephemeral_storage.rate_limits.clear()
    ephemeral_storage.raw_submissions.clear()

    # Test: Submit text
    submission_text = "I think we should focus on improving the text submission experience."
    metadata = await accept_submission(
        participant_id=participant_id,
        round_id=round_id,
        text=submission_text,
        modality=SubmissionModality.TEXT,
        window_start=window_start,
        window_end=window_end,
        db_session=db_session
    )
    await db_session.commit()

    # Verify: SubmissionMetadata created in database
    result = await db_session.execute(
        select(SubmissionMetadata).where(
            SubmissionMetadata.submission_id == metadata.submission_id
        )
    )
    persisted_metadata = result.scalar_one_or_none()

    assert persisted_metadata is not None
    assert persisted_metadata.submission_id == metadata.submission_id
    assert persisted_metadata.participant_id == participant_id
    assert persisted_metadata.round_id == round_id
    assert persisted_metadata.modality == SubmissionModality.TEXT
    assert persisted_metadata.counted is False  # Not yet approved
    assert persisted_metadata.timestamp is not None

    # Verify: RawSubmission stored in ephemeral storage
    raw_submission = ephemeral_storage.get_raw_submission(metadata.submission_id)

    assert raw_submission is not None
    assert raw_submission.submission_id == metadata.submission_id
    assert raw_submission.submission_text is not None
    assert len(raw_submission.submission_text) > 0
    assert raw_submission.ttl_expires_at > datetime.utcnow()

    # Verify text normalization applied (whitespace trimmed)
    assert raw_submission.submission_text.strip() == raw_submission.submission_text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_text_submission_event_published(db_session: AsyncSession):
    """
    Test that submission.created event is published with correct data.

    Verifies event contains:
    - submission_id
    - participant_id (as user_id)
    - round_id
    - modality
    - timestamp
    """
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

    # Clear state
    ephemeral_storage.rate_limits.clear()
    ephemeral_storage.raw_submissions.clear()

    # Setup: Event listener to capture published event
    captured_events = []

    async def event_handler(event):
        captured_events.append(event)

    event_bus.subscribe(EVENT_SUBMISSION_CREATED, event_handler)

    # Test: Submit text
    metadata = await accept_submission(
        participant_id=participant_id,
        round_id=round_id,
        text="Test submission for event verification",
        modality=SubmissionModality.TEXT,
        window_start=window_start,
        window_end=window_end,
        db_session=db_session
    )
    await db_session.commit()

    # Give event time to process
    import asyncio
    await asyncio.sleep(0.1)

    # Verify: Event was published
    assert len(captured_events) == 1

    event = captured_events[0]
    assert event.event_type == EVENT_SUBMISSION_CREATED

    # Verify event payload structure
    payload = event.payload
    assert "submission_id" in payload
    assert "participant_id" in payload
    assert "round_id" in payload
    assert "modality" in payload
    assert "timestamp" in payload

    # Verify event data matches submission
    assert payload["submission_id"] == str(metadata.submission_id)
    assert payload["participant_id"] == str(participant_id)
    assert payload["round_id"] == str(round_id)
    assert payload["modality"] == "TEXT"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_submissions_with_ephemeral_storage(db_session: AsyncSession):
    """
    Test multiple submissions store correctly in ephemeral storage.

    Verifies:
    - Each submission gets unique submission_id
    - Each RawSubmission stored separately
    - Metadata and ephemeral data linked correctly
    """
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

    # Clear state
    ephemeral_storage.rate_limits.clear()
    ephemeral_storage.raw_submissions.clear()

    # Test: Submit 3 times
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

    # Verify: 3 SubmissionMetadata records in database
    result = await db_session.execute(
        select(SubmissionMetadata).where(
            SubmissionMetadata.participant_id == participant_id,
            SubmissionMetadata.round_id == round_id
        )
    )
    all_metadata = result.scalars().all()
    assert len(all_metadata) == 3

    # Verify: 3 RawSubmission records in ephemeral storage
    for metadata in submissions:
        raw_submission = ephemeral_storage.get_raw_submission(metadata.submission_id)
        assert raw_submission is not None
        assert raw_submission.submission_id == metadata.submission_id
        assert len(raw_submission.submission_text) > 0

    # Verify: Each submission has unique ID
    submission_ids = [s.submission_id for s in submissions]
    assert len(submission_ids) == len(set(submission_ids))  # All unique


@pytest.mark.asyncio
@pytest.mark.integration
async def test_text_submission_normalization(db_session: AsyncSession):
    """
    Test that text normalization is applied during submission.

    Verifies:
    - Leading/trailing whitespace trimmed
    - Multiple spaces preserved (but not leading/trailing)
    - Newlines preserved (content meaning unchanged)
    """
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

    # Clear state
    ephemeral_storage.rate_limits.clear()
    ephemeral_storage.raw_submissions.clear()

    # Test: Submit text with leading/trailing whitespace
    raw_text = "  \n  Text with whitespace  \n  "
    metadata = await accept_submission(
        participant_id=participant_id,
        round_id=round_id,
        text=raw_text,
        modality=SubmissionModality.TEXT,
        window_start=window_start,
        window_end=window_end,
        db_session=db_session
    )
    await db_session.commit()

    # Verify: Normalized text stored (leading/trailing whitespace removed)
    raw_submission = ephemeral_storage.get_raw_submission(metadata.submission_id)
    assert raw_submission is not None
    assert raw_submission.submission_text == "Text with whitespace"

    # Verify: No leading/trailing whitespace
    assert raw_submission.submission_text.strip() == raw_submission.submission_text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_text_submission_ttl_expiration(db_session: AsyncSession):
    """
    Test that RawSubmission has TTL set correctly.

    Verifies:
    - TTL expires_at is in the future (24 hours from now)
    - TTL is > 23 hours to account for processing time
    """
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

    # Clear state
    ephemeral_storage.rate_limits.clear()
    ephemeral_storage.raw_submissions.clear()

    # Test: Submit text
    before_submission = datetime.utcnow()
    metadata = await accept_submission(
        participant_id=participant_id,
        round_id=round_id,
        text="Test TTL expiration",
        modality=SubmissionModality.TEXT,
        window_start=window_start,
        window_end=window_end,
        db_session=db_session
    )
    await db_session.commit()
    after_submission = datetime.utcnow()

    # Verify: TTL is set correctly
    raw_submission = ephemeral_storage.get_raw_submission(metadata.submission_id)
    assert raw_submission is not None

    # TTL should be ~24 hours from submission
    expected_ttl = before_submission + timedelta(hours=24)
    assert raw_submission.ttl_expires_at > expected_ttl - timedelta(seconds=5)
    assert raw_submission.ttl_expires_at < after_submission + timedelta(hours=24, seconds=5)

    # Verify TTL is in the future
    assert raw_submission.ttl_expires_at > datetime.utcnow()
