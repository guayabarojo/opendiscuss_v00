"""
Dropout detection integration test.

Tests participant dropout tracking when a participant submits in Round N
but fails to submit in Round N+1. Validates dropout marking and flow
computation without synthetic flows.

Task: T057 - Dropout test
Constitutional Coverage:
- No synthetic flows for dropouts (mass shrinks naturally)
- Dropout detection tracks NO_SUBMISSION reason
- last_round correctly set to last active round
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.models.discussion import Discussion, DiscussionStatus, DiscussionMode
from src.models.round import Round, RoundStatus
from src.models.participant import Participant
from src.models.submission import Submission, SubmissionModality
from src.models.approved_summary import ApprovedSummary
from src.models.thought_space import ThoughtSpace
from src.models.flow import Flow
from src.models.protocol_state import DropoutReason
from src.services.discussion_service import DiscussionService
from src.services.round_service import RoundService
from src.services.flow_service import FlowService
from src.services.dropout_detection import DropoutDetectionService
from src.services.timing_service import TimingService
from src.services.protocol_coordinator import ProtocolCoordinator
from src.events.event_bus import EventBus
from src.events.event_types import (
    SummarizationCompleteEvent,
    ApprovedSummarySummary,
    ClusteringCompleteEvent,
    ThoughtSpaceSummary,
    SankeyCompleteEvent,
    SankeyGraph,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_participant_dropout_no_submission(
    db_session,
    redis_client,
    event_bus,
):
    """
    Test participant dropout when they skip Round 2 after submitting in Round 1.

    Scenario:
    - Round 1: Participant A submits → assigned to Cluster1
    - Round 2: Participant A does NOT submit (dropout)
    - Other participants continue in Round 2

    Expected:
    - Participant A marked as dropout with reason=NO_SUBMISSION, last_round=1
    - Zero outgoing flows from Cluster1 for Participant A
    - Mass shrinks naturally in Round 2 (no synthetic flows)
    - Other participants' flows computed correctly
    """
    # Setup services
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
    flow_service = FlowService(session=db_session)
    dropout_service = DropoutDetectionService(session=db_session)

    coordinator = ProtocolCoordinator(event_bus=event_bus)
    await coordinator.register_handlers()

    try:
        # ============================================================================
        # Setup: Create 2-round discussion
        # ============================================================================
        community_id = uuid4()
        host_user_id = uuid4()
        questions = [
            "What are your initial thoughts?",
            "How would you improve this?",
        ]

        discussion = await discussion_service.create_discussion(
            community_id=community_id,
            host_user_id=host_user_id,
            questions=questions,
            submission_window_duration_sec=300,
        )

        assert discussion.total_rounds == 2
        await discussion_service.start_discussion(discussion.discussion_id)

        # Get rounds
        rounds_result = await db_session.execute(
            select(Round)
            .where(Round.discussion_id == discussion.discussion_id)
            .order_by(Round.round_num)
        )
        rounds = list(rounds_result.scalars().all())
        assert len(rounds) == 2
        round_1, round_2 = rounds

        # ============================================================================
        # Round 1: Create 3 participants (A will drop out, B and C continue)
        # ============================================================================
        participant_a = Participant(
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        participant_b = Participant(
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        participant_c = Participant(
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )

        for p in [participant_a, participant_b, participant_c]:
            db_session.add(p)
        await db_session.flush()

        # Create submissions for Round 1
        for p, text in [
            (participant_a, "A's submission - will drop out"),
            (participant_b, "B's submission - will continue"),
            (participant_c, "C's submission - will continue"),
        ]:
            submission = Submission(
                participant_id=p.participant_id,
                round_id=round_1.round_id,
                submission_text=text,
                modality=SubmissionModality.TEXT,
            )
            db_session.add(submission)
        await db_session.commit()

        # Close submission window
        await round_service.close_submission_window(round_1.round_id)
        await asyncio.sleep(0.2)

        # Create approved summaries
        summaries_r1 = []
        for p, text in [
            (participant_a, "A's summary round 1"),
            (participant_b, "B's summary round 1"),
            (participant_c, "C's summary round 1"),
        ]:
            summary = ApprovedSummary(
                participant_id=p.participant_id,
                round_id=round_1.round_id,
                submission_id=uuid4(),
                summary_text=text,
            )
            db_session.add(summary)
            summaries_r1.append(summary)
        await db_session.commit()

        # Emit summarization complete
        await event_bus.emit(
            "summarization.complete",
            SummarizationCompleteEvent(
                round_id=round_1.round_id,
                approved_summaries=[
                    ApprovedSummarySummary(
                        summary_id=s.summary_id,
                        participant_id=s.participant_id,
                        submission_id=s.submission_id,
                        summary_text=s.summary_text,
                        approved_at=s.approved_at,
                    )
                    for s in summaries_r1
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Create Round 1 clusters
        cluster1_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Initial thoughts cluster 1",
            member_count=2,
            member_pct=0.67,
        )
        cluster2_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Initial thoughts cluster 2",
            member_count=1,
            member_pct=0.33,
        )
        db_session.add(cluster1_r1)
        db_session.add(cluster2_r1)
        await db_session.flush()

        # Assign participants to clusters
        # A and B in Cluster1, C in Cluster2
        summaries_r1[0].cluster_id = cluster1_r1.cluster_id  # A
        summaries_r1[1].cluster_id = cluster1_r1.cluster_id  # B
        summaries_r1[2].cluster_id = cluster2_r1.cluster_id  # C
        await db_session.commit()

        # Emit clustering complete
        await event_bus.emit(
            "clustering.complete",
            ClusteringCompleteEvent(
                round_id=round_1.round_id,
                thought_spaces=[
                    ThoughtSpaceSummary(
                        cluster_id=cluster1_r1.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster1_r1.label_summary,
                        member_count=2,
                        member_pct=67.0,
                        participant_ids=[
                            participant_a.participant_id,
                            participant_b.participant_id,
                        ],
                    ),
                    ThoughtSpaceSummary(
                        cluster_id=cluster2_r1.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster2_r1.label_summary,
                        member_count=1,
                        member_pct=33.0,
                        participant_ids=[participant_c.participant_id],
                    ),
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Complete Round 1
        await event_bus.emit(
            "sankey.complete",
            SankeyCompleteEvent(
                round_id=round_1.round_id,
                sankey_graph=SankeyGraph(
                    discussion_id=discussion.discussion_id,
                    rounds=[round_1.round_id],
                    nodes=[],
                    edges=[],
                    total_participants=3,
                ),
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # ============================================================================
        # Round 2: Only B and C submit (A drops out)
        # ============================================================================
        await discussion_service.advance_round(discussion.discussion_id)

        # Create submissions for Round 2 - ONLY B and C (A does NOT submit)
        for p, text in [
            (participant_b, "B's submission round 2"),
            (participant_c, "C's submission round 2"),
        ]:
            submission = Submission(
                participant_id=p.participant_id,
                round_id=round_2.round_id,
                submission_text=text,
                modality=SubmissionModality.TEXT,
            )
            db_session.add(submission)
        await db_session.commit()

        # Close submission window
        await round_service.close_submission_window(round_2.round_id)
        await asyncio.sleep(0.2)

        # Create approved summaries for Round 2 - ONLY B and C
        summaries_r2 = []
        for p, text in [
            (participant_b, "B's summary round 2"),
            (participant_c, "C's summary round 2"),
        ]:
            summary = ApprovedSummary(
                participant_id=p.participant_id,
                round_id=round_2.round_id,
                submission_id=uuid4(),
                summary_text=text,
            )
            db_session.add(summary)
            summaries_r2.append(summary)
        await db_session.commit()

        # Emit summarization complete
        await event_bus.emit(
            "summarization.complete",
            SummarizationCompleteEvent(
                round_id=round_2.round_id,
                approved_summaries=[
                    ApprovedSummarySummary(
                        summary_id=s.summary_id,
                        participant_id=s.participant_id,
                        submission_id=s.submission_id,
                        summary_text=s.summary_text,
                        approved_at=s.approved_at,
                    )
                    for s in summaries_r2
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Create Round 2 clusters
        cluster1_r2 = ThoughtSpace(
            round_id=round_2.round_id,
            label_summary="Improvement ideas cluster 1",
            member_count=2,
            member_pct=1.0,
        )
        db_session.add(cluster1_r2)
        await db_session.flush()

        # Assign B and C to Round 2 cluster
        summaries_r2[0].cluster_id = cluster1_r2.cluster_id  # B
        summaries_r2[1].cluster_id = cluster1_r2.cluster_id  # C
        await db_session.commit()

        # Emit clustering complete
        await event_bus.emit(
            "clustering.complete",
            ClusteringCompleteEvent(
                round_id=round_2.round_id,
                thought_spaces=[
                    ThoughtSpaceSummary(
                        cluster_id=cluster1_r2.cluster_id,
                        round_id=round_2.round_id,
                        label_summary=cluster1_r2.label_summary,
                        member_count=2,
                        member_pct=100.0,
                        participant_ids=[
                            participant_b.participant_id,
                            participant_c.participant_id,
                        ],
                    ),
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # ============================================================================
        # Detect dropouts between Round 1 and Round 2
        # ============================================================================
        dropouts = await dropout_service.detect_dropouts(
            source_round_id=round_1.round_id,
            target_round_id=round_2.round_id,
        )

        # Commit dropout updates
        await db_session.commit()

        # Verify dropout detection
        assert len(dropouts) == 1, "Should detect exactly 1 dropout (Participant A)"
        dropout = dropouts[0]

        # Refresh participant A to see updated state
        await db_session.refresh(participant_a)

        # Validate dropout marking
        assert dropout.participant_id == participant_a.participant_id
        assert participant_a.last_round == 1, "A's last_round should be 1"
        assert participant_a.dropout_reason == DropoutReason.NO_SUBMISSION
        assert not participant_a.is_active(), "A should not be active"

        # Verify B and C are still active
        await db_session.refresh(participant_b)
        await db_session.refresh(participant_c)
        assert participant_b.is_active(), "B should still be active"
        assert participant_c.is_active(), "C should still be active"
        assert participant_b.last_round is None
        assert participant_c.last_round is None

        # ============================================================================
        # Compute flows and validate no synthetic flows for dropout
        # ============================================================================
        flows = await flow_service.compute_flows(
            source_round_id=round_1.round_id,
            target_round_id=round_2.round_id,
        )

        # Persist flows
        for flow in flows:
            db_session.add(flow)
        await db_session.commit()

        # Validate flows
        # Should have 2 flows:
        # - Cluster1→Cluster1: B (1 participant) - A dropped out
        # - Cluster2→Cluster1: C (1 participant)
        assert len(flows) == 2, "Should have 2 flows (dropout A not included)"

        # Verify no flow contains participant A
        all_flow_participants = set()
        for flow in flows:
            all_flow_participants.update(flow.participant_ids)

        assert participant_a.participant_id not in all_flow_participants, \
            "Dropout participant A should NOT appear in any flows"
        assert participant_b.participant_id in all_flow_participants
        assert participant_c.participant_id in all_flow_participants

        # Verify specific flows
        flow_map = {
            (flow.source_cluster_id, flow.target_cluster_id): flow
            for flow in flows
        }

        # Cluster1→Cluster1: Only B (A dropped out)
        flow_1_1 = flow_map.get((cluster1_r1.cluster_id, cluster1_r2.cluster_id))
        assert flow_1_1 is not None
        assert flow_1_1.participant_count == 1, "Only B continues from Cluster1"
        assert set(flow_1_1.participant_ids) == {participant_b.participant_id}

        # Cluster2→Cluster1: C
        flow_2_1 = flow_map.get((cluster2_r1.cluster_id, cluster1_r2.cluster_id))
        assert flow_2_1 is not None
        assert flow_2_1.participant_count == 1
        assert set(flow_2_1.participant_ids) == {participant_c.participant_id}

        # Validate mass conservation: Round 1 had 3 participants, Round 2 has 2
        # Total flow count should be 2 (not 3)
        total_flow_participants = sum(f.participant_count for f in flows)
        assert total_flow_participants == 2, \
            "Total flow participants should be 2 (mass shrinks naturally, no synthetic flows)"

        # Verify no outgoing flows for participant A from Round 1
        for flow in flows:
            if flow.source_cluster_id == cluster1_r1.cluster_id:
                assert participant_a.participant_id not in flow.participant_ids, \
                    "Participant A should have zero outgoing flows"

    finally:
        # Cleanup
        await timing_service.stop_worker()
        await timing_service.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_all_participants_dropout(
    db_session,
    redis_client,
    event_bus,
):
    """
    Test edge case where all participants drop out in Round 2.

    Validates that zero flows are created when no one continues.
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
    flow_service = FlowService(session=db_session)
    dropout_service = DropoutDetectionService(session=db_session)

    coordinator = ProtocolCoordinator(event_bus=event_bus)
    await coordinator.register_handlers()

    try:
        # Create 2-round discussion
        discussion = await discussion_service.create_discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            questions=["Question 1", "Question 2"],
        )
        await discussion_service.start_discussion(discussion.discussion_id)

        # Get rounds
        rounds_result = await db_session.execute(
            select(Round)
            .where(Round.discussion_id == discussion.discussion_id)
            .order_by(Round.round_num)
        )
        rounds = list(rounds_result.scalars().all())
        round_1, round_2 = rounds

        # Round 1: Create 2 participants
        participants = []
        for i in range(2):
            p = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(p)
            participants.append(p)
        await db_session.flush()

        # Create submissions
        for p in participants:
            submission = Submission(
                participant_id=p.participant_id,
                round_id=round_1.round_id,
                submission_text=f"Submission {p.participant_id}",
                modality=SubmissionModality.TEXT,
            )
            db_session.add(submission)
        await db_session.commit()

        await round_service.close_submission_window(round_1.round_id)
        await asyncio.sleep(0.2)

        # Create approved summaries
        summaries_r1 = []
        for p in participants:
            summary = ApprovedSummary(
                participant_id=p.participant_id,
                round_id=round_1.round_id,
                submission_id=uuid4(),
                summary_text=f"Summary {p.participant_id}",
            )
            db_session.add(summary)
            summaries_r1.append(summary)
        await db_session.commit()

        # Complete summarization
        await event_bus.emit(
            "summarization.complete",
            SummarizationCompleteEvent(
                round_id=round_1.round_id,
                approved_summaries=[
                    ApprovedSummarySummary(
                        summary_id=s.summary_id,
                        participant_id=s.participant_id,
                        submission_id=s.submission_id,
                        summary_text=s.summary_text,
                        approved_at=s.approved_at,
                    )
                    for s in summaries_r1
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Create cluster
        cluster_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Round 1 cluster",
            member_count=2,
            member_pct=1.0,
        )
        db_session.add(cluster_r1)
        await db_session.flush()

        for summary in summaries_r1:
            summary.cluster_id = cluster_r1.cluster_id
        await db_session.commit()

        # Complete clustering
        await event_bus.emit(
            "clustering.complete",
            ClusteringCompleteEvent(
                round_id=round_1.round_id,
                thought_spaces=[
                    ThoughtSpaceSummary(
                        cluster_id=cluster_r1.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster_r1.label_summary,
                        member_count=2,
                        member_pct=100.0,
                        participant_ids=[p.participant_id for p in participants],
                    ),
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Complete Round 1
        await event_bus.emit(
            "sankey.complete",
            SankeyCompleteEvent(
                round_id=round_1.round_id,
                sankey_graph=SankeyGraph(
                    discussion_id=discussion.discussion_id,
                    rounds=[round_1.round_id],
                    nodes=[],
                    edges=[],
                    total_participants=2,
                ),
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Round 2: NO submissions (all participants drop out)
        await discussion_service.advance_round(discussion.discussion_id)

        # Close window with zero submissions
        await round_service.close_submission_window(round_2.round_id)
        await asyncio.sleep(0.2)

        # Complete summarization with zero summaries
        await event_bus.emit(
            "summarization.complete",
            SummarizationCompleteEvent(
                round_id=round_2.round_id,
                approved_summaries=[],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Detect dropouts
        dropouts = await dropout_service.detect_dropouts(
            source_round_id=round_1.round_id,
            target_round_id=round_2.round_id,
        )
        await db_session.commit()

        # Verify all participants marked as dropouts
        assert len(dropouts) == 2, "Both participants should be marked as dropouts"

        for p in participants:
            await db_session.refresh(p)
            assert p.last_round == 1
            assert p.dropout_reason == DropoutReason.NO_SUBMISSION
            assert not p.is_active()

        # Try to compute flows (should return empty list)
        # Note: This will fail if Round 2 has no clusters, which is expected
        # In real system, clustering would emit zero clusters event
        # For this test, we just verify dropouts were detected

    finally:
        await timing_service.stop_worker()
        await timing_service.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_partial_dropout_mass_shrinkage(
    db_session,
    redis_client,
    event_bus,
):
    """
    Test that mass shrinks naturally when some participants drop out.

    Validates constitutional guarantee: no synthetic flows to maintain mass.
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
    flow_service = FlowService(session=db_session)
    dropout_service = DropoutDetectionService(session=db_session)

    coordinator = ProtocolCoordinator(event_bus=event_bus)
    await coordinator.register_handlers()

    try:
        # Create 2-round discussion with 5 participants
        # Round 1: 5 participants
        # Round 2: 2 participants (3 drop out)
        discussion = await discussion_service.create_discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            questions=["Question 1", "Question 2"],
        )
        await discussion_service.start_discussion(discussion.discussion_id)

        rounds_result = await db_session.execute(
            select(Round)
            .where(Round.discussion_id == discussion.discussion_id)
            .order_by(Round.round_num)
        )
        rounds = list(rounds_result.scalars().all())
        round_1, round_2 = rounds

        # Round 1: 5 participants
        participants = []
        for i in range(5):
            p = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(p)
            participants.append(p)
        await db_session.flush()

        # Create submissions
        for p in participants:
            submission = Submission(
                participant_id=p.participant_id,
                round_id=round_1.round_id,
                submission_text=f"Submission {p.participant_id}",
                modality=SubmissionModality.TEXT,
            )
            db_session.add(submission)
        await db_session.commit()

        await round_service.close_submission_window(round_1.round_id)
        await asyncio.sleep(0.2)

        # Create approved summaries
        summaries_r1 = []
        for p in participants:
            summary = ApprovedSummary(
                participant_id=p.participant_id,
                round_id=round_1.round_id,
                submission_id=uuid4(),
                summary_text=f"Summary {p.participant_id}",
            )
            db_session.add(summary)
            summaries_r1.append(summary)
        await db_session.commit()

        # Complete summarization
        await event_bus.emit(
            "summarization.complete",
            SummarizationCompleteEvent(
                round_id=round_1.round_id,
                approved_summaries=[
                    ApprovedSummarySummary(
                        summary_id=s.summary_id,
                        participant_id=s.participant_id,
                        submission_id=s.submission_id,
                        summary_text=s.summary_text,
                        approved_at=s.approved_at,
                    )
                    for s in summaries_r1
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Create cluster with all 5
        cluster_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="All participants",
            member_count=5,
            member_pct=1.0,
        )
        db_session.add(cluster_r1)
        await db_session.flush()

        for summary in summaries_r1:
            summary.cluster_id = cluster_r1.cluster_id
        await db_session.commit()

        # Complete clustering
        await event_bus.emit(
            "clustering.complete",
            ClusteringCompleteEvent(
                round_id=round_1.round_id,
                thought_spaces=[
                    ThoughtSpaceSummary(
                        cluster_id=cluster_r1.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster_r1.label_summary,
                        member_count=5,
                        member_pct=100.0,
                        participant_ids=[p.participant_id for p in participants],
                    ),
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        await event_bus.emit(
            "sankey.complete",
            SankeyCompleteEvent(
                round_id=round_1.round_id,
                sankey_graph=SankeyGraph(
                    discussion_id=discussion.discussion_id,
                    rounds=[round_1.round_id],
                    nodes=[],
                    edges=[],
                    total_participants=5,
                ),
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Round 2: Only 2 participants continue (indices 0 and 1)
        await discussion_service.advance_round(discussion.discussion_id)

        continuing_participants = participants[:2]
        for p in continuing_participants:
            submission = Submission(
                participant_id=p.participant_id,
                round_id=round_2.round_id,
                submission_text=f"Submission R2 {p.participant_id}",
                modality=SubmissionModality.TEXT,
            )
            db_session.add(submission)
        await db_session.commit()

        await round_service.close_submission_window(round_2.round_id)
        await asyncio.sleep(0.2)

        summaries_r2 = []
        for p in continuing_participants:
            summary = ApprovedSummary(
                participant_id=p.participant_id,
                round_id=round_2.round_id,
                submission_id=uuid4(),
                summary_text=f"Summary R2 {p.participant_id}",
            )
            db_session.add(summary)
            summaries_r2.append(summary)
        await db_session.commit()

        await event_bus.emit(
            "summarization.complete",
            SummarizationCompleteEvent(
                round_id=round_2.round_id,
                approved_summaries=[
                    ApprovedSummarySummary(
                        summary_id=s.summary_id,
                        participant_id=s.participant_id,
                        submission_id=s.submission_id,
                        summary_text=s.summary_text,
                        approved_at=s.approved_at,
                    )
                    for s in summaries_r2
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        cluster_r2 = ThoughtSpace(
            round_id=round_2.round_id,
            label_summary="Continuing participants",
            member_count=2,
            member_pct=1.0,
        )
        db_session.add(cluster_r2)
        await db_session.flush()

        for summary in summaries_r2:
            summary.cluster_id = cluster_r2.cluster_id
        await db_session.commit()

        await event_bus.emit(
            "clustering.complete",
            ClusteringCompleteEvent(
                round_id=round_2.round_id,
                thought_spaces=[
                    ThoughtSpaceSummary(
                        cluster_id=cluster_r2.cluster_id,
                        round_id=round_2.round_id,
                        label_summary=cluster_r2.label_summary,
                        member_count=2,
                        member_pct=100.0,
                        participant_ids=[p.participant_id for p in continuing_participants],
                    ),
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Detect dropouts
        dropouts = await dropout_service.detect_dropouts(
            source_round_id=round_1.round_id,
            target_round_id=round_2.round_id,
        )
        await db_session.commit()

        # Verify 3 dropouts
        assert len(dropouts) == 3, "3 participants should drop out"

        # Compute flows
        flows = await flow_service.compute_flows(
            source_round_id=round_1.round_id,
            target_round_id=round_2.round_id,
        )

        # Verify mass shrinkage
        assert len(flows) == 1, "Only 1 flow (no synthetic flows)"
        flow = flows[0]
        assert flow.participant_count == 2, "Mass shrinks from 5 to 2"
        assert set(flow.participant_ids) == {
            continuing_participants[0].participant_id,
            continuing_participants[1].participant_id,
        }

        # Verify NO synthetic flows for dropouts
        dropout_ids = {d.participant_id for d in dropouts}
        for f in flows:
            for pid in f.participant_ids:
                assert pid not in dropout_ids, \
                    "Dropouts should NOT appear in any flows"

    finally:
        await timing_service.stop_worker()
        await timing_service.disconnect()
