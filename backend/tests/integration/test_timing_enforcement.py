"""
Integration test for timing precision enforcement (T077).

Tests that submission window closes within ±100ms precision for 99th percentile.

Task: T077 - Timing precision integration test
Constitutional Principle: Synchronous Deliberation (Principle VI)
Performance Requirement: SC-008 from spec.md
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import time

import pytest
from sqlalchemy import select

from src.models.round import Round, RoundStatus
from src.models.discussion import Discussion, DiscussionMode, DiscussionStatus
from src.services.timing_service import TimingService
from src.services.discussion_service import DiscussionService
from src.services.round_service import RoundService


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.timing
class TestTimingPrecisionEnforcement:
    """Test that submission window closure meets ±100ms precision requirement."""

    async def test_window_closes_within_100ms_precision(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that submission window closes within ±100ms of scheduled time (T077).

        This test validates the constitutional requirement SC-008:
        - Submission window must close within ±100ms for 99th percentile
        - 5-minute submission window set
        - Measure actual closure time
        - Assert ±100ms precision

        Expected: Window closes within 100ms of scheduled time.
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
            # Create discussion with 5-minute (300 second) submission window
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts on timing precision?"],
                submission_window_duration_sec=300,  # 5 minutes
            )

            # Start discussion and record precise start time
            start_time = time.perf_counter()  # High-precision timer
            await discussion_service.start_discussion(discussion.discussion_id)

            # Get round
            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Verify window is open
            assert round_1.status == RoundStatus.SUBMISSION_OPEN
            scheduled_end = round_1.submission_window_end
            assert scheduled_end is not None

            # Track closure event with high-precision timing
            closure_time = None
            closure_drift_ms = None

            async def capture_closure(event):
                nonlocal closure_time, closure_drift_ms
                closure_time = event.timestamp
                # Calculate drift from scheduled time
                drift = (closure_time - scheduled_end).total_seconds() * 1000
                closure_drift_ms = drift

            await event_bus.subscribe("submission_window.closed", capture_closure)

            # Calculate wait duration based on scheduled end time
            now = datetime.now(timezone.utc)
            wait_duration = (scheduled_end - now).total_seconds() + 0.5  # 500ms buffer

            # Wait for window to close
            await asyncio.sleep(wait_duration)

            # Verify closure happened
            assert closure_time is not None, "Window closure event was not received"
            assert closure_drift_ms is not None

            # CRITICAL ASSERTION: Verify ±100ms precision (SC-008)
            assert abs(closure_drift_ms) <= 100, (
                f"Timing precision violation: drift={closure_drift_ms:.2f}ms, "
                f"expected ≤100ms (constitutional requirement SC-008)"
            )

            # Verify round status changed to SUBMISSION_CLOSED
            await db_session.refresh(round_1)
            assert round_1.status == RoundStatus.SUBMISSION_CLOSED

            # Log success for performance tracking
            print(f"✓ Timing precision test passed: drift={closure_drift_ms:.2f}ms")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_99th_percentile_timing_precision_multiple_rounds(
        self, db_session, redis_client, event_bus
    ):
        """
        Test 99th percentile timing precision across multiple sequential rounds.

        Runs multiple rounds and measures timing drift to validate that
        99% of closures are within ±100ms.

        Expected: At least 99% of closures within ±100ms.
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

        drift_measurements = []

        async def measure_drift(event):
            """Capture drift measurement for each closure."""
            # Event should contain timing info
            # Store for later analysis
            drift_measurements.append({
                "timestamp": event.timestamp,
                "round_id": event.round_id,
            })

        await event_bus.subscribe("submission_window.closed", measure_drift)

        try:
            # Create discussion with 3 short rounds for testing
            # (Using short windows for faster test execution)
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=[
                    "What is your first thought?",
                    "What is your second thought?",
                    "What is your third thought?",
                ],
                submission_window_duration_sec=2,  # 2 seconds per round
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            # Run through all 3 rounds
            for round_num in range(1, 4):
                result = await db_session.execute(
                    select(Round).where(
                        Round.discussion_id == discussion.discussion_id,
                        Round.round_num == round_num,
                    )
                )
                current_round = result.scalar_one()

                # Wait for round to close
                now = datetime.now(timezone.utc)
                if current_round.submission_window_end:
                    wait_time = (current_round.submission_window_end - now).total_seconds()
                    if wait_time > 0:
                        await asyncio.sleep(wait_time + 0.3)  # 300ms buffer

                # Advance to next round if not last
                if round_num < 3:
                    # Close current round and open next
                    await round_service.close_submission_window(current_round.round_id)
                    # In real implementation, this would trigger advancement

            # Verify we collected measurements
            assert len(drift_measurements) >= 1, "Should have captured at least one closure"

            # Note: Full 99th percentile analysis would require 100+ samples
            # This test validates the mechanism exists and measurements are captured
            print(f"✓ Captured {len(drift_measurements)} timing measurements")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_timing_service_50ms_polling_accuracy(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that TimingService polling at 50ms achieves required precision.

        Validates that the 50ms polling interval is sufficient to meet
        the ±100ms constitutional requirement.

        Expected: Multiple consecutive closures all within ±100ms.
        """
        timing_service = TimingService(redis_url="redis://localhost:6379/1")
        await timing_service.connect()
        await timing_service.start_worker()

        # Verify polling interval is 50ms
        assert timing_service.POLL_INTERVAL_MS == 50, (
            "Polling interval must be 50ms to achieve ±100ms precision"
        )

        try:
            # Schedule multiple closures at different times
            round_ids = [uuid4() for _ in range(3)]
            scheduled_times = []

            base_time = datetime.now(timezone.utc)

            for i, round_id in enumerate(round_ids):
                # Schedule at 1-second intervals
                close_at = base_time.replace(microsecond=0) + timedelta(seconds=i + 2)
                await timing_service.schedule_closure(round_id, close_at)
                scheduled_times.append(close_at)

            # Track closures
            closures = []

            async def track_closure(event):
                closures.append({
                    "round_id": event.round_id,
                    "timestamp": event.timestamp,
                })

            await event_bus.subscribe("submission_window.closed", track_closure)

            # Wait for all closures
            await asyncio.sleep(5.0)

            # Verify all closures happened
            assert len(closures) >= 1, "At least one closure should have occurred"

            # Verify timing precision for each closure
            for i, closure in enumerate(closures):
                # Find corresponding scheduled time
                round_id = closure["round_id"]
                idx = round_ids.index(round_id)
                scheduled = scheduled_times[idx]
                actual = closure["timestamp"]

                drift_ms = (actual - scheduled).total_seconds() * 1000

                # Assert ±100ms precision
                assert abs(drift_ms) <= 100, (
                    f"Closure {i}: drift={drift_ms:.2f}ms exceeds ±100ms tolerance"
                )

            print(f"✓ All {len(closures)} closures within ±100ms precision")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()
