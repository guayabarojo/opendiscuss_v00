"""
Integration test for T069: Multiple submissions per participant with last-approved-wins.

Tests the complete workflow:
1. Participant submits multiple times (up to 3 submissions)
2. Approve one submission (e.g., the 2nd one)
3. Verify other submissions marked as SUPERSEDED
4. Verify only approved submission enters clustering

Constitutional Principles:
- Intent Fidelity (Principle II): Only the last approved summary enters clustering
- Parallel-First (Principle I): Multiple participants can iterate independently
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
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
async def test_multiple_submissions_with_supersession(db_session: AsyncSession):
    """
    Test T069: Multiple submissions per participant with last-approved-wins rule.

    Flow:
    1. Create discussion and round in SUBMISSION_OPEN state
    2. Participant submits 3 times (sub1, sub2, sub3)
    3. Approve sub2 (creates ApprovedSummary2)
    4. Verify sub1 and sub3 marked SUPERSEDED
    5. Verify only sub2 has ApprovedSummary
    6. Verify only sub2 would enter clustering

    Expected:
    - All 3 submissions stored in database
    - Only sub2 has summary_status = APPROVED
    - sub1 and sub3 have summary_status = SUPERSEDED
    - Exactly one ApprovedSummary exists for the participant
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
        question_text="What challenges do you face with remote work?",
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

    # Initialize services
    submission_service = SubmissionService(db=db_session)
    supersession_service = SummarySupersessionService(db=db_session)

    # ============================================================================
    # Step 1: Participant submits 3 times
    # ============================================================================
    sub1, remaining1 = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="First submission about remote work challenges",
    )
    await db_session.commit()

    assert remaining1 == 2  # 2 submissions remaining
    assert sub1.summary_status == SummaryStatus.PENDING

    sub2, remaining2 = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Second submission with more details",
    )
    await db_session.commit()

    assert remaining2 == 1  # 1 submission remaining
    assert sub2.summary_status == SummaryStatus.PENDING

    sub3, remaining3 = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Third submission with refined thoughts",
    )
    await db_session.commit()

    assert remaining3 == 0  # No submissions remaining
    assert sub3.summary_status == SummaryStatus.PENDING

    # ============================================================================
    # Step 2: Approve sub2 (middle submission)
    # ============================================================================
    approved_summary = await supersession_service.apply_last_approved_wins(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=sub2.submission_id,
        summary_text="Summary: Remote work challenges include communication gaps",
    )
    await db_session.commit()

    # ============================================================================
    # Step 3: Verify sub1 and sub3 marked SUPERSEDED
    # ============================================================================
    await db_session.refresh(sub1)
    await db_session.refresh(sub2)
    await db_session.refresh(sub3)

    assert sub1.summary_status == SummaryStatus.SUPERSEDED, "sub1 should be SUPERSEDED"
    assert sub2.summary_status == SummaryStatus.APPROVED, "sub2 should be APPROVED"
    assert sub3.summary_status == SummaryStatus.SUPERSEDED, "sub3 should be SUPERSEDED"

    # ============================================================================
    # Step 4: Verify only one ApprovedSummary exists
    # ============================================================================
    stmt = select(ApprovedSummary).where(
        ApprovedSummary.participant_id == participant.participant_id,
        ApprovedSummary.round_id == round_entity.round_id,
    )
    result = await db_session.execute(stmt)
    approved_summaries = result.scalars().all()

    assert len(approved_summaries) == 1, "Exactly one ApprovedSummary should exist"
    assert approved_summaries[0].submission_id == sub2.submission_id
    assert approved_summaries[0].summary_text == "Summary: Remote work challenges include communication gaps"

    # ============================================================================
    # Step 5: Verify all submissions still exist (no deletion)
    # ============================================================================
    stmt = select(Submission).where(
        Submission.participant_id == participant.participant_id,
        Submission.round_id == round_entity.round_id,
    )
    result = await db_session.execute(stmt)
    all_submissions = result.scalars().all()

    assert len(all_submissions) == 3, "All 3 submissions should be stored"

    # Verify count by status
    status_counts = {}
    for submission in all_submissions:
        status = submission.summary_status
        status_counts[status] = status_counts.get(status, 0) + 1

    assert status_counts[SummaryStatus.APPROVED] == 1
    assert status_counts[SummaryStatus.SUPERSEDED] == 2
    assert SummaryStatus.PENDING not in status_counts


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_approvals_last_wins(db_session: AsyncSession):
    """
    Test that when a participant approves multiple summaries sequentially,
    only the last approval is retained.

    Flow:
    1. Submit twice (sub1, sub2)
    2. Approve sub1 (creates ApprovedSummary1)
    3. Approve sub2 (creates ApprovedSummary2, deletes ApprovedSummary1)
    4. Verify only ApprovedSummary2 exists
    5. Verify sub1 marked SUPERSEDED
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
        question_text="What are your thoughts on collaboration?",
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

    # Submit twice
    sub1, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="First submission about collaboration",
    )
    await db_session.commit()

    sub2, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        submission_text="Second submission with different perspective",
    )
    await db_session.commit()

    # Approve sub1 first
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
    summaries = result.scalars().all()
    assert len(summaries) == 1
    assert summaries[0].submission_id == sub1.submission_id

    # Approve sub2 (should supersede sub1)
    approved2 = await supersession_service.apply_last_approved_wins(
        participant_id=participant.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=sub2.submission_id,
        summary_text="Summary of second submission",
    )
    await db_session.commit()

    # Verify only ApprovedSummary2 exists
    result = await db_session.execute(stmt)
    summaries = result.scalars().all()
    assert len(summaries) == 1, "Only one ApprovedSummary should exist (last-approved-wins)"
    assert summaries[0].submission_id == sub2.submission_id
    assert summaries[0].summary_text == "Summary of second submission"

    # Verify sub1 marked SUPERSEDED
    await db_session.refresh(sub1)
    await db_session.refresh(sub2)
    assert sub1.summary_status == SummaryStatus.SUPERSEDED
    assert sub2.summary_status == SummaryStatus.APPROVED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_participants_iterate_independently(db_session: AsyncSession):
    """
    Test that multiple participants can iterate independently without interference.

    Validates Parallel-First principle: Each participant's iteration is isolated.
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

    # Create 2 participants
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

    # Participant 1 submits twice, approves first
    p1_sub1, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant1.participant_id,
        round_id=round_entity.round_id,
        submission_text="P1 submission 1",
    )
    p1_sub2, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant1.participant_id,
        round_id=round_entity.round_id,
        submission_text="P1 submission 2",
    )
    await db_session.commit()

    await supersession_service.apply_last_approved_wins(
        participant_id=participant1.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=p1_sub1.submission_id,
        summary_text="P1 summary 1",
    )
    await db_session.commit()

    # Participant 2 submits 3 times, approves last
    p2_sub1, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant2.participant_id,
        round_id=round_entity.round_id,
        submission_text="P2 submission 1",
    )
    p2_sub2, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant2.participant_id,
        round_id=round_entity.round_id,
        submission_text="P2 submission 2",
    )
    p2_sub3, _ = await submission_service.handle_multiple_submissions(
        participant_id=participant2.participant_id,
        round_id=round_entity.round_id,
        submission_text="P2 submission 3",
    )
    await db_session.commit()

    await supersession_service.apply_last_approved_wins(
        participant_id=participant2.participant_id,
        round_id=round_entity.round_id,
        new_submission_id=p2_sub3.submission_id,
        summary_text="P2 summary 3",
    )
    await db_session.commit()

    # Verify P1 has exactly one approved summary (sub1)
    stmt = select(ApprovedSummary).where(
        ApprovedSummary.participant_id == participant1.participant_id,
        ApprovedSummary.round_id == round_entity.round_id,
    )
    result = await db_session.execute(stmt)
    p1_summaries = result.scalars().all()
    assert len(p1_summaries) == 1
    assert p1_summaries[0].submission_id == p1_sub1.submission_id

    # Verify P2 has exactly one approved summary (sub3)
    stmt = select(ApprovedSummary).where(
        ApprovedSummary.participant_id == participant2.participant_id,
        ApprovedSummary.round_id == round_entity.round_id,
    )
    result = await db_session.execute(stmt)
    p2_summaries = result.scalars().all()
    assert len(p2_summaries) == 1
    assert p2_summaries[0].submission_id == p2_sub3.submission_id

    # Verify P1's supersession didn't affect P2
    await db_session.refresh(p2_sub1)
    await db_session.refresh(p2_sub2)
    await db_session.refresh(p2_sub3)
    assert p2_sub1.summary_status == SummaryStatus.SUPERSEDED
    assert p2_sub2.summary_status == SummaryStatus.SUPERSEDED
    assert p2_sub3.summary_status == SummaryStatus.APPROVED

    # Verify P2's supersession didn't affect P1
    await db_session.refresh(p1_sub1)
    await db_session.refresh(p1_sub2)
    assert p1_sub1.summary_status == SummaryStatus.APPROVED
    assert p1_sub2.summary_status == SummaryStatus.SUPERSEDED
