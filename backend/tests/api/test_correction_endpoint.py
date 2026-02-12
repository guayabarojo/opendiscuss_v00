"""
Test correction signal API endpoint (T053) for User Story 3.

Tests:
1. POST /summaries/{summary_id}/correction - Success path
2. Validation: reason_tag required
3. Validation: feedback_text max 240 chars
4. Validation: regen_count=2 required
5. Validation: status=REJECTED required
6. CorrectionSignal entity creation
7. Triggers regenerate_with_correction()
8. Returns new summary with regen_count=3
"""

import pytest
from uuid import uuid4
from httpx import AsyncClient

from src.main import app
from src.models import Participant, Round, Submission, SubmissionModality
from src.summarization.models.summary import Summary, SummaryStatus
from src.summarization.models.correction_signal import ReasonTag


@pytest.mark.asyncio
class TestCorrectionSignalEndpoint:
    """Test correction signal API endpoint (T053)."""

    async def test_correction_signal_success(
        self, async_client: AsyncClient, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test successful correction signal submission (T053)."""
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

        # Create summary with regen_count=2 and status=REJECTED
        summary = Summary(
            summary_id=uuid4(),
            submission_id=submission.submission_id,
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            summary_text="Previous summary that was rejected.",
            status=SummaryStatus.REJECTED,
            regen_count=2,
            safety_flags=[],
        )
        db_session.add(summary)
        await db_session.commit()

        # Submit correction signal
        request_data = {
            "reason_tag": "wrong_crux",
            "feedback_text": "Summary missed the urgency and government intervention aspect.",
        }

        response = await async_client.post(
            f"/api/v1/summaries/{summary.summary_id}/correction",
            json=request_data,
        )

        # Assert response
        assert response.status_code == 201
        data = response.json()

        assert "signal_id" in data
        assert data["summary_id"] == str(summary.summary_id)
        assert data["reason_tag"] == "wrong_crux"
        assert data["feedback_text"] == "Summary missed the urgency and government intervention aspect."
        assert "created_at" in data
        assert "new_summary_id" in data
        assert "new_summary_text" in data
        assert data["regen_count"] == 3
        assert "message" in data
        assert "final" in data["message"].lower()

    async def test_correction_signal_missing_reason_tag(
        self, async_client: AsyncClient, db_session, round_obj, participant
    ):
        """Test validation: reason_tag is required (T053, T060)."""
        # Create summary
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test submission.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        summary = Summary(
            summary_id=uuid4(),
            submission_id=submission.submission_id,
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            summary_text="Previous summary.",
            status=SummaryStatus.REJECTED,
            regen_count=2,
            safety_flags=[],
        )
        db_session.add(summary)
        await db_session.commit()

        # Submit correction without reason_tag
        request_data = {
            "feedback_text": "Some feedback.",
        }

        response = await async_client.post(
            f"/api/v1/summaries/{summary.summary_id}/correction",
            json=request_data,
        )

        # Assert validation error
        assert response.status_code == 422

    async def test_correction_signal_invalid_reason_tag(
        self, async_client: AsyncClient, db_session, round_obj, participant
    ):
        """Test validation: reason_tag must be valid enum (T053, T060)."""
        # Create summary
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test submission.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        summary = Summary(
            summary_id=uuid4(),
            submission_id=submission.submission_id,
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            summary_text="Previous summary.",
            status=SummaryStatus.REJECTED,
            regen_count=2,
            safety_flags=[],
        )
        db_session.add(summary)
        await db_session.commit()

        # Submit correction with invalid reason_tag
        request_data = {
            "reason_tag": "invalid_tag",
            "feedback_text": "Some feedback.",
        }

        response = await async_client.post(
            f"/api/v1/summaries/{summary.summary_id}/correction",
            json=request_data,
        )

        # Assert validation error
        assert response.status_code == 422
        data = response.json()
        assert "Invalid reason_tag" in data["detail"]

    async def test_correction_signal_feedback_too_long(
        self, async_client: AsyncClient, db_session, round_obj, participant
    ):
        """Test validation: feedback_text max 240 chars (T053, T059)."""
        # Create summary
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test submission.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        summary = Summary(
            summary_id=uuid4(),
            submission_id=submission.submission_id,
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            summary_text="Previous summary.",
            status=SummaryStatus.REJECTED,
            regen_count=2,
            safety_flags=[],
        )
        db_session.add(summary)
        await db_session.commit()

        # Submit correction with feedback > 240 chars
        request_data = {
            "reason_tag": "wrong_crux",
            "feedback_text": "a" * 241,  # 241 characters
        }

        response = await async_client.post(
            f"/api/v1/summaries/{summary.summary_id}/correction",
            json=request_data,
        )

        # Assert validation error
        assert response.status_code == 422
        data = response.json()
        assert "240 characters" in data["detail"]

    async def test_correction_signal_wrong_regen_count(
        self, async_client: AsyncClient, db_session, round_obj, participant
    ):
        """Test validation: summary must have regen_count=2 (T053)."""
        # Create submission
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test submission.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        # Create summary with regen_count=1 (not 2)
        summary = Summary(
            summary_id=uuid4(),
            submission_id=submission.submission_id,
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            summary_text="Previous summary.",
            status=SummaryStatus.REJECTED,
            regen_count=1,  # Wrong count
            safety_flags=[],
        )
        db_session.add(summary)
        await db_session.commit()

        # Submit correction signal
        request_data = {
            "reason_tag": "wrong_crux",
            "feedback_text": "Some feedback.",
        }

        response = await async_client.post(
            f"/api/v1/summaries/{summary.summary_id}/correction",
            json=request_data,
        )

        # Assert validation error
        assert response.status_code == 422
        data = response.json()
        assert "after 2 rejections" in data["detail"]
        assert "regen_count=1" in data["detail"]

    async def test_correction_signal_wrong_status(
        self, async_client: AsyncClient, db_session, round_obj, participant
    ):
        """Test validation: summary must have status=REJECTED (T053)."""
        # Create submission
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test submission.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        # Create summary with status=PENDING_REVIEW (not REJECTED)
        summary = Summary(
            summary_id=uuid4(),
            submission_id=submission.submission_id,
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            summary_text="Previous summary.",
            status=SummaryStatus.PENDING_REVIEW,  # Wrong status
            regen_count=2,
            safety_flags=[],
        )
        db_session.add(summary)
        await db_session.commit()

        # Submit correction signal
        request_data = {
            "reason_tag": "wrong_crux",
            "feedback_text": "Some feedback.",
        }

        response = await async_client.post(
            f"/api/v1/summaries/{summary.summary_id}/correction",
            json=request_data,
        )

        # Assert validation error
        assert response.status_code == 422
        data = response.json()
        assert "REJECTED state" in data["detail"]

    async def test_correction_signal_summary_not_found(
        self, async_client: AsyncClient
    ):
        """Test error handling: summary not found (T053)."""
        # Submit correction for non-existent summary
        non_existent_id = uuid4()
        request_data = {
            "reason_tag": "wrong_crux",
            "feedback_text": "Some feedback.",
        }

        response = await async_client.post(
            f"/api/v1/summaries/{non_existent_id}/correction",
            json=request_data,
        )

        # Assert not found error
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]

    async def test_correction_signal_without_feedback(
        self, async_client: AsyncClient, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test correction signal without optional feedback_text (T053)."""
        # Create submission
        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text="Test submission.",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        # Create summary with regen_count=2 and status=REJECTED
        summary = Summary(
            summary_id=uuid4(),
            submission_id=submission.submission_id,
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            summary_text="Previous summary.",
            status=SummaryStatus.REJECTED,
            regen_count=2,
            safety_flags=[],
        )
        db_session.add(summary)
        await db_session.commit()

        # Submit correction without feedback_text
        request_data = {
            "reason_tag": "too_vague",
        }

        response = await async_client.post(
            f"/api/v1/summaries/{summary.summary_id}/correction",
            json=request_data,
        )

        # Assert success
        assert response.status_code == 201
        data = response.json()
        assert data["reason_tag"] == "too_vague"
        assert data["feedback_text"] is None
        assert data["regen_count"] == 3

    async def test_all_reason_tags(
        self, async_client: AsyncClient, db_session, round_obj, participant, mock_llm_generate
    ):
        """Test all valid reason tags (T060)."""
        valid_tags = [
            "wrong_crux",
            "too_vague",
            "misrepresents_me",
            "missed_constraint",
            "missed_solution",
            "other",
        ]

        for tag in valid_tags:
            # Create submission
            submission = Submission(
                submission_id=uuid4(),
                participant_id=participant.participant_id,
                round_id=round_obj.round_id,
                submission_text="Test submission.",
                modality=SubmissionModality.TEXT,
            )
            db_session.add(submission)
            await db_session.commit()

            # Create summary
            summary = Summary(
                summary_id=uuid4(),
                submission_id=submission.submission_id,
                participant_id=participant.participant_id,
                round_id=round_obj.round_id,
                summary_text="Previous summary.",
                status=SummaryStatus.REJECTED,
                regen_count=2,
                safety_flags=[],
            )
            db_session.add(summary)
            await db_session.commit()

            # Submit correction with this tag
            request_data = {
                "reason_tag": tag,
                "feedback_text": f"Testing {tag}",
            }

            response = await async_client.post(
                f"/api/v1/summaries/{summary.summary_id}/correction",
                json=request_data,
            )

            # Assert success
            assert response.status_code == 201, f"Failed for tag: {tag}"
            data = response.json()
            assert data["reason_tag"] == tag
