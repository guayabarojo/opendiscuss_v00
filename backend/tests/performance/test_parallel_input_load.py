"""
Performance benchmark for parallel submission load (T082).

Tests that 100 concurrent participants can submit within 5-second window with zero failures.

Task: T082 - Parallel submission load performance test
Constitutional Requirement: SC-004 from spec.md
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
from src.services.submission_service import SubmissionService


@pytest.mark.asyncio
@pytest.mark.performance
@pytest.mark.benchmark
@pytest.mark.slow
class TestParallelSubmissionLoad:
    """Performance benchmarks for parallel submission handling."""

    async def test_100_concurrent_submissions_within_5_seconds(
        self, db_session, redis_client, event_bus
    ):
        """
        Test 100 concurrent participants submitting within 5-second window (T082).

        Constitutional Requirement: SC-004
        - System must handle 100 concurrent participants
        - All submissions complete within 5-second window
        - Zero failures (all submissions accepted)

        Expected: All 100 submissions succeed, total time <5 seconds.
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

        num_participants = 100

        try:
            # Create discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts on concurrent processing?"],
                submission_window_duration_sec=60,  # Long enough for test
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

            # Create participants
            participants = []
            for i in range(num_participants):
                participant = Participant(
                    discussion_id=discussion.discussion_id,
                    user_id=uuid4(),
                    first_round=1,
                )
                db_session.add(participant)
                participants.append(participant)

            await db_session.commit()

            # Prepare concurrent submission tasks
            async def submit_async(participant_idx, participant):
                """Submit for a single participant."""
                try:
                    submission = await submission_service.create_submission(
                        participant_id=participant.participant_id,
                        round_id=round_1.round_id,
                        submission_text=f"Concurrent submission {participant_idx}",
                        modality=SubmissionModality.TEXT,
                    )
                    return {"success": True, "submission_id": submission.submission_id}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            # Execute all submissions concurrently
            print(f"\n=== Parallel Submission Load Test ===")
            print(f"Submitting {num_participants} concurrent submissions...")

            start_time = time.perf_counter()

            # Use asyncio.gather to submit all concurrently
            results = await asyncio.gather(
                *[submit_async(i, p) for i, p in enumerate(participants)],
                return_exceptions=True
            )

            end_time = time.perf_counter()
            elapsed_seconds = end_time - start_time

            # Count successes and failures
            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            failures = num_participants - successes

            # CRITICAL ASSERTIONS
            # 1. Zero failures (SC-004)
            assert failures == 0, (
                f"Parallel submission failures: {failures}/{num_participants} failed, "
                f"expected 0 failures (SC-004)"
            )

            # 2. All completed within 5 seconds (SC-004)
            assert elapsed_seconds < 5.0, (
                f"Parallel submission time: {elapsed_seconds:.3f}s, "
                f"expected <5s (SC-004)"
            )

            print(f"✓ All {successes}/{num_participants} submissions succeeded")
            print(f"✓ Total time: {elapsed_seconds:.3f}s (<5s requirement)")
            print(f"✓ Throughput: {num_participants / elapsed_seconds:.1f} submissions/sec")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_concurrent_submissions_different_submission_rates(
        self, db_session, redis_client, event_bus
    ):
        """
        Test parallel submissions with staggered arrival times.

        Simulates realistic scenario where participants don't all submit
        at exactly the same instant.

        Expected: All submissions succeed even with varied timing.
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

        num_participants = 50  # Smaller for staggered test

        try:
            # Create discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts?"],
                submission_window_duration_sec=30,
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Create participants
            participants = []
            for i in range(num_participants):
                participant = Participant(
                    discussion_id=discussion.discussion_id,
                    user_id=uuid4(),
                    first_round=1,
                )
                db_session.add(participant)
                participants.append(participant)

            await db_session.commit()

            # Submit with staggered delays
            async def staggered_submit(participant_idx, participant, delay_ms):
                """Submit after a small delay."""
                await asyncio.sleep(delay_ms / 1000.0)
                try:
                    submission = await submission_service.create_submission(
                        participant_id=participant.participant_id,
                        round_id=round_1.round_id,
                        submission_text=f"Staggered submission {participant_idx}",
                        modality=SubmissionModality.TEXT,
                    )
                    return {"success": True}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            print(f"\n=== Staggered Submission Test ===")
            print(f"Submitting {num_participants} participants with staggered timing...")

            start_time = time.perf_counter()

            # Stagger submissions over 2 seconds
            delays = [i * (2000 / num_participants) for i in range(num_participants)]
            results = await asyncio.gather(
                *[staggered_submit(i, p, delays[i]) for i, p in enumerate(participants)],
                return_exceptions=True
            )

            end_time = time.perf_counter()
            elapsed = end_time - start_time

            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            failures = num_participants - successes

            # Verify zero failures
            assert failures == 0, f"Expected 0 failures, got {failures}"

            print(f"✓ All {successes}/{num_participants} staggered submissions succeeded")
            print(f"✓ Total time: {elapsed:.3f}s")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_burst_submission_patterns(
        self, db_session, redis_client, event_bus
    ):
        """
        Test system handling of burst submission patterns.

        Simulates realistic pattern:
        - Initial burst (30% of participants)
        - Sustained submissions (50%)
        - Last-minute rush (20%)

        Expected: All submissions succeed despite burst pattern.
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

        num_participants = 100

        try:
            # Create discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts?"],
                submission_window_duration_sec=30,
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Create participants
            participants = []
            for i in range(num_participants):
                participant = Participant(
                    discussion_id=discussion.discussion_id,
                    user_id=uuid4(),
                    first_round=1,
                )
                db_session.add(participant)
                participants.append(participant)

            await db_session.commit()

            async def burst_submit(participant_idx, participant, burst_time):
                """Submit in specific burst window."""
                await asyncio.sleep(burst_time)
                try:
                    submission = await submission_service.create_submission(
                        participant_id=participant.participant_id,
                        round_id=round_1.round_id,
                        submission_text=f"Burst submission {participant_idx}",
                        modality=SubmissionModality.TEXT,
                    )
                    return {"success": True, "burst_time": burst_time}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            print(f"\n=== Burst Submission Pattern Test ===")

            # Define burst pattern
            # 30% initial burst (0-0.5s)
            # 50% sustained (0.5-2s)
            # 20% last-minute rush (2-2.5s)

            burst_times = []
            initial_burst = int(num_participants * 0.3)
            sustained = int(num_participants * 0.5)
            last_minute = num_participants - initial_burst - sustained

            # Initial burst
            burst_times.extend([0.1 + (i * 0.01) for i in range(initial_burst)])
            # Sustained
            burst_times.extend([0.5 + (i * 0.03) for i in range(sustained)])
            # Last minute
            burst_times.extend([2.0 + (i * 0.01) for i in range(last_minute)])

            print(f"Pattern: {initial_burst} initial, {sustained} sustained, {last_minute} last-minute")

            start_time = time.perf_counter()

            results = await asyncio.gather(
                *[burst_submit(i, p, burst_times[i]) for i, p in enumerate(participants)],
                return_exceptions=True
            )

            end_time = time.perf_counter()
            elapsed = end_time - start_time

            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            failures = num_participants - successes

            # Verify zero failures
            assert failures == 0, f"Burst pattern failures: {failures}/{num_participants}"

            # Verify completed within reasonable time
            assert elapsed < 5.0, f"Burst pattern took {elapsed:.3f}s, expected <5s"

            print(f"✓ All {successes}/{num_participants} burst submissions succeeded")
            print(f"✓ Total time: {elapsed:.3f}s")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_database_connection_pool_under_load(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that database connection pool handles concurrent load.

        Validates that the system doesn't run out of database connections
        under high concurrent load.

        Expected: All database operations succeed without connection errors.
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

        num_participants = 100

        try:
            # Create discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts?"],
                submission_window_duration_sec=60,
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Create participants
            participants = []
            for i in range(num_participants):
                participant = Participant(
                    discussion_id=discussion.discussion_id,
                    user_id=uuid4(),
                    first_round=1,
                )
                db_session.add(participant)
                participants.append(participant)

            await db_session.commit()

            async def db_intensive_submit(participant_idx, participant):
                """Submit with multiple database operations."""
                try:
                    # Create submission
                    submission = await submission_service.create_submission(
                        participant_id=participant.participant_id,
                        round_id=round_1.round_id,
                        submission_text=f"DB load test submission {participant_idx}",
                        modality=SubmissionModality.TEXT,
                    )

                    # Perform additional read to stress connection pool
                    verify_result = await db_session.execute(
                        select(Submission).where(
                            Submission.submission_id == submission.submission_id
                        )
                    )
                    verified = verify_result.scalar_one()

                    return {"success": True, "verified": verified is not None}

                except Exception as e:
                    # Check if it's a connection pool error
                    error_msg = str(e).lower()
                    is_connection_error = any(
                        phrase in error_msg
                        for phrase in ["connection", "pool", "timeout"]
                    )
                    return {
                        "success": False,
                        "error": str(e),
                        "connection_error": is_connection_error,
                    }

            print(f"\n=== Database Connection Pool Test ===")
            print(f"Testing {num_participants} concurrent database operations...")

            start_time = time.perf_counter()

            results = await asyncio.gather(
                *[db_intensive_submit(i, p) for i, p in enumerate(participants)],
                return_exceptions=True
            )

            elapsed = time.perf_counter() - start_time

            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            failures = num_participants - successes
            connection_errors = sum(
                1 for r in results
                if isinstance(r, dict) and r.get("connection_error", False)
            )

            # Verify no connection pool errors
            assert connection_errors == 0, (
                f"Database connection pool errors: {connection_errors}/{failures} failures "
                f"were connection-related"
            )

            # Verify zero total failures
            assert failures == 0, f"Expected 0 failures, got {failures}"

            print(f"✓ All {successes}/{num_participants} operations succeeded")
            print(f"✓ No connection pool errors")
            print(f"✓ Total time: {elapsed:.3f}s")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_concurrent_load_with_retries(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that retry logic doesn't cause cascading failures under load.

        Validates that if transient errors occur, they are handled gracefully
        without causing system-wide failures.

        Expected: All submissions eventually succeed (with retries if needed).
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

        num_participants = 50  # Smaller for retry test

        try:
            # Create discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=["What are your thoughts?"],
                submission_window_duration_sec=60,
            )

            await discussion_service.start_discussion(discussion.discussion_id)

            result = await db_session.execute(
                select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == 1,
                )
            )
            round_1 = result.scalar_one()

            # Create participants
            participants = []
            for i in range(num_participants):
                participant = Participant(
                    discussion_id=discussion.discussion_id,
                    user_id=uuid4(),
                    first_round=1,
                )
                db_session.add(participant)
                participants.append(participant)

            await db_session.commit()

            async def submit_with_retry(participant_idx, participant, max_retries=3):
                """Submit with exponential backoff retry."""
                for attempt in range(max_retries):
                    try:
                        submission = await submission_service.create_submission(
                            participant_id=participant.participant_id,
                            round_id=round_1.round_id,
                            submission_text=f"Retry test submission {participant_idx}",
                            modality=SubmissionModality.TEXT,
                        )
                        return {"success": True, "attempts": attempt + 1}

                    except Exception as e:
                        if attempt < max_retries - 1:
                            # Exponential backoff
                            await asyncio.sleep(0.1 * (2 ** attempt))
                        else:
                            return {"success": False, "error": str(e)}

                return {"success": False, "error": "Max retries exceeded"}

            print(f"\n=== Concurrent Load with Retry Test ===")

            start_time = time.perf_counter()

            results = await asyncio.gather(
                *[submit_with_retry(i, p) for i, p in enumerate(participants)],
                return_exceptions=True
            )

            elapsed = time.perf_counter() - start_time

            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            failures = num_participants - successes

            # Count how many needed retries
            retry_counts = [
                r.get("attempts", 0)
                for r in results
                if isinstance(r, dict) and r.get("success")
            ]
            needed_retries = sum(1 for count in retry_counts if count > 1)

            # Verify all eventually succeeded
            assert failures == 0, f"Expected 0 final failures, got {failures}"

            print(f"✓ All {successes}/{num_participants} submissions succeeded")
            print(f"  {needed_retries} required retries")
            print(f"✓ Total time: {elapsed:.3f}s")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()
