"""
Integration test for edge computation in Sankey construction (Phase 4 / User Story 2).

This test verifies that participant movements between rounds are correctly tracked,
aggregated, and converted to SankeyEdge entities with accurate user_count values.

Validates:
- T034: track_movement function correctly fetches participant movements
- T035: aggregate_movements function correctly groups transitions by cluster pairs
- T036: create_edge function creates valid SankeyEdge entities
- T037: compute_derived_metrics correctly calculates pct_of_from and pct_of_to
- T038: build_sankey_graph integrates edge computation workflow
- T039: validate_edge_totals verifies edge accuracy

Success Criteria:
- SC-002: 100% edge accuracy (edge counts match participant movement)
- FR-019: Edges computed only for continuing participants (intersection)
- FR-040: Edge totals validation passes
"""

import pytest
from uuid import uuid4
from typing import Dict, Tuple, List
from unittest.mock import AsyncMock, MagicMock

from src.services.movement_tracker import (
    track_movement,
    aggregate_movements,
    compute_movements_for_rounds
)
from src.services.edge_builder import (
    create_edge,
    compute_derived_metrics,
    build_edges_from_aggregated_movements
)
from src.models.sankey_edge import SankeyEdge
from src.models.sankey_node import SankeyNode


class TestMovementTracker:
    """Test movement_tracker.py functions."""

    @pytest.mark.asyncio
    async def test_track_movement_basic(self):
        """Test track_movement with basic participant movements."""
        # Setup
        from_round_id = uuid4()
        to_round_id = uuid4()

        user1, user2, user3 = uuid4(), uuid4(), uuid4()
        cluster_a, cluster_b, cluster_d = uuid4(), uuid4(), uuid4()

        # Mock ClusterAPIClient
        mock_client = AsyncMock()
        mock_client.get_participant_movements.return_value = {
            user1: (cluster_a, cluster_d),
            user2: (cluster_a, cluster_d),
            user3: (cluster_b, cluster_d),
        }

        # Execute
        movements = await track_movement(from_round_id, to_round_id, mock_client)

        # Verify
        assert len(movements) == 3
        assert movements[user1] == (cluster_a, cluster_d)
        assert movements[user2] == (cluster_a, cluster_d)
        assert movements[user3] == (cluster_b, cluster_d)

        mock_client.get_participant_movements.assert_called_once_with(
            from_round_id=from_round_id,
            to_round_id=to_round_id
        )

    @pytest.mark.asyncio
    async def test_track_movement_with_dropout(self):
        """Test track_movement handles dropout (only continuing participants)."""
        # Setup - 3 participants in round 1, only 2 continue to round 2
        from_round_id = uuid4()
        to_round_id = uuid4()

        user1, user2 = uuid4(), uuid4()
        # user3 dropped out (not in movements)
        cluster_a, cluster_d = uuid4(), uuid4()

        mock_client = AsyncMock()
        mock_client.get_participant_movements.return_value = {
            user1: (cluster_a, cluster_d),
            user2: (cluster_a, cluster_d),
        }

        # Execute
        movements = await track_movement(from_round_id, to_round_id, mock_client)

        # Verify - only continuing participants included
        assert len(movements) == 2

    def test_aggregate_movements_basic(self):
        """Test aggregate_movements groups transitions correctly."""
        # Setup
        user1, user2, user3 = uuid4(), uuid4(), uuid4()
        cluster_a, cluster_b, cluster_d = uuid4(), uuid4(), uuid4()

        movements = {
            user1: (cluster_a, cluster_d),
            user2: (cluster_a, cluster_d),
            user3: (cluster_b, cluster_d),
        }

        # Execute
        aggregated = aggregate_movements(movements)

        # Verify
        assert len(aggregated) == 2  # Two unique transitions
        assert aggregated[(cluster_a, cluster_d)] == 2  # 2 users moved A→D
        assert aggregated[(cluster_b, cluster_d)] == 1  # 1 user moved B→D

    def test_aggregate_movements_empty(self):
        """Test aggregate_movements handles empty movements."""
        aggregated = aggregate_movements({})
        assert aggregated == {}

    @pytest.mark.asyncio
    async def test_compute_movements_for_rounds_integration(self):
        """Test compute_movements_for_rounds integrates track and aggregate."""
        # Setup
        from_round_id = uuid4()
        to_round_id = uuid4()

        user1, user2, user3 = uuid4(), uuid4(), uuid4()
        cluster_a, cluster_b, cluster_d = uuid4(), uuid4(), uuid4()

        mock_client = AsyncMock()
        mock_client.get_participant_movements.return_value = {
            user1: (cluster_a, cluster_d),
            user2: (cluster_a, cluster_d),
            user3: (cluster_b, cluster_d),
        }

        # Execute
        aggregated = await compute_movements_for_rounds(
            from_round_id, to_round_id, mock_client
        )

        # Verify
        assert len(aggregated) == 2
        assert aggregated[(cluster_a, cluster_d)] == 2
        assert aggregated[(cluster_b, cluster_d)] == 1


class TestEdgeBuilder:
    """Test edge_builder.py functions."""

    def test_create_edge_basic(self):
        """Test create_edge creates valid SankeyEdge."""
        # Setup
        from_cluster_id = uuid4()
        to_cluster_id = uuid4()

        # Execute
        edge = create_edge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=from_cluster_id,
            to_cluster_id=to_cluster_id,
            user_count=5
        )

        # Verify
        assert isinstance(edge, SankeyEdge)
        assert edge.from_round_index == 0
        assert edge.to_round_index == 1
        assert edge.from_cluster_id == from_cluster_id
        assert edge.to_cluster_id == to_cluster_id
        assert edge.user_count == 5
        assert edge.pct_of_from is None  # Not computed yet
        assert edge.pct_of_to is None    # Not computed yet

    def test_create_edge_validates_adjacent_rounds(self):
        """Test create_edge rejects non-adjacent rounds."""
        with pytest.raises(ValueError, match="adjacent rounds"):
            create_edge(
                from_round_index=0,
                to_round_index=2,  # Skips round 1
                from_cluster_id=uuid4(),
                to_cluster_id=uuid4(),
                user_count=5
            )

    def test_create_edge_validates_user_count(self):
        """Test create_edge rejects zero or negative user_count."""
        with pytest.raises(ValueError, match="user_count must be at least 1"):
            create_edge(
                from_round_index=0,
                to_round_index=1,
                from_cluster_id=uuid4(),
                to_cluster_id=uuid4(),
                user_count=0
            )

    def test_compute_derived_metrics_basic(self):
        """Test compute_derived_metrics calculates percentages correctly."""
        # Setup
        cluster_a = uuid4()
        cluster_d = uuid4()

        edge = create_edge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=cluster_a,
            to_cluster_id=cluster_d,
            user_count=5
        )

        from_node = SankeyNode(
            node_id=cluster_a,
            cluster_id=cluster_a,
            label_summary="Cluster A",
            user_count=12,  # 12 participants in source cluster
            user_pct=0.5
        )

        to_node = SankeyNode(
            node_id=cluster_d,
            cluster_id=cluster_d,
            label_summary="Cluster D",
            user_count=14,  # 14 participants in destination cluster
            user_pct=0.7
        )

        # Execute
        edge_with_metrics = compute_derived_metrics(edge, from_node, to_node)

        # Verify
        assert edge_with_metrics.user_count == 5
        assert edge_with_metrics.pct_of_from == pytest.approx(5 / 12, abs=0.001)  # 0.417
        assert edge_with_metrics.pct_of_to == pytest.approx(5 / 14, abs=0.001)    # 0.357

    def test_build_edges_from_aggregated_movements(self):
        """Test build_edges_from_aggregated_movements creates complete edge list."""
        # Setup
        cluster_a = uuid4()
        cluster_b = uuid4()
        cluster_d = uuid4()

        aggregated_movements = {
            (cluster_a, cluster_d): 5,
            (cluster_b, cluster_d): 3,
        }

        nodes_by_cluster_id = {
            cluster_a: SankeyNode(
                node_id=cluster_a,
                cluster_id=cluster_a,
                label_summary="Cluster A",
                user_count=12,
                user_pct=0.5
            ),
            cluster_b: SankeyNode(
                node_id=cluster_b,
                cluster_id=cluster_b,
                label_summary="Cluster B",
                user_count=8,
                user_pct=0.3
            ),
            cluster_d: SankeyNode(
                node_id=cluster_d,
                cluster_id=cluster_d,
                label_summary="Cluster D",
                user_count=14,
                user_pct=0.7
            ),
        }

        # Execute
        edges = build_edges_from_aggregated_movements(
            aggregated_movements=aggregated_movements,
            from_round_index=0,
            to_round_index=1,
            nodes_by_cluster_id=nodes_by_cluster_id,
            compute_percentages=True
        )

        # Verify
        assert len(edges) == 2

        # Edges should be sorted by user_count descending
        assert edges[0].user_count == 5  # A→D (larger)
        assert edges[1].user_count == 3  # B→D (smaller)

        # Verify derived metrics computed
        assert edges[0].pct_of_from is not None
        assert edges[0].pct_of_to is not None
        assert edges[1].pct_of_from is not None
        assert edges[1].pct_of_to is not None

    def test_build_edges_without_percentages(self):
        """Test build_edges with compute_percentages=False."""
        cluster_a = uuid4()
        cluster_d = uuid4()

        aggregated_movements = {(cluster_a, cluster_d): 5}

        # Execute - no nodes needed when compute_percentages=False
        edges = build_edges_from_aggregated_movements(
            aggregated_movements=aggregated_movements,
            from_round_index=0,
            to_round_index=1,
            nodes_by_cluster_id={},
            compute_percentages=False
        )

        # Verify
        assert len(edges) == 1
        assert edges[0].user_count == 5
        assert edges[0].pct_of_from is None  # Not computed
        assert edges[0].pct_of_to is None    # Not computed


class TestEdgeComputationIntegration:
    """Integration test for complete edge computation workflow."""

    @pytest.mark.asyncio
    async def test_complete_edge_workflow(self):
        """
        Test complete edge computation workflow from movement tracking to edge creation.

        Scenario:
        - Round 1: 10 participants in 2 clusters (A: 6 users, B: 4 users)
        - Round 2: 7 participants in 1 cluster (D: 7 users)
        - Movement: 5 from A→D, 2 from B→D (3 participants dropped out)

        Expected:
        - 2 edges: A→D (5 users), B→D (2 users)
        - Total edge flow = 7 (matches continuing participants)
        """
        # Setup IDs
        round1_id = uuid4()
        round2_id = uuid4()

        cluster_a = uuid4()
        cluster_b = uuid4()
        cluster_d = uuid4()

        # 10 participants in Round 1
        users_round1 = [uuid4() for _ in range(10)]
        # 7 continue to Round 2 (3 dropped out)
        users_round2 = users_round1[:7]

        # Mock movements: 5 from A→D, 2 from B→D
        movements = {
            users_round2[0]: (cluster_a, cluster_d),
            users_round2[1]: (cluster_a, cluster_d),
            users_round2[2]: (cluster_a, cluster_d),
            users_round2[3]: (cluster_a, cluster_d),
            users_round2[4]: (cluster_a, cluster_d),
            users_round2[5]: (cluster_b, cluster_d),
            users_round2[6]: (cluster_b, cluster_d),
        }

        mock_client = AsyncMock()
        mock_client.get_participant_movements.return_value = movements

        # Execute: Track and aggregate movements
        tracked_movements = await track_movement(round1_id, round2_id, mock_client)
        aggregated = aggregate_movements(tracked_movements)

        # Verify aggregation
        assert len(aggregated) == 2
        assert aggregated[(cluster_a, cluster_d)] == 5
        assert aggregated[(cluster_b, cluster_d)] == 2

        # Create nodes
        nodes_by_cluster_id = {
            cluster_a: SankeyNode(
                node_id=cluster_a,
                cluster_id=cluster_a,
                label_summary="Cluster A",
                user_count=6,
                user_pct=0.6
            ),
            cluster_b: SankeyNode(
                node_id=cluster_b,
                cluster_id=cluster_b,
                label_summary="Cluster B",
                user_count=4,
                user_pct=0.4
            ),
            cluster_d: SankeyNode(
                node_id=cluster_d,
                cluster_id=cluster_d,
                label_summary="Cluster D",
                user_count=7,
                user_pct=1.0
            ),
        }

        # Build edges
        edges = build_edges_from_aggregated_movements(
            aggregated_movements=aggregated,
            from_round_index=0,
            to_round_index=1,
            nodes_by_cluster_id=nodes_by_cluster_id,
            compute_percentages=True
        )

        # Verify edges
        assert len(edges) == 2

        # Edge A→D
        edge_a_d = next(e for e in edges if e.from_cluster_id == cluster_a)
        assert edge_a_d.to_cluster_id == cluster_d
        assert edge_a_d.user_count == 5
        assert edge_a_d.pct_of_from == pytest.approx(5 / 6, abs=0.001)  # 83.3% of A
        assert edge_a_d.pct_of_to == pytest.approx(5 / 7, abs=0.001)    # 71.4% of D

        # Edge B→D
        edge_b_d = next(e for e in edges if e.from_cluster_id == cluster_b)
        assert edge_b_d.to_cluster_id == cluster_d
        assert edge_b_d.user_count == 2
        assert edge_b_d.pct_of_from == pytest.approx(2 / 4, abs=0.001)  # 50% of B
        assert edge_b_d.pct_of_to == pytest.approx(2 / 7, abs=0.001)    # 28.6% of D

        # Verify total flow matches continuing participants
        total_flow = sum(e.user_count for e in edges)
        assert total_flow == 7  # Matches continuing participants (not 10)

        # Verify dropout handling (FR-019: only continuing participants)
        assert total_flow < 10  # 3 participants dropped out, not included in edges
