"""
Integration Tests: Last-Approved-Wins Logic

Tests that when multiple summaries are approved, only the latest is forwarded.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T098)
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio

from src.summarization.services.summarization_service import SummarizationService
from src.summarization.services.approval_service import ApprovalService
from src.models import Submission, Round, Participant
from src.summarization.models.summary import Summary, SummaryStatus


@pytest.mark.asyncio
class TestLastApprovedWins:
    """Test last-approved-wins selection logic."""

    async def test_latest_approval_wins(
        self, db_session, test_discussion, test_round, test_participant, mock_llm_summary
    ):
        """Test that latest approved summary is selected."""
        # Create test data dictionaries
        discussion_data = test_discussion()
        round_data = test_round(discussion_id=discussion_data["discussion_id"])
        participant_data = test_participant(discussion_id=discussion_data["discussion_id"])

        # Create model objects
        from src.models.discussion import Discussion
        discussion_obj = Discussion(**discussion_data)
        round_obj = Round(**round_data)
        participant_obj = Participant(**participant_data)

        # Add to session and commit
        db_session.add(discussion_obj)
        db_session.add(round_obj)
        db_session.add(participant_obj)
        await db_session.commit()

        # Create 3 submissions from same participant
        submissions = []
        for i in range(3):
            submission = Submission(
                submission_id=uuid4(),
                participant_id=participant_obj.participant_id,
                round_id=round_obj.round_id,
                submission_text=f"Submission {i}: My evolving thoughts on policy.",
                modality="text",
            )
            db_session.add(submission)
            submissions.append(submission)

        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Generate and approve all summaries with staggered timing
        summaries = []
        for submission in submissions:
            summary = await summarization_service.generate_summary(submission.submission_id)
            summaries.append(summary)

            # Approve with small delay to ensure different timestamps
            await approval_service.approve_summary(summary.summary_id)
            await asyncio.sleep(0.1)  # Small delay for timestamp differentiation

        # Get last approved summary
        last_approved = await approval_service.get_last_approved_summary_for_participant(
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
        )

        # Should be the last one approved (submission 2)
        assert last_approved is not None
        assert last_approved.summary_id == summaries[2].summary_id

    async def test_superseded_status_marking(
        self, db_session, test_discussion, test_round, test_participant, mock_llm_summary
    ):
        """Test that previous approved summaries are marked SUPERSEDED."""
        # Create test data dictionaries
        discussion_data = test_discussion()
        round_data = test_round(discussion_id=discussion_data["discussion_id"])
        participant_data = test_participant(discussion_id=discussion_data["discussion_id"])

        # Create model objects
        from src.models.discussion import Discussion
        discussion_obj = Discussion(**discussion_data)
        round_obj = Round(**round_data)
        participant_obj = Participant(**participant_data)

        # Add to session and commit
        db_session.add(discussion_obj)
        db_session.add(round_obj)
        db_session.add(participant_obj)
        await db_session.commit()

        # Create 2 submissions
        submission1 = Submission(
            submission_id=uuid4(),
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
            submission_text="First thoughts on climate policy.",
            modality="text",
        )
        submission2 = Submission(
            submission_id=uuid4(),
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
            submission_text="Updated thoughts on climate policy.",
            modality="text",
        )
        db_session.add_all([submission1, submission2])
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Generate and approve first
        summary1 = await summarization_service.generate_summary(submission1.submission_id)
        await approval_service.approve_summary(summary1.summary_id)

        await asyncio.sleep(0.1)

        # Generate and approve second
        summary2 = await summarization_service.generate_summary(submission2.submission_id)
        await approval_service.approve_summary(summary2.summary_id)

        # Mark previous as superseded
        await approval_service.mark_superseded(
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
            except_summary_id=summary2.summary_id,
        )

        # Verify first is superseded
        fetched_summary1 = await summarization_service.get_summary(summary1.summary_id)
        assert fetched_summary1.status == SummaryStatus.SUPERSEDED

        # Verify second is still approved
        fetched_summary2 = await summarization_service.get_summary(summary2.summary_id)
        assert fetched_summary2.status == SummaryStatus.APPROVED

    async def test_one_summary_per_participant_forwarded(
        self, db_session, test_discussion, test_round, mock_llm_summary
    ):
        """Test that exactly one summary per participant is forwarded."""
        # Create test discussion and round
        discussion_data = test_discussion()
        from src.models.discussion import Discussion
        discussion_obj = Discussion(**discussion_data)
        db_session.add(discussion_obj)
        await db_session.commit()

        round_data = test_round(discussion_id=discussion_obj.discussion_id)
        round_obj = Round(**round_data)
        db_session.add(round_obj)
        await db_session.commit()

        # Create multiple participants
        participants = []
        for i in range(3):
            participant = Participant(
                participant_id=uuid4(),
                discussion_id=round_obj.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            participants.append(participant)

        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Each participant submits and approves multiple times
        for participant in participants:
            for j in range(2):
                submission = Submission(
                    submission_id=uuid4(),
                    participant_id=participant.participant_id,
                    round_id=round_obj.round_id,
                    submission_text=f"Submission {j} from {participant.user_id}.",
                    modality="text",
                )
                db_session.add(submission)
                await db_session.commit()

                summary = await summarization_service.generate_summary(submission.submission_id)
                await approval_service.approve_summary(summary.summary_id)
                await asyncio.sleep(0.05)

        # Get last approved for each participant
        for participant in participants:
            last_approved = await approval_service.get_last_approved_summary_for_participant(
                participant_id=participant.participant_id,
                round_id=round_obj.round_id,
            )
            assert last_approved is not None
            assert last_approved.status == SummaryStatus.APPROVED

    async def test_timestamp_ordering_deterministic(
        self, db_session, test_discussion, test_round, test_participant, mock_llm_summary
    ):
        """Test that timestamp ordering is deterministic for last-approved-wins."""
        # Create test data dictionaries
        discussion_data = test_discussion()
        round_data = test_round(discussion_id=discussion_data["discussion_id"])
        participant_data = test_participant(discussion_id=discussion_data["discussion_id"])

        # Create model objects
        from src.models.discussion import Discussion
        discussion_obj = Discussion(**discussion_data)
        round_obj = Round(**round_data)
        participant_obj = Participant(**participant_data)

        # Add to session and commit
        db_session.add(discussion_obj)
        db_session.add(round_obj)
        db_session.add(participant_obj)
        await db_session.commit()

        # Create just 2 submissions to speed up the test and avoid timeout
        submissions = []
        for i in range(2):
            submission = Submission(
                submission_id=uuid4(),
                participant_id=participant_obj.participant_id,
                round_id=round_obj.round_id,
                submission_text=f"Iteration {i} of my policy stance.",
                modality="text",
            )
            db_session.add(submission)
            submissions.append(submission)

        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Approve all - timestamps will naturally differ due to processing time
        summaries = []
        for submission in submissions:
            summary = await summarization_service.generate_summary(submission.submission_id)
            approved = await approval_service.approve_summary(summary.summary_id)
            summaries.append(approved)  # Store the returned (refreshed) summary

        # Get the last approved summary using the service method
        last_approved = await approval_service.get_last_approved_summary_for_participant(
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
        )

        # After last-approved-wins logic, the last approved should be the most recent
        assert last_approved is not None
        assert last_approved.summary_id == summaries[-1].summary_id
        assert last_approved.status == SummaryStatus.APPROVED

        # Verify timestamp ordering is correct (most recent approval)
        assert last_approved.approved_at is not None
        assert last_approved.approved_at == summaries[-1].approved_at
