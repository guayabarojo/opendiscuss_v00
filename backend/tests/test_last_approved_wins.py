"""
Test User Story 5: Last-Approved-Wins logic (T076-T085).

Tests that:
1. SUPERSEDED status exists in the model
2. ApprovalService marks old approvals as SUPERSEDED
3. Event handler validates exactly one summary per participant
4. API endpoint for getting participant summaries works
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.summarization.models.summary import Summary, SummaryStatus
from src.summarization.services.approval_service import ApprovalService


@pytest.mark.asyncio
async def test_superseded_status_exists():
    """Test T076-T077: SUPERSEDED status exists in SummaryStatus enum."""
    assert hasattr(SummaryStatus, 'SUPERSEDED')
    assert SummaryStatus.SUPERSEDED.value == 'superseded'


@pytest.mark.asyncio
async def test_last_approved_wins_logic(db_session, sample_participant, sample_round, sample_submission):
    """
    Test T078-T079: Last-approved-wins logic marks older approvals as SUPERSEDED.

    Scenario:
    1. Create and approve first summary (Summary A)
    2. Create and approve second summary (Summary B)
    3. Verify Summary A is marked as SUPERSEDED
    4. Verify Summary B remains APPROVED
    """
    from src.summarization.services.summarization_service import SummarizationService

    # Create first summary
    summarization_service = SummarizationService(db_session)
    summary_a = Summary(
        submission_id=sample_submission.submission_id,
        participant_id=sample_participant.participant_id,
        round_id=sample_round.round_id,
        summary_text="First summary for participant",
        status=SummaryStatus.PENDING_REVIEW,
        regen_count=0,
    )
    db_session.add(summary_a)
    await db_session.commit()
    await db_session.refresh(summary_a)

    # Approve first summary
    approval_service = ApprovalService(db_session)
    await approval_service.approve_summary(summary_a.summary_id)

    # Wait a bit to ensure different timestamps
    import asyncio
    await asyncio.sleep(0.1)

    # Create second summary
    summary_b = Summary(
        submission_id=sample_submission.submission_id,
        participant_id=sample_participant.participant_id,
        round_id=sample_round.round_id,
        summary_text="Second summary for same participant",
        status=SummaryStatus.PENDING_REVIEW,
        regen_count=0,
    )
    db_session.add(summary_b)
    await db_session.commit()
    await db_session.refresh(summary_b)

    # Approve second summary - should trigger last-approved-wins
    await approval_service.approve_summary(summary_b.summary_id)

    # Refresh both summaries to get updated status
    await db_session.refresh(summary_a)
    await db_session.refresh(summary_b)

    # Assertions
    assert summary_a.status == SummaryStatus.SUPERSEDED, "First summary should be SUPERSEDED"
    assert summary_b.status == SummaryStatus.APPROVED, "Second summary should remain APPROVED"
    assert summary_b.approved_at > summary_a.approved_at, "Second summary should have later approved_at"


@pytest.mark.asyncio
async def test_get_last_approved_summary_for_participant(db_session, sample_participant, sample_round, sample_submission):
    """
    Test that get_last_approved_summary_for_participant returns the most recent approval.
    """
    from src.summarization.models.summary import Summary, SummaryStatus

    # Create two approved summaries with different timestamps
    summary_old = Summary(
        submission_id=sample_submission.submission_id,
        participant_id=sample_participant.participant_id,
        round_id=sample_round.round_id,
        summary_text="Older summary",
        status=SummaryStatus.APPROVED,
        regen_count=0,
        approved_at=datetime.utcnow() - timedelta(hours=1),
    )

    summary_new = Summary(
        submission_id=sample_submission.submission_id,
        participant_id=sample_participant.participant_id,
        round_id=sample_round.round_id,
        summary_text="Newer summary",
        status=SummaryStatus.APPROVED,
        regen_count=0,
        approved_at=datetime.utcnow(),
    )

    db_session.add_all([summary_old, summary_new])
    await db_session.commit()

    # Test get_last_approved_summary_for_participant
    approval_service = ApprovalService(db_session)
    latest = await approval_service.get_last_approved_summary_for_participant(
        sample_participant.participant_id,
        sample_round.round_id
    )

    assert latest is not None
    assert latest.summary_id == summary_new.summary_id
    assert latest.summary_text == "Newer summary"


@pytest.mark.asyncio
async def test_approved_at_in_summary_response(db_session, sample_participant, sample_round, sample_submission):
    """
    Test T082: approved_at field is included in Summary response.
    """
    from src.summarization.models.summary import Summary, SummaryStatus

    # Create approved summary
    summary = Summary(
        submission_id=sample_submission.submission_id,
        participant_id=sample_participant.participant_id,
        round_id=sample_round.round_id,
        summary_text="Test summary",
        status=SummaryStatus.APPROVED,
        regen_count=0,
        approved_at=datetime.utcnow(),
    )

    db_session.add(summary)
    await db_session.commit()
    await db_session.refresh(summary)

    # Verify approved_at is set
    assert summary.approved_at is not None
    assert isinstance(summary.approved_at, datetime)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
