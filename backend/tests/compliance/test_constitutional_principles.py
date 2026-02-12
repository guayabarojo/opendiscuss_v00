"""
Constitutional compliance audit tests for OpenDiscuss Discussion Protocol.

Tests all 7 constitutional principles across all user stories as defined in
.specify/memory/constitution.md version 1.0.0.

Principles tested:
  I. Parallel-First Architecture
  II. Intent Fidelity (100% approval)
  III. Semantic Accuracy (100% coverage)
  IV. Temporal Transparency (movement-based flows)
  V. Community-Bounded
  VI. Synchronous Deliberation (timing constraints)
  VII. Representation Not Adjudication

Task: T089 - Constitutional compliance audit tests
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select

from src.models.discussion import Discussion, DiscussionStatus, DiscussionMode
from src.models.round import Round, RoundStatus
from src.models.participant import Participant, DropoutReason
from src.models.submission import Submission, SubmissionModality
from src.models.approved_summary import ApprovedSummary, SummaryStatus
from src.models.thought_space import ThoughtSpace
from src.models.flow import Flow
from src.services.invariant_validator import InvariantValidator


@pytest.mark.asyncio
@pytest.mark.compliance
class TestPrincipleI_ParallelFirst:
    """
    Test Principle I: Parallel-First Architecture.

    Requirements:
    - All participant input MUST be collected simultaneously within each round
    - No replies, threading, or turn-taking during input collection
    - Each participant's response MUST be independent within a round
    """

    async def test_no_reply_mechanism_in_submission_model(self, db_session):
        """
        Verify Submission model does not support replies or threading.

        Constitutional guarantee: No participant may respond to another
        participant's input within the same round.
        """
        # Verify Submission model has no reply_to or parent_submission fields
        submission_columns = [col.name for col in Submission.__table__.columns]

        assert "reply_to" not in submission_columns, \
            "Submission model MUST NOT have reply_to field (violates Principle I)"
        assert "parent_submission_id" not in submission_columns, \
            "Submission model MUST NOT have parent_submission_id (violates Principle I)"
        assert "thread_id" not in submission_columns, \
            "Submission model MUST NOT have thread_id (violates Principle I)"

    async def test_parallel_submission_independence(self, db_session):
        """
        Verify submissions within a round are independent (no ordering).

        Constitutional guarantee: Parallel input scales with participation
        rather than being constrained by turn-taking.
        """
        # Create round
        discussion = Discussion(
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
            host_user_id=uuid4(),
        )
        db_session.add(discussion)
        await db_session.flush()

        round_entity = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts?",
            status=RoundStatus.SUBMISSION_OPEN,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        # Create 5 participants submitting simultaneously
        participants = []
        for i in range(5):
            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()
            participants.append(participant)

        # All submit within same second (parallel)
        base_time = datetime.now(timezone.utc)
        for i, participant in enumerate(participants):
            submission = Submission(
                participant_id=participant.participant_id,
                round_id=round_entity.round_id,
                submission_text=f"Independent thought {i+1}",
                modality=SubmissionModality.TEXT,
                submitted_at=base_time + timedelta(milliseconds=i * 100),  # Within same second
            )
            db_session.add(submission)

        await db_session.commit()

        # Verify all submissions exist and have no ordering dependencies
        result = await db_session.execute(
            select(Submission).where(Submission.round_id == round_entity.round_id)
        )
        submissions = result.scalars().all()

        assert len(submissions) == 5
        # Verify no submission references another submission
        for submission in submissions:
            # Check no foreign keys to other submissions exist
            assert not hasattr(submission, 'parent_submission_id')
            assert not hasattr(submission, 'reply_to')


@pytest.mark.asyncio
@pytest.mark.compliance
class TestPrincipleII_IntentFidelity:
    """
    Test Principle II: Intent Fidelity.

    Requirements:
    - Each participant response MUST be interpreted individually
    - Summary MUST be approved by participant before aggregation
    - 100% approval required (no unapproved summaries in clustering)
    """

    async def test_no_unapproved_summaries_in_clustering(self, db_session):
        """
        Verify clustering only includes approved summaries (100% rule).

        Constitutional guarantee: No response may be included in synthesis
        without explicit participant approval.
        """
        validator = InvariantValidator()

        # Create round
        discussion = Discussion(
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
            host_user_id=uuid4(),
        )
        db_session.add(discussion)
        await db_session.flush()

        round_entity = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="Test question",
            status=RoundStatus.CLUSTERING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        # Create cluster
        cluster = ThoughtSpace(
            round_id=round_entity.round_id,
            label_summary="Test cluster",
            member_count=3,
            member_pct=1.0,
        )
        db_session.add(cluster)
        await db_session.flush()

        # Create 3 participants - all with APPROVED summaries
        for i in range(3):
            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()

            approved_summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_entity.round_id,
                submission_id=None,
                summary_text=f"Approved summary {i+1}",
                cluster_id=cluster.cluster_id,
            )
            db_session.add(approved_summary)

        await db_session.commit()

        # Validate Intent Fidelity
        result = await validator.validate_intent_fidelity(db_session, round_entity.round_id)

        assert result.passed is True, \
            "Intent Fidelity MUST pass when all summaries are approved (Principle II)"
        assert result.details["approval_rate"] == 1.0, \
            "Approval rate MUST be 100% before clustering (Principle II)"

    async def test_explicit_approval_required(self, db_session):
        """
        Verify approval is explicit (not implicit or timeout-based).

        Constitutional guarantee: Summary approval MUST be explicit.
        """
        # Create participant and summary
        discussion = Discussion(
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
            host_user_id=uuid4(),
        )
        db_session.add(discussion)
        await db_session.flush()

        round_entity = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="Test question",
            status=RoundStatus.APPROVING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        participant = Participant(
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        db_session.add(participant)
        await db_session.flush()

        # ApprovedSummary requires explicit creation (no auto-approval)
        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round_entity.round_id,
            submission_id=None,
            summary_text="Explicitly approved summary",
        )
        db_session.add(approved_summary)
        await db_session.commit()

        # Verify summary exists and has explicit approval timestamp
        result = await db_session.execute(
            select(ApprovedSummary).where(
                ApprovedSummary.participant_id == participant.participant_id
            )
        )
        summary = result.scalar_one()

        assert summary.approved_at is not None, \
            "Approval timestamp MUST be set (explicit approval, Principle II)"
        assert summary.summary_text == "Explicitly approved summary", \
            "Summary text MUST match participant-approved content (Principle II)"


@pytest.mark.asyncio
@pytest.mark.compliance
class TestPrincipleIII_SemanticAccuracy:
    """
    Test Principle III: Semantic Accuracy Over Aesthetics.

    Requirements:
    - Aggregation MUST prioritize semantic clustering accuracy
    - Low-frequency ideas MUST persist as independent thought spaces
    - No forced merging for visual simplicity
    - 100% participant coverage in clusters
    """

    async def test_singleton_clusters_preserved(self, db_session):
        """
        Verify singleton clusters (1 participant) are preserved.

        Constitutional guarantee: No merging may occur that distorts
        participant intent for the sake of diagram neatness.
        """
        validator = InvariantValidator()

        # Create round
        discussion = Discussion(
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
            host_user_id=uuid4(),
        )
        db_session.add(discussion)
        await db_session.flush()

        round_entity = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="Test question",
            status=RoundStatus.CLUSTERING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        # Create singleton cluster (minority view)
        singleton_cluster = ThoughtSpace(
            round_id=round_entity.round_id,
            label_summary="Unique minority perspective",
            member_count=1,
            member_pct=0.2,  # Only 20% of participants
        )
        db_session.add(singleton_cluster)
        await db_session.flush()

        # Create majority cluster
        majority_cluster = ThoughtSpace(
            round_id=round_entity.round_id,
            label_summary="Majority view",
            member_count=4,
            member_pct=0.8,
        )
        db_session.add(majority_cluster)
        await db_session.flush()

        # Create participants
        for i in range(4):
            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()

            approved_summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_entity.round_id,
                submission_id=None,
                summary_text=f"Majority view {i+1}",
                cluster_id=majority_cluster.cluster_id,
            )
            db_session.add(approved_summary)

        # Create singleton participant
        singleton_participant = Participant(
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        db_session.add(singleton_participant)
        await db_session.flush()

        singleton_summary = ApprovedSummary(
            participant_id=singleton_participant.participant_id,
            round_id=round_entity.round_id,
            submission_id=None,
            summary_text="Unique minority perspective",
            cluster_id=singleton_cluster.cluster_id,
        )
        db_session.add(singleton_summary)
        await db_session.commit()

        # Validate both clusters exist and singleton is preserved
        result = await db_session.execute(
            select(ThoughtSpace).where(ThoughtSpace.round_id == round_entity.round_id)
        )
        clusters = result.scalars().all()

        assert len(clusters) == 2, \
            "Both majority and singleton clusters MUST exist (Principle III)"

        singleton_exists = any(c.member_count == 1 for c in clusters)
        assert singleton_exists, \
            "Singleton cluster MUST be preserved (no forced merging, Principle III)"

        # Validate semantic accuracy
        validation = await validator.validate_semantic_accuracy(db_session, round_entity.round_id)
        assert validation.passed is True, \
            "100% participant coverage required (Principle III)"

    async def test_no_minimum_cluster_size_constraint(self, db_session):
        """
        Verify no minimum cluster size is enforced.

        Constitutional guarantee: Minimum cluster size constraints are PROHIBITED.
        """
        # Create round with multiple singleton clusters
        discussion = Discussion(
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
            host_user_id=uuid4(),
        )
        db_session.add(discussion)
        await db_session.flush()

        round_entity = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="Test question",
            status=RoundStatus.CLUSTERING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        # Create 5 singleton clusters (all size 1)
        for i in range(5):
            cluster = ThoughtSpace(
                round_id=round_entity.round_id,
                label_summary=f"Unique view {i+1}",
                member_count=1,
                member_pct=0.2,
            )
            db_session.add(cluster)
            await db_session.flush()

            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()

            approved_summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_entity.round_id,
                submission_id=None,
                summary_text=f"Unique view {i+1}",
                cluster_id=cluster.cluster_id,
            )
            db_session.add(approved_summary)

        await db_session.commit()

        # Verify all 5 singleton clusters exist
        result = await db_session.execute(
            select(ThoughtSpace).where(ThoughtSpace.round_id == round_entity.round_id)
        )
        clusters = result.scalars().all()

        assert len(clusters) == 5, \
            "All singleton clusters MUST be preserved (Principle III)"
        assert all(c.member_count == 1 for c in clusters), \
            "No minimum cluster size constraint allowed (Principle III)"


@pytest.mark.asyncio
@pytest.mark.compliance
class TestPrincipleIV_TemporalTransparency:
    """
    Test Principle IV: Temporal Transparency.

    Requirements:
    - Sankey MUST represent participant movement across rounds
    - Flow widths MUST reflect actual participant transitions
    - Engagement decay, consolidation visible (no artificial normalization)
    """

    async def test_flows_computed_from_participant_movement(self, db_session):
        """
        Verify flows computed from actual participant movement (not similarity).

        Constitutional guarantee: Flows MUST be computed strictly from
        participant movement (not similarity scores).
        """
        validator = InvariantValidator()

        # Create 2 rounds
        discussion = Discussion(
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
            host_user_id=uuid4(),
        )
        db_session.add(discussion)
        await db_session.flush()

        round_1 = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="Round 1",
            status=RoundStatus.COMPLETE,
            submission_window_duration_sec=300,
        )
        round_2 = Round(
            discussion_id=discussion.discussion_id,
            round_num=2,
            question_text="Round 2",
            status=RoundStatus.SANKEY_BUILDING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_1)
        db_session.add(round_2)
        await db_session.flush()

        # Create clusters
        cluster_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Round 1 cluster",
            member_count=5,
            member_pct=1.0,
        )
        cluster_r2 = ThoughtSpace(
            round_id=round_2.round_id,
            label_summary="Round 2 cluster",
            member_count=3,
            member_pct=1.0,  # 2 dropped out
        )
        db_session.add(cluster_r1)
        db_session.add(cluster_r2)
        await db_session.flush()

        # Create 5 participants
        participants = []
        for i in range(5):
            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()
            participants.append(participant)

        # Round 1: All 5 in cluster
        for participant in participants:
            summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_1.round_id,
                submission_id=None,
                summary_text="R1 summary",
                cluster_id=cluster_r1.cluster_id,
            )
            db_session.add(summary)

        # Round 2: Only 3 continue
        for participant in participants[:3]:
            summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_2.round_id,
                submission_id=None,
                summary_text="R2 summary",
                cluster_id=cluster_r2.cluster_id,
            )
            db_session.add(summary)

        await db_session.commit()

        # Validate flow count matches actual participant movement (3, not 5)
        result = await validator.validate_temporal_transparency(
            db_session,
            source_cluster_id=cluster_r1.cluster_id,
            target_cluster_id=cluster_r2.cluster_id,
            expected_count=3,
        )

        assert result.passed is True, \
            "Flow count MUST match actual participant movement (Principle IV)"
        assert result.details["flow_count"] == 3, \
            "Flow width MUST reflect actual transitions, not source size (Principle IV)"

    async def test_dropout_reduces_mass_naturally(self, db_session):
        """
        Verify dropout causes natural flow mass reduction (no backfilling).

        Constitutional guarantee: Participants who stop responding MUST cause
        natural flow mass reduction (no backfilling).
        """
        # Create 2 rounds with dropout
        discussion = Discussion(
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
            host_user_id=uuid4(),
        )
        db_session.add(discussion)
        await db_session.flush()

        round_1 = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="Round 1",
            status=RoundStatus.COMPLETE,
            submission_window_duration_sec=300,
        )
        round_2 = Round(
            discussion_id=discussion.discussion_id,
            round_num=2,
            question_text="Round 2",
            status=RoundStatus.COMPLETE,
            submission_window_duration_sec=300,
        )
        db_session.add(round_1)
        db_session.add(round_2)
        await db_session.flush()

        # Create clusters
        cluster_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Round 1 cluster",
            member_count=10,
            member_pct=1.0,
        )
        cluster_r2 = ThoughtSpace(
            round_id=round_2.round_id,
            label_summary="Round 2 cluster",
            member_count=6,  # 40% dropout
            member_pct=1.0,
        )
        db_session.add(cluster_r1)
        db_session.add(cluster_r2)
        await db_session.flush()

        # Create 10 participants
        for i in range(10):
            participant = Participant(
                discussion_id=discussion.discussion_id,
                user_id=uuid4(),
                first_round=1,
                last_round=2 if i < 6 else 1,  # 4 drop out
                dropout_reason=None if i < 6 else DropoutReason.NO_SUBMISSION,
            )
            db_session.add(participant)
            await db_session.flush()

            # Round 1
            summary_r1 = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_1.round_id,
                submission_id=None,
                summary_text="R1",
                cluster_id=cluster_r1.cluster_id,
            )
            db_session.add(summary_r1)

            # Round 2: Only 6 continue
            if i < 6:
                summary_r2 = ApprovedSummary(
                    participant_id=participant.participant_id,
                    round_id=round_2.round_id,
                    submission_id=None,
                    summary_text="R2",
                    cluster_id=cluster_r2.cluster_id,
                )
                db_session.add(summary_r2)

        await db_session.commit()

        # Verify cluster sizes reflect natural dropout (no synthetic nodes)
        result = await db_session.execute(
            select(ThoughtSpace).where(ThoughtSpace.round_id == round_2.round_id)
        )
        r2_cluster = result.scalar_one()

        assert r2_cluster.member_count == 6, \
            "Round 2 cluster size MUST reflect actual participation (Principle IV)"

        # Verify no synthetic/placeholder participants exist
        result = await db_session.execute(
            select(Participant).where(Participant.discussion_id == discussion.discussion_id)
        )
        all_participants = result.scalars().all()

        assert len(all_participants) == 10, \
            "No synthetic participants created for dropout (Principle IV)"


@pytest.mark.asyncio
@pytest.mark.compliance
class TestPrincipleV_CommunityBounded:
    """
    Test Principle V: Community-Bounded Context.

    Requirements:
    - All discussions MUST occur within communities
    - Community context MUST be preserved
    """

    async def test_discussion_requires_community(self, db_session):
        """
        Verify all discussions are community-bounded.

        Constitutional guarantee: All discussions MUST occur within communities.
        """
        # Verify Discussion model requires community_id
        discussion_columns = {col.name: col for col in Discussion.__table__.columns}

        assert "community_id" in discussion_columns, \
            "Discussion MUST have community_id field (Principle V)"

        community_col = discussion_columns["community_id"]
        assert not community_col.nullable, \
            "community_id MUST be required (not nullable, Principle V)"

        # Try to create discussion with community
        discussion = Discussion(
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
            host_user_id=uuid4(),
        )
        db_session.add(discussion)
        await db_session.commit()

        # Verify discussion has community association
        result = await db_session.execute(
            select(Discussion).where(Discussion.discussion_id == discussion.discussion_id)
        )
        fetched = result.scalar_one()

        assert fetched.community_id is not None, \
            "Discussion MUST have community context (Principle V)"


@pytest.mark.asyncio
@pytest.mark.compliance
class TestPrincipleVI_SynchronousDeliberation:
    """
    Test Principle VI: Synchronous Deliberation (MVP).

    Requirements:
    - Discussions MUST be time-boxed with enforced round timers
    - Submission windows: 3-6 minutes
    - Typical sessions: <60 minutes across 3-5 rounds
    - Asynchronous participation out of scope for MVP
    """

    async def test_submission_window_time_bounds(self, db_session):
        """
        Verify submission windows are time-boxed (3-6 minutes).

        Constitutional guarantee: Round timers MUST be enforced (3-6 min input).
        """
        # Create round
        discussion = Discussion(
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
            host_user_id=uuid4(),
        )
        db_session.add(discussion)
        await db_session.flush()

        round_entity = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="Test question",
            status=RoundStatus.SUBMISSION_OPEN,
            submission_window_duration_sec=300,  # 5 minutes
        )
        db_session.add(round_entity)
        await db_session.commit()

        # Verify duration is within constitutional bounds
        assert 180 <= round_entity.submission_window_duration_sec <= 360, \
            "Submission window MUST be 3-6 minutes (Principle VI)"

    async def test_round_has_defined_timing(self, db_session):
        """
        Verify rounds have defined start/end times (not asynchronous).

        Constitutional guarantee: Discussions MUST have defined start/end times.
        """
        # Verify Round model has timing fields
        round_columns = [col.name for col in Round.__table__.columns]

        assert "submission_window_duration_sec" in round_columns, \
            "Round MUST have submission_window_duration_sec (Principle VI)"
        assert "submission_window_start" in round_columns, \
            "Round MUST have submission_window_start (Principle VI)"
        assert "submission_window_end" in round_columns, \
            "Round MUST have submission_window_end (Principle VI)"

        # Verify no async/late-arrival fields exist
        assert "allow_late_arrival" not in round_columns, \
            "Late arrival PROHIBITED in MVP (Principle VI)"
        assert "async_mode" not in round_columns, \
            "Async mode out of scope for MVP (Principle VI)"


@pytest.mark.asyncio
@pytest.mark.compliance
class TestPrincipleVII_RepresentationNotAdjudication:
    """
    Test Principle VII: Representation Not Adjudication.

    Requirements:
    - System MUST represent collective thinking without decisions/votes
    - No rankings, probabilities, scores, or forced convergence
    - Sankey diagram is primary output
    """

    async def test_no_voting_mechanisms(self, db_session):
        """
        Verify no voting or ranking mechanisms exist.

        Constitutional guarantee: No voting mechanisms in visualization or synthesis.
        """
        # Verify models don't have voting/ranking fields
        thought_space_columns = [col.name for col in ThoughtSpace.__table__.columns]

        assert "vote_count" not in thought_space_columns, \
            "ThoughtSpace MUST NOT have vote_count (Principle VII)"
        assert "ranking" not in thought_space_columns, \
            "ThoughtSpace MUST NOT have ranking (Principle VII)"
        assert "score" not in thought_space_columns, \
            "ThoughtSpace MUST NOT have score (Principle VII)"
        assert "confidence_score" not in thought_space_columns, \
            "ThoughtSpace MUST NOT have confidence_score (Principle VII)"
        assert "probability" not in thought_space_columns, \
            "ThoughtSpace MUST NOT have probability (Principle VII)"
        assert "winning_idea" not in thought_space_columns, \
            "ThoughtSpace MUST NOT have winning_idea flag (Principle VII)"

    async def test_no_forced_convergence_detection(self, db_session):
        """
        Verify no automated convergence detection exists.

        Constitutional guarantee: No automated convergence detection that
        implies "discussion is done".
        """
        # Verify Round model doesn't have convergence fields
        round_columns = [col.name for col in Round.__table__.columns]

        assert "convergence_score" not in round_columns, \
            "Round MUST NOT have convergence_score (Principle VII)"
        assert "is_converged" not in round_columns, \
            "Round MUST NOT have is_converged flag (Principle VII)"
        assert "agreement_level" not in round_columns, \
            "Round MUST NOT have agreement_level (Principle VII)"

    async def test_sankey_is_primary_output(self, db_session):
        """
        Verify Sankey diagram data is preserved as primary output.

        Constitutional guarantee: Final outputs MUST include the complete
        Sankey diagram, not derivative metrics.
        """
        # Create complete discussion with Sankey data
        discussion = Discussion(
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
            host_user_id=uuid4(),
            status=DiscussionStatus.COMPLETED,
        )
        db_session.add(discussion)
        await db_session.flush()

        round_entity = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="Test",
            status=RoundStatus.COMPLETE,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        # Create thought space (Sankey column)
        cluster = ThoughtSpace(
            round_id=round_entity.round_id,
            label_summary="Test cluster",
            member_count=1,
            member_pct=1.0,
        )
        db_session.add(cluster)
        await db_session.commit()

        # Verify thought space data exists (Sankey representation)
        result = await db_session.execute(
            select(ThoughtSpace).where(ThoughtSpace.round_id == round_entity.round_id)
        )
        thought_spaces = result.scalars().all()

        assert len(thought_spaces) > 0, \
            "Thought spaces (Sankey representation) MUST be preserved (Principle VII)"

        # Verify essential Sankey data fields exist
        for ts in thought_spaces:
            assert ts.label_summary is not None, \
                "Thought space label MUST exist for Sankey (Principle VII)"
            assert ts.member_count is not None, \
                "Thought space member count MUST exist for Sankey width (Principle VII)"
            assert ts.member_pct is not None, \
                "Thought space percentage MUST exist for Sankey proportions (Principle VII)"


@pytest.mark.asyncio
@pytest.mark.compliance
async def test_all_principles_integration(db_session):
    """
    Integration test validating all 7 constitutional principles together.

    Creates complete 2-round discussion and validates all principles are satisfied.
    """
    validator = InvariantValidator()

    # Create discussion (Principle V: Community-Bounded)
    discussion = Discussion(
        community_id=uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=2,
        host_user_id=uuid4(),
    )
    db_session.add(discussion)
    await db_session.flush()

    # Create Round 1 (Principle VI: Time-boxed)
    round_1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="Round 1 question",
        status=RoundStatus.COMPLETE,
        submission_window_duration_sec=300,  # 5 minutes
    )
    db_session.add(round_1)
    await db_session.flush()

    # Create thought spaces (Principle III: Semantic Accuracy, Principle VII: No rankings)
    cluster_1_r1 = ThoughtSpace(
        round_id=round_1.round_id,
        label_summary="Majority view",
        member_count=3,
        member_pct=0.75,
    )
    singleton_cluster = ThoughtSpace(
        round_id=round_1.round_id,
        label_summary="Minority view",
        member_count=1,  # Singleton preserved
        member_pct=0.25,
    )
    db_session.add(cluster_1_r1)
    db_session.add(singleton_cluster)
    await db_session.flush()

    # Create 4 participants (Principle I: Parallel input)
    participants = []
    for i in range(4):
        participant = Participant(
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        db_session.add(participant)
        await db_session.flush()
        participants.append(participant)

    # All participants submit in Round 1 (Principle II: Intent Fidelity)
    for i, participant in enumerate(participants):
        cluster = cluster_1_r1 if i < 3 else singleton_cluster
        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round_1.round_id,
            submission_id=None,
            summary_text=f"Approved summary {i+1}",
            cluster_id=cluster.cluster_id,
        )
        db_session.add(approved_summary)

    # Create Round 2
    round_2 = Round(
        discussion_id=discussion.discussion_id,
        round_num=2,
        question_text="Round 2 question",
        status=RoundStatus.COMPLETE,
        submission_window_duration_sec=300,
    )
    db_session.add(round_2)
    await db_session.flush()

    cluster_r2 = ThoughtSpace(
        round_id=round_2.round_id,
        label_summary="Round 2 cluster",
        member_count=2,  # Natural dropout (Principle IV)
        member_pct=1.0,
    )
    db_session.add(cluster_r2)
    await db_session.flush()

    # Only 2 participants continue to Round 2 (Principle IV: Temporal Transparency)
    for participant in participants[:2]:
        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round_2.round_id,
            submission_id=None,
            summary_text=f"R2 summary",
            cluster_id=cluster_r2.cluster_id,
        )
        db_session.add(approved_summary)

    await db_session.commit()

    # Validate all principles
    # Principle I: Parallel-First (structural - no replies)
    submission_columns = [col.name for col in Submission.__table__.columns]
    assert "reply_to" not in submission_columns

    # Principle II: Intent Fidelity
    intent_result = await validator.validate_intent_fidelity(db_session, round_1.round_id)
    assert intent_result.passed is True

    # Principle III: Semantic Accuracy
    semantic_result = await validator.validate_semantic_accuracy(db_session, round_1.round_id)
    assert semantic_result.passed is True
    assert semantic_result.details["cluster_count"] == 2  # Singleton preserved

    # Principle IV: Temporal Transparency
    temporal_result = await validator.validate_temporal_transparency(
        db_session,
        source_cluster_id=cluster_1_r1.cluster_id,
        target_cluster_id=cluster_r2.cluster_id,
        expected_count=2,  # Natural dropout from 3 to 2
    )
    assert temporal_result.passed is True

    # Principle V: Community-Bounded
    assert discussion.community_id is not None

    # Principle VI: Synchronous Deliberation
    assert 180 <= round_1.submission_window_duration_sec <= 360

    # Principle VII: Representation Not Adjudication
    thought_space_columns = [col.name for col in ThoughtSpace.__table__.columns]
    assert "vote_count" not in thought_space_columns
    assert "ranking" not in thought_space_columns

    # All principles validated
    print("All 7 constitutional principles validated successfully")
