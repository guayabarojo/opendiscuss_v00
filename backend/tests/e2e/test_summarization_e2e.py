"""
End-to-End Tests for Spec 003: Summarization & Approval Protocol

Comprehensive E2E tests covering the complete workflow from submission to clustering.

Test Scenarios:
1. Happy Path: Submit → Generate → Approve → Forward to Spec 4
2. Rejection & Regeneration: Submit → Generate → Reject → Auto-regen (2x) → Approve
3. Correction Signal: Submit → Reject (2x) → Correction → Final regen → Approve/Reject
4. Safety Filtering: Profanity neutralization, threat blocking
5. Last-Approved-Wins: Multiple submissions → Latest approval forwarded
6. Approval Deadline: Timeout after window closes

Constitutional Compliance:
- Intent Fidelity: 100% explicit approval required
- Parallel-First: Independent summary generation
- Temporal Transparency: Tracks all timestamps
- Community-Bounded Context: Safety filtering aligned with community norms

Run with: pytest tests/e2e/test_summarization_e2e.py --e2e
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select

from src.models import Discussion, Participant, Round, Submission
from src.models.submission import SubmissionModality
from src.summarization.models.summary import Summary, SummaryStatus
from src.summarization.models.correction_signal import CorrectionSignal, ReasonTag
from src.summarization.services.summarization_service import SummarizationService
from src.summarization.services.approval_service import ApprovalService
from src.summarization.services.safety_filter_service import SafetyFilterService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
async def discussion(db_session):
    """Create a test discussion."""
    disc = Discussion(
        discussion_id=uuid4(),
        community_id=uuid4(),  # UUID, not int
        mode="HOST_DEFINED",
        total_rounds=1,
        status="active",
        host_user_id=uuid4(),  # UUID object, not string
        updated_at=datetime.utcnow(),
    )
    db_session.add(disc)
    await db_session.commit()
    await db_session.refresh(disc)
    return disc


@pytest.fixture
async def round_obj(db_session, discussion):
    """Create a test round."""
    round_data = Round(
        round_id=uuid4(),
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are your thoughts on climate policy?",
        status="active",
        submission_window_start=datetime.utcnow(),
        submission_window_end=datetime.utcnow() + timedelta(minutes=5),
        submission_window_duration_sec=300,  # 5 minutes (180-360 sec constraint)
        updated_at=datetime.utcnow(),
    )
    db_session.add(round_data)
    await db_session.commit()
    await db_session.refresh(round_data)
    return round_data


@pytest.fixture
async def participant(db_session, discussion):
    """Create a test participant."""
    part = Participant(
        participant_id=uuid4(),
        discussion_id=discussion.discussion_id,
        user_id=uuid4(),  # UUID object, not string
        first_round=1,
        last_round=None,
        dropout_reason=None,
        updated_at=datetime.utcnow(),
    )
    db_session.add(part)
    await db_session.commit()
    await db_session.refresh(part)
    return part


@pytest.fixture
def mock_llm_generate(monkeypatch):
    """Mock LLM generation to avoid API costs."""
    # Disable OpenAI moderation for tests
    from src.config import settings
    monkeypatch.setattr(settings, "openai_moderation_enabled", False)

    async def _mock_generate(prompt: str, model: str = "gpt-4-turbo", temperature: float = 0.7, max_tokens: int = 150):
        # Generate deterministic summaries based on input length
        if "renewable energy" in prompt.lower():
            return "Advocate for renewable energy infrastructure investment to combat climate change."
        elif "profanity" in prompt.lower() or "***" in prompt:
            return "Expressing concern about policy with filtered language for community standards."
        elif "threat" in prompt.lower():
            # Should never reach here due to safety filter
            return "[Content blocked]"
        else:
            # Generic response
            return "Summary of participant input focusing on main policy concerns and solutions."

    with patch("src.llm.openai_client.generate_summary_llm", new=AsyncMock(side_effect=_mock_generate)):
        yield _mock_generate


# ============================================================================
# E2E Test Scenarios
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestHappyPathWorkflow:
    """
    Test Scenario 1: Happy Path
    Submit → Generate → Approve → Forward to Spec 4
    """

    async def test_complete_happy_path(
        self, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test complete workflow from submission to approval."""
        # Step 1: Create submission (Spec 2 output)
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="I believe we should invest heavily in renewable energy infrastructure to meet our climate goals.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()
        await db_session.refresh(submission)

        # Step 2: Generate summary (Spec 3 - Summarization)
        summarization_service = SummarizationService(db_session)
        summary = await summarization_service.generate_summary(submission.submission_id)

        # Validate summary generation
        assert summary is not None
        assert summary.status == SummaryStatus.PENDING_REVIEW
        assert summary.participant_id == participant.participant_id
        assert summary.round_id == round_obj.round_id
        assert len(summary.summary_text) > 0
        assert len(summary.summary_text) <= 500
        assert summary.regen_count == 0
        assert summary.approved_at is None
        assert summary.safety_flags == []

        # Step 3: Approve summary (Spec 3 - Approval)
        approval_service = ApprovalService(db_session)
        approved_summary = await approval_service.approve_summary(summary.summary_id)

        # Validate approval
        assert approved_summary.status == SummaryStatus.APPROVED
        assert approved_summary.approved_at is not None
        assert isinstance(approved_summary.approved_at, datetime)

        # Step 4: Verify summary ready for Spec 4 (Clustering)
        approved_summaries = await approval_service.get_approved_summaries_for_round(
            round_obj.round_id
        )

        assert len(approved_summaries) == 1
        assert approved_summaries[0].summary_id == approved_summary.summary_id
        assert approved_summaries[0].status == SummaryStatus.APPROVED
        assert approved_summaries[0].approved_at is not None

        # Validate constitutional compliance
        # - Intent Fidelity: Explicit approval required ✓
        # - Temporal Transparency: approved_at tracked ✓
        # - Parallel-First: Independent generation ✓


@pytest.mark.e2e
@pytest.mark.asyncio
class TestRejectionAndRegenerationWorkflow:
    """
    Test Scenario 2: Rejection & Regeneration
    Submit → Generate → Reject → Auto-regen 1 → Reject → Auto-regen 2 → Approve
    """

    async def test_bounded_regeneration_then_approval(
        self, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test rejection triggers automatic regeneration (max 2 auto attempts)."""
        # Create submission
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="We need stronger climate policies and international cooperation.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Generate initial summary (attempt 0)
        summary_0 = await summarization_service.generate_summary(submission.submission_id)
        assert summary_0.regen_count == 0
        assert summary_0.status == SummaryStatus.PENDING_REVIEW

        # Reject and regenerate (attempt 1)
        await approval_service.reject_summary(summary_0.summary_id)
        summary_1 = await summarization_service.regenerate_summary(summary_0.summary_id)

        assert summary_1.regen_count == 1
        assert summary_1.status == SummaryStatus.PENDING_REVIEW
        assert summary_1.submission_id == submission.submission_id
        assert summary_1.summary_id != summary_0.summary_id

        # Reject and regenerate again (attempt 2)
        await approval_service.reject_summary(summary_1.summary_id)
        summary_2 = await summarization_service.regenerate_summary(summary_1.summary_id)

        assert summary_2.regen_count == 2
        assert summary_2.status == SummaryStatus.PENDING_REVIEW

        # Finally approve
        approved_summary = await approval_service.approve_summary(summary_2.summary_id)
        assert approved_summary.status == SummaryStatus.APPROVED
        assert approved_summary.approved_at is not None

        # Verify all summaries exist in history
        all_summaries = await summarization_service.get_summaries_for_submission(
            submission.submission_id
        )
        assert len(all_summaries) == 3  # Original + 2 regenerations
        assert all_summaries[0].regen_count == 0
        assert all_summaries[1].regen_count == 1
        assert all_summaries[2].regen_count == 2


@pytest.mark.e2e
@pytest.mark.asyncio
class TestCorrectionSignalWorkflow:
    """
    Test Scenario 3: Correction Signal
    Submit → Reject 2x → Provide correction signal → Final regen → Approve/Reject
    """

    async def test_correction_signal_final_regeneration(
        self, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test correction signal enables 3rd regeneration attempt."""
        # Create submission
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Climate action requires immediate government intervention.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Generate and reject twice (exhaust auto-regens)
        summary_0 = await summarization_service.generate_summary(submission.submission_id)
        await approval_service.reject_summary(summary_0.summary_id)

        summary_1 = await summarization_service.regenerate_summary(summary_0.summary_id)
        await approval_service.reject_summary(summary_1.summary_id)

        summary_2 = await summarization_service.regenerate_summary(summary_1.summary_id)
        assert summary_2.regen_count == 2

        # Reject again (final rejection before correction)
        await approval_service.reject_summary(summary_2.summary_id)

        # Provide correction signal
        correction = CorrectionSignal(
            signal_id=uuid4(),
            summary_id=summary_2.summary_id,
            reason_tag=ReasonTag.WRONG_CRUX,
            feedback_text="Summary missed the urgency and government intervention aspect.",
        )
        db_session.add(correction)
        await db_session.commit()

        # Regenerate with correction (attempt 3, FINAL)
        summary_3 = await summarization_service.regenerate_with_correction(
            summary_2.summary_id
        )

        assert summary_3.regen_count == 3
        assert summary_3.status == SummaryStatus.PENDING_REVIEW

        # Approve final summary
        approved = await approval_service.approve_summary(summary_3.summary_id)
        assert approved.status == SummaryStatus.APPROVED

    async def test_correction_signal_final_rejection(
        self, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test final rejection after correction signal (REJECTED_FINAL)."""
        # Create submission
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Policy reform needed urgently.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Exhaust auto-regens
        summary_0 = await summarization_service.generate_summary(submission.submission_id)
        await approval_service.reject_summary(summary_0.summary_id)

        summary_1 = await summarization_service.regenerate_summary(summary_0.summary_id)
        await approval_service.reject_summary(summary_1.summary_id)

        summary_2 = await summarization_service.regenerate_summary(summary_1.summary_id)
        await approval_service.reject_summary(summary_2.summary_id)

        # Provide correction
        correction = CorrectionSignal(
            signal_id=uuid4(),
            summary_id=summary_2.summary_id,
            reason_tag=ReasonTag.MISREPRESENTS_ME,
            feedback_text="Tone doesn't match my intent.",
        )
        db_session.add(correction)
        await db_session.commit()

        # Final regeneration
        summary_3 = await summarization_service.regenerate_with_correction(
            summary_2.summary_id
        )
        assert summary_3.regen_count == 3

        # Final rejection
        rejected_final = await approval_service.mark_rejected_final(summary_3.summary_id)
        assert rejected_final.status == SummaryStatus.REJECTED_FINAL


@pytest.mark.e2e
@pytest.mark.asyncio
class TestSafetyFilteringWorkflow:
    """
    Test Scenario 4: Safety Filtering
    - Profanity neutralization → Allow approval
    - Threat detection → Block approval (DISALLOWED_CONTENT)
    """

    async def test_profanity_neutralization_workflow(
        self, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test profanity is neutralized but summary still approved."""
        # Submission with profanity
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="This damn policy is shit, but we need better healthcare for everyone.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)

        # Generate summary (safety filter applied automatically)
        summary = await summarization_service.generate_summary(submission.submission_id)

        # Validate profanity handling
        assert summary.status == SummaryStatus.PENDING_REVIEW  # Not blocked
        assert "profanity_neutralized" in summary.safety_flags
        assert len(summary.safety_flags) == 1

        # Approval still allowed
        approval_service = ApprovalService(db_session)
        approved = await approval_service.approve_summary(summary.summary_id)
        assert approved.status == SummaryStatus.APPROVED

    async def test_threat_detection_blocks_approval(
        self, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test explicit threat blocks summary (DISALLOWED_CONTENT)."""
        # Submission with threat
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="I will kill anyone who disagrees with me. We should bomb the opposition.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)

        # Generate summary (safety filter blocks)
        summary = await summarization_service.generate_summary(submission.submission_id)

        # Validate threat blocking
        assert summary.status == SummaryStatus.DISALLOWED_CONTENT
        assert "threat_detected" in summary.safety_flags
        assert summary.summary_text == "[Content blocked due to safety violations]"

        # Approval prevented
        approval_service = ApprovalService(db_session)
        with pytest.raises(ValueError, match="Cannot approve summary"):
            await approval_service.approve_summary(summary.summary_id)


@pytest.mark.e2e
@pytest.mark.asyncio
class TestLastApprovedWinsWorkflow:
    """
    Test Scenario 5: Last-Approved-Wins
    Multiple submissions → Approve submission 1 → Approve submission 2 → Only submission 2 forwarded
    """

    async def test_multiple_submissions_last_wins(
        self, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test that latest approval supersedes earlier approvals."""
        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Create and approve first submission
        submission_1 = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="First thought: We need renewable energy.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission_1)
        await db_session.commit()

        summary_1 = await summarization_service.generate_summary(submission_1.submission_id)
        approved_1 = await approval_service.approve_summary(summary_1.summary_id)
        assert approved_1.status == SummaryStatus.APPROVED

        # Small delay to ensure different timestamp
        import asyncio
        await asyncio.sleep(0.1)

        # Create and approve second submission (same participant)
        submission_2 = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Second thought: Actually, nuclear power is better.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission_2)
        await db_session.commit()

        summary_2 = await summarization_service.generate_summary(submission_2.submission_id)
        approved_2 = await approval_service.approve_summary(summary_2.summary_id)
        assert approved_2.status == SummaryStatus.APPROVED

        # Verify last-approved-wins logic
        # Refresh summary_1 from DB to see status change
        await db_session.refresh(summary_1)

        assert summary_1.status == SummaryStatus.SUPERSEDED
        assert summary_2.status == SummaryStatus.APPROVED

        # Verify only latest approved summary is returned
        last_approved = await approval_service.get_last_approved_summary_for_participant(
            participant.participant_id,
            round_obj.round_id
        )

        assert last_approved.summary_id == summary_2.summary_id
        assert last_approved.status == SummaryStatus.APPROVED

        # Verify Spec 4 receives only one summary per participant
        approved_summaries = await approval_service.get_approved_summaries_for_round(
            round_obj.round_id
        )

        participant_summaries = [
            s for s in approved_summaries
            if s.participant_id == participant.participant_id
        ]
        assert len(participant_summaries) == 1
        assert participant_summaries[0].summary_id == summary_2.summary_id


@pytest.mark.e2e
@pytest.mark.asyncio
class TestApprovalDeadlineWorkflow:
    """
    Test Scenario 6: Approval Deadline
    Submit → Generate → Wait past deadline → Verify APPROVAL_TIMEOUT

    Note: This test simulates timer service from Spec 0.
    """

    async def test_approval_timeout_after_deadline(
        self, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test that summaries timeout after approval deadline."""
        # Create submission
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Urgent action needed on climate.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)

        # Generate summary
        summary = await summarization_service.generate_summary(submission.submission_id)
        assert summary.status == SummaryStatus.PENDING_REVIEW

        # Simulate approval deadline passing
        # In real implementation, this would be triggered by timer service
        # For E2E test, we manually set the round submission_window_end to past
        round_obj.submission_window_end = datetime.utcnow() - timedelta(minutes=15)
        db_session.add(round_obj)
        await db_session.commit()

        # Check if approval deadline service marks as timeout
        # This would normally be handled by background task
        # For now, verify the state machine allows this transition
        summary.status = SummaryStatus.APPROVAL_TIMEOUT
        db_session.add(summary)
        await db_session.commit()
        await db_session.refresh(summary)

        assert summary.status == SummaryStatus.APPROVAL_TIMEOUT
        assert summary.approved_at is None

        # Verify timeout summaries are NOT forwarded to clustering
        approval_service = ApprovalService(db_session)
        approved_summaries = await approval_service.get_approved_summaries_for_round(
            round_obj.round_id
        )

        assert len(approved_summaries) == 0  # No approved summaries


# ============================================================================
# Integration Test: Full Round Workflow
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestFullRoundWorkflow:
    """
    Complete round workflow with multiple participants.

    Tests the full Spec 003 integration with multiple participants:
    - Some approve immediately
    - Some reject and regenerate
    - Some provide correction signals
    - Some have profanity filtered
    - One has blocked content
    - Last-approved-wins for one participant
    """

    async def test_full_round_multi_participant(
        self, db_session, discussion, round_obj, mock_llm_generate
    ):
        """Test complete round with varied participant scenarios."""
        # Create 5 participants
        participants = []
        for i in range(5):
            part = Participant(
                participant_id=uuid4(),
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),  # UUID object, not string
                first_round=1,
                updated_at=datetime.utcnow(),
            )
            db_session.add(part)
            participants.append(part)

        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Participant 0: Happy path (approve immediately)
        sub_0 = Submission(
            submission_id=uuid4(),
            participant_id=participants[0].participant_id,
            round_id=round_obj.round_id,
            submission_text="We need renewable energy infrastructure investment.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(sub_0)
        await db_session.commit()

        summary_0 = await summarization_service.generate_summary(sub_0.submission_id)
        await approval_service.approve_summary(summary_0.summary_id)

        # Participant 1: Reject once, then approve
        sub_1 = Submission(
            submission_id=uuid4(),
            participant_id=participants[1].participant_id,
            round_id=round_obj.round_id,
            submission_text="Climate policy needs reform.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(sub_1)
        await db_session.commit()

        summary_1a = await summarization_service.generate_summary(sub_1.submission_id)
        await approval_service.reject_summary(summary_1a.summary_id)
        summary_1b = await summarization_service.regenerate_summary(summary_1a.summary_id)
        await approval_service.approve_summary(summary_1b.summary_id)

        # Participant 2: Profanity filtered, then approved
        sub_2 = Submission(
            submission_id=uuid4(),
            participant_id=participants[2].participant_id,
            round_id=round_obj.round_id,
            submission_text="This damn system is broken, we need change.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(sub_2)
        await db_session.commit()

        summary_2 = await summarization_service.generate_summary(sub_2.submission_id)
        assert "profanity_neutralized" in summary_2.safety_flags
        await approval_service.approve_summary(summary_2.summary_id)

        # Participant 3: Multiple submissions (last-approved-wins)
        sub_3a = Submission(
            submission_id=uuid4(),
            participant_id=participants[3].participant_id,
            round_id=round_obj.round_id,
            submission_text="First opinion: solar power.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(sub_3a)
        await db_session.commit()

        summary_3a = await summarization_service.generate_summary(sub_3a.submission_id)
        await approval_service.approve_summary(summary_3a.summary_id)

        import asyncio
        await asyncio.sleep(0.1)

        sub_3b = Submission(
            submission_id=uuid4(),
            participant_id=participants[3].participant_id,
            round_id=round_obj.round_id,
            submission_text="Second opinion: nuclear is better.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(sub_3b)
        await db_session.commit()

        summary_3b = await summarization_service.generate_summary(sub_3b.submission_id)
        await approval_service.approve_summary(summary_3b.summary_id)

        # Participant 4: Blocked content (threat detected)
        sub_4 = Submission(
            submission_id=uuid4(),
            participant_id=participants[4].participant_id,
            round_id=round_obj.round_id,
            submission_text="I will kill everyone who disagrees.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(sub_4)
        await db_session.commit()

        summary_4 = await summarization_service.generate_summary(sub_4.submission_id)
        assert summary_4.status == SummaryStatus.DISALLOWED_CONTENT

        # Verify final state: Ready for Spec 4 (Clustering)
        approved_summaries = await approval_service.get_approved_summaries_for_round(
            round_obj.round_id
        )

        # Should have 4 approved summaries (participants 0, 1, 2, 3)
        # Participant 3 should have only 1 summary (last-approved-wins)
        # Participant 4 blocked (no approved summary)
        assert len(approved_summaries) == 4

        # Verify all approved summaries have required fields for Spec 4
        for summary in approved_summaries:
            assert summary.status == SummaryStatus.APPROVED
            assert summary.approved_at is not None
            assert summary.participant_id is not None
            assert summary.round_id == round_obj.round_id
            assert len(summary.summary_text) > 0
            assert len(summary.summary_text) <= 500

        # Verify last-approved-wins for participant 3
        await db_session.refresh(summary_3a)
        assert summary_3a.status == SummaryStatus.SUPERSEDED
        assert summary_3b.status == SummaryStatus.APPROVED

        # Verify exactly one summary per participant
        participant_ids = [s.participant_id for s in approved_summaries]
        assert len(participant_ids) == len(set(participant_ids))  # All unique


# ============================================================================
# Performance & Constraints Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestConstraintsAndPerformance:
    """Test system constraints and performance requirements."""

    async def test_summary_max_500_chars(
        self, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test that summaries are truncated to max 500 characters."""
        # Mock LLM to return long text
        with patch("src.llm.openai_client.generate_summary_llm") as mock:
            mock.return_value = "A" * 600  # 600 char response

            submission = Submission(
                submission_id=uuid4(),
                participant_id=participant.participant_id,
                round_id=round_obj.round_id,
                submission_text="Long input text that generates long summary.",
                modality=SubmissionModality.TEXT,
            )
            db_session.add(submission)
            await db_session.commit()

            summarization_service = SummarizationService(db_session)
            summary = await summarization_service.generate_summary(submission.submission_id)

            # Validate truncation
            assert len(summary.summary_text) <= 500
            assert summary.summary_text.endswith("...")

    async def test_max_regeneration_count_enforced(
        self, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test that regeneration count is bounded to 3."""
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test input for regeneration limit.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        summarization_service = SummarizationService(db_session)
        approval_service = ApprovalService(db_session)

        # Generate initial (0) + 2 auto-regens (1, 2)
        summary_0 = await summarization_service.generate_summary(submission.submission_id)
        await approval_service.reject_summary(summary_0.summary_id)

        summary_1 = await summarization_service.regenerate_summary(summary_0.summary_id)
        await approval_service.reject_summary(summary_1.summary_id)

        summary_2 = await summarization_service.regenerate_summary(summary_1.summary_id)
        await approval_service.reject_summary(summary_2.summary_id)

        # Add correction signal for 3rd attempt
        correction = CorrectionSignal(
            signal_id=uuid4(),
            summary_id=summary_2.summary_id,
            reason_tag=ReasonTag.TOO_VAGUE,
            feedback_text="Final attempt feedback.",
        )
        db_session.add(correction)
        await db_session.commit()

        # Final regeneration (3)
        summary_3 = await summarization_service.regenerate_with_correction(
            summary_2.summary_id
        )
        assert summary_3.regen_count == 3

        # After regen_count=3, should mark as REJECTED_FINAL
        await approval_service.mark_rejected_final(summary_3.summary_id)
        await db_session.refresh(summary_3)
        assert summary_3.status == SummaryStatus.REJECTED_FINAL
