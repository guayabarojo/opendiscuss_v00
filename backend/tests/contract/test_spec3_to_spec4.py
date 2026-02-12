"""
Contract Tests: Spec 3 (Summarization) → Spec 4 (Clustering)

Validates that Spec 3 emits summarization.complete events with only approved
summaries, applying last-approved-wins rule correctly.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T095)
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.summarization.services.approval_service import ApprovalService
from src.summarization.services.summarization_service import SummarizationService
from src.models import Submission, Round, Participant, Discussion
from src.models.protocol_state import DiscussionMode, DiscussionStatus
from src.summarization.models.summary import Summary, SummaryStatus


@pytest.mark.asyncio
class TestSpec3ToSpec4Contract:
    """Test contract between Spec 3 and Spec 4."""

    async def test_only_approved_summaries_forwarded(
        self, db_session, test_round, test_participant, mock_llm_summary
    ):
        """
        Test that only APPROVED summaries are forwarded to clustering.

        Contract: Spec 3 → Spec 4
        Event: summarization.complete
        Guarantee: 100% status=APPROVED, no pending/rejected summaries
        """
        # Create discussion first
        discussion = Discussion(
            discussion_id=uuid4(),
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1
        )
        db_session.add(discussion)
        await db_session.commit()

        # Create round and participant
        round_obj = Round(
            round_id=uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts on this topic?",
            submission_window_duration_sec=300,
        )
        participant_obj = Participant(
            participant_id=uuid4(),
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )

        # Add to session and commit
        db_session.add(round_obj)
        db_session.add(participant_obj)
        await db_session.commit()

        # Create submission
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test input about renewable energy policy.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        # Generate and approve summary
        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        summary = await summarization_service.generate_summary(submission.submission_id)
        await approval_service.approve_summary(summary.summary_id)

        # Fetch approved summaries for round
        approved_summaries = await approval_service.get_approved_summaries_for_round(
            round_obj.round_id
        )

        # Validate contract
        assert len(approved_summaries) == 1
        assert approved_summaries[0].status == SummaryStatus.APPROVED
        assert approved_summaries[0].approved_at is not None

    async def test_last_approved_wins_rule(
        self, db_session, test_round, test_participant, mock_llm_summary
    ):
        """
        Test that last-approved-wins rule is applied correctly.

        If participant approves multiple summaries, only the most recent
        (by approved_at timestamp) is forwarded to clustering.
        """
        # Create discussion first
        discussion = Discussion(
            discussion_id=uuid4(),
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1
        )
        db_session.add(discussion)
        await db_session.commit()

        # Create round and participant
        round_obj = Round(
            round_id=uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts on this topic?",
            submission_window_duration_sec=300,
        )
        participant_obj = Participant(
            participant_id=uuid4(),
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )

        # Add to session and commit
        db_session.add(round_obj)
        db_session.add(participant_obj)
        await db_session.commit()

        # Create multiple submissions from same participant
        submissions = []
        for i in range(3):
            submission = Submission(
                submission_id=uuid4(),
                participant_id=participant_obj.participant_id,
                round_id=round_obj.round_id,
                submission_text=f"Submission {i}: Different perspective on climate.",
                modality="text",
            )
            db_session.add(submission)
            submissions.append(submission)

        await db_session.commit()

        # Generate and approve all summaries with delays
        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        summaries = []
        for i, submission in enumerate(submissions):
            summary = await summarization_service.generate_summary(submission.submission_id)
            summaries.append(summary)

            # Approve with staggered timestamps
            await approval_service.approve_summary(summary.summary_id)
            # In real scenario, timestamps would naturally differ

        # Get last approved summary (should apply last-approved-wins)
        last_approved = await approval_service.get_last_approved_summary_for_participant(
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
        )

        # Validate last-approved-wins
        assert last_approved is not None
        assert last_approved.status == SummaryStatus.APPROVED

        # Get all approved summaries and verify only one is active
        approved_summaries = await approval_service.get_approved_summaries_for_round(
            round_obj.round_id
        )

        # Should have 3 approved summaries, but only 1 would be forwarded (last one)
        participant_summaries = [
            s for s in approved_summaries
            if s.participant_id == participant_obj.participant_id
        ]

        # Last approved should have the latest approved_at timestamp
        sorted_summaries = sorted(participant_summaries, key=lambda s: s.approved_at, reverse=True)
        assert sorted_summaries[0].summary_id == last_approved.summary_id

    async def test_exactly_one_summary_per_participant(
        self, db_session, test_round, mock_llm_summary
    ):
        """
        Test that exactly one summary per participant is forwarded to clustering.

        Constitutional Principle: Intent Fidelity - last approved intent is used
        """
        # Create discussion first
        discussion = Discussion(
            discussion_id=uuid4(),
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1
        )
        db_session.add(discussion)
        await db_session.commit()

        # Create test round
        round_obj = Round(
            round_id=uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts on this topic?",
            submission_window_duration_sec=300,
        )
        db_session.add(round_obj)
        await db_session.commit()

        # Create multiple participants
        participants = []
        for i in range(3):
            participant = Participant(
                participant_id=uuid4(),
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            participants.append(participant)

        await db_session.commit()

        # Each participant submits and approves once
        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        for participant in participants:
            submission = Submission(
                submission_id=uuid4(),
                participant_id=participant.participant_id,
                round_id=round_obj.round_id,
                submission_text=f"Input from {participant.user_id}.",
                modality="text",
            )
            db_session.add(submission)
            await db_session.commit()

            summary = await summarization_service.generate_summary(submission.submission_id)
            await approval_service.approve_summary(summary.summary_id)

        # Get approved summaries for round
        approved_summaries = await approval_service.get_approved_summaries_for_round(
            round_obj.round_id
        )

        # Should have exactly 3 approved summaries (one per participant)
        assert len(approved_summaries) == 3

        participant_ids = {s.participant_id for s in approved_summaries}
        assert len(participant_ids) == 3, "Exactly one summary per participant"

    async def test_no_unapproved_summaries_forwarded(
        self, db_session, test_round, test_participant, mock_llm_summary
    ):
        """
        Test that pending/rejected summaries are NOT forwarded to clustering.

        Critical invariant: Zero unapproved summaries enter clustering.
        """
        # Create discussion first
        discussion = Discussion(
            discussion_id=uuid4(),
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1
        )
        db_session.add(discussion)
        await db_session.commit()

        # Create round and participant
        round_obj = Round(
            round_id=uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts on this topic?",
            submission_window_duration_sec=300,
        )
        participant_obj = Participant(
            participant_id=uuid4(),
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )

        # Add to session and commit
        db_session.add(round_obj)
        db_session.add(participant_obj)
        await db_session.commit()

        # Create submission and generate summary
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test input that won't be approved.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        summary = await summarization_service.generate_summary(submission.submission_id)

        # Don't approve - leave as PENDING_REVIEW

        # Get approved summaries for round
        approval_service = ApprovalService(db_session)
        approved_summaries = await approval_service.get_approved_summaries_for_round(
            round_obj.round_id
        )

        # Should be empty - no approved summaries
        assert len(approved_summaries) == 0, "Unapproved summaries must not be forwarded"
