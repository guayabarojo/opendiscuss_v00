"""
Integration tests for async discussion mode.

Tests the new ASYNCHRONOUS timing mode functionality including:
- Creating async discussions
- Manual round closure by host
- Permission enforcement (host vs participant)
- Window enforcement (permissive for async mode)
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.models.discussion import Discussion
from src.models.round import Round
from src.models.protocol_state import (
    DiscussionMode,
    DiscussionTimingMode,
    RoundStatus,
)
from src.services.window_enforcement import is_within_window


@pytest.mark.asyncio
async def test_create_async_discussion(db_session):
    """Test creating async discussion with timing config."""
    # Create async discussion
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=3,
        timing_mode=DiscussionTimingMode.ASYNCHRONOUS,
        round_duration_hours=24,
        min_submissions_for_advance=10,
        auto_advance_enabled=True,
    )

    db_session.add(discussion)
    await db_session.commit()
    await db_session.refresh(discussion)

    # Verify timing mode fields
    assert discussion.timing_mode == DiscussionTimingMode.ASYNCHRONOUS
    assert discussion.round_duration_hours == 24
    assert discussion.min_submissions_for_advance == 10
    assert discussion.auto_advance_enabled is True


@pytest.mark.asyncio
async def test_manual_close_round_as_host(
    db_session, event_bus, timing_service
):
    """Test host can manually close async round."""
    from src.services.round_service import RoundService

    # Create async discussion
    host_user_id = uuid4()
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=host_user_id,
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=3,
        timing_mode=DiscussionTimingMode.ASYNCHRONOUS,
        round_duration_hours=48,
    )
    db_session.add(discussion)
    await db_session.flush()

    # Create round in SUBMISSION_OPEN state
    round_entity = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What do you think?",
        submission_window_duration_sec=3600,
    )
    round_entity.open_submission_window()
    db_session.add(round_entity)
    await db_session.commit()
    await db_session.refresh(round_entity)

    # Host manually closes round
    round_service = RoundService(db_session, event_bus, timing_service)
    closed_round = await round_service.manual_close_submission_window(
        round_id=round_entity.round_id,
        user_id=host_user_id,
    )

    # Verify round is closed
    assert closed_round.status == RoundStatus.SUBMISSION_CLOSED


@pytest.mark.asyncio
async def test_manual_close_round_as_participant_fails(
    db_session, event_bus, timing_service
):
    """Test participant cannot close rounds (403)."""
    from src.services.round_service import RoundService

    # Create async discussion
    host_user_id = uuid4()
    participant_user_id = uuid4()  # Different from host

    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=host_user_id,
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=3,
        timing_mode=DiscussionTimingMode.ASYNCHRONOUS,
    )
    db_session.add(discussion)
    await db_session.flush()

    # Create round
    round_entity = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What do you think?",
        submission_window_duration_sec=3600,
    )
    round_entity.open_submission_window()
    db_session.add(round_entity)
    await db_session.commit()
    await db_session.refresh(round_entity)

    # Participant attempts to close round - should fail
    round_service = RoundService(db_session, event_bus, timing_service)

    with pytest.raises(PermissionError, match="Only discussion host"):
        await round_service.manual_close_submission_window(
            round_id=round_entity.round_id,
            user_id=participant_user_id,
        )


@pytest.mark.asyncio
async def test_async_window_enforcement():
    """Test submissions accepted after soft deadline in async mode."""
    window_start = datetime.utcnow()
    window_end = window_start + timedelta(hours=24)  # Soft deadline

    # Sync mode: strict enforcement
    timestamp_after_deadline = window_end + timedelta(hours=1)

    sync_result = is_within_window(
        timestamp=timestamp_after_deadline,
        window_start=window_start,
        window_end=window_end,
        timing_mode=DiscussionTimingMode.SYNCHRONOUS,
    )
    assert sync_result is False  # Rejected in sync mode

    # Async mode: permissive (only checks start)
    async_result = is_within_window(
        timestamp=timestamp_after_deadline,
        window_start=window_start,
        window_end=window_end,
        timing_mode=DiscussionTimingMode.ASYNCHRONOUS,
    )
    assert async_result is True  # Accepted in async mode


@pytest.mark.asyncio
async def test_manual_close_sync_discussion_fails(
    db_session, event_bus, timing_service
):
    """Test manual close only available for async discussions."""
    from src.services.round_service import RoundService

    # Create SYNCHRONOUS discussion
    host_user_id = uuid4()
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=host_user_id,
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=3,
        timing_mode=DiscussionTimingMode.SYNCHRONOUS,  # Not async!
    )
    db_session.add(discussion)
    await db_session.flush()

    # Create round
    round_entity = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What do you think?",
        submission_window_duration_sec=300,
    )
    round_entity.open_submission_window()
    db_session.add(round_entity)
    await db_session.commit()
    await db_session.refresh(round_entity)

    # Attempt manual close on sync discussion - should fail
    round_service = RoundService(db_session, event_bus, timing_service)

    with pytest.raises(ValueError, match="Manual close only.*ASYNCHRONOUS"):
        await round_service.manual_close_submission_window(
            round_id=round_entity.round_id,
            user_id=host_user_id,
        )


@pytest.mark.asyncio
async def test_backward_compatibility_defaults(db_session):
    """Test existing discussions default to SYNCHRONOUS mode."""
    # Create discussion without specifying timing_mode
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=3,
    )

    db_session.add(discussion)
    await db_session.commit()
    await db_session.refresh(discussion)

    # Should default to SYNCHRONOUS
    assert discussion.timing_mode == DiscussionTimingMode.SYNCHRONOUS
    assert discussion.round_duration_hours is None
    assert discussion.min_submissions_for_advance is None
    assert discussion.auto_advance_enabled is False
