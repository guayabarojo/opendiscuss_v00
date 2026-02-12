"""
Integration tests for US1 constitutional invariant validation.

Tests the three core constitutional principles:
1. Intent Fidelity: 100% approved summaries before clustering
2. Semantic Accuracy: 100% participant coverage in clusters
3. Temporal Transparency: Correct proportions in thought spaces

Task: T042 - Invariant validation integration test
"""

import pytest
from uuid import uuid4
from sqlalchemy import select

from src.models.round import Round, RoundStatus
from src.models.participant import Participant
from src.models.submission import Submission, SubmissionModality
from src.models.approved_summary import ApprovedSummary
from src.models.thought_space import ThoughtSpace
from src.models.flow import Flow
from src.services.invariant_validator import InvariantValidator, ValidationResult


@pytest.mark.asyncio
@pytest.mark.integration
class TestIntentFidelityValidation:
    """Test Intent Fidelity: 100% approved summaries before clustering."""

    async def test_intent_fidelity_all_approved(self, db_session):
        """
        Test successful validation when all summaries are approved.

        Expected: Validation passes with 100% approval rate.
        """
        validator = InvariantValidator()

        # Create round
        round_entity = Round(
            discussion_id=uuid4(),
            round_num=1,
            question_text="What are your thoughts?",
            status=RoundStatus.APPROVING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        # Create participants and approved summaries
        for i in range(5):
            participant = Participant(
                discussion_id=round_entity.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()

            approved_summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_entity.round_id,
                submission_id=None,  # Can be null after ephemeral deletion
                summary_text=f"Approved summary {i+1}",
            )
            db_session.add(approved_summary)

        await db_session.commit()

        # Validate Intent Fidelity
        result = await validator.validate_intent_fidelity(db_session, round_entity.round_id)

        assert result.passed is True
        assert "100%" in result.message
        assert result.details["total_summaries"] == 5
        assert result.details["approved_summaries"] == 5
        assert result.details["approval_rate"] == 1.0

    async def test_intent_fidelity_zero_participants(self, db_session):
        """
        Test validation with zero participants (edge case).

        Expected: Validation passes (zero participants is valid).
        """
        validator = InvariantValidator()

        # Create round with no participants
        round_entity = Round(
            discussion_id=uuid4(),
            round_num=1,
            question_text="What are your thoughts?",
            status=RoundStatus.APPROVING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.commit()

        # Validate Intent Fidelity
        result = await validator.validate_intent_fidelity(db_session, round_entity.round_id)

        assert result.passed is True
        assert "zero participants" in result.message.lower()
        assert result.details["total_summaries"] == 0


@pytest.mark.asyncio
@pytest.mark.integration
class TestSemanticAccuracyValidation:
    """Test Semantic Accuracy: 100% participant coverage in clusters."""

    async def test_semantic_accuracy_full_coverage(self, db_session):
        """
        Test successful validation when all participants are clustered.

        Expected: Validation passes with 100% coverage.
        """
        validator = InvariantValidator()

        # Create round
        round_entity = Round(
            discussion_id=uuid4(),
            round_num=1,
            question_text="What are your thoughts?",
            status=RoundStatus.CLUSTERING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        # Create 2 thought spaces
        cluster_1 = ThoughtSpace(
            round_id=round_entity.round_id,
            label_summary="Cluster 1",
            member_count=3,
            member_pct=0.6,
        )
        cluster_2 = ThoughtSpace(
            round_id=round_entity.round_id,
            label_summary="Cluster 2",
            member_count=2,
            member_pct=0.4,
        )
        db_session.add(cluster_1)
        db_session.add(cluster_2)
        await db_session.flush()

        # Create 5 participants with approved summaries assigned to clusters
        for i in range(3):
            participant = Participant(
                discussion_id=round_entity.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()

            approved_summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_entity.round_id,
                submission_id=None,
                summary_text=f"Summary {i+1}",
                cluster_id=cluster_1.cluster_id,
            )
            db_session.add(approved_summary)

        for i in range(2):
            participant = Participant(
                discussion_id=round_entity.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()

            approved_summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_entity.round_id,
                submission_id=None,
                summary_text=f"Summary {i+4}",
                cluster_id=cluster_2.cluster_id,
            )
            db_session.add(approved_summary)

        await db_session.commit()

        # Validate Semantic Accuracy
        result = await validator.validate_semantic_accuracy(db_session, round_entity.round_id)

        assert result.passed is True
        assert "100% coverage" in result.message
        assert result.details["total_participants"] == 5
        assert result.details["clustered_participants"] == 5
        assert result.details["cluster_count"] == 2
        assert result.details["coverage_rate"] == 1.0

    async def test_semantic_accuracy_partial_coverage(self, db_session):
        """
        Test validation failure when some participants are not clustered.

        Expected: Validation fails with detailed error message.
        """
        validator = InvariantValidator()

        # Create round
        round_entity = Round(
            discussion_id=uuid4(),
            round_num=1,
            question_text="What are your thoughts?",
            status=RoundStatus.CLUSTERING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        # Create 1 thought space
        cluster = ThoughtSpace(
            round_id=round_entity.round_id,
            label_summary="Cluster 1",
            member_count=2,
            member_pct=0.4,  # Only 40% coverage
        )
        db_session.add(cluster)
        await db_session.flush()

        # Create 5 participants, but only 2 assigned to cluster
        for i in range(2):
            participant = Participant(
                discussion_id=round_entity.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()

            approved_summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_entity.round_id,
                submission_id=None,
                summary_text=f"Clustered summary {i+1}",
                cluster_id=cluster.cluster_id,
            )
            db_session.add(approved_summary)

        # Create 3 unclustered participants
        for i in range(3):
            participant = Participant(
                discussion_id=round_entity.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()

            approved_summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_entity.round_id,
                submission_id=None,
                summary_text=f"Unclustered summary {i+3}",
                cluster_id=None,  # NOT clustered
            )
            db_session.add(approved_summary)

        await db_session.commit()

        # Validate Semantic Accuracy
        result = await validator.validate_semantic_accuracy(db_session, round_entity.round_id)

        assert result.passed is False
        assert "FAILED" in result.message
        assert "3 participants not assigned" in result.message
        assert result.details["total_participants"] == 5
        assert result.details["clustered_participants"] == 2
        assert result.details["unclustered_count"] == 3
        assert result.details["coverage_rate"] == 0.4

    async def test_semantic_accuracy_member_count_mismatch(self, db_session):
        """
        Test validation failure when cluster member_count doesn't match actual.

        Expected: Validation fails with mismatch details.
        """
        validator = InvariantValidator()

        # Create round
        round_entity = Round(
            discussion_id=uuid4(),
            round_num=1,
            question_text="What are your thoughts?",
            status=RoundStatus.CLUSTERING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        # Create thought space with INCORRECT member_count
        cluster = ThoughtSpace(
            round_id=round_entity.round_id,
            label_summary="Cluster 1",
            member_count=5,  # Claims 5 members
            member_pct=1.0,
        )
        db_session.add(cluster)
        await db_session.flush()

        # Create only 3 participants (mismatch)
        for i in range(3):
            participant = Participant(
                discussion_id=round_entity.discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()

            approved_summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_entity.round_id,
                submission_id=None,
                summary_text=f"Summary {i+1}",
                cluster_id=cluster.cluster_id,
            )
            db_session.add(approved_summary)

        await db_session.commit()

        # Validate Semantic Accuracy
        result = await validator.validate_semantic_accuracy(db_session, round_entity.round_id)

        assert result.passed is False
        assert "member_count sum" in result.message
        assert result.details["total_participants"] == 3
        assert result.details["total_members"] == 5  # Claimed by cluster
        assert result.details["mismatch"] == 2

    async def test_semantic_accuracy_singleton_cluster_preserved(self, db_session):
        """
        Test validation passes with singleton cluster (1 participant).

        Constitutional guarantee: Singleton clusters must be preserved.
        Expected: Validation passes.
        """
        validator = InvariantValidator()

        # Create round
        round_entity = Round(
            discussion_id=uuid4(),
            round_num=1,
            question_text="What are your thoughts?",
            status=RoundStatus.CLUSTERING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_entity)
        await db_session.flush()

        # Create singleton thought space
        cluster = ThoughtSpace(
            round_id=round_entity.round_id,
            label_summary="Singleton cluster",
            member_count=1,
            member_pct=1.0,
        )
        db_session.add(cluster)
        await db_session.flush()

        # Create 1 participant
        participant = Participant(
            discussion_id=round_entity.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        db_session.add(participant)
        await db_session.flush()

        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round_entity.round_id,
            submission_id=None,
            summary_text="Singleton summary",
            cluster_id=cluster.cluster_id,
        )
        db_session.add(approved_summary)
        await db_session.commit()

        # Validate Semantic Accuracy
        result = await validator.validate_semantic_accuracy(db_session, round_entity.round_id)

        assert result.passed is True
        assert result.details["total_participants"] == 1
        assert result.details["cluster_count"] == 1


@pytest.mark.asyncio
@pytest.mark.integration
class TestTemporalTransparencyValidation:
    """Test Temporal Transparency: Flow counts match actual participant movement."""

    async def test_temporal_transparency_accurate_flow(self, db_session):
        """
        Test successful validation when flow count matches actual movement.

        Expected: Validation passes with verified flow count.
        """
        validator = InvariantValidator()

        # Create 2 rounds
        discussion_id = uuid4()

        round_1 = Round(
            discussion_id=discussion_id,
            round_num=1,
            question_text="Round 1 question",
            status=RoundStatus.COMPLETE,
            submission_window_duration_sec=300,
        )
        round_2 = Round(
            discussion_id=discussion_id,
            round_num=2,
            question_text="Round 2 question",
            status=RoundStatus.SANKEY_BUILDING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_1)
        db_session.add(round_2)
        await db_session.flush()

        # Create clusters
        cluster_1_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Round 1 Cluster 1",
            member_count=3,
            member_pct=1.0,
        )
        cluster_1_r2 = ThoughtSpace(
            round_id=round_2.round_id,
            label_summary="Round 2 Cluster 1",
            member_count=2,
            member_pct=1.0,
        )
        db_session.add(cluster_1_r1)
        db_session.add(cluster_1_r2)
        await db_session.flush()

        # Create 3 participants
        participants = []
        for i in range(3):
            participant = Participant(
                discussion_id=discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()
            participants.append(participant)

        # Round 1: All 3 participants in cluster_1_r1
        for participant in participants:
            summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_1.round_id,
                submission_id=None,
                summary_text=f"Round 1 summary for {participant.participant_id}",
                cluster_id=cluster_1_r1.cluster_id,
            )
            db_session.add(summary)

        # Round 2: Only 2 participants continue to cluster_1_r2
        for participant in participants[:2]:  # Only first 2
            summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_2.round_id,
                submission_id=None,
                summary_text=f"Round 2 summary for {participant.participant_id}",
                cluster_id=cluster_1_r2.cluster_id,
            )
            db_session.add(summary)

        await db_session.commit()

        # Validate flow: cluster_1_r1 → cluster_1_r2 with count=2
        result = await validator.validate_temporal_transparency(
            db_session,
            source_cluster_id=cluster_1_r1.cluster_id,
            target_cluster_id=cluster_1_r2.cluster_id,
            expected_count=2,
        )

        assert result.passed is True
        assert "matches actual participant movement" in result.message
        assert result.details["flow_count"] == 2
        assert result.details["source_size"] == 3
        assert result.details["target_size"] == 2

    async def test_temporal_transparency_flow_count_mismatch(self, db_session):
        """
        Test validation failure when flow count doesn't match actual movement.

        Expected: Validation fails with mismatch details.
        """
        validator = InvariantValidator()

        # Create 2 rounds
        discussion_id = uuid4()

        round_1 = Round(
            discussion_id=discussion_id,
            round_num=1,
            question_text="Round 1 question",
            status=RoundStatus.COMPLETE,
            submission_window_duration_sec=300,
        )
        round_2 = Round(
            discussion_id=discussion_id,
            round_num=2,
            question_text="Round 2 question",
            status=RoundStatus.SANKEY_BUILDING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_1)
        db_session.add(round_2)
        await db_session.flush()

        # Create clusters
        cluster_1_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Round 1 Cluster 1",
            member_count=3,
            member_pct=1.0,
        )
        cluster_1_r2 = ThoughtSpace(
            round_id=round_2.round_id,
            label_summary="Round 2 Cluster 1",
            member_count=2,
            member_pct=1.0,
        )
        db_session.add(cluster_1_r1)
        db_session.add(cluster_1_r2)
        await db_session.flush()

        # Create 3 participants
        participants = []
        for i in range(3):
            participant = Participant(
                discussion_id=discussion_id,
                user_id=uuid4(),
                first_round=1,
            )
            db_session.add(participant)
            await db_session.flush()
            participants.append(participant)

        # Round 1: All 3 in cluster
        for participant in participants:
            summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_1.round_id,
                submission_id=None,
                summary_text=f"R1 {participant.participant_id}",
                cluster_id=cluster_1_r1.cluster_id,
            )
            db_session.add(summary)

        # Round 2: Only 2 continue (actual movement)
        for participant in participants[:2]:
            summary = ApprovedSummary(
                participant_id=participant.participant_id,
                round_id=round_2.round_id,
                submission_id=None,
                summary_text=f"R2 {participant.participant_id}",
                cluster_id=cluster_1_r2.cluster_id,
            )
            db_session.add(summary)

        await db_session.commit()

        # Validate with INCORRECT expected_count=3 (should be 2)
        result = await validator.validate_temporal_transparency(
            db_session,
            source_cluster_id=cluster_1_r1.cluster_id,
            target_cluster_id=cluster_1_r2.cluster_id,
            expected_count=3,  # Wrong! Actual is 2
        )

        assert result.passed is False
        assert "FAILED" in result.message
        assert "mismatch" in result.message.lower()
        assert result.details["expected_count"] == 3
        assert result.details["actual_count"] == 2
        assert result.details["mismatch"] == 1

    async def test_temporal_transparency_non_consecutive_rounds(self, db_session):
        """
        Test validation failure when clusters are not in consecutive rounds.

        Expected: Validation fails with round mismatch error.
        """
        validator = InvariantValidator()

        # Create non-consecutive rounds
        discussion_id = uuid4()

        round_1 = Round(
            discussion_id=discussion_id,
            round_num=1,
            question_text="Round 1 question",
            status=RoundStatus.COMPLETE,
            submission_window_duration_sec=300,
        )
        round_3 = Round(
            discussion_id=discussion_id,
            round_num=3,  # Skip round 2
            question_text="Round 3 question",
            status=RoundStatus.SANKEY_BUILDING,
            submission_window_duration_sec=300,
        )
        db_session.add(round_1)
        db_session.add(round_3)
        await db_session.flush()

        # Create clusters
        cluster_r1 = ThoughtSpace(
            round_id=round_1.round_id,
            label_summary="Round 1 cluster",
            member_count=1,
            member_pct=1.0,
        )
        cluster_r3 = ThoughtSpace(
            round_id=round_3.round_id,
            label_summary="Round 3 cluster",
            member_count=1,
            member_pct=1.0,
        )
        db_session.add(cluster_r1)
        db_session.add(cluster_r3)
        await db_session.commit()

        # Validate flow between non-consecutive rounds
        result = await validator.validate_temporal_transparency(
            db_session,
            source_cluster_id=cluster_r1.cluster_id,
            target_cluster_id=cluster_r3.cluster_id,
            expected_count=1,
        )

        assert result.passed is False
        assert "not in consecutive rounds" in result.message
        assert result.details["source_round"] == 1
        assert result.details["target_round"] == 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validate_all_invariants(db_session):
    """
    Test comprehensive validation of all constitutional invariants.

    Creates a complete round with all data and validates all three principles.
    """
    validator = InvariantValidator()

    # Create round
    round_entity = Round(
        discussion_id=uuid4(),
        round_num=1,
        question_text="What are your thoughts?",
        status=RoundStatus.SANKEY_BUILDING,
        submission_window_duration_sec=300,
    )
    db_session.add(round_entity)
    await db_session.flush()

    # Create cluster
    cluster = ThoughtSpace(
        round_id=round_entity.round_id,
        label_summary="Main cluster",
        member_count=3,
        member_pct=1.0,
    )
    db_session.add(cluster)
    await db_session.flush()

    # Create 3 participants with approved summaries
    for i in range(3):
        participant = Participant(
            discussion_id=round_entity.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        db_session.add(participant)
        await db_session.flush()

        approved_summary = ApprovedSummary(
            participant_id=participant.participant_id,
            round_id=round_entity.round_id,
            submission_id=None,
            summary_text=f"Summary {i+1}",
            cluster_id=cluster.cluster_id,
        )
        db_session.add(approved_summary)

    await db_session.commit()

    # Validate all invariants
    results = await validator.validate_all_invariants(db_session, round_entity.round_id)

    # Verify all validations passed
    assert "intent_fidelity" in results
    assert "semantic_accuracy" in results

    assert results["intent_fidelity"].passed is True
    assert results["semantic_accuracy"].passed is True

    # Verify details
    assert results["intent_fidelity"].details["total_summaries"] == 3
    assert results["semantic_accuracy"].details["total_participants"] == 3
    assert results["semantic_accuracy"].details["cluster_count"] == 1
