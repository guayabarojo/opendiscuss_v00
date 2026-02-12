"""
Integration tests for User Story 5: Graceful Dropout Handling (Spec 002)

T069: Integration test for dropout flow with no synthetic placeholder nodes.

Tests:
1. Create round with 5 participants
2. Only 3 submit
3. Verify 2 have no counted submission
4. Verify Sankey shows natural flow reduction (no placeholder nodes)
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.discussion import Discussion, DiscussionMode
from src.models.round import Round
from src.models.participant import Participant
from src.models.submission import Submission, SummaryStatus
from src.models.approved_summary import ApprovedSummary
from src.models.protocol_state import RoundStatus, DiscussionStatus
from src.services.dropout_detection import DropoutDetectionService


@pytest.mark.asyncio
async def test_dropout_with_no_submission(db_session: AsyncSession):
    """
    T069: Test that participants who don't submit have NO counted submission.

    Scenario:
    - Create Round 1 with 5 participants
    - Only 3 submit
    - Verify 2 have no Submission or ApprovedSummary
    - Natural dropout - no synthetic nodes
    """
    # Create discussion
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=2,
        status=DiscussionStatus.ACTIVE,
        current_round_num=1
    )
    db_session.add(discussion)
    await db_session.flush()

    # Create Round 1
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What is your initial thought?",
        submission_window_duration_sec=300,
        status=RoundStatus.SUBMISSION_OPEN
    )
    round1.submission_window_start = datetime.utcnow()
    round1.submission_window_end = datetime.utcnow() + timedelta(minutes=5)
    db_session.add(round1)
    await db_session.flush()

    # Create 5 participants
    participants = []
    for i in range(5):
        participant = Participant(
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1
        )
        db_session.add(participant)
        participants.append(participant)
    await db_session.flush()

    # Only 3 participants submit
    submitted_participants = participants[:3]
    dropout_participants = participants[3:]

    for participant in submitted_participants:
        submission = Submission(
            participant_id=participant.participant_id,
            round_id=round1.round_id,
            submission_text=f"Submission from participant {participant.participant_id}",
            modality="text",
            summary_status=SummaryStatus.APPROVED
        )
        db_session.add(submission)
        await db_session.flush()

        # Create approved summary (counted submission)
        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round1.round_id,
            submission_id=submission.submission_id,
            summary_text=f"Summary for {participant.participant_id}"
        )
        db_session.add(approved_summary)

    await db_session.commit()

    # VERIFICATION: Check submission counts
    # Count total participants
    total_participants_result = await db_session.execute(
        select(func.count(Participant.participant_id))
        .where(Participant.discussion_id == discussion.discussion_id)
    )
    total_participants = total_participants_result.scalar()
    assert total_participants == 5, "Should have 5 participants"

    # Count submissions
    submission_count_result = await db_session.execute(
        select(func.count(Submission.submission_id))
        .where(Submission.round_id == round1.round_id)
    )
    submission_count = submission_count_result.scalar()
    assert submission_count == 3, "Should have exactly 3 submissions"

    # Count approved summaries (counted submissions)
    approved_count_result = await db_session.execute(
        select(func.count(ApprovedSummary.summary_id))
        .where(ApprovedSummary.round_id == round1.round_id)
    )
    approved_count = approved_count_result.scalar()
    assert approved_count == 3, "Should have exactly 3 approved summaries"

    # Verify dropout participants have NO submission
    for dropout_participant in dropout_participants:
        submission_result = await db_session.execute(
            select(Submission)
            .where(
                Submission.participant_id == dropout_participant.participant_id,
                Submission.round_id == round1.round_id
            )
        )
        submission = submission_result.scalar_one_or_none()
        assert submission is None, f"Dropout participant {dropout_participant.participant_id} should have NO submission"

        # Verify no approved summary
        approved_result = await db_session.execute(
            select(ApprovedSummary)
            .where(
                ApprovedSummary.participant_id == dropout_participant.participant_id,
                ApprovedSummary.round_id == round1.round_id
            )
        )
        approved = approved_result.scalar_one_or_none()
        assert approved is None, f"Dropout participant {dropout_participant.participant_id} should have NO approved summary"

    # Verify no synthetic placeholder nodes
    # Query all approved summaries - should be exactly 3, no extras
    all_approved_result = await db_session.execute(
        select(ApprovedSummary)
        .where(ApprovedSummary.round_id == round1.round_id)
    )
    all_approved = all_approved_result.scalars().all()
    assert len(all_approved) == 3, "Should have exactly 3 approved summaries, no synthetic nodes"

    # Verify all approved summaries have valid participant_ids
    for approved_summary in all_approved:
        assert approved_summary.participant_id in [p.participant_id for p in submitted_participants], \
            "All approved summaries should belong to participants who actually submitted"


@pytest.mark.asyncio
async def test_dropout_detection_across_rounds(db_session: AsyncSession):
    """
    T069: Test dropout detection across multiple rounds.

    Scenario:
    - Round 1: 5 participants submit
    - Round 2: Only 3 participants submit (2 dropout)
    - Verify dropout detection identifies the 2 dropouts
    - Verify Sankey flow mass naturally reduces from 5 to 3
    """
    # Create discussion
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=3,
        status=DiscussionStatus.ACTIVE,
        current_round_num=2
    )
    db_session.add(discussion)
    await db_session.flush()

    # Create Round 1
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="Round 1 question?",
        submission_window_duration_sec=300,
        status=RoundStatus.COMPLETE
    )
    db_session.add(round1)
    await db_session.flush()

    # Create Round 2
    round2 = Round(
        discussion_id=discussion.discussion_id,
        round_num=2,
        question_text="Round 2 question?",
        submission_window_duration_sec=300,
        status=RoundStatus.SUBMISSION_OPEN
    )
    round2.submission_window_start = datetime.utcnow()
    round2.submission_window_end = datetime.utcnow() + timedelta(minutes=5)
    db_session.add(round2)
    await db_session.flush()

    # Create 5 participants - all submit in Round 1
    participants = []
    for i in range(5):
        participant = Participant(
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1
        )
        db_session.add(participant)
        participants.append(participant)
    await db_session.flush()

    # All 5 submit in Round 1
    for participant in participants:
        submission = Submission(
            participant_id=participant.participant_id,
            round_id=round1.round_id,
            submission_text=f"Round 1 submission from {participant.participant_id}",
            modality="text",
            summary_status=SummaryStatus.APPROVED
        )
        db_session.add(submission)
        await db_session.flush()

        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round1.round_id,
            submission_id=submission.submission_id,
            summary_text=f"Round 1 summary for {participant.participant_id}"
        )
        db_session.add(approved_summary)

    # Only 3 submit in Round 2 (indices 0, 1, 2)
    continuing_participants = participants[:3]
    dropout_participants = participants[3:]

    for participant in continuing_participants:
        submission = Submission(
            participant_id=participant.participant_id,
            round_id=round2.round_id,
            submission_text=f"Round 2 submission from {participant.participant_id}",
            modality="text",
            summary_status=SummaryStatus.APPROVED
        )
        db_session.add(submission)
        await db_session.flush()

        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round2.round_id,
            submission_id=submission.submission_id,
            summary_text=f"Round 2 summary for {participant.participant_id}"
        )
        db_session.add(approved_summary)

    await db_session.commit()

    # Use dropout detection service to identify dropouts
    dropout_service = DropoutDetectionService(db_session)
    dropout_ids = await dropout_service.get_round_dropouts(
        round_id=round2.round_id,
        discussion_id=discussion.discussion_id
    )

    # VERIFICATION: Should detect 2 dropouts
    assert len(dropout_ids) == 2, "Should detect 2 dropouts"
    assert set(dropout_ids) == {p.participant_id for p in dropout_participants}, \
        "Should identify correct dropout participants"

    # Verify Round 1 flow mass = 5
    round1_count_result = await db_session.execute(
        select(func.count(ApprovedSummary.summary_id))
        .where(ApprovedSummary.round_id == round1.round_id)
    )
    round1_count = round1_count_result.scalar()
    assert round1_count == 5, "Round 1 should have 5 approved summaries"

    # Verify Round 2 flow mass = 3 (natural reduction)
    round2_count_result = await db_session.execute(
        select(func.count(ApprovedSummary.summary_id))
        .where(ApprovedSummary.round_id == round2.round_id)
    )
    round2_count = round2_count_result.scalar()
    assert round2_count == 3, "Round 2 should have 3 approved summaries (natural reduction)"

    # Verify no synthetic nodes in Round 2
    # Total approved summaries should equal continuing participants only
    round2_approved_result = await db_session.execute(
        select(ApprovedSummary.participant_id)
        .where(ApprovedSummary.round_id == round2.round_id)
    )
    round2_participant_ids = set(round2_approved_result.scalars().all())
    expected_participant_ids = {p.participant_id for p in continuing_participants}
    assert round2_participant_ids == expected_participant_ids, \
        "Round 2 approved summaries should only include continuing participants, no synthetic nodes"


@pytest.mark.asyncio
async def test_dropout_analytics_stored_in_round(db_session: AsyncSession):
    """
    T068: Test that dropout analytics are stored in Round model.

    Scenario:
    - Create Round 1 with 10 participants
    - Round 2: 5 participants dropout
    - Verify Round 2 has dropout_count = 5
    - Verify dropout_rate = 0.5
    """
    # Create discussion
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=2,
        status=DiscussionStatus.ACTIVE,
        current_round_num=2
    )
    db_session.add(discussion)
    await db_session.flush()

    # Create Round 1
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="Round 1 question?",
        submission_window_duration_sec=300,
        status=RoundStatus.COMPLETE
    )
    db_session.add(round1)
    await db_session.flush()

    # Create Round 2
    round2 = Round(
        discussion_id=discussion.discussion_id,
        round_num=2,
        question_text="Round 2 question?",
        submission_window_duration_sec=300,
        status=RoundStatus.SUBMISSION_OPEN
    )
    db_session.add(round2)
    await db_session.flush()

    # Create 10 participants
    participants = []
    for i in range(10):
        participant = Participant(
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1
        )
        db_session.add(participant)
        participants.append(participant)
    await db_session.flush()

    # All 10 submit in Round 1
    for participant in participants:
        submission = Submission(
            participant_id=participant.participant_id,
            round_id=round1.round_id,
            submission_text=f"Round 1 submission",
            modality="text",
            summary_status=SummaryStatus.APPROVED
        )
        db_session.add(submission)
        await db_session.flush()

        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round1.round_id,
            submission_id=submission.submission_id,
            summary_text=f"Round 1 summary"
        )
        db_session.add(approved_summary)

    # Only 5 submit in Round 2 (50% dropout)
    for participant in participants[:5]:
        submission = Submission(
            participant_id=participant.participant_id,
            round_id=round2.round_id,
            submission_text=f"Round 2 submission",
            modality="text",
            summary_status=SummaryStatus.APPROVED
        )
        db_session.add(submission)
        await db_session.flush()

        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round2.round_id,
            submission_id=submission.submission_id,
            summary_text=f"Round 2 summary"
        )
        db_session.add(approved_summary)

    await db_session.commit()

    # Update dropout analytics
    dropout_service = DropoutDetectionService(db_session)
    dropout_ids = await dropout_service.get_round_dropouts(
        round_id=round2.round_id,
        discussion_id=discussion.discussion_id
    )

    # Set dropout count in Round model
    round2.set_dropout_count(len(dropout_ids))
    await db_session.commit()

    # Reload round to verify
    await db_session.refresh(round2)

    # VERIFICATION: Dropout analytics stored correctly
    assert round2.dropout_count == 5, "Round 2 should have dropout_count = 5"

    # Calculate dropout rate
    dropout_rate = round2.get_dropout_rate(previous_round_participant_count=10)
    assert dropout_rate == 0.5, "Dropout rate should be 0.5 (50%)"


@pytest.mark.asyncio
async def test_participant_can_reenter_after_dropout(db_session: AsyncSession):
    """
    T069: Test that participants who drop out can re-enter in subsequent rounds.

    Scenario:
    - Participant submits in Round 1
    - Participant drops out in Round 2 (no submission)
    - Participant re-enters in Round 3 (submits again)
    - Verify participant_id remains stable
    """
    # Create discussion
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=3,
        status=DiscussionStatus.ACTIVE,
        current_round_num=3
    )
    db_session.add(discussion)
    await db_session.flush()

    # Create 3 rounds
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="Round 1 question?",
        submission_window_duration_sec=300,
        status=RoundStatus.COMPLETE
    )
    db_session.add(round1)

    round2 = Round(
        discussion_id=discussion.discussion_id,
        round_num=2,
        question_text="Round 2 question?",
        submission_window_duration_sec=300,
        status=RoundStatus.COMPLETE
    )
    db_session.add(round2)

    round3 = Round(
        discussion_id=discussion.discussion_id,
        round_num=3,
        question_text="Round 3 question?",
        submission_window_duration_sec=300,
        status=RoundStatus.SUBMISSION_OPEN
    )
    db_session.add(round3)
    await db_session.flush()

    # Create participant
    participant = Participant(
        discussion_id=discussion.discussion_id,
        user_id=uuid4(),
        first_round=1
    )
    db_session.add(participant)
    await db_session.flush()

    original_participant_id = participant.participant_id

    # Participant submits in Round 1
    submission1 = Submission(
        participant_id=participant.participant_id,
        round_id=round1.round_id,
        submission_text="Round 1 submission",
        modality="text",
        summary_status=SummaryStatus.APPROVED
    )
    db_session.add(submission1)
    await db_session.flush()

    approved1 = ApprovedSummary(
        participant_id=participant.participant_id,
        round_id=round1.round_id,
        submission_id=submission1.submission_id,
        summary_text="Round 1 summary"
    )
    db_session.add(approved1)

    # Participant DOES NOT submit in Round 2 (dropout)
    # No submission, no approved summary

    # Participant re-enters in Round 3
    submission3 = Submission(
        participant_id=participant.participant_id,
        round_id=round3.round_id,
        submission_text="Round 3 submission",
        modality="text",
        summary_status=SummaryStatus.APPROVED
    )
    db_session.add(submission3)
    await db_session.flush()

    approved3 = ApprovedSummary(
        participant_id=participant.participant_id,
        round_id=round3.round_id,
        submission_id=submission3.submission_id,
        summary_text="Round 3 summary"
    )
    db_session.add(approved3)

    await db_session.commit()

    # VERIFICATION: participant_id remains stable
    await db_session.refresh(participant)
    assert participant.participant_id == original_participant_id, \
        "Participant ID should remain stable across rounds"

    # Verify submissions exist in Round 1 and Round 3 only
    round1_submission_result = await db_session.execute(
        select(Submission)
        .where(
            Submission.participant_id == participant.participant_id,
            Submission.round_id == round1.round_id
        )
    )
    assert round1_submission_result.scalar_one_or_none() is not None, \
        "Participant should have submission in Round 1"

    round2_submission_result = await db_session.execute(
        select(Submission)
        .where(
            Submission.participant_id == participant.participant_id,
            Submission.round_id == round2.round_id
        )
    )
    assert round2_submission_result.scalar_one_or_none() is None, \
        "Participant should have NO submission in Round 2 (dropout)"

    round3_submission_result = await db_session.execute(
        select(Submission)
        .where(
            Submission.participant_id == participant.participant_id,
            Submission.round_id == round3.round_id
        )
    )
    assert round3_submission_result.scalar_one_or_none() is not None, \
        "Participant should have submission in Round 3 (re-entry)"

    # Verify approved summaries exist in Round 1 and Round 3 only
    round1_approved_result = await db_session.execute(
        select(ApprovedSummary)
        .where(
            ApprovedSummary.participant_id == participant.participant_id,
            ApprovedSummary.round_id == round1.round_id
        )
    )
    assert round1_approved_result.scalar_one_or_none() is not None, \
        "Participant should have approved summary in Round 1"

    round2_approved_result = await db_session.execute(
        select(ApprovedSummary)
        .where(
            ApprovedSummary.participant_id == participant.participant_id,
            ApprovedSummary.round_id == round2.round_id
        )
    )
    assert round2_approved_result.scalar_one_or_none() is None, \
        "Participant should have NO approved summary in Round 2 (dropout)"

    round3_approved_result = await db_session.execute(
        select(ApprovedSummary)
        .where(
            ApprovedSummary.participant_id == participant.participant_id,
            ApprovedSummary.round_id == round3.round_id
        )
    )
    assert round3_approved_result.scalar_one_or_none() is not None, \
        "Participant should have approved summary in Round 3 (re-entry)"
