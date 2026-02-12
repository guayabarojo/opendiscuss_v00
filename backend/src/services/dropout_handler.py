"""
Dropout Handler Service - Natural participant dropout handling

This module provides functions for computing user intersections between rounds
and tracking dropout without creating synthetic dropout nodes. Implements the
"temporal transparency" principle by showing honest participant engagement.

Constitutional Compliance:
- Temporal Transparency: Dropout visible through natural flow mass shrinkage
- Representation Not Adjudication: No synthetic "dropout" or "no response" nodes
- Semantic Accuracy: Per-round normalization preserves actual percentages
"""

from typing import Dict, List, Set, Tuple
from uuid import UUID
from collections import defaultdict
import logging

from ..services.cluster_api_client import ClusterAPIClient

logger = logging.getLogger(__name__)


async def compute_user_intersection(
    from_round_id: UUID,
    to_round_id: UUID,
    cluster_client: ClusterAPIClient
) -> Set[UUID]:
    """
    Identify participants present in both rounds (continuing participants).

    This function computes the intersection of participants who submitted in
    both the source and destination rounds. Only continuing participants will
    have edges computed for their movement.

    Args:
        from_round_id: Source round UUID
        to_round_id: Destination round UUID
        cluster_client: ClusterAPIClient instance for querying assignments

    Returns:
        Set of user_ids who submitted in BOTH rounds (continuing participants)

    Validates:
        FR-019: Edges computed only for continuing participants
        SC-011: No synthetic dropout nodes created

    Constitutional Compliance:
        - Temporal Transparency: Honest representation of who continued
        - Representation Not Adjudication: No value judgment on dropout

    Performance:
        Target <50ms for 100 participants (two set operations)

    Example:
        continuing = await compute_user_intersection(round1_id, round2_id, client)
        # Returns: {user1, user2, user3, ...}
        # Excludes users who only submitted in one round
    """
    if not from_round_id or not to_round_id:
        raise ValueError("round_id parameters cannot be None")

    logger.info(
        f"Computing user intersection between round {from_round_id} and {to_round_id}"
    )

    # Get participant assignments for both rounds (more reliable than extracting from clusters)
    from_assignments = await cluster_client.get_participant_assignments(from_round_id)
    to_assignments = await cluster_client.get_participant_assignments(to_round_id)

    if not from_assignments:
        logger.warning(f"No participants found for source round {from_round_id}")
        return set()

    if not to_assignments:
        logger.warning(f"No participants found for destination round {to_round_id}")
        return set()

    # Extract all user_ids from assignments
    from_users = set(from_assignments.keys())
    to_users = set(to_assignments.keys())

    # Compute intersection (continuing participants)
    continuing_users = from_users & to_users

    # Compute dropout metrics for logging
    from_count = len(from_users)
    to_count = len(to_users)
    continuing_count = len(continuing_users)
    dropout_count = from_count - continuing_count

    logger.info(
        f"User intersection computed: "
        f"{from_count} in round 1, {to_count} in round 2, "
        f"{continuing_count} continuing ({dropout_count} dropped out, "
        f"{to_count - continuing_count} new in round 2)"
    )

    return continuing_users


async def compute_per_round_participant_counts(
    discussion_id: UUID,
    rounds: List[UUID],
    cluster_client: ClusterAPIClient
) -> List[Tuple[int, int]]:
    """
    Compute participant counts for each round (for dropout curve generation).

    This function generates the data needed to visualize participant dropout
    over the course of a discussion. Each round gets (round_index, participant_count).

    Args:
        discussion_id: Discussion UUID
        rounds: List of round UUIDs in temporal order
        cluster_client: ClusterAPIClient instance

    Returns:
        List of (round_index, participant_count) tuples, ordered by round_index

    Validates:
        FR-021: Per-round participant tracking for dropout curve
        SC-012: Natural mass shrinkage visible

    Constitutional Compliance:
        - Temporal Transparency: Honest engagement numbers per round
        - Representation Not Adjudication: No hiding of dropout data

    Example:
        counts = await compute_per_round_participant_counts(discussion_id, rounds, client)
        # Returns: [(0, 20), (1, 18), (2, 15), ...]
        # Shows 20 participants in round 0, 18 in round 1, etc.
    """
    if not rounds:
        raise ValueError(f"Cannot compute participant counts: no rounds for discussion {discussion_id}")

    logger.info(
        f"Computing per-round participant counts for discussion {discussion_id}: {len(rounds)} rounds"
    )

    participant_counts: List[Tuple[int, int]] = []

    for round_index, round_id in enumerate(rounds):
        # Get all clusters for this round
        clusters = await cluster_client.get_clusters_for_round(round_id)

        if not clusters:
            logger.warning(f"No clusters found for round {round_index} ({round_id})")
            participant_counts.append((round_index, 0))
            continue

        # Extract all unique user_ids in this round
        users_in_round: Set[UUID] = set()
        for cluster in clusters:
            if hasattr(cluster, 'members'):
                users_in_round.update(member.user_id for member in cluster.members)
            elif hasattr(cluster, 'member_ids'):
                users_in_round.update(cluster.member_ids)

        participant_count = len(users_in_round)
        participant_counts.append((round_index, participant_count))

        logger.debug(f"Round {round_index}: {participant_count} participants")

    # Log dropout summary for monitoring
    if len(participant_counts) >= 2:
        initial_count = participant_counts[0][1]
        final_count = participant_counts[-1][1]
        total_dropout = initial_count - final_count
        dropout_rate = total_dropout / initial_count if initial_count > 0 else 0.0

        logger.info(
            f"Dropout summary: {initial_count} initial → {final_count} final "
            f"({total_dropout} dropped, {dropout_rate:.1%} dropout rate)"
        )

    return participant_counts


def validate_no_dropout_nodes(clusters: List) -> Tuple[bool, List[str]]:
    """
    Validate that no synthetic "dropout" or "no response" nodes exist.

    This validation enforces the constitutional principle that dropout should
    be represented through natural flow mass shrinkage, not synthetic nodes.

    Args:
        clusters: List of clusters (nodes) to validate

    Returns:
        Tuple of (is_valid, error_messages)
        - is_valid: True if no dropout nodes found, False otherwise
        - error_messages: List of validation errors (empty if valid)

    Validates:
        FR-020: No synthetic dropout nodes
        SC-011: Dropout via natural mass shrinkage only

    Constitutional Compliance:
        - Temporal Transparency: Honest representation without artificial constructs
        - Representation Not Adjudication: No special treatment for dropouts

    Example:
        is_valid, errors = validate_no_dropout_nodes(all_clusters)
        # Returns: (True, []) if valid
        # Returns: (False, ["Synthetic dropout node found: cluster_xyz"]) if invalid
    """
    errors: List[str] = []

    # Forbidden labels that indicate synthetic dropout nodes
    forbidden_labels = [
        "dropout",
        "no response",
        "did not respond",
        "no submission",
        "left discussion",
        "[dropout]",
        "[no response]",
    ]

    for cluster in clusters:
        # Get cluster label (from medoid summary or label field)
        label = ""
        if hasattr(cluster, 'label_summary'):
            label = cluster.label_summary.lower()
        elif hasattr(cluster, 'medoid_summary') and cluster.medoid_summary:
            label = cluster.medoid_summary.summary_text.lower()

        # Check if label contains any forbidden terms
        for forbidden in forbidden_labels:
            if forbidden in label:
                errors.append(
                    f"Synthetic dropout node detected: cluster {cluster.id} "
                    f"has label containing '{forbidden}'"
                )

    is_valid = len(errors) == 0

    if not is_valid:
        logger.error(f"Dropout node validation failed: {len(errors)} violations found")
    else:
        logger.debug("Dropout node validation passed: no synthetic nodes found")

    return is_valid, errors


def validate_natural_mass_shrinkage(
    edge_total: int,
    from_round_participant_count: int,
    to_round_participant_count: int
) -> Tuple[bool, List[str]]:
    """
    Validate that edge totals reflect natural mass shrinkage when dropout occurs.

    When participants drop out between rounds, the total edge flow should equal
    the number of continuing participants (user intersection), not the source
    round participant count. This validates temporal transparency.

    Args:
        edge_total: Sum of all edge user_counts for this round transition
        from_round_participant_count: Total participants in source round
        to_round_participant_count: Total participants in destination round

    Returns:
        Tuple of (is_valid, error_messages)

    Validates:
        FR-021: Edge totals match continuing participants, not source count
        FR-022: Visual narrowing occurs naturally when dropout happens
        SC-012: Natural mass shrinkage

    Constitutional Compliance:
        - Temporal Transparency: Honest representation of participant movement
        - Representation Not Adjudication: No artificial flow for dropouts

    Example:
        # 10 participants in Round 1, 7 in Round 2 (3 dropped out)
        # Edge total should be 7 (continuing), not 10 (source)
        is_valid, errors = validate_natural_mass_shrinkage(7, 10, 7)
        # Returns: (True, [])

        # Invalid: Edge total of 10 would mean all source participants have edges
        is_valid, errors = validate_natural_mass_shrinkage(10, 10, 7)
        # Returns: (False, ["Edge total 10 should not exceed destination count 7"])
    """
    errors: List[str] = []

    # Edge total should not exceed destination round participant count
    # (cannot have more flow than participants in destination)
    if edge_total > to_round_participant_count:
        errors.append(
            f"Edge total {edge_total} exceeds destination round participant count "
            f"{to_round_participant_count}. Natural shrinkage violated."
        )

    # Edge total should be less than or equal to source round participant count
    # (cannot have more flow than participants in source)
    if edge_total > from_round_participant_count:
        errors.append(
            f"Edge total {edge_total} exceeds source round participant count "
            f"{from_round_participant_count}. This should be impossible."
        )

    # If dropout occurred (from_count > to_count), edge total should match
    # the smaller count (continuing participants)
    if from_round_participant_count > to_round_participant_count:
        # Dropout occurred
        if edge_total > to_round_participant_count:
            errors.append(
                f"Dropout occurred ({from_round_participant_count} → {to_round_participant_count}), "
                f"but edge total {edge_total} exceeds continuing participant count. "
                f"Should be ≤ {to_round_participant_count}."
            )

    is_valid = len(errors) == 0

    if not is_valid:
        logger.error(f"Natural mass shrinkage validation failed: {len(errors)} violations")
    else:
        logger.debug(
            f"Natural mass shrinkage validated: edge_total={edge_total}, "
            f"from={from_round_participant_count}, to={to_round_participant_count}"
        )

    return is_valid, errors
