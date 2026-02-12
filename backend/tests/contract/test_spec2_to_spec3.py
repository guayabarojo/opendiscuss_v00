"""
Contract Tests: Spec 2 (Input Collection) → Spec 3 (Summarization)

Validates that Spec 3 correctly handles submission_window.closed events
from Spec 2 and generates summaries for all collected submissions.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T094)
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.summarization.services.summarization_service import SummarizationService
from src.models import Submission, Round, Participant, Discussion
from src.models.protocol_state import DiscussionMode, DiscussionStatus
from src.summarization.models.summary import Summary, SummaryStatus


@pytest.mark.asyncio
class TestSpec2ToSpec3Contract:
    """Test contract between Spec 2 and Spec 3."""

    async def test_submission_window_closed_triggers_summarization(
        self, db_session, test_round, test_participant, mock_llm_summary
    ):
        """
        Test that submission_window.closed event triggers summary generation.

        Contract: Spec 2 → Spec 3
        Event: submission_window.closed
        Payload: {round_id, submissions: [{submission_id, participant_id, submission_text}]}
        Expected: Summaries generated for all submissions
        """
        # Create discussion first (required for foreign key)
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

        # Create submissions (simulating Spec 2 output)
        submissions = []
        for i in range(3):
            submission = Submission(
                submission_id=uuid4(),
                participant_id=participant_obj.participant_id,
                round_id=round_obj.round_id,
                submission_text=f"Test submission {i}: This is my input about climate change.",
                modality="text",
            )
            db_session.add(submission)
            submissions.append(submission)

        await db_session.commit()

        # Simulate Spec 3 handler processing submissions
        summarization_service = SummarizationService(db_session)

        summaries = []
        for submission in submissions:
            summary = await summarization_service.generate_summary(submission.submission_id)
            summaries.append(summary)

        # Validate contract expectations
        assert len(summaries) == 3, "Should generate summary for each submission"

        for i, summary in enumerate(summaries):
            assert summary.status == SummaryStatus.PENDING_REVIEW
            assert summary.submission_id == submissions[i].submission_id
            assert summary.participant_id == participant_obj.participant_id
            assert summary.round_id == round_obj.round_id
            assert len(summary.summary_text) <= 500
            assert summary.regen_count == 0

    async def test_multiple_participants_independent_summarization(
        self, db_session, test_round, mock_llm_summary
    ):
        """
        Test that summaries are generated independently per participant.

        Constitutional Principle: Parallel-First Architecture
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
        for i in range(5):
            participant = Participant(
                participant_id=uuid4(),
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            participants.append(participant)

        await db_session.commit()

        # Create submissions from different participants
        submissions = []
        for participant in participants:
            submission = Submission(
                submission_id=uuid4(),
                participant_id=participant.participant_id,
                round_id=round_obj.round_id,
                submission_text=f"Participant {participant.user_id} input on climate policy.",
                modality="text",
            )
            db_session.add(submission)
            submissions.append(submission)

        await db_session.commit()

        # Generate summaries independently
        summarization_service = SummarizationService(db_session)
        summaries = []

        for submission in submissions:
            summary = await summarization_service.generate_summary(submission.submission_id)
            summaries.append(summary)

        # Validate independence
        assert len(summaries) == 5
        participant_ids = {s.participant_id for s in summaries}
        assert len(participant_ids) == 5, "Each participant should have independent summary"

    async def test_empty_submission_handling(self, db_session, test_round, test_participant, mock_llm_summary):
        """Test that empty or invalid submissions are handled gracefully."""
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

        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
            submission_text="",  # Empty text
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)

        with pytest.raises(ValueError, match="has no text content"):
            await summarization_service.generate_summary(submission.submission_id)
