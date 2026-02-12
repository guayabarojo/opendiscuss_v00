"""
Integration tests for Discussion Report Generation (Spec 005 User Story 5)

Tests all 4 core report generation functions:
- generate_cluster_summaries
- generate_dropout_curve
- generate_top_movements
- assemble_discussion_report

Validates:
- FR-034: System generates discussion report including final SankeyGraph
- FR-035: Report includes per-round cluster summaries
- FR-036: Report includes participant counts per round (dropout curve)
- FR-037: Report includes top movement edges per round transition
- FR-038: Report is exportable in structured format
- SC-008: Reports include all required sections 100% of the time
"""

import pytest
from uuid import uuid4

from src.models.sankey_graph import SankeyGraph
from src.models.sankey_column import SankeyColumn
from src.models.sankey_node import SankeyNode
from src.models.sankey_edge import SankeyEdge
from src.services.report_service import (
    generate_cluster_summaries,
    generate_dropout_curve,
    generate_top_movements,
    assemble_discussion_report,
)


@pytest.fixture
def single_round_sankey():
    """
    Create a single-round Sankey graph for testing.

    Structure:
    - 1 round
    - 3 clusters: 10, 15, 5 participants
    - 0 edges (single round)
    """
    discussion_id = uuid4()
    round_id = uuid4()

    cluster_1 = uuid4()
    cluster_2 = uuid4()
    cluster_3 = uuid4()

    nodes = [
        SankeyNode(
            node_id=cluster_1,
            cluster_id=cluster_1,
            label_summary="Climate action is critical",
            user_count=10,
            user_pct=0.333,
        ),
        SankeyNode(
            node_id=cluster_2,
            cluster_id=cluster_2,
            label_summary="Economic growth should be prioritized",
            user_count=15,
            user_pct=0.5,
        ),
        SankeyNode(
            node_id=cluster_3,
            cluster_id=cluster_3,
            label_summary="Education reform needed",
            user_count=5,
            user_pct=0.167,
        ),
    ]

    column = SankeyColumn(
        round_index=0,
        nodes=nodes,
        total_participants=30
    )

    return SankeyGraph(
        discussion_id=discussion_id,
        rounds=[round_id],
        columns=[column],
        edges=[],
    )


@pytest.fixture
def multi_round_sankey():
    """
    Create a multi-round Sankey graph with dropout and movements.

    Structure:
    - 3 rounds
    - Round 0: 20 participants, 2 clusters (12, 8)
    - Round 1: 18 participants, 3 clusters (10, 5, 3)
    - Round 2: 15 participants, 2 clusters (9, 6)
    - 5 edges total showing various movements
    """
    discussion_id = uuid4()
    round_ids = [uuid4(), uuid4(), uuid4()]

    # Round 0 clusters
    c0_1 = uuid4()
    c0_2 = uuid4()

    # Round 1 clusters
    c1_1 = uuid4()
    c1_2 = uuid4()
    c1_3 = uuid4()

    # Round 2 clusters
    c2_1 = uuid4()
    c2_2 = uuid4()

    # Round 0 column
    column_0 = SankeyColumn(
        round_index=0,
        nodes=[
            SankeyNode(
                node_id=c0_1,
                cluster_id=c0_1,
                label_summary="Tech innovation drives progress",
                user_count=12,
                user_pct=0.6,
            ),
            SankeyNode(
                node_id=c0_2,
                cluster_id=c0_2,
                label_summary="Social equity matters most",
                user_count=8,
                user_pct=0.4,
            ),
        ],
        total_participants=20
    )

    # Round 1 column
    column_1 = SankeyColumn(
        round_index=1,
        nodes=[
            SankeyNode(
                node_id=c1_1,
                cluster_id=c1_1,
                label_summary="Balanced approach needed",
                user_count=10,
                user_pct=0.5556,
            ),
            SankeyNode(
                node_id=c1_2,
                cluster_id=c1_2,
                label_summary="Tech with social conscience",
                user_count=5,
                user_pct=0.2778,
            ),
            SankeyNode(
                node_id=c1_3,
                cluster_id=c1_3,
                label_summary="Equity first always",
                user_count=3,
                user_pct=0.1666,
            ),
        ],
        total_participants=18
    )

    # Round 2 column
    column_2 = SankeyColumn(
        round_index=2,
        nodes=[
            SankeyNode(
                node_id=c2_1,
                cluster_id=c2_1,
                label_summary="Integrated solution consensus",
                user_count=9,
                user_pct=0.6,
            ),
            SankeyNode(
                node_id=c2_2,
                cluster_id=c2_2,
                label_summary="Pure equity stance",
                user_count=6,
                user_pct=0.4,
            ),
        ],
        total_participants=15
    )

    # Edges (Round 0 -> Round 1)
    edges = [
        SankeyEdge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=c0_1,
            to_cluster_id=c1_1,
            user_count=8,  # Most from tech to balanced
        ),
        SankeyEdge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=c0_1,
            to_cluster_id=c1_2,
            user_count=3,  # Some from tech to tech+social
        ),
        SankeyEdge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=c0_2,
            to_cluster_id=c1_1,
            user_count=2,  # Some from equity to balanced
        ),
        SankeyEdge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=c0_2,
            to_cluster_id=c1_2,
            user_count=2,  # Some from equity to tech+social
        ),
        SankeyEdge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=c0_2,
            to_cluster_id=c1_3,
            user_count=3,  # Some from equity to equity
        ),
        # Edges (Round 1 -> Round 2)
        SankeyEdge(
            from_round_index=1,
            to_round_index=2,
            from_cluster_id=c1_1,
            to_cluster_id=c2_1,
            user_count=7,  # Most from balanced to integrated
        ),
        SankeyEdge(
            from_round_index=1,
            to_round_index=2,
            from_cluster_id=c1_2,
            to_cluster_id=c2_1,
            user_count=2,  # Some from tech+social to integrated
        ),
        SankeyEdge(
            from_round_index=1,
            to_round_index=2,
            from_cluster_id=c1_1,
            to_cluster_id=c2_2,
            user_count=1,  # Few from balanced to equity
        ),
        SankeyEdge(
            from_round_index=1,
            to_round_index=2,
            from_cluster_id=c1_2,
            to_cluster_id=c2_2,
            user_count=2,  # Some from tech+social to equity
        ),
        SankeyEdge(
            from_round_index=1,
            to_round_index=2,
            from_cluster_id=c1_3,
            to_cluster_id=c2_2,
            user_count=3,  # All from equity to equity
        ),
    ]

    return SankeyGraph(
        discussion_id=discussion_id,
        rounds=round_ids,
        columns=[column_0, column_1, column_2],
        edges=edges,
    )


class TestGenerateClusterSummaries:
    """Test generate_cluster_summaries function."""

    def test_single_round_summaries(self, single_round_sankey):
        """Test cluster summaries for single-round discussion."""
        summaries = generate_cluster_summaries(single_round_sankey)

        # FR-035: Report includes per-round cluster summaries
        assert len(summaries) == 1
        assert summaries[0].round_index == 0
        assert summaries[0].total_participants == 30
        assert summaries[0].cluster_count == 3

        # Clusters should be sorted by user_count descending
        assert summaries[0].clusters[0].user_count == 15
        assert summaries[0].clusters[1].user_count == 10
        assert summaries[0].clusters[2].user_count == 5

        # Singleton count
        assert summaries[0].singleton_count == 0

        # Largest cluster percentage
        assert summaries[0].largest_cluster_pct == 0.5

    def test_multi_round_summaries(self, multi_round_sankey):
        """Test cluster summaries for multi-round discussion."""
        summaries = generate_cluster_summaries(multi_round_sankey)

        # FR-035: Report includes per-round cluster summaries
        assert len(summaries) == 3

        # Round 0
        assert summaries[0].round_index == 0
        assert summaries[0].total_participants == 20
        assert summaries[0].cluster_count == 2

        # Round 1
        assert summaries[1].round_index == 1
        assert summaries[1].total_participants == 18
        assert summaries[1].cluster_count == 3

        # Round 2
        assert summaries[2].round_index == 2
        assert summaries[2].total_participants == 15
        assert summaries[2].cluster_count == 2

    def test_cluster_info_fields(self, single_round_sankey):
        """Test ClusterInfo contains all required fields."""
        summaries = generate_cluster_summaries(single_round_sankey)
        cluster = summaries[0].clusters[0]

        assert cluster.cluster_id is not None
        assert cluster.label != ""
        assert cluster.user_count > 0
        assert 0.0 < cluster.user_pct <= 1.0


class TestGenerateDropoutCurve:
    """Test generate_dropout_curve function."""

    def test_single_round_dropout_curve(self, single_round_sankey):
        """Test dropout curve for single-round discussion."""
        dropout_curve = generate_dropout_curve(single_round_sankey)

        # FR-036: Report includes participant counts per round
        assert len(dropout_curve) == 1
        assert dropout_curve[0].round_index == 0
        assert dropout_curve[0].participant_count == 30

    def test_multi_round_dropout_curve(self, multi_round_sankey):
        """Test dropout curve for multi-round discussion with dropout."""
        dropout_curve = generate_dropout_curve(multi_round_sankey)

        # FR-036: Report includes participant counts per round
        assert len(dropout_curve) == 3

        # Should show declining participants
        assert dropout_curve[0].participant_count == 20
        assert dropout_curve[1].participant_count == 18
        assert dropout_curve[2].participant_count == 15

        # Dropout is visible
        assert dropout_curve[0].participant_count > dropout_curve[1].participant_count
        assert dropout_curve[1].participant_count > dropout_curve[2].participant_count


class TestGenerateTopMovements:
    """Test generate_top_movements function."""

    def test_single_round_no_movements(self, single_round_sankey):
        """Test top movements for single-round discussion (should be empty)."""
        top_movements = generate_top_movements(single_round_sankey)

        # Single round has no edges
        assert len(top_movements) == 0

    def test_multi_round_top_movements(self, multi_round_sankey):
        """Test top movements for multi-round discussion."""
        top_movements = generate_top_movements(multi_round_sankey, top_n=5)

        # FR-037: Report includes top movement edges per round transition
        assert len(top_movements) == 2  # 2 round transitions (0->1, 1->2)

        # Round 0 -> 1
        transition_0_1 = top_movements[0]
        assert transition_0_1.from_round_index == 0
        assert transition_0_1.to_round_index == 1
        assert len(transition_0_1.movements) <= 5
        assert transition_0_1.total_transitions == 5  # 5 edges in round 0->1

        # Top movement should be largest
        top_movement = transition_0_1.movements[0]
        assert top_movement.participant_count == 8  # Largest flow

        # Round 1 -> 2
        transition_1_2 = top_movements[1]
        assert transition_1_2.from_round_index == 1
        assert transition_1_2.to_round_index == 2
        assert len(transition_1_2.movements) <= 5
        assert transition_1_2.total_transitions == 5  # 5 edges in round 1->2

    def test_top_n_parameter(self, multi_round_sankey):
        """Test top_n parameter limits movements returned."""
        top_movements = generate_top_movements(multi_round_sankey, top_n=2)

        # Should only return top 2 per transition
        assert len(top_movements[0].movements) <= 2
        assert len(top_movements[1].movements) <= 2

    def test_movement_detail_fields(self, multi_round_sankey):
        """Test MovementDetail contains all required fields."""
        top_movements = generate_top_movements(multi_round_sankey)
        movement = top_movements[0].movements[0]

        assert movement.from_cluster_id is not None
        assert movement.from_label != ""
        assert movement.to_cluster_id is not None
        assert movement.to_label != ""
        assert movement.participant_count > 0
        assert 0.0 < movement.pct_of_from <= 1.0
        assert 0.0 < movement.pct_of_to <= 1.0

    def test_label_truncation(self, multi_round_sankey):
        """Test labels are truncated to 100 chars."""
        top_movements = generate_top_movements(multi_round_sankey)
        movement = top_movements[0].movements[0]

        assert len(movement.from_label) <= 100
        assert len(movement.to_label) <= 100


class TestAssembleDiscussionReport:
    """Test assemble_discussion_report function."""

    def test_single_round_report(self, single_round_sankey):
        """Test report assembly for single-round discussion."""
        report = assemble_discussion_report(single_round_sankey)

        # FR-034: System generates discussion report including final SankeyGraph
        assert report.discussion_id == single_round_sankey.discussion_id
        assert report.sankey_graph == single_round_sankey

        # FR-035: Cluster summaries included
        assert len(report.cluster_summaries) == 1

        # FR-036: Dropout curve included
        assert len(report.dropout_curve) == 1

        # FR-037: Top movements included (empty for single round)
        assert len(report.top_movements) == 0

        # FR-038: Report is exportable
        assert report.export_format == "json-v1"

    def test_multi_round_report(self, multi_round_sankey):
        """Test report assembly for multi-round discussion."""
        report = assemble_discussion_report(multi_round_sankey)

        # SC-008: Reports include all required sections 100% of the time
        assert report.discussion_id == multi_round_sankey.discussion_id
        assert report.sankey_graph == multi_round_sankey
        assert len(report.cluster_summaries) == 3
        assert len(report.dropout_curve) == 3
        assert len(report.top_movements) == 2

    def test_report_export_format(self, multi_round_sankey):
        """Test report is JSON serializable."""
        report = assemble_discussion_report(multi_round_sankey)

        # FR-038: Report is exportable in structured format
        report_json = report.model_dump(mode='json')

        assert "discussion_id" in report_json
        assert "sankey_graph" in report_json
        assert "cluster_summaries" in report_json
        assert "dropout_curve" in report_json
        assert "top_movements" in report_json
        assert "generated_at" in report_json
        assert "export_format" in report_json

    def test_report_helper_methods(self, multi_round_sankey):
        """Test report helper methods for statistics."""
        report = assemble_discussion_report(multi_round_sankey)

        # Test helper methods
        assert report.get_total_rounds() == 3
        assert report.get_initial_participants() == 20
        assert report.get_final_participants() == 15
        assert report.get_total_dropout() == 5
        assert report.get_dropout_rate() == 0.25  # 5/20 = 0.25

    def test_report_completeness(self, multi_round_sankey):
        """Test report contains complete data for all rounds."""
        report = assemble_discussion_report(multi_round_sankey)

        # SC-008: Reports include all required sections 100% of the time
        # Verify each round has data in all sections
        for round_index in range(3):
            # Cluster summary for this round
            assert any(s.round_index == round_index for s in report.cluster_summaries)

            # Dropout point for this round
            assert any(d.round_index == round_index for d in report.dropout_curve)

        # Verify all transitions have top movements (if multi-round)
        expected_transitions = 2  # 0->1, 1->2
        assert len(report.top_movements) == expected_transitions


@pytest.mark.parametrize("fixture_name", ["single_round_sankey", "multi_round_sankey"])
def test_all_functions_with_fixtures(fixture_name, request):
    """
    Parametrized test to ensure all functions work with all fixtures.

    Validates:
    - All functions are callable
    - All functions return expected types
    - No exceptions raised
    """
    sankey = request.getfixturevalue(fixture_name)

    # Test all 4 functions
    summaries = generate_cluster_summaries(sankey)
    assert isinstance(summaries, list)
    assert len(summaries) > 0

    dropout_curve = generate_dropout_curve(sankey)
    assert isinstance(dropout_curve, list)
    assert len(dropout_curve) > 0

    top_movements = generate_top_movements(sankey)
    assert isinstance(top_movements, list)

    report = assemble_discussion_report(sankey)
    assert report is not None
    assert report.discussion_id == sankey.discussion_id
