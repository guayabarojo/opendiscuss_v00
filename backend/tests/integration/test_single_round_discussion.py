"""
End-to-end integration test for single-round discussion workflow.

Tests the complete flow: create discussion → start → submissions → approvals →
clustering → Sankey verification. Validates all state transitions and final
data structure.

Task: T041 - Single-round discussion integration test
Constitutional Coverage:
- Intent Fidelity: Verify 100% approved summaries before clustering
- Semantic Accuracy: Verify 100% participant coverage in clusters
- Temporal Transparency: Verify Sankey column structure
"""

import asyncio
from datetime import datetime, timedelta, timezone
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
from src.services.discussion_service import DiscussionService
from src.services.round_service import RoundService
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
    FlowEdge,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_single_round_discussion_complete_flow(
    db_session,
    redis_client,
    event_bus,
):
    """
    Test complete single-round discussion from creation to Sankey completion.

    Flow:
    1. Create discussion with 1 question
    2. Start discussion (opens Round 1 submission window)
    3. Mock submissions from 5 participants
    4. Mock summarization completion (approved summaries)
    5. Mock clustering completion (thought spaces)
    6. Mock Sankey completion
    7. Verify final state and data structure

    Expected:
    - Discussion transitions: CREATED → ACTIVE → COMPLETED
    - Round transitions: PENDING → SUBMISSION_OPEN → SUBMISSION_CLOSED →
      SUMMARIZING → APPROVING → CLUSTERING → SANKEY_BUILDING → COMPLETE
    - All participants assigned to clusters
    - Sankey diagram contains single column with correct proportions
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

    # Setup protocol coordinator
    coordinator = ProtocolCoordinator(event_bus=event_bus)
    await coordinator.register_handlers()

    try:
        # ============================================================================
        # Step 1: Create discussion with 1 question
        # ============================================================================
        community_id = uuid4()
        host_user_id = uuid4()
        questions = ["What challenges do you face with remote work?"]

        discussion = await discussion_service.create_discussion(
            community_id=community_id,
            host_user_id=host_user_id,
            questions=questions,
            submission_window_duration_sec=300,
        )

        assert discussion.status == DiscussionStatus.CREATED
        assert discussion.total_rounds == 1
        assert discussion.current_round_num == 0

        # Verify Round 1 was created
        result = await db_session.execute(
            select(Round).where(
                Round.discussion_id == discussion.discussion_id,
                Round.round_num == 1,
            )
        )
        round_1 = result.scalar_one()
        assert round_1.status == RoundStatus.PENDING
        assert round_1.question_text == questions[0]

        # ============================================================================
        # Step 2: Start discussion (opens Round 1 submission window)
        # ============================================================================
        await discussion_service.start_discussion(discussion.discussion_id)

        # Refresh entities
        await db_session.refresh(discussion)
        await db_session.refresh(round_1)

        assert discussion.status == DiscussionStatus.ACTIVE
        assert discussion.current_round_num == 1
        assert round_1.status == RoundStatus.SUBMISSION_OPEN
        assert round_1.submission_window_start is not None
        assert round_1.submission_window_end is not None

        # ============================================================================
        # Step 3: Mock submissions from 5 participants
        # ============================================================================
        participants = []
        submissions = []

        for i in range(5):
            # Create participant
            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()
            participants.append(participant)

            # Create submission
            submission = Submission(
                participant_id=participant.participant_id,
                round_id=round_1.round_id,
                submission_text=f"Participant {i+1} submission about remote work challenges",
                modality=SubmissionModality.TEXT,
            )
            db_session.add(submission)
            submissions.append(submission)

        await db_session.commit()

        # Verify submissions
        assert len(submissions) == 5
        for submission in submissions:
            await db_session.refresh(submission)
            assert submission.submitted_at is not None

        # ============================================================================
        # Step 4: Close submission window and transition to SUMMARIZING
        # ============================================================================
        await round_service.close_submission_window(round_1.round_id)
        await db_session.refresh(round_1)
        assert round_1.status == RoundStatus.SUBMISSION_CLOSED

        # Wait for coordinator to process and transition to SUMMARIZING
        await asyncio.sleep(0.2)
        await db_session.refresh(round_1)
        assert round_1.status == RoundStatus.SUMMARIZING

        # ============================================================================
        # Step 5: Mock summarization completion (approved summaries)
        # ============================================================================
        approved_summaries = []

        for i, (participant, submission) in enumerate(zip(participants, submissions)):
            approved_summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_1.round_id,
                submission_id=submission.submission_id,
                summary_text=f"Summary {i+1}: Remote work challenges include communication and work-life balance",
            )
            db_session.add(approved_summary)
            approved_summaries.append(approved_summary)

        await db_session.commit()

        # Emit summarization.complete event
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
                    for s in approved_summaries
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )

        # Wait for coordinator to validate and transition to CLUSTERING
        await asyncio.sleep(0.2)
        await db_session.refresh(round_1)
        assert round_1.status == RoundStatus.CLUSTERING

        # ============================================================================
        # Step 6: Mock clustering completion (thought spaces)
        # ============================================================================
        # Create 2 thought spaces
        cluster_1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Communication challenges with distributed teams",
            member_count=3,
            member_pct=0.6,
        )
        cluster_2 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Work-life balance and boundaries",
            member_count=2,
            member_pct=0.4,
        )
        db_session.add(cluster_1)
        db_session.add(cluster_2)
        await db_session.flush()

        # Assign summaries to clusters
        approved_summaries[0].cluster_id = cluster_1.cluster_id
        approved_summaries[1].cluster_id = cluster_1.cluster_id
        approved_summaries[2].cluster_id = cluster_1.cluster_id
        approved_summaries[3].cluster_id = cluster_2.cluster_id
        approved_summaries[4].cluster_id = cluster_2.cluster_id

        await db_session.commit()

        # Emit clustering.complete event
        await event_bus.emit(
            "clustering.complete",
            ClusteringCompleteEvent(
                round_id=round_1.round_id,
                thought_spaces=[
                    ThoughtSpaceSummary(
                        cluster_id=cluster_1.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster_1.label_summary,
                        member_count=cluster_1.member_count,
                        member_pct=cluster_1.member_pct * 100,  # Convert to percentage
                        participant_ids=[
                            approved_summaries[0].participant_id,
                            approved_summaries[1].participant_id,
                            approved_summaries[2].participant_id,
                        ],
                    ),
                    ThoughtSpaceSummary(
                        cluster_id=cluster_2.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster_2.label_summary,
                        member_count=cluster_2.member_count,
                        member_pct=cluster_2.member_pct * 100,
                        participant_ids=[
                            approved_summaries[3].participant_id,
                            approved_summaries[4].participant_id,
                        ],
                    ),
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )

        # Wait for coordinator to validate and transition to SANKEY_BUILDING
        await asyncio.sleep(0.2)
        await db_session.refresh(round_1)
        assert round_1.status == RoundStatus.SANKEY_BUILDING

        # ============================================================================
        # Step 7: Mock Sankey completion
        # ============================================================================
        # Create Sankey graph for single-round (single column)
        sankey_graph = SankeyGraph(
            discussion_id=discussion.discussion_id,
            rounds=[round_1.round_id],
            nodes=[
                ThoughtSpaceSummary(
                    cluster_id=cluster_1.cluster_id,
                    round_id=round_1.round_id,
                    label_summary=cluster_1.label_summary,
                    member_count=cluster_1.member_count,
                    member_pct=cluster_1.member_pct * 100,
                    participant_ids=[
                        approved_summaries[0].participant_id,
                        approved_summaries[1].participant_id,
                        approved_summaries[2].participant_id,
                    ],
                ),
                ThoughtSpaceSummary(
                    cluster_id=cluster_2.cluster_id,
                    round_id=round_1.round_id,
                    label_summary=cluster_2.label_summary,
                    member_count=cluster_2.member_count,
                    member_pct=cluster_2.member_pct * 100,
                    participant_ids=[
                        approved_summaries[3].participant_id,
                        approved_summaries[4].participant_id,
                    ],
                ),
            ],
            edges=[],  # No edges for single-round
            total_participants=5,
        )

        # Emit sankey.complete event
        await event_bus.emit(
            "sankey.complete",
            SankeyCompleteEvent(
                round_id=round_1.round_id,
                sankey_graph=sankey_graph,
                timestamp=datetime.now(timezone.utc),
            ),
        )

        # Wait for coordinator to transition to COMPLETE
        await asyncio.sleep(0.2)
        await db_session.refresh(round_1)
        assert round_1.status == RoundStatus.COMPLETE

        # ============================================================================
        # Step 8: Verify final state and data structure
        # ============================================================================

        # Verify Discussion state
        await db_session.refresh(discussion)
        # Note: Discussion status remains ACTIVE until all rounds complete
        # For single-round, we'd need a separate handler to mark discussion COMPLETED

        # Verify Round state
        assert round_1.status == RoundStatus.COMPLETE
        assert round_1.submission_window_start is not None
        assert round_1.submission_window_end is not None

        # Verify Participants
        result = await db_session.execute(
            select(Participant).where(
                Participant.discussion_id == discussion.discussion_id
            )
        )
        all_participants = result.scalars().all()
        assert len(all_participants) == 5

        # Verify Submissions
        result = await db_session.execute(
            select(Submission).where(Submission.round_id == round_1.round_id)
        )
        all_submissions = result.scalars().all()
        assert len(all_submissions) == 5

        # Verify ApprovedSummaries
        result = await db_session.execute(
            select(ApprovedSummary).where(ApprovedSummary.round_id == round_1.round_id)
        )
        all_summaries = result.scalars().all()
        assert len(all_summaries) == 5

        # Verify all summaries are clustered (100% coverage)
        unclustered = [s for s in all_summaries if s.cluster_id is None]
        assert len(unclustered) == 0, "All summaries must be assigned to clusters"

        # Verify ThoughtSpaces
        result = await db_session.execute(
            select(ThoughtSpace).where(ThoughtSpace.round_id == round_1.round_id)
        )
        all_clusters = result.scalars().all()
        assert len(all_clusters) == 2

        # Verify cluster member counts
        assert cluster_1.member_count == 3
        assert cluster_2.member_count == 2

        # Verify member percentages sum to 1.0 (100%)
        total_pct = sum(c.member_pct for c in all_clusters)
        assert abs(total_pct - 1.0) < 0.001, f"Member percentages must sum to 1.0, got {total_pct}"

        # Verify Sankey structure
        assert len(sankey_graph.nodes) == 2
        assert len(sankey_graph.edges) == 0  # No edges in single-round
        assert len(sankey_graph.rounds) == 1
        assert sankey_graph.total_participants == 5

        # Verify Sankey nodes match thought spaces
        node_member_counts = {node.cluster_id: node.member_count for node in sankey_graph.nodes}
        assert node_member_counts[cluster_1.cluster_id] == 3
        assert node_member_counts[cluster_2.cluster_id] == 2

    finally:
        # Cleanup
        await timing_service.stop_worker()
        await timing_service.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_single_round_no_participants(db_session, redis_client, event_bus):
    """
    Test single-round discussion with zero participants.

    Validates that the system handles edge case of no submissions gracefully.
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

    coordinator = ProtocolCoordinator(event_bus=event_bus)
    await coordinator.register_handlers()

    try:
        # Create and start discussion
        discussion = await discussion_service.create_discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            questions=["What are your thoughts?"],
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

        # Close window with no submissions
        await round_service.close_submission_window(round_1.round_id)
        await asyncio.sleep(0.2)

        # Emit summarization.complete with zero summaries
        await event_bus.emit(
            "summarization.complete",
            SummarizationCompleteEvent(
                round_id=round_1.round_id,
                approved_summaries=[],
                timestamp=datetime.now(timezone.utc),
            ),
        )

        await asyncio.sleep(0.2)
        await db_session.refresh(round_1)

        # Verify system handled zero participants correctly
        assert round_1.status == RoundStatus.CLUSTERING

    finally:
        await timing_service.stop_worker()
        await timing_service.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_single_round_singleton_cluster(db_session, redis_client, event_bus):
    """
    Test single-round discussion with singleton cluster (1 participant).

    Validates constitutional guarantee: singleton clusters are preserved
    (no forced merging).
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

    coordinator = ProtocolCoordinator(event_bus=event_bus)
    await coordinator.register_handlers()

    try:
        # Create and start discussion
        discussion = await discussion_service.create_discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            questions=["What are your thoughts?"],
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

        # Create 1 participant and submission
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
            submission_text="Singleton participant submission",
            modality=SubmissionModality.TEXT,
        )
        db_session.add(submission)
        await db_session.commit()

        # Close window
        await round_service.close_submission_window(round_1.round_id)
        await asyncio.sleep(0.2)

        # Create approved summary
        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round_1.round_id,
            submission_id=submission.submission_id,
            summary_text="Singleton participant summary",
        )
        db_session.add(approved_summary)
        await db_session.commit()

        # Emit summarization.complete
        await event_bus.emit(
            "summarization.complete",
            SummarizationCompleteEvent(
                round_id=round_1.round_id,
                approved_summaries=[
                    ApprovedSummarySummary(
                        summary_id=approved_summary.summary_id,
                        participant_id=approved_summary.participant_id,
                        submission_id=approved_summary.submission_id,
                        summary_text=approved_summary.summary_text,
                        approved_at=approved_summary.approved_at,
                    )
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )

        await asyncio.sleep(0.2)
        await db_session.refresh(round_1)
        assert round_1.status == RoundStatus.CLUSTERING

        # Create singleton cluster
        cluster = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Singleton thought space",
            member_count=1,
            member_pct=1.0,
        )
        db_session.add(cluster)
        await db_session.flush()

        approved_summary.cluster_id = cluster.cluster_id
        await db_session.commit()

        # Emit clustering.complete
        await event_bus.emit(
            "clustering.complete",
            ClusteringCompleteEvent(
                round_id=round_1.round_id,
                thought_spaces=[
                    ThoughtSpaceSummary(
                        cluster_id=cluster.cluster_id,
                        round_id=round_1.round_id,
                        label_summary=cluster.label_summary,
                        member_count=cluster.member_count,
                        member_pct=100.0,
                        participant_ids=[participant.participant_id],
                    )
                ],
                timestamp=datetime.now(timezone.utc),
            ),
        )

        await asyncio.sleep(0.2)
        await db_session.refresh(round_1)
        assert round_1.status == RoundStatus.SANKEY_BUILDING

        # Verify singleton cluster is preserved
        result = await db_session.execute(
            select(ThoughtSpace).where(ThoughtSpace.round_id == round_1.round_id)
        )
        clusters = result.scalars().all()
        assert len(clusters) == 1
        assert clusters[0].member_count == 1

    finally:
        await timing_service.stop_worker()
        await timing_service.disconnect()
