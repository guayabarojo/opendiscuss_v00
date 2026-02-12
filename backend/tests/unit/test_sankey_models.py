"""
Unit Tests for Sankey Pydantic Models

Tests basic validation for SankeyNode, SankeyEdge, SankeyColumn, and SankeyGraph.
"""

import pytest
from uuid import uuid4
from datetime import datetime

from src.models.sankey_node import SankeyNode
from src.models.sankey_edge import SankeyEdge
from src.models.sankey_column import SankeyColumn
from src.models.sankey_graph import SankeyGraph


class TestSankeyNode:
    """Test SankeyNode validation."""

    def test_valid_node_creation(self):
        """Test creating a valid node."""
        node = SankeyNode(
            node_id=uuid4(),
            cluster_id=uuid4(),
            label_summary="Climate action is critical",
            user_count=10,
            user_pct=0.5,
            display_group_id=None
        )
        assert node.user_count == 10
        assert node.user_pct == 0.5
        assert node.display_group_id is None

    def test_user_count_must_be_positive(self):
        """Test that user_count >= 1."""
        with pytest.raises(ValueError, match="user_count"):
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Test",
                user_count=0,  # Invalid
                user_pct=0.5
            )

    def test_user_pct_must_be_positive(self):
        """Test that user_pct > 0.0."""
        with pytest.raises(ValueError, match="user_pct"):
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Test",
                user_count=5,
                user_pct=0.0  # Invalid
            )

    def test_user_pct_must_not_exceed_one(self):
        """Test that user_pct <= 1.0."""
        with pytest.raises(ValueError, match="user_pct"):
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Test",
                user_count=5,
                user_pct=1.5  # Invalid
            )

    def test_is_singleton(self):
        """Test is_singleton detection."""
        singleton = SankeyNode(
            node_id=uuid4(),
            cluster_id=uuid4(),
            label_summary="Outlier opinion",
            user_count=1,
            user_pct=0.05
        )
        assert singleton.is_singleton()

        non_singleton = SankeyNode(
            node_id=uuid4(),
            cluster_id=uuid4(),
            label_summary="Majority opinion",
            user_count=10,
            user_pct=0.5
        )
        assert not non_singleton.is_singleton()


class TestSankeyEdge:
    """Test SankeyEdge validation."""

    def test_valid_edge_creation(self):
        """Test creating a valid edge."""
        edge = SankeyEdge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=uuid4(),
            to_cluster_id=uuid4(),
            user_count=5,
            pct_of_from=0.5,
            pct_of_to=0.3
        )
        assert edge.from_round_index == 0
        assert edge.to_round_index == 1
        assert edge.user_count == 5

    def test_adjacency_validation(self):
        """Test that edges must connect adjacent rounds."""
        with pytest.raises(ValueError, match="adjacent"):
            SankeyEdge(
                from_round_index=0,
                to_round_index=2,  # Skip round 1 - invalid
                from_cluster_id=uuid4(),
                to_cluster_id=uuid4(),
                user_count=5
            )

    def test_user_count_must_be_positive(self):
        """Test that user_count >= 1."""
        with pytest.raises(ValueError, match="user_count"):
            SankeyEdge(
                from_round_index=0,
                to_round_index=1,
                from_cluster_id=uuid4(),
                to_cluster_id=uuid4(),
                user_count=0  # Invalid
            )

    def test_is_self_loop(self):
        """Test self-loop detection."""
        cluster_id = uuid4()
        self_loop = SankeyEdge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=cluster_id,
            to_cluster_id=cluster_id,  # Same cluster
            user_count=5
        )
        assert self_loop.is_self_loop()

        normal_edge = SankeyEdge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=uuid4(),
            to_cluster_id=uuid4(),  # Different clusters
            user_count=5
        )
        assert not normal_edge.is_self_loop()


class TestSankeyColumn:
    """Test SankeyColumn validation."""

    def test_valid_column_creation(self):
        """Test creating a valid column."""
        nodes = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Climate action",
                user_count=12,
                user_pct=0.6
            ),
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Economic growth",
                user_count=8,
                user_pct=0.4
            )
        ]
        column = SankeyColumn(
            round_index=0,
            nodes=nodes,
            total_participants=20
        )
        assert column.round_index == 0
        assert len(column.nodes) == 2
        assert column.total_participants == 20

    def test_percentage_sum_validation(self):
        """Test that sum of node user_pct == 1.0 within tolerance."""
        nodes = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="A",
                user_count=10,
                user_pct=0.5
            ),
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="B",
                user_count=10,
                user_pct=0.4  # Sum = 0.9, not 1.0
            )
        ]
        with pytest.raises(ValueError, match="must equal 1.0"):
            SankeyColumn(
                round_index=0,
                nodes=nodes,
                total_participants=20
            )

    def test_user_count_sum_validation(self):
        """Test that sum of node user_count == total_participants."""
        nodes = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="A",
                user_count=10,
                user_pct=0.6
            ),
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="B",
                user_count=8,
                user_pct=0.4
            )
        ]
        # Sum = 18, but total_participants = 20
        with pytest.raises(ValueError, match="must equal total_participants"):
            SankeyColumn(
                round_index=0,
                nodes=nodes,
                total_participants=20
            )

    def test_get_singleton_count(self):
        """Test singleton counting."""
        nodes = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="A",
                user_count=1,  # Singleton
                user_pct=0.05
            ),
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="B",
                user_count=1,  # Singleton
                user_pct=0.05
            ),
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="C",
                user_count=18,
                user_pct=0.9
            )
        ]
        column = SankeyColumn(
            round_index=0,
            nodes=nodes,
            total_participants=20
        )
        assert column.get_singleton_count() == 2


class TestSankeyGraph:
    """Test SankeyGraph validation."""

    def test_valid_graph_creation(self):
        """Test creating a valid single-round graph."""
        discussion_id = uuid4()
        round_id = uuid4()

        nodes = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Climate action",
                user_count=20,
                user_pct=1.0
            )
        ]
        column = SankeyColumn(
            round_index=0,
            nodes=nodes,
            total_participants=20
        )

        graph = SankeyGraph(
            discussion_id=discussion_id,
            rounds=[round_id],
            columns=[column],
            edges=[],
            created_at=datetime.utcnow()
        )
        assert graph.discussion_id == discussion_id
        assert len(graph.rounds) == 1
        assert len(graph.columns) == 1
        assert len(graph.edges) == 0

    def test_columns_must_match_rounds(self):
        """Test that len(columns) == len(rounds)."""
        round_id_1 = uuid4()
        round_id_2 = uuid4()

        nodes = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Test",
                user_count=20,
                user_pct=1.0
            )
        ]
        column = SankeyColumn(
            round_index=0,
            nodes=nodes,
            total_participants=20
        )

        # 2 rounds but only 1 column
        with pytest.raises(ValueError, match="must equal"):
            SankeyGraph(
                discussion_id=uuid4(),
                rounds=[round_id_1, round_id_2],
                columns=[column],
                edges=[]
            )

    def test_column_ordering_validation(self):
        """Test that columns must be ordered by round_index."""
        nodes_0 = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Test",
                user_count=20,
                user_pct=1.0
            )
        ]
        nodes_1 = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Test",
                user_count=20,
                user_pct=1.0
            )
        ]

        # Create columns with wrong ordering
        column_0 = SankeyColumn(round_index=1, nodes=nodes_0, total_participants=20)  # Wrong
        column_1 = SankeyColumn(round_index=0, nodes=nodes_1, total_participants=20)  # Wrong

        with pytest.raises(ValueError, match="round_index"):
            SankeyGraph(
                discussion_id=uuid4(),
                rounds=[uuid4(), uuid4()],
                columns=[column_0, column_1],  # Wrong order
                edges=[]
            )

    def test_single_round_no_edges(self):
        """Test that single-round graphs cannot have edges."""
        nodes = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Test",
                user_count=20,
                user_pct=1.0
            )
        ]
        column = SankeyColumn(
            round_index=0,
            nodes=nodes,
            total_participants=20
        )

        # Create an invalid edge for single-round
        edge = SankeyEdge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=uuid4(),
            to_cluster_id=uuid4(),
            user_count=5
        )

        with pytest.raises(ValueError, match="Single-round.*cannot have edges"):
            SankeyGraph(
                discussion_id=uuid4(),
                rounds=[uuid4()],
                columns=[column],
                edges=[edge]  # Invalid for single-round
            )

    def test_get_dropout_rate(self):
        """Test dropout rate calculation."""
        # Create 2-round graph with dropout
        nodes_0 = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Test",
                user_count=20,
                user_pct=1.0
            )
        ]
        nodes_1 = [
            SankeyNode(
                node_id=uuid4(),
                cluster_id=uuid4(),
                label_summary="Test",
                user_count=15,  # 5 dropped out
                user_pct=1.0
            )
        ]

        column_0 = SankeyColumn(round_index=0, nodes=nodes_0, total_participants=20)
        column_1 = SankeyColumn(round_index=1, nodes=nodes_1, total_participants=15)

        graph = SankeyGraph(
            discussion_id=uuid4(),
            rounds=[uuid4(), uuid4()],
            columns=[column_0, column_1],
            edges=[]
        )

        dropout_rate = graph.get_dropout_rate()
        assert dropout_rate == 0.25  # 5/20 = 0.25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
