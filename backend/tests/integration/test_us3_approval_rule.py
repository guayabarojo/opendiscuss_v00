"""
Integration test for T071: Last-approved-wins rule for participant summaries.

Tests that when a participant approves multiple summaries sequentially,
only the last approval is retained in the aggregation, and the previous
ApprovedSummary is properly superseded.

Constitutional Principles:
- Intent Fidelity (Principle II): Only the last approved summary represents intent
- Temporal Transparency (Principle IV): Audit trail preserved in Submission records
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.discussion import Discussion, DiscussionStatus, DiscussionMode
from src.models.round import Round, RoundStatus
from src.models.participant import Participant
from src.models.submission import Submission, SummaryStatus
from src.models.approved_summary import ApprovedSummary
from src.services.submission_service import SubmissionService
from src.services.summary_service import SummarySupersessionService


@pytest.mark.asyncio
@pytest.mark.integration
async def test_last_approved_wins_basic(db_session: AsyncSession):
    """
    Test T071: Last-approved-wins rule - basic flow.

    Flow:
    1. Submit twice (sub1, sub2)
    2. Approve sub1 (creates ApprovedSummary1)
    3. Approve sub2 (creates ApprovedSummary2, supersedes ApprovedSummary1)
    4. Verify ApprovedSummary1 deleted
    5. Verify sub1 marked SUPERSEDED
    6. Verify exactly one ApprovedSummary exists (sub2)
    7. Verify only sub2 would enter final aggregation

    Expected:
    - After approving sub1: 1 ApprovedSummary (sub1)
    - After approving sub2: 1 ApprovedSummary (sub2)
    - sub1 marked SUPERSEDED
    - sub2 marked APPROVED
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
    supersession_service = SummarySupersessionService(db=db_session)

    # ============================================================================
    # Step 1: Submit twice
    # ============================================================================
    sub1, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="First submission about improvements",
    )
    await db_session.commit()

    sub2, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Second submission with refined thoughts",
    )
    await db_session.commit()

    # ============================================================================
    # Step 2: Approve sub1 (creates ApprovedSummary1)
    # ============================================================================
    approved1 = await supersession_service.apply_last_approved_wins(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=sub1.submission_id,
        summary_text="Summary of first submission",
    )
    await db_session.commit()

    # Verify ApprovedSummary1 exists
    stmt = select(ApprovedSummary).where(
        ApprovedSummary.participant_id == participant.participant_id,
        ApprovedSummary.round_id == round_entity.round_id,
    )
    result = await db_session.execute(stmt)
    summaries_after_first_approval = result.scalars().all()

    assert len(summaries_after_first_approval) == 1, "Should have 1 ApprovedSummary after first approval"
    assert summaries_after_first_approval[0].submission_id == sub1.submission_id
    assert summaries_after_first_approval[0].summary_text == "Summary of first submission"

    # ============================================================================
    # Step 3: Approve sub2 (creates ApprovedSummary2, supersedes ApprovedSummary1)
    # ============================================================================
    approved2 = await supersession_service.apply_last_approved_wins(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=sub2.submission_id,
        summary_text="Summary of second submission",
    )
    await db_session.commit()

    # ============================================================================
    # Step 4: Verify ApprovedSummary1 deleted
    # ============================================================================
    result = await db_session.execute(stmt)
    summaries_after_second_approval = result.scalars().all()

    assert len(summaries_after_second_approval) == 1, "Should have exactly 1 ApprovedSummary (last-approved-wins)"
    assert summaries_after_second_approval[0].submission_id == sub2.submission_id
    assert summaries_after_second_approval[0].summary_text == "Summary of second submission"

    # ============================================================================
    # Step 5: Verify sub1 marked SUPERSEDED
    # ============================================================================
    await db_session.refresh(sub1)
    await db_session.refresh(sub2)

    assert sub1.summary_status == SummaryStatus.SUPERSEDED, "sub1 should be SUPERSEDED"
    assert sub2.summary_status == SummaryStatus.APPROVED, "sub2 should be APPROVED"

    # ============================================================================
    # Step 6: Verify exactly one ApprovedSummary in final aggregation
    # ============================================================================
    # Count approved summaries for this participant in this round
    count_stmt = (
        select(func.count())
        .select_from(ApprovedSummary)
        .where(
            ApprovedSummary.participant_id == participant.participant_id,
            ApprovedSummary.round_id == round_entity.round_id,
        )
    )
    result = await db_session.execute(count_stmt)
    count = result.scalar_one()

    assert count == 1, "Exactly one ApprovedSummary should exist for clustering"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_last_approved_wins_three_approvals(db_session: AsyncSession):
    """
    Test last-approved-wins with 3 sequential approvals.

    Flow:
    1. Submit 3 times
    2. Approve sub1
    3. Approve sub2 (supersedes sub1)
    4. Approve sub3 (supersedes sub2)
    5. Verify only sub3 has ApprovedSummary
    6. Verify sub1 and sub2 marked SUPERSEDED

    Validates that the rule works for multiple re-approvals.
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

    participant = Participant(
        discussion_id=discussion.discussion_id,
        user_id=uuid4(),
        first_round=1,
    )
    db_session.add(participant)
    await db_session.flush()

    submission_service = SubmissionService(db=db_session)
    supersession_service = SummarySupersessionService(db=db_session)

    # Submit 3 times
    sub1, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="First submission",
    )
    sub2, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Second submission",
    )
    sub3, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Third submission",
    )
    await db_session.commit()

    # Approve sub1
    await supersession_service.apply_last_approved_wins(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=sub1.submission_id,
        summary_text="Summary 1",
    )
    await db_session.commit()

    # Approve sub2 (supersedes sub1)
    await supersession_service.apply_last_approved_wins(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=sub2.submission_id,
        summary_text="Summary 2",
    )
    await db_session.commit()

    # Approve sub3 (supersedes sub2)
    await supersession_service.apply_last_approved_wins(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=sub3.submission_id,
        summary_text="Summary 3",
    )
    await db_session.commit()

    # Verify only sub3 has ApprovedSummary
    stmt = select(ApprovedSummary).where(
        ApprovedSummary.participant_id == participant.participant_id,
        ApprovedSummary.round_id == round_entity.round_id,
    )
    result = await db_session.execute(stmt)
    summaries = result.scalars().all()

    assert len(summaries) == 1, "Only one ApprovedSummary should exist"
    assert summaries[0].submission_id == sub3.submission_id
    assert summaries[0].summary_text == "Summary 3"

    # Verify sub1 and sub2 marked SUPERSEDED
    await db_session.refresh(sub1)
    await db_session.refresh(sub2)
    await db_session.refresh(sub3)

    assert sub1.summary_status == SummaryStatus.SUPERSEDED
    assert sub2.summary_status == SummaryStatus.SUPERSEDED
    assert sub3.summary_status == SummaryStatus.APPROVED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_last_approved_wins_approval_order_matters(db_session: AsyncSession):
    """
    Test that approval order matters, not submission order.

    Flow:
    1. Submit sub1, sub2, sub3 (in that order)
    2. Approve sub3 first
    3. Approve sub1 second (supersedes sub3)
    4. Verify sub1 is the final approved summary (not sub3)

    Validates that it's truly "last approved wins", not "last submitted wins".
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
        question_text="What are your priorities?",
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
    supersession_service = SummarySupersessionService(db=db_session)

    # Submit 3 times in order
    sub1, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="First submission",
    )
    sub2, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Second submission",
    )
    sub3, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Third submission",
    )
    await db_session.commit()

    # Approve sub3 first (last submitted)
    await supersession_service.apply_last_approved_wins(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=sub3.submission_id,
        summary_text="Summary of third submission",
    )
    await db_session.commit()

    # Approve sub1 second (first submitted, but last approved)
    await supersession_service.apply_last_approved_wins(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=sub1.submission_id,
        summary_text="Summary of first submission",
    )
    await db_session.commit()

    # Verify sub1 is the final approved summary
    stmt = select(ApprovedSummary).where(
        ApprovedSummary.participant_id == participant.participant_id,
        ApprovedSummary.round_id == round_entity.round_id,
    )
    result = await db_session.execute(stmt)
    summaries = result.scalars().all()

    assert len(summaries) == 1
    assert summaries[0].submission_id == sub1.submission_id, "sub1 should be the approved summary (last approved)"
    assert summaries[0].summary_text == "Summary of first submission"

    # Verify statuses
    await db_session.refresh(sub1)
    await db_session.refresh(sub2)
    await db_session.refresh(sub3)

    assert sub1.summary_status == SummaryStatus.APPROVED
    assert sub2.summary_status == SummaryStatus.SUPERSEDED
    assert sub3.summary_status == SummaryStatus.SUPERSEDED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ensure_single_approved_summary_validator(db_session: AsyncSession):
    """
    Test ensure_single_approved_summary validation method.

    Validates that the invariant checker correctly validates that exactly
    one ApprovedSummary exists per participant per round.
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

    participant = Participant(
        discussion_id=discussion.discussion_id,
        user_id=uuid4(),
        first_round=1,
    )
    db_session.add(participant)
    await db_session.flush()

    submission_service = SubmissionService(db=db_session)
    supersession_service = SummarySupersessionService(db=db_session)

    # Initially, no approved summary
    result = await supersession_service.ensure_single_approved_summary(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
    )
    assert result is None, "Should return None when no approved summary exists"

    # Create and approve a submission
    sub1, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="First submission",
    )
    await db_session.commit()

    await supersession_service.apply_last_approved_wins(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=sub1.submission_id,
        summary_text="Summary 1",
    )
    await db_session.commit()

    # Validate single approved summary
    result = await supersession_service.ensure_single_approved_summary(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
    )
    assert result is not None, "Should return the approved summary"
    assert result.submission_id == sub1.submission_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_last_approved_wins_clustering_integration(db_session: AsyncSession):
    """
    Test that only the last approved summary would enter clustering.

    Flow:
    1. Two participants each submit multiple times
    2. Each approves one summary
    3. Verify exactly 2 ApprovedSummaries total (one per participant)
    4. Verify these would be the only summaries entering clustering

    Validates Intent Fidelity principle at the round level.
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
    supersession_service = SummarySupersessionService(db=db_session)

    # Participant 1: Submit 3 times, approve last
    p1_subs = []
    for i in range(3):
        sub, _ = await submission_service.handle_multiple_submissions(
            participant_id=participant1.participant_id,
            round_id=round_entity.round_id,
            submission_text=f"P1 submission {i+1}",
        )
        p1_subs.append(sub)
        await db_session.commit()

    await supersession_service.apply_last_approved_wins(
        participant_id=participant1.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=p1_subs[2].submission_id,
        summary_text="P1 final summary",
    )
    await db_session.commit()

    # Participant 2: Submit 2 times, approve first
    p2_subs = []
    for i in range(2):
        sub, _ = await submission_service.handle_multiple_submissions(
            participant_id=participant2.participant_id,
            round_id=round_entity.round_id,
            submission_text=f"P2 submission {i+1}",
        )
        p2_subs.append(sub)
        await db_session.commit()

    await supersession_service.apply_last_approved_wins(
        participant_id=participant2.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=p2_subs[0].submission_id,
        summary_text="P2 final summary",
    )
    await db_session.commit()

    # Verify exactly 2 ApprovedSummaries total for the round
    count_stmt = (
        select(func.count())
        .select_from(ApprovedSummary)
        .where(ApprovedSummary.round_id == round_entity.round_id)
    )
    result = await db_session.execute(count_stmt)
    total_count = result.scalar_one()

    assert total_count == 2, "Exactly 2 ApprovedSummaries should exist for clustering"

    # Verify correct summaries approved
    stmt = select(ApprovedSummary).where(
        ApprovedSummary.round_id == round_entity.round_id
    )
    result = await db_session.execute(stmt)
    approved_summaries = result.scalars().all()

    approved_submission_ids = {s.submission_id for s in approved_summaries}
    assert p1_subs[2].submission_id in approved_submission_ids
    assert p2_subs[0].submission_id in approved_submission_ids

    # Verify these are the only APPROVED submissions in the round
    stmt = select(Submission).where(
        Submission.round_id == round_entity.round_id,
        Submission.summary_status == SummaryStatus.APPROVED,
    )
    result = await db_session.execute(stmt)
    approved_submissions = result.scalars().all()

    assert len(approved_submissions) == 2, "Only 2 submissions should have APPROVED status"
