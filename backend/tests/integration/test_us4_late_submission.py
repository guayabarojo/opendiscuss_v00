"""
Integration test for late submission rejection (T080).

Tests that submissions after window_end are rejected with proper error message.

Task: T080 - Late submission rejection integration test
Constitutional Requirement: Synchronous Deliberation (Principle VI)
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from src.models.round import Round, RoundStatus
from src.models.discussion import Discussion, DiscussionMode, DiscussionStatus
from src.models.participant import Participant
from src.models.submission import Submission, SubmissionModality
from src.services.timing_service import TimingService
from src.services.discussion_service import DiscussionService
from src.services.round_service import RoundService
from src.services.submission_service import SubmissionService


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.timing
class TestLateSubmissionRejection:
    """Test that late submissions are properly rejected."""

    async def test_submission_rejected_after_window_close(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that submission after window_end returns 400 error (T080).

        Validates that the system enforces submission window timing
        and rejects late submissions with appropriate error message.

        Expected: 400 error with "window closed" message.
        """
        timing_service = TimingService(redis_url="redis://localhost:6379/1")
        await timing_service.connect()
        await timing_service.start_worker()

        discussion_service = DiscussionService(
            db_session=db_session,
            event_bus=event_bus,
            timing_service=timing_service,
        )
        round_service = RoundService(
            db_session=db_session,
            event_bus=event_bus,
            timing_service=timing_service,
        )
        submission_service = SubmissionService(
            db_session=db_session,
            event_bus=event_bus,
        )

        try:
            # Create discussion with short submission window
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts?"],
                submission_window_duration_sec=2,  # 2 seconds
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            # Get round
            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Create participant
            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.commit()

            # Wait for submission window to close
            now = datetime.now(timezone.utc)
            wait_time = (round_1.submission_window_end - now).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time + 0.3)  # Extra buffer to ensure closed

            # Close the submission window
            await round_service.close_submission_window(round_1.round_id)
            await db_session.refresh(round_1)

            # Verify window is closed
            assert round_1.status == RoundStatus.SUBMISSION_CLOSED
            now = datetime.now(timezone.utc)
            assert now > round_1.submission_window_end, "Current time should be past window end"

            # Attempt to create submission after window closed
            # This should raise an error or be rejected by the service
            with pytest.raises((HTTPException, ValueError)) as exc_info:
                await submission_service.create_submission(
                    participant_id=participant.participant_id,
                    round_id=round_1.round_id,
                    submission_text="This is a late submission",
                    modality=SubmissionModality.TEXT,
                )

            # Verify error contains "window closed" or similar message
            error_message = str(exc_info.value).lower()
            assert any(
                phrase in error_message
                for phrase in ["window closed", "submission closed", "deadline passed", "too late"]
            ), f"Error message should indicate window closed, got: {error_message}"

            print("✓ Late submission properly rejected with appropriate error")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_submission_accepted_before_window_close(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that submission before window_end is accepted.

        Validates that valid submissions within the window are processed correctly.

        Expected: Submission created successfully.
        """
        timing_service = TimingService(redis_url="redis://localhost:6379/1")
        await timing_service.connect()
        await timing_service.start_worker()

        discussion_service = DiscussionService(
            db_session=db_session,
            event_bus=event_bus,
            timing_service=timing_service,
        )
        submission_service = SubmissionService(
            db_session=db_session,
            event_bus=event_bus,
        )

        try:
            # Create discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts?"],
                submission_window_duration_sec=5,  # 5 seconds
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Create participant
            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.commit()

            # Submit immediately (well before window closes)
            submission = await submission_service.create_submission(
                participant_id=participant.participant_id,
                round_id=round_1.round_id,
                submission_text="Valid submission within window",
                modality=SubmissionModality.TEXT,
            )

            # Verify submission was created
            assert submission.submission_id is not None
            assert submission.submitted_at is not None
            assert submission.submitted_at < round_1.submission_window_end

            print("✓ Valid submission within window accepted successfully")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_submission_at_exact_window_boundary(
        self, db_session, redis_client, event_bus
    ):
        """
        Test submission behavior at the exact window boundary.

        Tests edge case where submission occurs at or very near window_end.

        Expected: Submission very close to boundary may be accepted or rejected
        depending on timing precision, but must be handled gracefully.
        """
        timing_service = TimingService(redis_url="redis://localhost:6379/1")
        await timing_service.connect()
        await timing_service.start_worker()

        discussion_service = DiscussionService(
            db_session=db_session,
            event_bus=event_bus,
            timing_service=timing_service,
        )
        round_service = RoundService(
            db_session=db_session,
            event_bus=event_bus,
            timing_service=timing_service,
        )
        submission_service = SubmissionService(
            db_session=db_session,
            event_bus=event_bus,
        )

        try:
            # Create discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts?"],
                submission_window_duration_sec=3,  # 3 seconds
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Create participant
            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.commit()

            # Wait until very close to window end (within 50ms)
            now = datetime.now(timezone.utc)
            wait_time = (round_1.submission_window_end - now).total_seconds() - 0.05
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # Attempt submission at boundary
            # This may succeed or fail depending on exact timing
            try:
                submission = await submission_service.create_submission(
                    participant_id=participant.participant_id,
                    round_id=round_1.round_id,
                    submission_text="Boundary submission",
                    modality=SubmissionModality.TEXT,
                )

                # If accepted, verify it was within window
                assert submission.submitted_at <= round_1.submission_window_end, (
                    "Submission accepted must be before window_end"
                )
                print("✓ Boundary submission accepted (within window)")

            except (HTTPException, ValueError) as e:
                # If rejected, this is also acceptable at the boundary
                print("✓ Boundary submission rejected (timing precision)")

            # The important thing is that the system handles it gracefully
            # and doesn't crash or produce undefined behavior

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_multiple_late_submissions_all_rejected(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that multiple attempts to submit late are all rejected.

        Validates consistent enforcement of submission deadline.

        Expected: All late submissions rejected with consistent error.
        """
        timing_service = TimingService(redis_url="redis://localhost:6379/1")
        await timing_service.connect()
        await timing_service.start_worker()

        discussion_service = DiscussionService(
            db_session=db_session,
            event_bus=event_bus,
            timing_service=timing_service,
        )
        round_service = RoundService(
            db_session=db_session,
            event_bus=event_bus,
            timing_service=timing_service,
        )
        submission_service = SubmissionService(
            db_session=db_session,
            event_bus=event_bus,
        )

        try:
            # Create discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts?"],
                submission_window_duration_sec=2,
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Create multiple participants
            participants = []
            for i in range(3):
                participant = Participant(
                    discussion_id=discussion.discussion_id,
                    user_id=uuid4(),
                    first_round=1,
                )
                db_session.add(participant)
                participants.append(participant)

            await db_session.commit()

            # Wait for window to close
            now = datetime.now(timezone.utc)
            wait_time = (round_1.submission_window_end - now).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time + 0.3)

            # Close window
            await round_service.close_submission_window(round_1.round_id)
            await db_session.refresh(round_1)

            # Attempt multiple late submissions
            rejection_count = 0
            for i, participant in enumerate(participants):
                try:
                    await submission_service.create_submission(
                        participant_id=participant.participant_id,
                        round_id=round_1.round_id,
                        submission_text=f"Late submission {i}",
                        modality=SubmissionModality.TEXT,
                    )
                    # If we get here, submission was incorrectly accepted
                    pytest.fail(f"Late submission {i} was incorrectly accepted")

                except (HTTPException, ValueError):
                    rejection_count += 1

            # Verify all late submissions were rejected
            assert rejection_count == 3, (
                f"Expected all 3 late submissions to be rejected, "
                f"but only {rejection_count} were rejected"
            )

            print(f"✓ All {rejection_count} late submissions consistently rejected")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_error_message_format_for_late_submission(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that late submission error message is properly formatted.

        Validates error response structure and content per API spec.

        Expected: 400 status with structured error including "window closed" message.
        """
        timing_service = TimingService(redis_url="redis://localhost:6379/1")
        await timing_service.connect()
        await timing_service.start_worker()

        discussion_service = DiscussionService(
            db_session=db_session,
            event_bus=event_bus,
            timing_service=timing_service,
        )
        round_service = RoundService(
            db_session=db_session,
            event_bus=event_bus,
            timing_service=timing_service,
        )
        submission_service = SubmissionService(
            db_session=db_session,
            event_bus=event_bus,
        )

        try:
            # Create discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts?"],
                submission_window_duration_sec=2,
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Create participant
            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.commit()

            # Wait for window to close
            now = datetime.now(timezone.utc)
            wait_time = (round_1.submission_window_end - now).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time + 0.3)

            await round_service.close_submission_window(round_1.round_id)
            await db_session.refresh(round_1)

            # Attempt late submission and capture error
            try:
                await submission_service.create_submission(
                    participant_id=participant.participant_id,
                    round_id=round_1.round_id,
                    submission_text="Late submission",
                    modality=SubmissionModality.TEXT,
                )
                pytest.fail("Late submission should have been rejected")

            except HTTPException as e:
                # Verify HTTP status code
                assert e.status_code == 400, f"Expected 400 status, got {e.status_code}"

                # Verify error detail contains appropriate message
                error_detail = str(e.detail).lower()
                assert any(
                    phrase in error_detail
                    for phrase in ["window closed", "closed", "deadline", "late"]
                ), f"Error should indicate window closed, got: {e.detail}"

                print(f"✓ Error message properly formatted: {e.detail}")

            except ValueError as e:
                # ValueError is also acceptable
                error_message = str(e).lower()
                assert any(
                    phrase in error_message
                    for phrase in ["window", "closed", "deadline"]
                ), f"Error should indicate window closed, got: {e}"

                print(f"✓ Error properly raised: {e}")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()
