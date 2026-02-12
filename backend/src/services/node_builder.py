"""
Node Builder Service - Converts Spec 004 clusters to Sankey nodes

This module provides functions for converting cluster data from Spec 004 into
SankeyNode entities and assembling them into SankeyColumn structures.

Constitutional Compliance:
- Semantic Accuracy: Every cluster preserved as a node (100% coverage)
- Intent Fidelity: Node labels use actual medoid summaries
- Representation Not Adjudication: No filtering or ranking of clusters
"""

from typing import List, Dict
from uuid import UUID
import logging

from ..models.cluster import Cluster
from ..models.sankey_node import SankeyNode
from ..models.sankey_column import SankeyColumn

logger = logging.getLogger(__name__)


async def create_node_from_cluster(
    cluster: Cluster,
    total_round_participants: int,
    medoid_summary: str,
    display_group_id: UUID | None = None
) -> SankeyNode:
    """
    Convert a Spec 004 cluster to a SankeyNode entity.

    Args:
        cluster: Cluster entity from Spec 004
        total_round_participants: Total participants in this round (for user_pct calculation)
        medoid_summary: Medoid summary text from approved summary
        display_group_id: Optional alignment group ID for visual continuity

    Returns:
        SankeyNode with computed user_pct and mapped fields

    Raises:
        ValueError: If cluster has invalid data (user_count = 0, etc.)

    Validates:
        FR-014: Node creation from cluster data
        FR-015: Percentage computation per round

    Constitutional Compliance:
        - Intent Fidelity: Uses actual medoid summary text
        - Semantic Accuracy: Every cluster becomes a node (no filtering)
    """
    if not cluster:
        raise ValueError("Cluster cannot be None")

    if total_round_participants <= 0:
        raise ValueError(f"total_round_participants must be > 0, got {total_round_participants}")

    # Get member count from cluster
    # Note: cluster.member_count comes from Spec 004 clusters table
    user_count = len(cluster.members) if hasattr(cluster, 'members') else getattr(cluster, 'member_count', 0)

    if user_count <= 0:
        raise ValueError(f"Cluster {cluster.cluster_id} has no members (user_count = {user_count})")

    # Compute user_pct = user_count / total_round_participants
    user_pct = user_count / total_round_participants

    # Create SankeyNode
    node = SankeyNode(
        node_id=cluster.cluster_id,  # Use cluster_id as node_id for traceability
        cluster_id=cluster.cluster_id,
        label_summary=medoid_summary,
        user_count=user_count,
        user_pct=user_pct,
        display_group_id=display_group_id
    )

    logger.debug(
        f"Created node from cluster {cluster.cluster_id}: "
        f"{user_count} users ({user_pct:.2%}), label: {medoid_summary[:50]}..."
    )

    return node


async def build_column(
    round_index: int,
    round_id: UUID,
    clusters: List[Cluster],
    medoid_summaries: Dict[UUID, str],
    alignment_metadata: Dict[UUID, UUID] | None = None
) -> SankeyColumn:
    """
    Build a SankeyColumn from all clusters in a round.

    Args:
        round_index: Round number (0-indexed, 0 = first round)
        round_id: Round UUID from Spec 001
        clusters: List of all clusters in this round
        medoid_summaries: Dict mapping cluster_id to medoid summary text
        alignment_metadata: Optional dict mapping cluster_id to display_group_id

    Returns:
        SankeyColumn with all nodes, validated for percentage sum and coverage

    Raises:
        ValueError: If no clusters, or validation fails

    Validates:
        SC-003: 100% participant coverage
        SC-005: Percentage sum = 1.0 ± 0.0001
        FR-016: Every participant assigned to exactly one cluster

    Constitutional Compliance:
        - Semantic Accuracy: All clusters included as nodes
        - Intent Fidelity: Uses approved medoid summaries
    """
    if not clusters:
        raise ValueError(f"Cannot build column for round {round_index}: no clusters provided")

    if not medoid_summaries:
        raise ValueError(f"Cannot build column for round {round_index}: no medoid summaries provided")

    # Compute total participants in this round
    total_participants = sum(
        len(cluster.members) if hasattr(cluster, 'members') else getattr(cluster, 'member_count', 0)
        for cluster in clusters
    )

    if total_participants <= 0:
        raise ValueError(
            f"Cannot build column for round {round_index}: total_participants = {total_participants}"
        )

    logger.info(
        f"Building column for round {round_index}: {len(clusters)} clusters, "
        f"{total_participants} participants"
    )

    # Create nodes from clusters
    nodes: List[SankeyNode] = []
    for cluster in clusters:
        # Get medoid summary
        medoid_summary = medoid_summaries.get(cluster.cluster_id)
        if not medoid_summary:
            logger.warning(
                f"No medoid summary found for cluster {cluster.cluster_id}, using placeholder"
            )
            medoid_summary = f"[Cluster {cluster.cluster_id}]"

        # Get alignment metadata if available
        display_group_id = None
        if alignment_metadata:
            display_group_id = alignment_metadata.get(cluster.cluster_id)

        # Create node
        node = await create_node_from_cluster(
            cluster=cluster,
            total_round_participants=total_participants,
            medoid_summary=medoid_summary,
            display_group_id=display_group_id
        )
        nodes.append(node)

    # Sort nodes by user_count descending (largest clusters first)
    nodes.sort(key=lambda n: n.user_count, reverse=True)

    # Create column (this will validate percentage sum and coverage)
    column = SankeyColumn(
        round_index=round_index,
        nodes=nodes,
        total_participants=total_participants
    )

    logger.info(
        f"Column for round {round_index} built successfully: "
        f"{len(nodes)} nodes, {total_participants} participants, "
        f"percentage sum = {sum(n.user_pct for n in nodes):.6f}"
    )

    # Log cluster distribution for monitoring
    singleton_count = column.get_singleton_count()
    minority_count = column.get_minority_count()
    largest_pct = column.get_largest_cluster_pct()

    logger.info(
        f"Round {round_index} distribution: "
        f"{singleton_count} singletons, {minority_count} minorities (<5%), "
        f"largest cluster = {largest_pct:.1%}"
    )

    return column


def get_medoid_summaries_for_clusters(
    clusters: List[Cluster]
) -> Dict[UUID, str]:
    """
    Extract medoid summary text for each cluster.

    Args:
        clusters: List of clusters with medoid_summary_id references

    Returns:
        Dict mapping cluster_id to medoid summary text

    Note:
        This function assumes cluster.medoid_summary relationship is loaded.
        In practice, you may need to join with summaries table.
    """
    medoid_summaries = {}

    for cluster in clusters:
        # Get medoid summary text
        # Check for label_summary (ThoughtSpace) first
        if hasattr(cluster, 'label_summary') and cluster.label_summary:
            summary_text = cluster.label_summary
        # Then check for medoid_summary relationship (Cluster)
        elif hasattr(cluster, 'medoid_summary') and cluster.medoid_summary:
            summary_text = cluster.medoid_summary.summary_text
        else:
            # Fallback: use placeholder if medoid not available
            logger.warning(f"Cluster {cluster.cluster_id} has no medoid_summary or label_summary, using placeholder")
            summary_text = f"[Cluster summary unavailable]"

        medoid_summaries[cluster.cluster_id] = summary_text

    return medoid_summaries


async def build_columns_for_discussion(
    discussion_id: UUID,
    rounds: List[UUID],
    clusters_by_round: Dict[UUID, List[Cluster]],
    alignment_metadata: Dict[UUID, UUID] | None = None
) -> List[SankeyColumn]:
    """
    Build all columns for a discussion from cluster data.

    Args:
        discussion_id: Discussion UUID
        rounds: List of round UUIDs in temporal order
        clusters_by_round: Dict mapping round_id to list of clusters
        alignment_metadata: Optional dict mapping cluster_id to display_group_id

    Returns:
        List of SankeyColumn entities, ordered by round_index

    Raises:
        ValueError: If any round has no clusters or validation fails

    Validates:
        FR-013: Every round has at least one cluster
        SC-007: Columns in sequential order (0, 1, 2, ...)
    """
    if not rounds:
        raise ValueError(f"Cannot build columns for discussion {discussion_id}: no rounds")

    logger.info(
        f"Building columns for discussion {discussion_id}: {len(rounds)} rounds"
    )

    columns: List[SankeyColumn] = []

    for round_index, round_id in enumerate(rounds):
        # Get clusters for this round
        clusters = clusters_by_round.get(round_id)
        if not clusters:
            raise ValueError(
                f"No clusters found for round {round_id} (index {round_index}) "
                f"in discussion {discussion_id}"
            )

        # Get medoid summaries for clusters
        medoid_summaries = get_medoid_summaries_for_clusters(clusters)

        # Build column
        column = await build_column(
            round_index=round_index,
            round_id=round_id,
            clusters=clusters,
            medoid_summaries=medoid_summaries,
            alignment_metadata=alignment_metadata
        )

        columns.append(column)

    logger.info(
        f"All columns built for discussion {discussion_id}: {len(columns)} columns"
    )

    # Validate column ordering
    for i, column in enumerate(columns):
        if column.round_index != i:
            raise ValueError(
                f"Column ordering violation: Expected round_index {i}, "
                f"got {column.round_index} at position {i}"
            )

    return columns
