"""
Edge Builder Service - Converts aggregated movements to SankeyEdge entities

This module provides functions for creating SankeyEdge entities from aggregated
participant movements, computing derived metrics (pct_of_from, pct_of_to), and
validating edge construction.

Constitutional Compliance:
- Temporal Transparency: Edges reflect actual participant movement
- Semantic Accuracy: Edge widths proportional to actual transitions
- Representation Not Adjudication: No filtering or ranking of edges
"""

from typing import Dict, List, Tuple, Optional
from uuid import UUID
import logging

from ..models.sankey_edge import SankeyEdge
from ..models.sankey_node import SankeyNode

logger = logging.getLogger(__name__)


def create_edge(
    from_round_index: int,
    to_round_index: int,
    from_cluster_id: UUID,
    to_cluster_id: UUID,
    user_count: int
) -> SankeyEdge:
    """
    Create SankeyEdge entity from aggregated movement data.

    Args:
        from_round_index: Source round index (0-indexed, 0 = first round)
        to_round_index: Destination round index (must be from_round_index + 1)
        from_cluster_id: Source cluster UUID
        to_cluster_id: Destination cluster UUID
        user_count: Number of participants who made this transition

    Returns:
        SankeyEdge entity with user_count (pct_of_from and pct_of_to are None)

    Raises:
        ValueError: If parameters are invalid (e.g., user_count < 1, non-adjacent rounds)

    Validates:
        FR-017: Edge connects adjacent rounds only
        FR-018: Edge user_count >= 1 (no zero-width edges)
        SC-002: Edge accuracy (reflects actual movement)

    Constitutional Compliance:
        - Temporal Transparency: Edge represents actual participant transition
        - Semantic Accuracy: user_count reflects real behavior
        - Representation Not Adjudication: All transitions preserved (no filtering)

    Example:
        edge = create_edge(
            from_round_index=0,
            to_round_index=1,
            from_cluster_id=cluster_a_id,
            to_cluster_id=cluster_d_id,
            user_count=5
        )
    """
    if user_count < 1:
        raise ValueError(f"user_count must be at least 1, got {user_count}")

    if to_round_index != from_round_index + 1:
        raise ValueError(
            f"Edge must connect adjacent rounds: to_round_index ({to_round_index}) "
            f"must equal from_round_index ({from_round_index}) + 1"
        )

    # Create edge without derived metrics (pct_of_from, pct_of_to)
    # These will be computed separately by compute_derived_metrics if needed
    edge = SankeyEdge(
        from_round_index=from_round_index,
        to_round_index=to_round_index,
        from_cluster_id=from_cluster_id,
        to_cluster_id=to_cluster_id,
        user_count=user_count,
        pct_of_from=None,
        pct_of_to=None
    )

    logger.debug(
        f"Created edge: Round {from_round_index} → {to_round_index}, "
        f"Cluster {from_cluster_id} → {to_cluster_id}, "
        f"{user_count} participants"
    )

    return edge


def compute_derived_metrics(
    edge: SankeyEdge,
    from_node: SankeyNode,
    to_node: SankeyNode
) -> SankeyEdge:
    """
    Calculate pct_of_from and pct_of_to for an edge.

    These metrics are optional (FR-028, FR-029) and provide additional context:
    - pct_of_from: What percentage of the source cluster moved to destination?
    - pct_of_to: What percentage of the destination cluster came from source?

    Args:
        edge: SankeyEdge entity (will be modified with derived metrics)
        from_node: Source SankeyNode (provides user_count for denominator)
        to_node: Destination SankeyNode (provides user_count for denominator)

    Returns:
        SankeyEdge with pct_of_from and pct_of_to computed

    Raises:
        ValueError: If node user_counts are invalid (< 1)

    Validates:
        FR-028: pct_of_from = edge.user_count / from_node.user_count
        FR-029: pct_of_to = edge.user_count / to_node.user_count

    Constitutional Compliance:
        - Semantic Accuracy: Percentages computed from actual counts
        - Temporal Transparency: Per-round normalization (no cross-round manipulation)

    Example:
        edge = create_edge(0, 1, cluster_a, cluster_d, 5)
        from_node = SankeyNode(..., user_count=12)  # Cluster A has 12 participants
        to_node = SankeyNode(..., user_count=14)    # Cluster D has 14 participants
        edge_with_metrics = compute_derived_metrics(edge, from_node, to_node)
        # edge.pct_of_from = 5/12 = 0.417 (41.7% of A moved to D)
        # edge.pct_of_to = 5/14 = 0.357 (35.7% of D came from A)
    """
    if from_node.user_count < 1:
        raise ValueError(
            f"from_node.user_count must be at least 1, got {from_node.user_count}"
        )

    if to_node.user_count < 1:
        raise ValueError(
            f"to_node.user_count must be at least 1, got {to_node.user_count}"
        )

    # Compute pct_of_from (what % of source cluster moved to destination?)
    pct_of_from = edge.user_count / from_node.user_count

    # Compute pct_of_to (what % of destination cluster came from source?)
    pct_of_to = edge.user_count / to_node.user_count

    # Create new edge with derived metrics
    # Use model_copy to create a new instance with updated fields
    edge_with_metrics = edge.model_copy(
        update={
            "pct_of_from": pct_of_from,
            "pct_of_to": pct_of_to
        }
    )

    logger.debug(
        f"Computed derived metrics for edge {from_node.cluster_id} → {to_node.cluster_id}: "
        f"pct_of_from={pct_of_from:.3f}, pct_of_to={pct_of_to:.3f}"
    )

    return edge_with_metrics


def build_edges_from_aggregated_movements(
    aggregated_movements: Dict[Tuple[UUID, UUID], int],
    from_round_index: int,
    to_round_index: int,
    nodes_by_cluster_id: Dict[UUID, SankeyNode],
    compute_percentages: bool = True
) -> List[SankeyEdge]:
    """
    Build complete list of SankeyEdge entities from aggregated movements.

    This is a convenience function that creates edges and optionally computes
    derived metrics in a single operation.

    Args:
        aggregated_movements: Dict mapping (from_cluster_id, to_cluster_id) to user_count
        from_round_index: Source round index
        to_round_index: Destination round index
        nodes_by_cluster_id: Dict mapping cluster_id to SankeyNode (for derived metrics)
        compute_percentages: Whether to compute pct_of_from and pct_of_to (default: True)

    Returns:
        List of SankeyEdge entities with user_count and optional derived metrics

    Raises:
        ValueError: If cluster_id not found in nodes_by_cluster_id (when compute_percentages=True)

    Example:
        aggregated = {(cluster_a, cluster_d): 5, (cluster_b, cluster_d): 3}
        nodes = {cluster_a: node_a, cluster_b: node_b, cluster_d: node_d}
        edges = build_edges_from_aggregated_movements(
            aggregated, 0, 1, nodes, compute_percentages=True
        )
    """
    if not aggregated_movements:
        logger.debug("No aggregated movements provided, returning empty edge list")
        return []

    edges: List[SankeyEdge] = []

    for (from_cluster_id, to_cluster_id), user_count in aggregated_movements.items():
        # Create base edge
        edge = create_edge(
            from_round_index=from_round_index,
            to_round_index=to_round_index,
            from_cluster_id=from_cluster_id,
            to_cluster_id=to_cluster_id,
            user_count=user_count
        )

        # Compute derived metrics if requested
        if compute_percentages:
            from_node = nodes_by_cluster_id.get(from_cluster_id)
            to_node = nodes_by_cluster_id.get(to_cluster_id)

            if not from_node:
                raise ValueError(
                    f"Source cluster {from_cluster_id} not found in nodes_by_cluster_id"
                )

            if not to_node:
                raise ValueError(
                    f"Destination cluster {to_cluster_id} not found in nodes_by_cluster_id"
                )

            edge = compute_derived_metrics(edge, from_node, to_node)

        edges.append(edge)

    # Sort edges by user_count descending (largest flows first)
    edges.sort(key=lambda e: e.user_count, reverse=True)

    logger.info(
        f"Built {len(edges)} edges from round {from_round_index} to {to_round_index}, "
        f"total flow = {sum(e.user_count for e in edges)} participants"
    )

    # Log edge distribution for monitoring
    if edges:
        edge_counts = [e.user_count for e in edges]
        logger.debug(
            f"Edge distribution: largest={max(edge_counts)}, "
            f"smallest={min(edge_counts)}, "
            f"mean={sum(edge_counts) / len(edge_counts):.1f}"
        )

    return edges
