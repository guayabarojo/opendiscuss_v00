"""
Unit Tests: Summarization Service

Tests SummarizationService with mocked LLM calls.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T106)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.summarization.services.summarization_service import SummarizationService
from src.models import Submission, Round, Participant
from src.summarization.models.summary import Summary, SummaryStatus


@pytest.mark.asyncio
class TestSummarizationService:
    """Unit tests for SummarizationService."""

    @patch('src.llm.openai_client.generate_summary_llm')
    async def test_generate_summary_calls_llm(
        self, mock_llm, db_session, sample_round, sample_participant
    ):
        """Test that generate_summary calls LLM correctly."""
        # Setup mock
        mock_llm.return_value = "Test summary of participant input."

        # Create submission
        submission = Submission(
            submission_id=uuid4(),
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
            submission_text="We should invest in renewable energy.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        # Generate summary
        service = SummarizationService(db_session)
        summary = await service.generate_summary(submission.submission_id)

        # Verify LLM called
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args.kwargs
        assert 'prompt' in call_kwargs
        assert 'model' in call_kwargs

        # Verify summary created
        assert summary.summary_text == "Test summary of participant input."
        assert summary.status == SummaryStatus.PENDING_REVIEW
        assert summary.regen_count == 0

    @patch('src.llm.openai_client.generate_summary_llm')
    async def test_generate_summary_truncates_long_output(
        self, mock_llm, db_session, sample_round, sample_participant
    ):
        """Test that summaries longer than 500 chars are truncated."""
        # Setup mock with long output
        long_text = "a" * 600
        mock_llm.return_value = long_text

        submission = Submission(
            submission_id=uuid4(),
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
            submission_text="Test input.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        service = SummarizationService(db_session)
        summary = await service.generate_summary(submission.submission_id)

        # Verify truncation
        assert len(summary.summary_text) == 500
        assert summary.summary_text.endswith("...")

    @patch('src.llm.openai_client.generate_summary_llm')
    async def test_model_selection_default_vs_fallback(
        self, mock_llm, db_session, sample_round, sample_participant
    ):
        """Test that model selection uses default or fallback correctly."""
        mock_llm.return_value = "Summary text."

        submission = Submission(
            submission_id=uuid4(),
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
            submission_text="Test input.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        service = SummarizationService(db_session)

        # Test default model
        await service.generate_summary(submission.submission_id, use_fallback_model=False)
        assert mock_llm.call_args.kwargs['model'] == 'gpt-4-turbo'

        # Test fallback model
        submission2 = Submission(
            submission_id=uuid4(),
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
            submission_text="Test input 2.",
            modality="text",
        )
        db_session.add(submission2)
        await db_session.commit()

        await service.generate_summary(submission2.submission_id, use_fallback_model=True)
        assert mock_llm.call_args.kwargs['model'] == 'gpt-3.5-turbo'

    async def test_generate_summary_invalid_submission(self, db_session):
        """Test that invalid submission raises ValueError."""
        service = SummarizationService(db_session)
        fake_id = uuid4()

        with pytest.raises(ValueError, match="Submission .* not found"):
            await service.generate_summary(fake_id)

    async def test_generate_summary_empty_text(
        self, db_session, sample_round, sample_participant
    ):
        """Test that empty submission text raises ValueError."""
        submission = Submission(
            submission_id=uuid4(),
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
            submission_text="",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        service = SummarizationService(db_session)

        with pytest.raises(ValueError, match="has no text content"):
            await service.generate_summary(submission.submission_id)

    @patch('src.llm.openai_client.generate_summary_llm')
    async def test_regenerate_increments_count(
        self, mock_llm, db_session, sample_round, sample_participant
    ):
        """Test that regeneration increments regen_count."""
        mock_llm.return_value = "Regenerated summary."

        submission = Submission(
            submission_id=uuid4(),
            participant_id=sample_participant.participant_id,
            round_id=sample_round.round_id,
            submission_text="Test input.",
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        service = SummarizationService(db_session)

        # Generate initial
        summary1 = await service.generate_summary(submission.submission_id)
        assert summary1.regen_count == 0

        # Regenerate
        summary2 = await service.regenerate_summary(summary1.summary_id)
        assert summary2.regen_count == 1
        assert summary2.summary_id != summary1.summary_id
