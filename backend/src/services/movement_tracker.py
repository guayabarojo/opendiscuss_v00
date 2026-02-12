"""
Movement Tracker Service - Tracks participant transitions between rounds

This module provides functions for tracking participant movement across adjacent
rounds, computing transitions between clusters, and aggregating movements for
edge construction. Integrates with dropout_handler to ensure only continuing
participants (user intersection) are included in edge computation.

Constitutional Compliance:
- Temporal Transparency: Edges computed from actual participant movement
- Semantic Accuracy: 100% edge accuracy matches real transitions
- Intent Fidelity: Uses actual participant assignments, not similarity
- Natural Dropout: Only continuing participants generate edges (FR-019)
"""

from typing import Dict, List, Tuple, Set
from uuid import UUID
from collections import defaultdict
import logging

from ..services.cluster_api_client import ClusterAPIClient
from ..services.dropout_handler import compute_user_intersection

logger = logging.getLogger(__name__)


async def track_movement(
    from_round_id: UUID,
    to_round_id: UUID,
    cluster_client: ClusterAPIClient,
    filter_dropouts: bool = True
) -> Dict[UUID, Tuple[UUID, UUID]]:
    """
    Compute participant transitions between adjacent rounds.

    This function uses the ClusterAPIClient to fetch participant movements
    between two rounds. By default, it returns only continuing participants
    (intersection) who submitted in both rounds, filtering out dropouts.

    Args:
        from_round_id: Source round UUID
        to_round_id: Destination round UUID
        cluster_client: ClusterAPIClient instance for querying Spec 004 data
        filter_dropouts: If True (default), only include continuing participants.
                        If False, include all movements (for testing/debugging).

    Returns:
        Dict mapping user_id to (from_cluster_id, to_cluster_id) for participants
        who submitted in BOTH rounds (continuing participants only, if filter_dropouts=True)

    Raises:
        ValueError: If round_id parameters are invalid

    Validates:
        FR-019: Edges computed only for continuing participants (intersection)
        SC-002: 100% edge accuracy (matches actual participant movement)

    Constitutional Compliance:
        - Temporal Transparency: Uses actual participant assignments across rounds
        - Semantic Accuracy: Movement based on real behavior, not similarity
        - Intent Fidelity: Preserves actual participant transitions
        - Natural Dropout: Dropouts excluded from edge computation (FR-019)

    Performance:
        Target <100ms for 100 participants (two database queries + set intersection)

    Example:
        movements = await track_movement(round1_id, round2_id, client)
        # Returns: {user1: (cluster_a, cluster_d), user2: (cluster_b, cluster_d), ...}
        # Only includes users who submitted in BOTH rounds
    """
    if not from_round_id or not to_round_id:
        raise ValueError("round_id parameters cannot be None")

    logger.info(
        f"Tracking participant movements from round {from_round_id} to {to_round_id} "
        f"(filter_dropouts={filter_dropouts})"
    )

    # Use ClusterAPIClient to get participant movements
    # This method already computes the intersection (continuing participants only)
    movements = await cluster_client.get_participant_movements(
        from_round_id=from_round_id,
        to_round_id=to_round_id
    )

    # Optional: Additional explicit dropout filtering using dropout_handler
    # This is defensive - cluster_client.get_participant_movements should already
    # return only continuing participants, but we can verify with compute_user_intersection
    if filter_dropouts:
        # Get continuing users (intersection)
        continuing_users = await compute_user_intersection(
            from_round_id=from_round_id,
            to_round_id=to_round_id,
            cluster_client=cluster_client
        )

        # Filter movements to only include continuing users
        original_count = len(movements)
        movements = {
            user_id: transition
            for user_id, transition in movements.items()
            if user_id in continuing_users
        }

        filtered_count = original_count - len(movements)
        if filtered_count > 0:
            logger.info(
                f"Filtered out {filtered_count} dropout movements, "
                f"kept {len(movements)} continuing participant movements"
            )

    # Log metrics for monitoring
    logger.info(
        f"Tracked {len(movements)} participant movements from round "
        f"{from_round_id} to {to_round_id}"
    )

    return movements


def aggregate_movements(
    movements: Dict[UUID, Tuple[UUID, UUID]]
) -> Dict[Tuple[UUID, UUID], int]:
    """
    Group transitions by (from_cluster_id, to_cluster_id) and count participants.

    This function aggregates individual participant movements into cluster-to-cluster
    transitions, counting how many participants made each transition. The result
    is used to create SankeyEdge entities with correct user_count values.

    Args:
        movements: Dict mapping user_id to (from_cluster_id, to_cluster_id)

    Returns:
        Dict mapping (from_cluster_id, to_cluster_id) to participant count

    Validates:
        SC-002: Edge totals match participant movement
        FR-040: Edge totals validation

    Constitutional Compliance:
        - Semantic Accuracy: Every participant counted exactly once
        - Temporal Transparency: Aggregation preserves actual movement counts

    Example:
        movements = {
            user1: (cluster_a, cluster_d),
            user2: (cluster_a, cluster_d),
            user3: (cluster_b, cluster_d),
        }
        aggregated = aggregate_movements(movements)
        # Returns: {(cluster_a, cluster_d): 2, (cluster_b, cluster_d): 1}
    """
    if not movements:
        logger.debug("No movements to aggregate (empty movements dict)")
        return {}

    # Use defaultdict for efficient counting
    aggregated: Dict[Tuple[UUID, UUID], int] = defaultdict(int)

    # Count participants for each (from_cluster, to_cluster) transition
    for user_id, (from_cluster_id, to_cluster_id) in movements.items():
        transition = (from_cluster_id, to_cluster_id)
        aggregated[transition] += 1

    # Convert back to regular dict
    result = dict(aggregated)

    # Log aggregation metrics
    total_participants = len(movements)
    total_edges = len(result)
    logger.info(
        f"Aggregated {total_participants} participant movements into {total_edges} edges"
    )

    # Log edge distribution for monitoring
    edge_counts = sorted(result.values(), reverse=True)
    if edge_counts:
        logger.debug(
            f"Edge distribution: largest={edge_counts[0]}, "
            f"smallest={edge_counts[-1]}, "
            f"mean={sum(edge_counts) / len(edge_counts):.1f}"
        )

    return result


async def compute_movements_for_rounds(
    from_round_id: UUID,
    to_round_id: UUID,
    cluster_client: ClusterAPIClient
) -> Dict[Tuple[UUID, UUID], int]:
    """
    Convenience function to track and aggregate movements in one call.

    This function combines track_movement and aggregate_movements into a single
    operation, useful for the common case of computing edges between two rounds.

    Args:
        from_round_id: Source round UUID
        to_round_id: Destination round UUID
        cluster_client: ClusterAPIClient instance

    Returns:
        Dict mapping (from_cluster_id, to_cluster_id) to participant count

    Example:
        aggregated = await compute_movements_for_rounds(round1_id, round2_id, client)
        # Returns: {(cluster_a, cluster_d): 2, (cluster_b, cluster_d): 1}
    """
    movements = await track_movement(from_round_id, to_round_id, cluster_client)
    aggregated = aggregate_movements(movements)
    return aggregated
