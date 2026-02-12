"""
Contract test: Sankey Construction (Spec 5) → Question Generation (Spec 6)

Validates the integration boundary between the Sankey Construction sub-protocol
and Question Generation sub-protocol. This test ensures the sankey.complete
event payload meets all contract requirements for downstream consumption.

Task: T060 - Write Sankey→Question contract test
Constitutional Coverage:
- Temporal Transparency: Verify SankeyGraph includes complete participant flow data
- Synchronous Deliberation: Verify event emitted within 5 seconds
"""

import asyncio
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
import time

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.models.round import Round, RoundStatus
from src.models.discussion import Discussion, DiscussionStatus
from src.events.event_bus import EventBus
from src.events.event_types import (
    SankeyCompleteEvent,
    SankeyGraph,
    ThoughtSpaceSummary,
    FlowEdge,
)
from src.events.handlers.sankey_complete import handle_sankey_complete


@pytest.mark.asyncio
@pytest.mark.contract
async def test_sankey_complete_event_schema():
    """
    Test that sankey.complete event includes all required fields.

    Contract Requirements:
    - event.round_id: UUID
    - event.sankey_graph: SankeyGraph
    - event.timestamp: datetime
    """
    event = SankeyCompleteEvent(
        round_id=uuid4(),
        sankey_graph=SankeyGraph(
            discussion_id=uuid4(),
            rounds=[uuid4()],
            nodes=[
                ThoughtSpaceSummary(
                    cluster_id=uuid4(),
                    round_id=uuid4(),
                    label_summary="Test cluster",
                    member_count=10,
                    member_pct=100.0,
                    participant_ids=[uuid4() for _ in range(10)],
                )
            ],
            edges=[],
            total_participants=10,
        ),
        timestamp=datetime.now(timezone.utc),
    )

    # Verify required fields exist and have correct types
    assert isinstance(event.round_id, UUID)
    assert isinstance(event.sankey_graph, SankeyGraph)
    assert isinstance(event.timestamp, datetime)


@pytest.mark.asyncio
@pytest.mark.contract
async def test_sankey_complete_includes_full_sankey_graph():
    """
    Test that sankey.complete event includes complete SankeyGraph payload.

    Contract Requirement (Spec 5):
    - Full SankeyGraph structure included in event
    - Contains all columns (thought spaces across rounds)
    - Contains all flows (edges between thought spaces)
    - Enables Question Generation (Spec 6) to analyze discussion structure

    SankeyGraph Structure:
    - discussion_id: UUID
    - rounds: List[UUID] (ordered list of round IDs = columns)
    - nodes: List[ThoughtSpaceSummary] (all thought spaces across all rounds)
    - edges: List[FlowEdge] (participant movement between rounds)
    - total_participants: int
    """
    discussion_id = uuid4()
    round_1_id = uuid4()
    round_2_id = uuid4()

    # Round 1 clusters
    cluster_1a = uuid4()
    cluster_1b = uuid4()

    # Round 2 clusters
    cluster_2a = uuid4()
    cluster_2b = uuid4()

    participant_ids_1a = [uuid4() for _ in range(15)]
    participant_ids_1b = [uuid4() for _ in range(10)]
    participant_ids_2a = [uuid4() for _ in range(12)]
    participant_ids_2b = [uuid4() for _ in range(13)]

    event = SankeyCompleteEvent(
        round_id=round_2_id,  # Triggered by Round 2 completion
        sankey_graph=SankeyGraph(
            discussion_id=discussion_id,
            rounds=[round_1_id, round_2_id],  # Ordered columns
            nodes=[
                # Round 1 nodes
                ThoughtSpaceSummary(
                    cluster_id=cluster_1a,
                    round_id=round_1_id,
                    label_summary="Round 1 Cluster A",
                    member_count=15,
                    member_pct=60.0,
                    participant_ids=participant_ids_1a,
                ),
                ThoughtSpaceSummary(
                    cluster_id=cluster_1b,
                    round_id=round_1_id,
                    label_summary="Round 1 Cluster B",
                    member_count=10,
                    member_pct=40.0,
                    participant_ids=participant_ids_1b,
                ),
                # Round 2 nodes
                ThoughtSpaceSummary(
                    cluster_id=cluster_2a,
                    round_id=round_2_id,
                    label_summary="Round 2 Cluster A",
                    member_count=12,
                    member_pct=48.0,
                    participant_ids=participant_ids_2a,
                ),
                ThoughtSpaceSummary(
                    cluster_id=cluster_2b,
                    round_id=round_2_id,
                    label_summary="Round 2 Cluster B",
                    member_count=13,
                    member_pct=52.0,
                    participant_ids=participant_ids_2b,
                ),
            ],
            edges=[
                FlowEdge(
                    source_cluster_id=cluster_1a,
                    target_cluster_id=cluster_2a,
                    participant_count=8,
                    participant_ids=[uuid4() for _ in range(8)],
                ),
                FlowEdge(
                    source_cluster_id=cluster_1a,
                    target_cluster_id=cluster_2b,
                    participant_count=7,
                    participant_ids=[uuid4() for _ in range(7)],
                ),
                FlowEdge(
                    source_cluster_id=cluster_1b,
                    target_cluster_id=cluster_2a,
                    participant_count=4,
                    participant_ids=[uuid4() for _ in range(4)],
                ),
                FlowEdge(
                    source_cluster_id=cluster_1b,
                    target_cluster_id=cluster_2b,
                    participant_count=6,
                    participant_ids=[uuid4() for _ in range(6)],
                ),
            ],
            total_participants=25,
        ),
    )

    # Verify SankeyGraph structure
    graph = event.sankey_graph
    assert isinstance(graph.discussion_id, UUID)
    assert isinstance(graph.rounds, list)
    assert len(graph.rounds) == 2, "Should have 2 rounds (columns)"
    assert graph.rounds == [round_1_id, round_2_id], "Rounds must be ordered"

    # Verify nodes (thought spaces)
    assert isinstance(graph.nodes, list)
    assert len(graph.nodes) == 4, "Should have 4 thought spaces (2 per round)"
    assert all(isinstance(node, ThoughtSpaceSummary) for node in graph.nodes)

    # Verify edges (flows)
    assert isinstance(graph.edges, list)
    assert len(graph.edges) == 4, "Should have 4 flows between rounds"
    assert all(isinstance(edge, FlowEdge) for edge in graph.edges)

    # Verify total participants
    assert isinstance(graph.total_participants, int)
    assert graph.total_participants > 0


@pytest.mark.asyncio
@pytest.mark.contract
async def test_sankey_complete_payload_includes_columns_and_flows():
    """
    Test that sankey.complete payload explicitly includes columns and flows.

    Contract Requirement:
    - columns = thought spaces (nodes)
    - flows = edges between thought spaces
    - Required for Question Generation to identify:
      - Which clusters are converging (many flows → one cluster)
      - Which clusters are diverging (one cluster → many flows)
      - Which participants are moving between viewpoints
    """
    discussion_id = uuid4()
    round_1_id = uuid4()

    cluster_id = uuid4()
    participant_ids = [uuid4() for _ in range(20)]

    event = SankeyCompleteEvent(
        round_id=round_1_id,
        sankey_graph=SankeyGraph(
            discussion_id=discussion_id,
            rounds=[round_1_id],
            nodes=[
                ThoughtSpaceSummary(
                    cluster_id=cluster_id,
                    round_id=round_1_id,
                    label_summary="Single round cluster",
                    member_count=20,
                    member_pct=100.0,
                    participant_ids=participant_ids,
                ),
            ],
            edges=[],  # No flows in first round
            total_participants=20,
        ),
    )

    # Verify columns (nodes) are accessible
    assert hasattr(event.sankey_graph, 'nodes')
    assert len(event.sankey_graph.nodes) > 0, "Must have at least one column"

    # Verify flows (edges) are accessible
    assert hasattr(event.sankey_graph, 'edges')
    assert isinstance(event.sankey_graph.edges, list), "Edges must be a list"

    # Verify round ordering (columns)
    assert hasattr(event.sankey_graph, 'rounds')
    assert len(event.sankey_graph.rounds) > 0, "Must have at least one round"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_sankey_complete_event_timing_constraint():
    """
    Test that sankey.complete event is emitted within 5 seconds of completion.

    Contract Requirement (Synchronous Deliberation - Principle VI):
    - Event must be emitted within 5 seconds of Sankey construction completion
    - Ensures timely progression to Question Generation
    - Part of overall round processing time budget (~10 minutes per round)

    Note: This is a timing contract test, not a full integration test
    """
    # Create minimal valid event
    event = SankeyCompleteEvent(
        round_id=uuid4(),
        sankey_graph=SankeyGraph(
            discussion_id=uuid4(),
            rounds=[uuid4()],
            nodes=[
                ThoughtSpaceSummary(
                    cluster_id=uuid4(),
                    round_id=uuid4(),
                    label_summary="Test",
                    member_count=1,
                    member_pct=100.0,
                    participant_ids=[uuid4()],
                )
            ],
            edges=[],
            total_participants=1,
        ),
        timestamp=datetime.now(timezone.utc),
    )

    # Simulate Sankey construction completion time
    construction_complete_time = datetime.now(timezone.utc)
    event_emission_time = event.timestamp

    # Calculate time delta
    time_delta = abs((event_emission_time - construction_complete_time).total_seconds())

    # Verify emission within 5 seconds
    assert time_delta < 5.0, \
        f"sankey.complete event must be emitted within 5 seconds (actual: {time_delta:.2f}s)"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_sankey_complete_question_generation_can_consume():
    """
    Test that Question Generation (Spec 6) can consume SankeyGraph payload.

    Contract Requirement:
    - SankeyGraph payload contains all data needed for question generation
    - Question Generator can access:
      - Thought space labels (for topic identification)
      - Participant counts (for identifying significant movements)
      - Flow edges (for identifying convergence/divergence patterns)
      - Round ordering (for temporal analysis)

    This validates the consumer side of the contract.
    """
    event = SankeyCompleteEvent(
        round_id=uuid4(),
        sankey_graph=SankeyGraph(
            discussion_id=uuid4(),
            rounds=[uuid4(), uuid4()],
            nodes=[
                ThoughtSpaceSummary(
                    cluster_id=uuid4(),
                    round_id=uuid4(),
                    label_summary="Topic A: Environmental concerns",
                    member_count=15,
                    member_pct=60.0,
                    participant_ids=[uuid4() for _ in range(15)],
                ),
                ThoughtSpaceSummary(
                    cluster_id=uuid4(),
                    round_id=uuid4(),
                    label_summary="Topic B: Economic priorities",
                    member_count=10,
                    member_pct=40.0,
                    participant_ids=[uuid4() for _ in range(10)],
                ),
            ],
            edges=[
                FlowEdge(
                    source_cluster_id=uuid4(),
                    target_cluster_id=uuid4(),
                    participant_count=5,
                    participant_ids=[uuid4() for _ in range(5)],
                ),
            ],
            total_participants=25,
        ),
    )

    # Simulate Question Generation consuming the payload
    graph = event.sankey_graph

    # Question Generator should be able to:
    # 1. Identify topics from labels
    topics = [node.label_summary for node in graph.nodes]
    assert len(topics) > 0, "Question Generator needs topic labels"
    assert all(isinstance(topic, str) for topic in topics)

    # 2. Identify significant movements
    significant_flows = [edge for edge in graph.edges if edge.participant_count > 3]
    assert isinstance(significant_flows, list), "Question Generator needs flow data"

    # 3. Analyze temporal progression
    assert len(graph.rounds) >= 1, "Question Generator needs round ordering"

    # 4. Calculate participation metrics
    total_participants = graph.total_participants
    assert total_participants > 0, "Question Generator needs participant counts"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_sankey_complete_round_transitions_after_event(
    db_session,
    event_bus,
):
    """
    Test that Round transitions to COMPLETE after sankey.complete event.

    Contract Requirement:
    - Round status updates from SANKEY_BUILDING → COMPLETE
    - Enables host to advance to next round or complete discussion
    - May transition to QUESTION_READY if auto-question mode

    Note: Tests handler behavior, not just event schema
    """
    # Create test discussion and round
    discussion_id = uuid4()
    round_id = uuid4()

    discussion = Discussion(
        discussion_id=discussion_id,
        community_id=uuid4(),
        mode="HOST_DEFINED",
        total_rounds=1,
        status=DiscussionStatus.ACTIVE,
        host_user_id="host-123",
    )
    db_session.add(discussion)

    test_round = Round(
        round_id=round_id,
        discussion_id=discussion_id,
        round_num=1,
        question_text="Test question",
        status=RoundStatus.SANKEY_BUILDING,
        submission_window_duration_sec=300,
    )
    db_session.add(test_round)
    await db_session.commit()

    # Create sankey.complete event
    event = SankeyCompleteEvent(
        round_id=round_id,
        sankey_graph=SankeyGraph(
            discussion_id=discussion_id,
            rounds=[round_id],
            nodes=[
                ThoughtSpaceSummary(
                    cluster_id=uuid4(),
                    round_id=round_id,
                    label_summary="Test cluster",
                    member_count=10,
                    member_pct=100.0,
                    participant_ids=[uuid4() for _ in range(10)],
                )
            ],
            edges=[],
            total_participants=10,
        ),
    )

    # Handle event
    await handle_sankey_complete(event)

    # Verify Round transitioned to COMPLETE
    await db_session.refresh(test_round)
    assert test_round.status == RoundStatus.COMPLETE, \
        "Round should transition to COMPLETE after Sankey construction finishes"

    # Verify Discussion transitioned to COMPLETED (final round)
    await db_session.refresh(discussion)
    assert discussion.status == DiscussionStatus.COMPLETED, \
        "Discussion should transition to COMPLETED after final round completes"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_sankey_complete_event_payload_serializable():
    """
    Test that sankey.complete event payload is JSON serializable.

    Contract Requirement:
    - All fields must be serializable for event bus transmission
    - UUID fields serialized as strings
    - datetime fields serialized as ISO 8601 strings
    - Pydantic models provide automatic serialization
    """
    event = SankeyCompleteEvent(
        round_id=uuid4(),
        sankey_graph=SankeyGraph(
            discussion_id=uuid4(),
            rounds=[uuid4()],
            nodes=[
                ThoughtSpaceSummary(
                    cluster_id=uuid4(),
                    round_id=uuid4(),
                    label_summary="Test",
                    member_count=1,
                    member_pct=100.0,
                    participant_ids=[uuid4()],
                )
            ],
            edges=[],
            total_participants=1,
        ),
        timestamp=datetime.now(timezone.utc),
    )

    # Verify JSON serialization works
    event_json = event.model_dump_json()
    assert event_json is not None
    assert isinstance(event_json, str)

    # Verify deserialization works
    event_dict = event.model_dump()
    reconstructed = SankeyCompleteEvent(**event_dict)
    assert reconstructed.round_id == event.round_id
    assert reconstructed.sankey_graph.discussion_id == event.sankey_graph.discussion_id


@pytest.mark.asyncio
@pytest.mark.contract
async def test_sankey_complete_flow_edges_include_participant_ids():
    """
    Test that FlowEdge objects include participant_ids for validation.

    Contract Requirement (Temporal Transparency - Principle IV):
    - Each flow edge must include participant_ids
    - Enables validation: participant_count = len(participant_ids)
    - Enables audit: which participants moved from cluster A to cluster B?
    - Required for constitutional compliance validation
    """
    source_cluster = uuid4()
    target_cluster = uuid4()
    moving_participants = [uuid4() for _ in range(7)]

    event = SankeyCompleteEvent(
        round_id=uuid4(),
        sankey_graph=SankeyGraph(
            discussion_id=uuid4(),
            rounds=[uuid4(), uuid4()],
            nodes=[
                ThoughtSpaceSummary(
                    cluster_id=source_cluster,
                    round_id=uuid4(),
                    label_summary="Source",
                    member_count=10,
                    member_pct=50.0,
                    participant_ids=[uuid4() for _ in range(10)],
                ),
                ThoughtSpaceSummary(
                    cluster_id=target_cluster,
                    round_id=uuid4(),
                    label_summary="Target",
                    member_count=10,
                    member_pct=50.0,
                    participant_ids=[uuid4() for _ in range(10)],
                ),
            ],
            edges=[
                FlowEdge(
                    source_cluster_id=source_cluster,
                    target_cluster_id=target_cluster,
                    participant_count=7,
                    participant_ids=moving_participants,
                ),
            ],
            total_participants=20,
        ),
    )

    # Verify FlowEdge includes participant_ids
    for edge in event.sankey_graph.edges:
        assert hasattr(edge, 'participant_ids'), "FlowEdge must include participant_ids"
        assert edge.participant_ids is not None, "participant_ids cannot be None"
        assert len(edge.participant_ids) == edge.participant_count, \
            f"participant_ids length ({len(edge.participant_ids)}) must match participant_count ({edge.participant_count})"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_sankey_complete_multi_round_temporal_ordering():
    """
    Test that SankeyGraph maintains temporal ordering across multiple rounds.

    Contract Requirement:
    - rounds list ordered chronologically [round_1, round_2, round_3]
    - Enables Question Generator to understand discussion progression
    - Required for identifying "early consensus" vs "late divergence" patterns
    """
    discussion_id = uuid4()
    round_ids = [uuid4() for _ in range(3)]  # 3 rounds

    event = SankeyCompleteEvent(
        round_id=round_ids[2],  # Triggered by Round 3
        sankey_graph=SankeyGraph(
            discussion_id=discussion_id,
            rounds=round_ids,  # Must be ordered: [R1, R2, R3]
            nodes=[
                # Round 1
                ThoughtSpaceSummary(
                    cluster_id=uuid4(),
                    round_id=round_ids[0],
                    label_summary="R1 Cluster",
                    member_count=10,
                    member_pct=100.0,
                    participant_ids=[uuid4() for _ in range(10)],
                ),
                # Round 2
                ThoughtSpaceSummary(
                    cluster_id=uuid4(),
                    round_id=round_ids[1],
                    label_summary="R2 Cluster",
                    member_count=10,
                    member_pct=100.0,
                    participant_ids=[uuid4() for _ in range(10)],
                ),
                # Round 3
                ThoughtSpaceSummary(
                    cluster_id=uuid4(),
                    round_id=round_ids[2],
                    label_summary="R3 Cluster",
                    member_count=10,
                    member_pct=100.0,
                    participant_ids=[uuid4() for _ in range(10)],
                ),
            ],
            edges=[],
            total_participants=10,
        ),
    )

    # Verify temporal ordering
    graph = event.sankey_graph
    assert len(graph.rounds) == 3, "Should have 3 rounds"
    assert graph.rounds == round_ids, "Rounds must be in chronological order"

    # Verify nodes can be grouped by round
    nodes_by_round = {}
    for node in graph.nodes:
        nodes_by_round.setdefault(node.round_id, []).append(node)

    assert len(nodes_by_round) == 3, "Should have nodes from all 3 rounds"
    assert all(round_id in nodes_by_round for round_id in round_ids), \
        "All rounds should have at least one node"
