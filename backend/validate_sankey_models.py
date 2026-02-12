"""
Manual validation script for Sankey Pydantic models.

Runs basic validation tests without pytest dependency.
"""

from uuid import uuid4
from datetime import datetime
import sys

# Add src to path
sys.path.insert(0, 'src')

from models.sankey_node import SankeyNode
from models.sankey_edge import SankeyEdge
from models.sankey_column import SankeyColumn
from models.sankey_graph import SankeyGraph

def test_sankey_node():
    """Test SankeyNode validation."""
    print("Testing SankeyNode...")

    # Valid node
    node = SankeyNode(
        node_id=uuid4(),
        cluster_id=uuid4(),
        label_summary="Climate action is critical",
        user_count=10,
        user_pct=0.5,
        display_group_id=None
    )
    print(f"  ✓ Valid node created: {node.user_count} users, {node.user_pct} pct")

    # Test is_singleton
    singleton = SankeyNode(
        node_id=uuid4(),
        cluster_id=uuid4(),
        label_summary="Outlier",
        user_count=1,
        user_pct=0.05
    )
    assert singleton.is_singleton(), "Singleton detection failed"
    print(f"  ✓ Singleton detection works")

    # Invalid user_count
    try:
        SankeyNode(
            node_id=uuid4(),
            cluster_id=uuid4(),
            label_summary="Test",
            user_count=0,  # Invalid
            user_pct=0.5
        )
        print("  ✗ FAILED: Should reject user_count=0")
        return False
    except ValueError:
        print("  ✓ Correctly rejects user_count=0")

    # Invalid user_pct
    try:
        SankeyNode(
            node_id=uuid4(),
            cluster_id=uuid4(),
            label_summary="Test",
            user_count=5,
            user_pct=0.0  # Invalid
        )
        print("  ✗ FAILED: Should reject user_pct=0")
        return False
    except ValueError:
        print("  ✓ Correctly rejects user_pct=0")

    return True


def test_sankey_edge():
    """Test SankeyEdge validation."""
    print("\nTesting SankeyEdge...")

    # Valid edge
    edge = SankeyEdge(
        from_round_index=0,
        to_round_index=1,
        from_cluster_id=uuid4(),
        to_cluster_id=uuid4(),
        user_count=5
    )
    print(f"  ✓ Valid edge created: round {edge.from_round_index} → {edge.to_round_index}")

    # Test adjacency validation
    try:
        SankeyEdge(
            from_round_index=0,
            to_round_index=2,  # Skip round 1 - invalid
            from_cluster_id=uuid4(),
            to_cluster_id=uuid4(),
            user_count=5
        )
        print("  ✗ FAILED: Should reject non-adjacent rounds")
        return False
    except ValueError:
        print("  ✓ Correctly rejects non-adjacent rounds")

    # Test self-loop detection
    cluster_id = uuid4()
    self_loop = SankeyEdge(
        from_round_index=0,
        to_round_index=1,
        from_cluster_id=cluster_id,
        to_cluster_id=cluster_id,
        user_count=5
    )
    assert self_loop.is_self_loop(), "Self-loop detection failed"
    print("  ✓ Self-loop detection works")

    return True


def test_sankey_column():
    """Test SankeyColumn validation."""
    print("\nTesting SankeyColumn...")

    # Valid column
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
    print(f"  ✓ Valid column created: {len(column.nodes)} nodes, {column.total_participants} participants")

    # Test percentage sum validation
    try:
        bad_nodes = [
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
        SankeyColumn(
            round_index=0,
            nodes=bad_nodes,
            total_participants=20
        )
        print("  ✗ FAILED: Should reject percentage sum != 1.0")
        return False
    except ValueError:
        print("  ✓ Correctly validates percentage sum = 1.0")

    # Test user_count sum validation
    try:
        bad_nodes = [
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
        SankeyColumn(
            round_index=0,
            nodes=bad_nodes,
            total_participants=20
        )
        print("  ✗ FAILED: Should reject user_count sum mismatch")
        return False
    except ValueError:
        print("  ✓ Correctly validates user_count sum = total_participants")

    # Test singleton counting
    singleton_nodes = [
        SankeyNode(
            node_id=uuid4(),
            cluster_id=uuid4(),
            label_summary="A",
            user_count=1,
            user_pct=0.05
        ),
        SankeyNode(
            node_id=uuid4(),
            cluster_id=uuid4(),
            label_summary="B",
            user_count=1,
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
    col = SankeyColumn(
        round_index=0,
        nodes=singleton_nodes,
        total_participants=20
    )
    assert col.get_singleton_count() == 2, "Singleton counting failed"
    print("  ✓ Singleton counting works")

    return True


def test_sankey_graph():
    """Test SankeyGraph validation."""
    print("\nTesting SankeyGraph...")

    # Valid single-round graph
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
    print(f"  ✓ Valid single-round graph created: {len(graph.columns)} columns, {len(graph.edges)} edges")

    # Test columns must match rounds
    try:
        SankeyGraph(
            discussion_id=uuid4(),
            rounds=[uuid4(), uuid4()],  # 2 rounds
            columns=[column],  # 1 column
            edges=[]
        )
        print("  ✗ FAILED: Should reject columns != rounds")
        return False
    except ValueError:
        print("  ✓ Correctly validates len(columns) = len(rounds)")

    # Test single-round no edges
    try:
        edge = SankeyEdge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=uuid4(),
            to_cluster_id=uuid4(),
            user_count=5
        )
        SankeyGraph(
            discussion_id=uuid4(),
            rounds=[uuid4()],
            columns=[column],
            edges=[edge]  # Invalid for single-round
        )
        print("  ✗ FAILED: Should reject edges in single-round graph")
        return False
    except ValueError:
        print("  ✓ Correctly rejects edges in single-round graph")

    # Test dropout rate calculation
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
            user_count=15,
            user_pct=1.0
        )
    ]

    column_0 = SankeyColumn(round_index=0, nodes=nodes_0, total_participants=20)
    column_1 = SankeyColumn(round_index=1, nodes=nodes_1, total_participants=15)

    multi_graph = SankeyGraph(
        discussion_id=uuid4(),
        rounds=[uuid4(), uuid4()],
        columns=[column_0, column_1],
        edges=[]
    )

    dropout_rate = multi_graph.get_dropout_rate()
    assert dropout_rate == 0.25, f"Dropout rate calculation failed: expected 0.25, got {dropout_rate}"
    print(f"  ✓ Dropout rate calculation works: {dropout_rate}")

    return True


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Sankey Model Validation Tests")
    print("=" * 60)

    results = []

    results.append(("SankeyNode", test_sankey_node()))
    results.append(("SankeyEdge", test_sankey_edge()))
    results.append(("SankeyColumn", test_sankey_column()))
    results.append(("SankeyGraph", test_sankey_graph()))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{name:20s} {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All validation tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
