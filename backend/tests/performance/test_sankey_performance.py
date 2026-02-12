"""
Performance benchmark for Sankey diagram construction (T081).

Tests that Sankey construction completes in <2 seconds per round for 100 participants, 3 rounds.

Task: T081 - Sankey construction performance benchmark
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
from src.models.approved_summary import ApprovedSummary
from src.models.thought_space import ThoughtSpace
from src.services.flow_service import FlowService


@pytest.mark.asyncio
@pytest.mark.performance
@pytest.mark.benchmark
class TestSankeyConstructionPerformance:
    """Performance benchmarks for Sankey diagram construction."""

    async def test_sankey_construction_100_participants_3_rounds(
        self, db_session, redis_client, event_bus
    ):
        """
        Test Sankey construction performance with 100 participants, 3 rounds (T081).

        Constitutional Requirement: SC-004
        - Sankey diagram construction: <2 seconds per round
        - Test with realistic load: 100 participants
        - Measure construction time for 3-round discussion

        Expected: Construction <2 seconds per round (total <6 seconds for 3 rounds).
        """
        num_participants = 100
        num_rounds = 3
        num_clusters_per_round = 5  # Typical clustering output

        # Create discussion with 3 rounds
        discussion = Discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=num_rounds,
        )
        db_session.add(discussion)
        await db_session.flush()

        # Create rounds
        rounds = []
        for round_num in range(1, num_rounds + 1):
            round_obj = Round(
                discussion_id=discussion.discussion_id,
                round_num=round_num,
                question_text=f"What are your thoughts on topic {round_num}?",
                submission_window_duration_sec=300,
            )
            db_session.add(round_obj)
            rounds.append(round_obj)

        await db_session.flush()

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

        await db_session.flush()

        # Create submissions, approved summaries, and thought spaces for each round
        for round_idx, round_obj in enumerate(rounds):
            # Open round
            round_obj.open_submission_window()

            # Create thought spaces (clusters) for this round
            thought_spaces = []
            for cluster_idx in range(num_clusters_per_round):
                ts = ThoughtSpace(
                    round_id=round_obj.round_id,
                    cluster_id=uuid4(),
                    label_summary=f"Cluster {cluster_idx} in Round {round_obj.round_num}",
                    member_count=0,  # Will update below
                    member_pct=0.0,
                )
                db_session.add(ts)
                thought_spaces.append(ts)

            await db_session.flush()

            # Distribute participants across clusters
            for participant_idx, participant in enumerate(participants):
                # Create submission
                submission = Submission(
                    participant_id=participant.participant_id,
                    round_id=round_obj.round_id,
                    submission_text=f"Participant {participant_idx} submission for round {round_obj.round_num}",
                    modality=SubmissionModality.TEXT,
                )
                db_session.add(submission)
                await db_session.flush()

                # Assign to cluster (distribute evenly)
                cluster_idx = participant_idx % num_clusters_per_round
                target_cluster = thought_spaces[cluster_idx]

                # Create approved summary
                approved_summary = ApprovedSummary(
                    round_id=round_obj.round_id,
                    participant_id=participant.participant_id,
                    submission_id=submission.submission_id,
                    cluster_id=target_cluster.cluster_id,
                    summary_text=f"Summary for participant {participant_idx}",
                )
                db_session.add(approved_summary)

            await db_session.flush()

            # Update thought space member counts
            for ts in thought_spaces:
                result = await db_session.execute(
                    select(ApprovedSummary).where(
                        ApprovedSummary.cluster_id == ts.cluster_id
                    )
                )
                members = result.scalars().all()
                ts.member_count = len(members)
                ts.member_pct = len(members) / num_participants

        await db_session.commit()

        # Now benchmark Sankey construction (flow computation)
        flow_service = FlowService(session=db_session)
        construction_times = []

        print(f"\n=== Sankey Construction Performance Benchmark ===")
        print(f"Participants: {num_participants}, Rounds: {num_rounds}, Clusters/Round: {num_clusters_per_round}")

        # Measure flow computation between consecutive rounds
        for round_idx in range(num_rounds - 1):
            source_round = rounds[round_idx]
            target_round = rounds[round_idx + 1]

            # Measure construction time
            start_time = time.perf_counter()

            flows = await flow_service.compute_flows(
                source_round_id=source_round.round_id,
                target_round_id=target_round.round_id,
            )

            end_time = time.perf_counter()
            elapsed_seconds = end_time - start_time
            construction_times.append(elapsed_seconds)

            # CRITICAL ASSERTION: Verify <2 seconds per round (SC-004)
            assert elapsed_seconds < 2.0, (
                f"Sankey construction time violation for Round {source_round.round_num}→{target_round.round_num}: "
                f"{elapsed_seconds:.3f}s elapsed, expected <2s (SC-004)"
            )

            print(f"✓ Round {source_round.round_num}→{target_round.round_num}: {elapsed_seconds:.3f}s (<2s requirement)")
            print(f"  Flows computed: {len(flows)}")

        # Calculate statistics
        avg_time = sum(construction_times) / len(construction_times)
        max_time = max(construction_times)
        total_time = sum(construction_times)

        print(f"\nPerformance Summary:")
        print(f"  Average time per round: {avg_time:.3f}s")
        print(f"  Max time per round: {max_time:.3f}s")
        print(f"  Total construction time: {total_time:.3f}s")
        print(f"  All rounds <2s: {'✓ PASS' if max_time < 2.0 else '✗ FAIL'}")

        # Verify all rounds meet requirement
        assert max_time < 2.0, (
            f"Worst-case construction time {max_time:.3f}s exceeds 2s requirement"
        )

    async def test_sankey_construction_scales_linearly(
        self, db_session, redis_client, event_bus
    ):
        """
        Test that Sankey construction time scales linearly with participant count.

        Validates performance characteristics at different scales:
        - 25 participants
        - 50 participants
        - 100 participants

        Expected: Time scales linearly (O(N)) with participant count.
        """
        participant_counts = [25, 50, 100]
        num_rounds = 2
        num_clusters = 5

        results = []

        for num_participants in participant_counts:
            # Create discussion
            discussion = Discussion(
                community_id=uuid4(),
                host_user_id=uuid4(),
                mode=DiscussionMode.HOST_DEFINED,
                total_rounds=num_rounds,
            )
            db_session.add(discussion)
            await db_session.flush()

            # Create rounds
            rounds = []
            for round_num in range(1, num_rounds + 1):
                round_obj = Round(
                    discussion_id=discussion.discussion_id,
                    round_num=round_num,
                    question_text=f"What are your thoughts?",
                    submission_window_duration_sec=300,
                )
                db_session.add(round_obj)
                rounds.append(round_obj)

            await db_session.flush()

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

            await db_session.flush()

            # Create data for both rounds
            for round_obj in rounds:
                round_obj.open_submission_window()

                # Create thought spaces
                thought_spaces = []
                for cluster_idx in range(num_clusters):
                    ts = ThoughtSpace(
                        round_id=round_obj.round_id,
                        cluster_id=uuid4(),
                        label_summary=f"Cluster {cluster_idx}",
                        member_count=0,
                        member_pct=0.0,
                    )
                    db_session.add(ts)
                    thought_spaces.append(ts)

                await db_session.flush()

                # Create submissions and approved summaries
                for participant_idx, participant in enumerate(participants):
                    submission = Submission(
                        participant_id=participant.participant_id,
                        round_id=round_obj.round_id,
                        submission_text=f"Submission {participant_idx}",
                        modality=SubmissionModality.TEXT,
                    )
                    db_session.add(submission)
                    await db_session.flush()

                    cluster_idx = participant_idx % num_clusters
                    target_cluster = thought_spaces[cluster_idx]

                    approved_summary = ApprovedSummary(
                        round_id=round_obj.round_id,
                        participant_id=participant.participant_id,
                        submission_id=submission.submission_id,
                        cluster_id=target_cluster.cluster_id,
                        summary_text=f"Summary {participant_idx}",
                    )
                    db_session.add(approved_summary)

                await db_session.flush()

                # Update counts
                for ts in thought_spaces:
                    result = await db_session.execute(
                        select(ApprovedSummary).where(
                            ApprovedSummary.cluster_id == ts.cluster_id
                        )
                    )
                    members = result.scalars().all()
                    ts.member_count = len(members)
                    ts.member_pct = len(members) / num_participants

            await db_session.commit()

            # Measure flow computation
            flow_service = FlowService(session=db_session)
            start_time = time.perf_counter()

            flows = await flow_service.compute_flows(
                source_round_id=rounds[0].round_id,
                target_round_id=rounds[1].round_id,
            )

            elapsed = time.perf_counter() - start_time

            results.append({
                "participants": num_participants,
                "time_seconds": elapsed,
                "flows": len(flows),
            })

            # Verify <2s requirement
            assert elapsed < 2.0, (
                f"Construction time for {num_participants} participants: {elapsed:.3f}s, expected <2s"
            )

        # Print results
        print(f"\n=== Scalability Benchmark ===")
        for r in results:
            time_per_participant_ms = (r["time_seconds"] / r["participants"]) * 1000
            print(
                f"{r['participants']:3d} participants: {r['time_seconds']:.3f}s "
                f"({time_per_participant_ms:.2f}ms/participant, {r['flows']} flows)"
            )

        # Verify linear scaling (each doubling should roughly double time)
        # Allow for 3x variance due to overhead and database operations
        if len(results) >= 2:
            ratio_participants = results[1]["participants"] / results[0]["participants"]
            ratio_time = results[1]["time_seconds"] / results[0]["time_seconds"]

            # Time ratio should be close to participant ratio (linear scaling)
            # Allow up to 3x variance for overhead
            assert ratio_time < ratio_participants * 3, (
                f"Scaling appears worse than linear: {results[0]['participants']} participants took "
                f"{results[0]['time_seconds']:.3f}s, {results[1]['participants']} participants took "
                f"{results[1]['time_seconds']:.3f}s (ratio: {ratio_time:.2f}x, expected ~{ratio_participants:.2f}x)"
            )

        print("✓ Performance scales linearly with participant count")

    async def test_sankey_construction_with_complex_flow_patterns(
        self, db_session, redis_client, event_bus
    ):
        """
        Test Sankey construction performance with complex flow patterns.

        Tests worst-case scenario:
        - 100 participants
        - High cluster count (10 clusters)
        - Maximum flow complexity (all participants move between rounds)

        Expected: Still completes <2 seconds per round even with complexity.
        """
        num_participants = 100
        num_clusters_round1 = 10
        num_clusters_round2 = 10

        # Create discussion
        discussion = Discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
        )
        db_session.add(discussion)
        await db_session.flush()

        # Create rounds
        round1 = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your initial thoughts?",
            submission_window_duration_sec=300,
        )
        round2 = Round(
            discussion_id=discussion.discussion_id,
            round_num=2,
            question_text="How have your thoughts evolved?",
            submission_window_duration_sec=300,
        )
        db_session.add(round1)
        db_session.add(round2)
        await db_session.flush()

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

        await db_session.flush()

        # Create thought spaces for round 1
        round1.open_submission_window()
        round1_clusters = []
        for i in range(num_clusters_round1):
            ts = ThoughtSpace(
                round_id=round1.round_id,
                cluster_id=uuid4(),
                label_summary=f"R1 Cluster {i}",
                member_count=0,
                member_pct=0.0,
            )
            db_session.add(ts)
            round1_clusters.append(ts)

        await db_session.flush()

        # Assign participants to round 1 clusters
        for idx, participant in enumerate(participants):
            submission = Submission(
                participant_id=participant.participant_id,
                round_id=round1.round_id,
                submission_text=f"R1 Submission {idx}",
                modality=SubmissionModality.TEXT,
            )
            db_session.add(submission)
            await db_session.flush()

            cluster_idx = idx % num_clusters_round1
            approved_summary = ApprovedSummary(
                round_id=round1.round_id,
                participant_id=participant.participant_id,
                submission_id=submission.submission_id,
                cluster_id=round1_clusters[cluster_idx].cluster_id,
                summary_text=f"R1 Summary {idx}",
            )
            db_session.add(approved_summary)

        # Update round 1 cluster counts
        for ts in round1_clusters:
            result = await db_session.execute(
                select(ApprovedSummary).where(ApprovedSummary.cluster_id == ts.cluster_id)
            )
            members = result.scalars().all()
            ts.member_count = len(members)
            ts.member_pct = len(members) / num_participants

        await db_session.flush()

        # Create thought spaces for round 2
        round2.open_submission_window()
        round2_clusters = []
        for i in range(num_clusters_round2):
            ts = ThoughtSpace(
                round_id=round2.round_id,
                cluster_id=uuid4(),
                label_summary=f"R2 Cluster {i}",
                member_count=0,
                member_pct=0.0,
            )
            db_session.add(ts)
            round2_clusters.append(ts)

        await db_session.flush()

        # Assign participants to round 2 clusters
        # Use different distribution to create complex flow pattern
        for idx, participant in enumerate(participants):
            submission = Submission(
                participant_id=participant.participant_id,
                round_id=round2.round_id,
                submission_text=f"R2 Submission {idx}",
                modality=SubmissionModality.TEXT,
            )
            db_session.add(submission)
            await db_session.flush()

            # Shift cluster assignment to create complex flows
            cluster_idx = (idx * 3) % num_clusters_round2
            approved_summary = ApprovedSummary(
                round_id=round2.round_id,
                participant_id=participant.participant_id,
                submission_id=submission.submission_id,
                cluster_id=round2_clusters[cluster_idx].cluster_id,
                summary_text=f"R2 Summary {idx}",
            )
            db_session.add(approved_summary)

        # Update round 2 cluster counts
        for ts in round2_clusters:
            result = await db_session.execute(
                select(ApprovedSummary).where(ApprovedSummary.cluster_id == ts.cluster_id)
            )
            members = result.scalars().all()
            ts.member_count = len(members)
            ts.member_pct = len(members) / num_participants

        await db_session.commit()

        # Benchmark complex flow computation
        flow_service = FlowService(session=db_session)
        start_time = time.perf_counter()

        flows = await flow_service.compute_flows(
            source_round_id=round1.round_id,
            target_round_id=round2.round_id,
        )

        elapsed = time.perf_counter() - start_time

        # CRITICAL ASSERTION: Even with complexity, must be <2s
        assert elapsed < 2.0, (
            f"Complex flow construction: {elapsed:.3f}s, expected <2s (SC-004)"
        )

        print(f"\n=== Complex Flow Pattern Benchmark ===")
        print(f"Participants: {num_participants}")
        print(f"Round 1 clusters: {num_clusters_round1}")
        print(f"Round 2 clusters: {num_clusters_round2}")
        print(f"Flows computed: {len(flows)}")
        print(f"Construction time: {elapsed:.3f}s (<2s requirement)")
        print(f"✓ Complex flow pattern handled within performance requirements")
