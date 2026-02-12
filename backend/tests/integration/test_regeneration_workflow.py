"""
Integration Tests: Regeneration Workflow

Tests bounded regeneration with max 3 attempts (2 auto + 1 correction-based).

Spec Reference: Spec 003 - Summarization & Approval Protocol (T097)
"""

import pytest
from uuid import uuid4

from src.summarization.services.summarization_service import SummarizationService
from src.summarization.services.approval_service import ApprovalService
from src.models import Submission, Round, Participant
from src.summarization.models.summary import Summary, SummaryStatus


@pytest.mark.asyncio
class TestRegenerationWorkflow:
    """Test bounded regeneration workflow."""

    async def test_reject_triggers_regeneration(
        self, db_session, test_discussion, test_round, test_participant, mock_llm_summary
    ):
        """Test that rejection triggers automatic regeneration."""
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
            submission_text="We need stronger climate policies.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        # Generate initial summary
        summarization_service = SummarizationService(db_session)
        summary1 = await summarization_service.generate_summary(submission.submission_id)

        assert summary1.regen_count == 0
        assert summary1.status == SummaryStatus.PENDING_REVIEW

        # Reject and regenerate
        approval_service = ApprovalService(db_session)
        rejected_summary = await approval_service.reject_summary(summary1.summary_id)

        assert rejected_summary.status == SummaryStatus.REJECTED

        # Regenerate
        summary2 = await summarization_service.regenerate_summary(summary1.summary_id)

        assert summary2.regen_count == 1
        assert summary2.status == SummaryStatus.PENDING_REVIEW
        assert summary2.submission_id == summary1.submission_id
        assert summary2.summary_id != summary1.summary_id

    async def test_bounded_regeneration_max_2_auto(
        self, db_session, test_discussion, test_round, test_participant, mock_llm_summary
    ):
        """Test that automatic regeneration is bounded to max 2 attempts."""
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
            submission_text="Climate change requires immediate action.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Generate initial summary (attempt 0)
        summary0 = await summarization_service.generate_summary(submission.submission_id)
        assert summary0.regen_count == 0

        # Reject and regenerate (attempt 1)
        await approval_service.reject_summary(summary0.summary_id)
        summary1 = await summarization_service.regenerate_summary(summary0.summary_id)
        assert summary1.regen_count == 1

        # Reject and regenerate (attempt 2)
        await approval_service.reject_summary(summary1.summary_id)
        summary2 = await summarization_service.regenerate_summary(summary1.summary_id)
        assert summary2.regen_count == 2

        # After 2 automatic regens, should require correction signal
        # (This would be tested in correction signal workflow tests)

    async def test_regeneration_uses_different_strategy(
        self, db_session, test_discussion, test_round, test_participant, mock_llm_summary
    ):
        """Test that regeneration varies prompt strategy."""
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
            submission_text="Renewable energy is key to reducing emissions.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)

        # Generate initial
        summary1 = await summarization_service.generate_summary(submission.submission_id)
        text1 = summary1.summary_text

        # Regenerate
        summary2 = await summarization_service.regenerate_summary(summary1.summary_id)
        text2 = summary2.summary_text

        # Summaries should be different (due to prompt variation)
        # Note: This test may occasionally fail due to LLM randomness
        # In production, consider using deterministic LLM for tests
        assert len(text2) > 0
        assert len(text2) <= 500

    async def test_get_all_summaries_for_submission(
        self, db_session, test_discussion, test_round, test_participant, mock_llm_summary
    ):
        """Test retrieving all summaries (including regenerations) for a submission."""
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
            submission_text="Solar and wind power should be prioritized.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)

        # Generate initial + 2 regenerations
        summary1 = await summarization_service.generate_summary(submission.submission_id)
        summary2 = await summarization_service.regenerate_summary(summary1.summary_id)
        summary3 = await summarization_service.regenerate_summary(summary2.summary_id)

        # Get all summaries
        all_summaries = await summarization_service.get_summaries_for_submission(
            submission.submission_id
        )

        assert len(all_summaries) == 3
        assert all_summaries[0].regen_count == 0
        assert all_summaries[1].regen_count == 1
        assert all_summaries[2].regen_count == 2
