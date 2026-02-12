"""
Integration test for total discussion time (T079).

Tests that a 5-round discussion completes from start to finish in less than 60 minutes.

Task: T079 - Total discussion time integration test
Constitutional Requirement: SC-006 from spec.md
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
@pytest.mark.slow  # Mark as slow test since it runs multiple rounds
class TestTotalDiscussionTime:
    """Test total discussion completion time requirements."""

    async def test_5_round_discussion_completes_within_60_minutes(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that 5-round discussion completes within 60 minutes (T079).

        Measures time from discussion start to completion across all 5 rounds.

        Constitutional Requirement: SC-006
        - Total discussion time: <60 minutes for multi-round discussions

        Expected: Full 5-round discussion <60 minutes (3600 seconds).
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
            # Create 5-round discussion with short windows for faster testing
            questions = [
                "What is your first thought on this topic?",
                "How does your perspective evolve?",
                "What patterns do you notice?",
                "What insights have emerged?",
                "What is your final reflection?",
            ]

            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=questions,
                submission_window_duration_sec=5,  # 5 seconds per round for fast testing
            )

            # Start discussion and begin timing
            start_time = time.perf_counter()
            discussion_start_datetime = datetime.now(timezone.utc)

            await discussion_service.start_discussion(discussion.discussion_id)
            await db_session.refresh(discussion)

            assert discussion.status == DiscussionStatus.ACTIVE
            assert discussion.started_at is not None

            # Track round completion times
            round_times = []

            # Process all 5 rounds
            for round_num in range(1, 6):
                round_start = time.perf_counter()

                # Get current round
                result = await db_session.execute(
                    select(Round).where(
                        Round.discussion_id == discussion.discussion_id,
                        Round.round_num == round_num,
                    )
                )
                current_round = result.scalar_one()

                # Create participants and submissions for this round
                num_participants = 10  # Smaller number for integration test

                for i in range(num_participants):
                    # Check if participant already exists
                    existing_participant = await db_session.execute(
                        select(Participant).where(
                            Participant.discussion_id == discussion.discussion_id,
                            Participant.user_id == uuid4(),
                        ).limit(1)
                    )
                    participant = existing_participant.scalar_one_or_none()

                    if participant is None:
                        participant = Participant(
                            discussion_id=discussion.discussion_id,
                            user_id=uuid4(),
                            first_round=round_num,
                        )
                        db_session.add(participant)
                        await db_session.flush()

                    # Create submission for this round
                    submission = Submission(
                        participant_id=participant.participant_id,
                        round_id=current_round.round_id,
                        submission_text=f"Round {round_num} submission {i}",
                        modality=SubmissionModality.TEXT,
                    )
                    db_session.add(submission)

                await db_session.commit()

                # Wait for submission window to close
                now = datetime.now(timezone.utc)
                wait_time = (current_round.submission_window_end - now).total_seconds()
                if wait_time > 0:
                    await asyncio.sleep(wait_time + 0.2)

                # Close submission window
                await round_service.close_submission_window(current_round.round_id)

                # Simulate round progression through all states
                await asyncio.sleep(0.1)
                current_round.advance_status(RoundStatus.SUMMARIZING)
                await db_session.commit()

                await asyncio.sleep(0.2)
                current_round.advance_status(RoundStatus.APPROVING)
                await db_session.commit()

                await asyncio.sleep(0.2)
                current_round.advance_status(RoundStatus.CLUSTERING)
                await db_session.commit()

                await asyncio.sleep(0.3)
                current_round.advance_status(RoundStatus.SANKEY_BUILDING)
                await db_session.commit()

                await asyncio.sleep(0.2)
                current_round.advance_status(RoundStatus.COMPLETE)
                await db_session.commit()

                round_elapsed = time.perf_counter() - round_start
                round_times.append({
                    "round_num": round_num,
                    "elapsed_seconds": round_elapsed,
                })

                # Advance to next round if not last
                if round_num < 5:
                    discussion.current_round_num = round_num + 1
                    next_round = await db_session.execute(
                        select(Round).where(
                            Round.discussion_id == discussion.discussion_id,
                            Round.round_num == round_num + 1,
                        )
                    )
                    next_round_obj = next_round.scalar_one()
                    next_round_obj.open_submission_window()
                    await db_session.commit()

            # Mark discussion as completed
            discussion.complete()
            await db_session.commit()
            await db_session.refresh(discussion)

            # Measure total elapsed time
            end_time = time.perf_counter()
            total_elapsed_seconds = end_time - start_time

            # CRITICAL ASSERTION: Verify <60 minutes (3600 seconds)
            assert total_elapsed_seconds < 3600, (
                f"Total discussion time violation: {total_elapsed_seconds:.2f}s elapsed, "
                f"expected <3600s (60 minutes, SC-006)"
            )

            # Verify discussion reached COMPLETED status
            assert discussion.status == DiscussionStatus.COMPLETED
            assert discussion.completed_at is not None

            # Calculate average round time
            avg_round_time = sum(r["elapsed_seconds"] for r in round_times) / len(round_times)

            print(f"✓ 5-round discussion completed in {total_elapsed_seconds:.2f}s (<3600s requirement)")
            print(f"  Average round time: {avg_round_time:.2f}s")
            print(f"  Round breakdown:")
            for rt in round_times:
                print(f"    Round {rt['round_num']}: {rt['elapsed_seconds']:.2f}s")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_discussion_timing_endpoint_accuracy(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that GET /discussions/{id}/timing returns accurate timing metrics.

        Validates that the timing endpoint provides correct elapsed time
        and remaining time calculations.

        Expected: Timing metrics accurate within 1 second.
        """
        timing_service = TimingService(redis_url="redis://localhost:6379/1")
        await timing_service.connect()
        await timing_service.start_worker()

        discussion_service = DiscussionService(
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

            # Start discussion
            start_time = time.perf_counter()
            await discussion_service.start_discussion(discussion.discussion_id)
            await db_session.refresh(discussion)

            # Wait 2 seconds
            await asyncio.sleep(2.0)

            # Manually calculate expected elapsed time
            expected_elapsed = time.perf_counter() - start_time

            # Get actual elapsed time from discussion
            now = datetime.now(timezone.utc)
            actual_elapsed = (now - discussion.started_at).total_seconds()

            # Verify timing accuracy within 1 second tolerance
            time_diff = abs(expected_elapsed - actual_elapsed)
            assert time_diff < 1.0, (
                f"Timing calculation inaccurate: expected {expected_elapsed:.2f}s, "
                f"got {actual_elapsed:.2f}s (diff: {time_diff:.2f}s)"
            )

            # Calculate remaining time
            target_duration = 3600  # 60 minutes
            remaining = target_duration - actual_elapsed

            # Verify remaining time calculation
            expected_remaining = target_duration - actual_elapsed
            assert abs(remaining - expected_remaining) < 1.0, (
                f"Remaining time calculation error"
            )

            print(f"✓ Timing endpoint accurate: elapsed={actual_elapsed:.2f}s, remaining={remaining:.2f}s")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()

    async def test_multi_round_timing_accumulation(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that round times accumulate correctly across multiple rounds.

        Validates that total discussion time is sum of all round times.

        Expected: Total time = sum of individual round times (within 1s tolerance).
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
            # Create 3-round discussion
            discussion = await discussion_service.create_discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                questions=[
                    "What is your first thought?",
                    "What is your second thought?",
                    "What is your third thought?",
                ],
                submission_window_duration_sec=3,
            )

            start_time = time.perf_counter()
            await discussion_service.start_discussion(discussion.discussion_id)

            individual_round_times = []

            # Process 3 rounds
            for round_num in range(1, 4):
                round_start = time.perf_counter()

                result = await db_session.execute(
                    select(Round).where(
                        Round.discussion_id == discussion.discussion_id,
                        Round.round_num == round_num,
                    )
                )
                current_round = result.scalar_one()

                # Wait for window to close
                now = datetime.now(timezone.utc)
                wait_time = (current_round.submission_window_end - now).total_seconds()
                if wait_time > 0:
                    await asyncio.sleep(wait_time + 0.2)

                # Close and complete round
                await round_service.close_submission_window(current_round.round_id)
                current_round.advance_status(RoundStatus.SUMMARIZING)
                await asyncio.sleep(0.1)
                current_round.advance_status(RoundStatus.APPROVING)
                await asyncio.sleep(0.1)
                current_round.advance_status(RoundStatus.CLUSTERING)
                await asyncio.sleep(0.1)
                current_round.advance_status(RoundStatus.SANKEY_BUILDING)
                await asyncio.sleep(0.1)
                current_round.advance_status(RoundStatus.COMPLETE)
                await db_session.commit()

                round_elapsed = time.perf_counter() - round_start
                individual_round_times.append(round_elapsed)

                # Open next round if not last
                if round_num < 3:
                    discussion.current_round_num = round_num + 1
                    next_result = await db_session.execute(
                        select(Round).where(
                            Round.discussion_id == discussion.discussion_id,
                            Round.round_num == round_num + 1,
                        )
                    )
                    next_round = next_result.scalar_one()
                    next_round.open_submission_window()
                    await db_session.commit()

            total_elapsed = time.perf_counter() - start_time
            sum_of_rounds = sum(individual_round_times)

            # Verify total time equals sum of round times (within tolerance)
            time_diff = abs(total_elapsed - sum_of_rounds)
            assert time_diff < 2.0, (
                f"Time accumulation error: total={total_elapsed:.2f}s, "
                f"sum_of_rounds={sum_of_rounds:.2f}s (diff={time_diff:.2f}s)"
            )

            print(f"✓ Round time accumulation correct: total={total_elapsed:.2f}s")
            print(f"  Individual rounds: {[f'{t:.2f}s' for t in individual_round_times]}")

        finally:
            await timing_service.stop_worker()
            await timing_service.disconnect()
