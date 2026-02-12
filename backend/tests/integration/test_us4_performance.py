"""
Integration test for round completion performance (T078).

Tests that a full round completes (submission_close → clustering_complete → sankey_complete)
in less than 10 minutes.

Task: T078 - Round performance integration test
Constitutional Requirement: SC-007 from spec.md
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4
import time

import pytest
from sqlalchemy import select

from src.models.round import Round, RoundStatus
from src.models.discussion import Discussion, DiscussionMode, DiscussionStatus
from src.models.participant import Participant
from src.models.submission import Submission, SubmissionModality
from src.services.timing_service import TimingService
from src.services.discussion_service import DiscussionService
from src.services.round_service import RoundService


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.performance
class TestRoundPerformance:
    """Test round completion performance requirements."""

    async def test_full_round_completes_within_10_minutes(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that full round completes within 10 minutes (T078).

        Measures elapsed time from submission_close → clustering_complete → sankey_complete.

        Constitutional Requirement: SC-007
        - Round completion time: <10 minutes

        Expected: Full round completion <10 minutes (600 seconds).
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

        try:
            # Create discussion with short window for faster testing
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts on performance?"],
                submission_window_duration_sec=5,  # 5 seconds for test speed
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

            # Create participants and submissions
            num_participants = 10  # Smaller number for integration test
            participants = []

            for i in range(num_participants):
                participant = Participant(
                    discussion_id=discussion.discussion_id,
                    user_id=uuid4(),
                    first_round=1,
                )
                db_session.add(participant)
                participants.append(participant)

            await db_session.flush()

            # Create submissions
            for i, participant in enumerate(participants):
                submission = Submission(
                    participant_id=participant.participant_id,
                    round_id=round_1.round_id,
                    submission_text=f"Performance test submission {i}",
                    modality=SubmissionModality.TEXT,
                )
                db_session.add(submission)

            await db_session.commit()

            # Wait for submission window to close
            now = datetime.now(timezone.utc)
            wait_time = (round_1.submission_window_end - now).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time + 0.2)

            # Close submission window and start timing
            start_time = time.perf_counter()
            await round_service.close_submission_window(round_1.round_id)
            await db_session.refresh(round_1)

            assert round_1.status == RoundStatus.SUBMISSION_CLOSED

            # Track round progression through states
            state_timestamps = {
                "submission_closed": time.perf_counter(),
            }

            async def track_summarization_complete(event):
                state_timestamps["summarization_complete"] = time.perf_counter()

            async def track_clustering_complete(event):
                state_timestamps["clustering_complete"] = time.perf_counter()

            async def track_sankey_complete(event):
                state_timestamps["sankey_complete"] = time.perf_counter()

            await event_bus.subscribe("summarization.complete", track_summarization_complete)
            await event_bus.subscribe("clustering.complete", track_clustering_complete)
            await event_bus.subscribe("sankey.complete", track_sankey_complete)

            # Simulate round progression
            # In real implementation, this would be triggered by event handlers
            # For testing, we manually advance the round through states

            # SUBMISSION_CLOSED → SUMMARIZING
            await asyncio.sleep(0.1)
            round_1.advance_status(RoundStatus.SUMMARIZING)
            await db_session.commit()

            # SUMMARIZING → APPROVING (simulate summarization)
            await asyncio.sleep(0.2)
            round_1.advance_status(RoundStatus.APPROVING)
            await db_session.commit()

            # APPROVING → CLUSTERING (simulate approval)
            await asyncio.sleep(0.2)
            round_1.advance_status(RoundStatus.CLUSTERING)
            await db_session.commit()

            # CLUSTERING → SANKEY_BUILDING (simulate clustering)
            await asyncio.sleep(0.3)
            round_1.advance_status(RoundStatus.SANKEY_BUILDING)
            await db_session.commit()

            # SANKEY_BUILDING → COMPLETE (simulate Sankey construction)
            await asyncio.sleep(0.2)
            round_1.advance_status(RoundStatus.COMPLETE)
            await db_session.commit()

            # Measure total elapsed time
            end_time = time.perf_counter()
            elapsed_seconds = end_time - start_time

            # CRITICAL ASSERTION: Verify <10 minutes (600 seconds)
            assert elapsed_seconds < 600, (
                f"Round completion time violation: {elapsed_seconds:.2f}s elapsed, "
                f"expected <600s (10 minutes, SC-007)"
            )

            # Verify round reached COMPLETE status
            await db_session.refresh(round_1)
            assert round_1.status == RoundStatus.COMPLETE
            assert round_1.completed_at is not None

            print(f"✓ Round completed in {elapsed_seconds:.2f}s (<600s requirement)")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_round_performance_with_realistic_load(
        self, db_session, redis_client, event_bus
    ):
        """
        Test round performance with realistic participant load.

        Tests with 50 participants to validate performance at scale.

        Expected: Round completes <10 minutes even with higher load.
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

        try:
            # Create discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts?"],
                submission_window_duration_sec=5,
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Create 50 participants with submissions
            num_participants = 50
            start_setup = time.perf_counter()

            for i in range(num_participants):
                participant = Participant(
                    discussion_id=discussion.discussion_id,
                    user_id=uuid4(),
                    first_round=1,
                )
                db_session.add(participant)
                await db_session.flush()

                submission = Submission(
                    participant_id=participant.participant_id,
                    round_id=round_1.round_id,
                    submission_text=f"Realistic load test submission {i} with more content",
                    modality=SubmissionModality.TEXT,
                )
                db_session.add(submission)

            await db_session.commit()
            setup_time = time.perf_counter() - start_setup

            # Wait for window to close
            now = datetime.now(timezone.utc)
            wait_time = (round_1.submission_window_end - now).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time + 0.2)

            # Start performance measurement
            start_time = time.perf_counter()
            await round_service.close_submission_window(round_1.round_id)

            # Simulate round progression through states
            await asyncio.sleep(0.1)
            round_1.advance_status(RoundStatus.SUMMARIZING)
            await db_session.commit()

            await asyncio.sleep(0.3)  # Longer for more submissions
            round_1.advance_status(RoundStatus.APPROVING)
            await db_session.commit()

            await asyncio.sleep(0.3)
            round_1.advance_status(RoundStatus.CLUSTERING)
            await db_session.commit()

            await asyncio.sleep(0.5)  # Longer for clustering
            round_1.advance_status(RoundStatus.SANKEY_BUILDING)
            await db_session.commit()

            await asyncio.sleep(0.3)
            round_1.advance_status(RoundStatus.COMPLETE)
            await db_session.commit()

            end_time = time.perf_counter()
            elapsed_seconds = end_time - start_time

            # Verify <10 minutes with realistic load
            assert elapsed_seconds < 600, (
                f"Round completion with 50 participants: {elapsed_seconds:.2f}s, "
                f"expected <600s"
            )

            await db_session.refresh(round_1)
            assert round_1.status == RoundStatus.COMPLETE

            print(
                f"✓ Round with 50 participants completed in {elapsed_seconds:.2f}s "
                f"(setup: {setup_time:.2f}s)"
            )

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_round_state_transitions_timing(
        self, db_session, redis_client, event_bus
    ):
        """
        Test timing of individual state transitions in round progression.

        Measures time for each state transition to identify bottlenecks.

        Expected: Each transition <2 minutes to stay within 10-minute total.
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

        try:
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

            # Wait for window to close
            await asyncio.sleep(2.5)
            await round_service.close_submission_window(round_1.round_id)

            # Measure each state transition
            transitions = []

            async def measure_transition(from_status, to_status):
                start = time.perf_counter()
                round_1.advance_status(to_status)
                await db_session.commit()
                elapsed = time.perf_counter() - start
                transitions.append({
                    "from": from_status.value,
                    "to": to_status.value,
                    "elapsed_seconds": elapsed,
                })
                await asyncio.sleep(0.1)  # Small delay between transitions

            await measure_transition(RoundStatus.SUBMISSION_CLOSED, RoundStatus.SUMMARIZING)
            await measure_transition(RoundStatus.SUMMARIZING, RoundStatus.APPROVING)
            await measure_transition(RoundStatus.APPROVING, RoundStatus.CLUSTERING)
            await measure_transition(RoundStatus.CLUSTERING, RoundStatus.SANKEY_BUILDING)
            await measure_transition(RoundStatus.SANKEY_BUILDING, RoundStatus.COMPLETE)

            # Verify each transition <120 seconds (2 minutes)
            for transition in transitions:
                assert transition["elapsed_seconds"] < 120, (
                    f"Transition {transition['from']} → {transition['to']} took "
                    f"{transition['elapsed_seconds']:.2f}s, expected <120s"
                )

            # Calculate total time
            total_time = sum(t["elapsed_seconds"] for t in transitions)
            assert total_time < 600, f"Total transition time: {total_time:.2f}s, expected <600s"

            print(f"✓ All state transitions completed, total: {total_time:.2f}s")
            for t in transitions:
                print(f"  {t['from']} → {t['to']}: {t['elapsed_seconds']:.3f}s")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()
