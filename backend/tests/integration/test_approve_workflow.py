"""
Integration Tests: Approval Workflow

Tests end-to-end approval workflow from generation to approval persistence.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T096)
"""

import pytest
from datetime import datetime
from uuid import uuid4

from src.summarization.services.summarization_service import SummarizationService
from src.summarization.services.approval_service import ApprovalService
from src.models import Submission, Round, Participant
from src.summarization.models.summary import Summary, SummaryStatus


@pytest.mark.asyncio
class TestApprovalWorkflow:
    """Test complete approval workflow."""

    async def test_generate_approve_persist(
        self, db_session, test_discussion, test_round, test_participant, mock_llm_summary
    ):
        """Test complete workflow: generate → approve → verify persisted."""
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

        # Create submission
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
            submission_text="I believe we should invest in renewable energy infrastructure.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        # Generate summary
        summarization_service = SummarizationService(db_session)
        summary = await summarization_service.generate_summary(submission.submission_id)

        assert summary.status == SummaryStatus.PENDING_REVIEW
        assert summary.approved_at is None
        assert len(summary.summary_text) > 0
        assert len(summary.summary_text) <= 500

        # Approve summary
        approval_service = ApprovalService(db_session)
        approved_summary = await approval_service.approve_summary(summary.summary_id)

        assert approved_summary.status == SummaryStatus.APPROVED
        assert approved_summary.approved_at is not None
        assert isinstance(approved_summary.approved_at, datetime)

        # Verify persistence
        fetched_summary = await summarization_service.get_summary(summary.summary_id)
        assert fetched_summary.status == SummaryStatus.APPROVED
        assert fetched_summary.approved_at == approved_summary.approved_at

    async def test_approve_updates_timestamp(
        self, db_session, test_discussion, test_round, test_participant, mock_llm_summary
    ):
        """Test that approval sets approved_at timestamp correctly."""
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

        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test input for timestamp validation.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        summary = await summarization_service.generate_summary(submission.submission_id)

        before_approval = datetime.utcnow()

        approval_service = ApprovalService(db_session)
        approved_summary = await approval_service.approve_summary(summary.summary_id)

        after_approval = datetime.utcnow()

        # Validate timestamp is within expected range
        assert approved_summary.approved_at >= before_approval
        assert approved_summary.approved_at <= after_approval

    async def test_cannot_approve_nonexistent_summary(self, db_session):
        """Test that approving nonexistent summary raises error."""
        approval_service = ApprovalService(db_session)
        fake_id = uuid4()

        with pytest.raises(ValueError, match="Summary .* not found"):
            await approval_service.approve_summary(fake_id)

    async def test_approve_already_approved_summary(
        self, db_session, test_discussion, test_round, test_participant, mock_llm_summary
    ):
        """Test that approving an already-approved summary is idempotent."""
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

        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant_obj.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test idempotent approval.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        summary = await summarization_service.generate_summary(submission.submission_id)

        approval_service = ApprovalService(db_session)

        # First approval
        first_approval = await approval_service.approve_summary(summary.summary_id)
        first_timestamp = first_approval.approved_at

        # Second approval (should be idempotent)
        second_approval = await approval_service.approve_summary(summary.summary_id)

        # Timestamp should remain the same
        assert second_approval.approved_at == first_timestamp
        assert second_approval.status == SummaryStatus.APPROVED
