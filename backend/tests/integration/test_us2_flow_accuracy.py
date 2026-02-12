"""
Flow accuracy validation integration test.

Tests that flow.participant_count = COUNT(DISTINCT participant_id in BOTH
source AND target clusters). Validates constitutional guarantee that flows
represent actual participant movement, not semantic similarity.

Task: T058 - Flow accuracy test
Constitutional Coverage:
- Temporal Transparency: Flows = actual movement, not semantic similarity
- Flow accuracy: edge.participant_count = intersection of source and target
- Alignment metadata (display_group_id) doesn't inflate flow counts
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
from src.services.discussion_service import DiscussionService
from src.services.round_service import RoundService
from src.services.flow_service import FlowService
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
async def test_flow_participant_count_accuracy(
    db_session,
    redis_client,
    event_bus,
):
    """
    Test that flow.participant_count equals actual intersection of participants.

    Validates the core constitutional guarantee:
    flow.participant_count = COUNT(DISTINCT participant_id in BOTH source AND target)

    Scenario:
    - Round 1: Cluster A (participants 1,2,3), Cluster B (participants 4,5)
    - Round 2: Cluster C (participants 1,2,4), Cluster D (participants 3,5)

    Expected flows:
    - A→C: 2 participants (1,2)
    - A→D: 1 participant (3)
    - B→C: 1 participant (4)
    - B→D: 1 participant (5)
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

        rounds_result = await db_session.execute(
            select(Round)
            .where(Round.discussion_id == discussion.discussion_id)
            .order_by(Round.round_num)
        )
        rounds = list(rounds_result.scalars().all())
        round_1, round_2 = rounds

        # Create 5 participants
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

        # Round 1 submissions
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

        # Round 1 approved summaries
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

        # Create Round 1 clusters: A (1,2,3), B (4,5)
        cluster_a = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Cluster A",
            member_count=3,
            member_pct=0.6,
        )
        cluster_b = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Cluster B",
            member_count=2,
            member_pct=0.4,
        )
        db_session.add(cluster_a)
        db_session.add(cluster_b)
        await db_session.flush()

        # Assign: 0,1,2 to A; 3,4 to B
        summaries_r1[0].cluster_id = cluster_a.cluster_id
        summaries_r1[1].cluster_id = cluster_a.cluster_id
        summaries_r1[2].cluster_id = cluster_a.cluster_id
        summaries_r1[3].cluster_id = cluster_b.cluster_id
        summaries_r1[4].cluster_id = cluster_b.cluster_id
        await db_session.commit()

        await event_bus.emit(
            "clustering.complete",
            ClusteringCompleteEvent(
                round_id=round_1.round_id,
                thought_spaces=[
                    ThoughtSpaceSummary(
                        cluster_id=cluster_a.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster_a.label_summary,
                        member_count=3,
                        member_pct=60.0,
                        participant_ids=[
                            participants[0].participant_id,
                            participants[1].participant_id,
                            participants[2].participant_id,
                        ],
                    ),
                    ThoughtSpaceSummary(
                        cluster_id=cluster_b.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster_b.label_summary,
                        member_count=2,
                        member_pct=40.0,
                        participant_ids=[
                            participants[3].participant_id,
                            participants[4].participant_id,
                        ],
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

        # Round 2
        await discussion_service.advance_round(discussion.discussion_id)

        for p in participants:
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
        for p in participants:
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

        # Create Round 2 clusters: C (0,1,3), D (2,4)
        cluster_c = ThoughtSpace(
            round_id=round_2.round_id,
            label_summary="Cluster C",
            member_count=3,
            member_pct=0.6,
        )
        cluster_d = ThoughtSpace(
            round_id=round_2.round_id,
            label_summary="Cluster D",
            member_count=2,
            member_pct=0.4,
        )
        db_session.add(cluster_c)
        db_session.add(cluster_d)
        await db_session.flush()

        summaries_r2[0].cluster_id = cluster_c.cluster_id
        summaries_r2[1].cluster_id = cluster_c.cluster_id
        summaries_r2[2].cluster_id = cluster_d.cluster_id
        summaries_r2[3].cluster_id = cluster_c.cluster_id
        summaries_r2[4].cluster_id = cluster_d.cluster_id
        await db_session.commit()

        await event_bus.emit(
            "clustering.complete",
            ClusteringCompleteEvent(
                round_id=round_2.round_id,
                thought_spaces=[
                    ThoughtSpaceSummary(
                        cluster_id=cluster_c.cluster_id,
                        round_id=round_2.round_id,
                        label_summary=cluster_c.label_summary,
                        member_count=3,
                        member_pct=60.0,
                        participant_ids=[
                            participants[0].participant_id,
                            participants[1].participant_id,
                            participants[3].participant_id,
                        ],
                    ),
                    ThoughtSpaceSummary(
                        cluster_id=cluster_d.cluster_id,
                        round_id=round_2.round_id,
                        label_summary=cluster_d.label_summary,
                        member_count=2,
                        member_pct=40.0,
                        participant_ids=[
                            participants[2].participant_id,
                            participants[4].participant_id,
                        ],
                    ),
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Compute flows
        flows = await flow_service.compute_flows(
            source_round_id=round_1.round_id,
            target_round_id=round_2.round_id,
        )

        # Persist flows
        for flow in flows:
            db_session.add(flow)
        await db_session.commit()

        # Validate flows
        assert len(flows) == 4, "Should have 4 flows"

        flow_map = {
            (flow.source_cluster_id, flow.target_cluster_id): flow
            for flow in flows
        }

        # A→C: participants 0,1 (intersection of {0,1,2} and {0,1,3})
        flow_a_c = flow_map.get((cluster_a.cluster_id, cluster_c.cluster_id))
        assert flow_a_c is not None
        assert flow_a_c.participant_count == 2
        assert set(flow_a_c.participant_ids) == {
            participants[0].participant_id,
            participants[1].participant_id,
        }

        # A→D: participant 2 (intersection of {0,1,2} and {2,4})
        flow_a_d = flow_map.get((cluster_a.cluster_id, cluster_d.cluster_id))
        assert flow_a_d is not None
        assert flow_a_d.participant_count == 1
        assert set(flow_a_d.participant_ids) == {participants[2].participant_id}

        # B→C: participant 3 (intersection of {3,4} and {0,1,3})
        flow_b_c = flow_map.get((cluster_b.cluster_id, cluster_c.cluster_id))
        assert flow_b_c is not None
        assert flow_b_c.participant_count == 1
        assert set(flow_b_c.participant_ids) == {participants[3].participant_id}

        # B→D: participant 4 (intersection of {3,4} and {2,4})
        flow_b_d = flow_map.get((cluster_b.cluster_id, cluster_d.cluster_id))
        assert flow_b_d is not None
        assert flow_b_d.participant_count == 1
        assert set(flow_b_d.participant_ids) == {participants[4].participant_id}

        # Validate total conservation
        total_flow_count = sum(f.participant_count for f in flows)
        assert total_flow_count == 5, "All 5 participants accounted for"

        # Validate each flow's participant_count matches len(participant_ids)
        for flow in flows:
            assert flow.participant_count == len(flow.participant_ids), \
                f"Flow {flow.flow_id} count mismatch"

    finally:
        await timing_service.stop_worker()
        await timing_service.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_all_participants_move_to_same_cluster(
    db_session,
    redis_client,
    event_bus,
):
    """
    Test edge case where all participants from multiple clusters converge to one.

    Validates correct flow computation when everyone ends up in the same cluster.
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

    coordinator = ProtocolCoordinator(event_bus=event_bus)
    await coordinator.register_handlers()

    try:
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

        # Create 4 participants
        participants = []
        for i in range(4):
            p = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(p)
            participants.append(p)
        await db_session.flush()

        # Round 1
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

        # Round 1: 2 clusters
        cluster1_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Cluster 1",
            member_count=2,
            member_pct=0.5,
        )
        cluster2_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Cluster 2",
            member_count=2,
            member_pct=0.5,
        )
        db_session.add(cluster1_r1)
        db_session.add(cluster2_r1)
        await db_session.flush()

        summaries_r1[0].cluster_id = cluster1_r1.cluster_id
        summaries_r1[1].cluster_id = cluster1_r1.cluster_id
        summaries_r1[2].cluster_id = cluster2_r1.cluster_id
        summaries_r1[3].cluster_id = cluster2_r1.cluster_id
        await db_session.commit()

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
                        member_pct=50.0,
                        participant_ids=[
                            participants[0].participant_id,
                            participants[1].participant_id,
                        ],
                    ),
                    ThoughtSpaceSummary(
                        cluster_id=cluster2_r1.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster2_r1.label_summary,
                        member_count=2,
                        member_pct=50.0,
                        participant_ids=[
                            participants[2].participant_id,
                            participants[3].participant_id,
                        ],
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
                    total_participants=4,
                ),
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Round 2
        await discussion_service.advance_round(discussion.discussion_id)

        for p in participants:
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
        for p in participants:
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

        # Round 2: Single cluster with all 4 participants
        cluster_r2 = ThoughtSpace(
            round_id=round_2.round_id,
            label_summary="Converged cluster",
            member_count=4,
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
                        member_count=4,
                        member_pct=100.0,
                        participant_ids=[p.participant_id for p in participants],
                    ),
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Compute flows
        flows = await flow_service.compute_flows(
            source_round_id=round_1.round_id,
            target_round_id=round_2.round_id,
        )

        # Validate: 2 flows (one from each source cluster to the single target)
        assert len(flows) == 2

        flow_map = {flow.source_cluster_id: flow for flow in flows}

        # Cluster1→Converged: 2 participants
        flow_1 = flow_map.get(cluster1_r1.cluster_id)
        assert flow_1 is not None
        assert flow_1.participant_count == 2
        assert flow_1.target_cluster_id == cluster_r2.cluster_id

        # Cluster2→Converged: 2 participants
        flow_2 = flow_map.get(cluster2_r1.cluster_id)
        assert flow_2 is not None
        assert flow_2.participant_count == 2
        assert flow_2.target_cluster_id == cluster_r2.cluster_id

        # Validate total
        total = sum(f.participant_count for f in flows)
        assert total == 4

    finally:
        await timing_service.stop_worker()
        await timing_service.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_alignment_metadata_does_not_inflate_counts(
    db_session,
    redis_client,
    event_bus,
):
    """
    Test that display_group_id alignment metadata does NOT inflate flow counts.

    Validates constitutional guarantee: flows computed from participant_id
    intersection only, regardless of display_group_id values.

    Note: Since display_group_id is not yet implemented in ThoughtSpace model,
    this test validates the core flow computation principle without alignment
    metadata. Once display_group_id is added, this test should be expanded.
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

    coordinator = ProtocolCoordinator(event_bus=event_bus)
    await coordinator.register_handlers()

    try:
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

        # Create 3 participants
        participants = []
        for i in range(3):
            p = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(p)
            participants.append(p)
        await db_session.flush()

        # Round 1
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

        # Round 1: Cluster with display_group_id (when implemented)
        # For now, create cluster without it
        cluster_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Cluster R1",
            member_count=3,
            member_pct=1.0,
            # TODO: Add display_group_id when implemented
        )
        db_session.add(cluster_r1)
        await db_session.flush()

        for summary in summaries_r1:
            summary.cluster_id = cluster_r1.cluster_id
        await db_session.commit()

        await event_bus.emit(
            "clustering.complete",
            ClusteringCompleteEvent(
                round_id=round_1.round_id,
                thought_spaces=[
                    ThoughtSpaceSummary(
                        cluster_id=cluster_r1.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster_r1.label_summary,
                        member_count=3,
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
                    total_participants=3,
                ),
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Round 2
        await discussion_service.advance_round(discussion.discussion_id)

        # Only 2 participants continue (one drops out)
        continuing = participants[:2]
        for p in continuing:
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
        for p in continuing:
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

        # Round 2: Cluster with same display_group_id (when implemented)
        cluster_r2 = ThoughtSpace(
            round_id=round_2.round_id,
            label_summary="Cluster R2",
            member_count=2,
            member_pct=1.0,
            # TODO: Add same display_group_id as R1 when implemented
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
                        participant_ids=[p.participant_id for p in continuing],
                    ),
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )
        await asyncio.sleep(0.2)

        # Compute flows
        flows = await flow_service.compute_flows(
            source_round_id=round_1.round_id,
            target_round_id=round_2.round_id,
        )

        # Validate: Flow count = actual intersection (2), NOT inflated by metadata
        assert len(flows) == 1
        flow = flows[0]
        assert flow.participant_count == 2, \
            "Flow count should be 2 (actual intersection), not inflated by alignment"
        assert set(flow.participant_ids) == {
            continuing[0].participant_id,
            continuing[1].participant_id,
        }

        # Verify the third participant (dropout) is NOT in flow
        assert participants[2].participant_id not in flow.participant_ids

    finally:
        await timing_service.stop_worker()
        await timing_service.disconnect()
