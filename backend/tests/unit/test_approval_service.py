"""
Unit Tests: Approval Service

Tests ApprovalService approval/rejection workflows.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T107)
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from src.summarization.services.approval_service import ApprovalService
from src.summarization.services.summarization_service import SummarizationService
from src.models import Submission, Round, Participant
from src.summarization.models.summary import Summary, SummaryStatus


@pytest.mark.asyncio
class TestApprovalService:
    """Unit tests for ApprovalService."""

    @patch('src.llm.openai_client.generate_summary_llm')
    async def test_approve_summary_sets_status(
        self, mock_llm, db_session, sample_round, sample_participant
    ):
        """Test that approve_summary sets APPROVED status."""
        mock_llm.return_value = "Test summary."

        # Create submission and summary
        submission = Submission(
            submission_id=uuid4(),
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
            submission_text="Test input.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        summary = await summarization_service.generate_summary(submission.submission_id)

        # Approve
        approval_service = ApprovalService(db_session)
        approved = await approval_service.approve_summary(summary.summary_id)

        assert approved.status == SummaryStatus.APPROVED
        assert approved.approved_at is not None
        assert isinstance(approved.approved_at, datetime)

    @patch('src.llm.openai_client.generate_summary_llm')
    async def test_reject_summary_sets_status(
        self, mock_llm, db_session, sample_round, sample_participant
    ):
        """Test that reject_summary sets REJECTED status."""
        mock_llm.return_value = "Test summary."

        submission = Submission(
            submission_id=uuid4(),
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
            submission_text="Test input.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        summary = await summarization_service.generate_summary(submission.submission_id)

        # Reject
        approval_service = ApprovalService(db_session)
        rejected = await approval_service.reject_summary(summary.summary_id)

        assert rejected.status == SummaryStatus.REJECTED

    @patch('src.llm.openai_client.generate_summary_llm')
    async def test_get_approved_summaries_filters_correctly(
        self, mock_llm, db_session, sample_round, sample_participant
    ):
        """Test that get_approved_summaries returns only approved summaries."""
        mock_llm.return_value = "Test summary."

        # Create multiple submissions
        submissions = []
        for i in range(3):
            submission = Submission(
                submission_id=uuid4(),
                participant_id=sample_participant.participant_id,
                round_id=sample_round.round_id,
                submission_text=f"Input {i}.",
                modality="text",
            )
            db_session.add(submission)
            submissions.append(submission)

        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Generate summaries
        summaries = []
        for submission in submissions:
            summary = await summarization_service.generate_summary(submission.submission_id)
            summaries.append(summary)

        # Approve only first two
        await approval_service.approve_summary(summaries[0].summary_id)
        await approval_service.approve_summary(summaries[1].summary_id)
        # Leave summaries[2] as PENDING_REVIEW

        # Get approved
        approved = await approval_service.get_approved_summaries_for_round(sample_round.round_id)

        assert len(approved) == 2
        assert all(s.status == SummaryStatus.APPROVED for s in approved)

    @patch('src.llm.openai_client.generate_summary_llm')
    async def test_get_last_approved_returns_latest(
        self, mock_llm, db_session, sample_round, sample_participant
    ):
        """Test that get_last_approved_summary_for_participant returns latest."""
        mock_llm.return_value = "Test summary."

        # Create two submissions
        submission1 = Submission(
            submission_id=uuid4(),
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
            submission_text="First input.",
            modality="text",
        )
        submission2 = Submission(
            submission_id=uuid4(),
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
            submission_text="Second input.",
            modality="text",
        )
        db_session.add_all([submission1, submission2])
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Generate and approve both
        summary1 = await summarization_service.generate_summary(submission1.submission_id)
        await approval_service.approve_summary(summary1.summary_id)

        import asyncio
        await asyncio.sleep(0.1)

        summary2 = await summarization_service.generate_summary(submission2.submission_id)
        await approval_service.approve_summary(summary2.summary_id)

        # Get last approved
        last_approved = await approval_service.get_last_approved_summary_for_participant(
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
        )

        # Should be summary2 (latest)
        assert last_approved.summary_id == summary2.summary_id

    async def test_approve_nonexistent_summary_raises_error(self, db_session):
        """Test that approving nonexistent summary raises ValueError."""
        approval_service = ApprovalService(db_session)
        fake_id = uuid4()

        with pytest.raises(ValueError, match="Summary .* not found"):
            await approval_service.approve_summary(fake_id)
