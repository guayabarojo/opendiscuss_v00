"""
Report Service - Generates comprehensive discussion reports.

Implements Spec 005 User Story 5: Discussion Report Generation.
Provides 4 core functions for assembling reports with Sankey data and statistics.

Constitutional Compliance:
- Representation Not Adjudication: Reports show data without rankings or judgments
- Temporal Transparency: Dropout curve shows honest participant engagement
- Intent Fidelity: All summaries from actual participant text
"""

import logging
from typing import List
from uuid import UUID

from ..models.discussion_report import (
    DiscussionReport,
    RoundClusterSummary,
    ClusterInfo,
    DropoutPoint,
    TopMovement,
    MovementDetail,
)
from ..models.sankey_graph import SankeyGraph

logger = logging.getLogger(__name__)


def generate_cluster_summaries(sankey: SankeyGraph) -> List[RoundClusterSummary]:
    """
    Generate per-round cluster summaries from a SankeyGraph.

    Args:
        sankey: Complete SankeyGraph with columns and nodes

    Returns:
        List of RoundClusterSummary (one per round), ordered by round_index

    Validates:
        FR-035: Report includes per-round cluster summaries (label, user_count)
    """
    logger.info(f"Generating cluster summaries for {len(sankey.columns)} rounds")

    summaries = []

    for column in sankey.columns:
        # Convert nodes to ClusterInfo
        clusters = []
        for node in sorted(column.nodes, key=lambda n: n.user_count, reverse=True):
            clusters.append(
                ClusterInfo(
                    cluster_id=node.cluster_id,
                    label=node.label_summary,
                    user_count=node.user_count,
                    user_pct=node.user_pct,
                )
            )

        # Count singletons (outliers with user_count = 1)
        singleton_count = sum(1 for node in column.nodes if node.user_count == 1)

        # Find largest cluster percentage
        largest_cluster_pct = max(node.user_pct for node in column.nodes) if column.nodes else 0.0

        # Build RoundClusterSummary
        summary = RoundClusterSummary(
            round_index=column.round_index,
            round_id=sankey.rounds[column.round_index],
            total_participants=column.total_participants,
            cluster_count=len(column.nodes),
            clusters=clusters,
            singleton_count=singleton_count,
            largest_cluster_pct=largest_cluster_pct,
        )

        summaries.append(summary)

    logger.info(f"Generated {len(summaries)} cluster summaries")
    return summaries


def generate_dropout_curve(sankey: SankeyGraph) -> List[DropoutPoint]:
    """
    Generate dropout curve showing participant counts per round.

    Args:
        sankey: Complete SankeyGraph with columns

    Returns:
        List of DropoutPoint (one per round), ordered by round_index

    Validates:
        FR-036: Report includes participant counts per round (dropout curve)
    """
    logger.info(f"Generating dropout curve for {len(sankey.columns)} rounds")

    dropout_curve = []

    for column in sankey.columns:
        dropout_curve.append(
            DropoutPoint(
                round_index=column.round_index,
                participant_count=column.total_participants,
            )
        )

    logger.info(
        f"Dropout curve generated: {dropout_curve[0].participant_count} "
        f"-> {dropout_curve[-1].participant_count} participants"
    )

    return dropout_curve


def generate_top_movements(sankey: SankeyGraph, top_n: int = 5) -> List[TopMovement]:
    """
    Generate top participant movements between rounds.

    Args:
        sankey: Complete SankeyGraph with edges
        top_n: Number of top movements to return per round transition (default 5)

    Returns:
        List of TopMovement (one per round transition), each with top N flows

    Validates:
        FR-037: Report includes top movement edges (largest flows) per round transition
    """
    logger.info(f"Generating top {top_n} movements for {len(sankey.edges)} total edges")

    if sankey.is_single_round():
        logger.info("Single-round discussion, no movements to report")
        return []

    top_movements = []

    # Group edges by round transition
    for round_index in range(len(sankey.columns) - 1):
        from_round_index = round_index
        to_round_index = round_index + 1

        # Get all edges for this transition
        round_edges = [
            edge
            for edge in sankey.edges
            if edge.from_round_index == from_round_index
            and edge.to_round_index == to_round_index
        ]

        if not round_edges:
            logger.warning(f"No edges found for round {from_round_index} -> {to_round_index}")
            continue

        # Sort by user_count descending and take top N
        top_edges = sorted(round_edges, key=lambda e: e.user_count, reverse=True)[:top_n]

        # Convert to MovementDetail
        movements = []
        for edge in top_edges:
            # Find source and target nodes for labels
            from_column = sankey.get_column(from_round_index)
            to_column = sankey.get_column(to_round_index)

            from_node = next(
                (n for n in from_column.nodes if n.cluster_id == edge.from_cluster_id),
                None
            )
            to_node = next(
                (n for n in to_column.nodes if n.cluster_id == edge.to_cluster_id),
                None
            )

            if not from_node or not to_node:
                logger.warning(
                    f"Could not find nodes for edge {edge.from_cluster_id} -> {edge.to_cluster_id}"
                )
                continue

            # Truncate labels to 100 chars
            from_label = from_node.label_summary[:100]
            to_label = to_node.label_summary[:100]

            # Calculate percentages
            pct_of_from = edge.user_count / from_node.user_count if from_node.user_count > 0 else 0.0
            pct_of_to = edge.user_count / to_node.user_count if to_node.user_count > 0 else 0.0

            movements.append(
                MovementDetail(
                    from_cluster_id=edge.from_cluster_id,
                    from_label=from_label,
                    to_cluster_id=edge.to_cluster_id,
                    to_label=to_label,
                    participant_count=edge.user_count,
                    pct_of_from=pct_of_from,
                    pct_of_to=pct_of_to,
                )
            )

        # Create TopMovement for this transition
        top_movement = TopMovement(
            from_round_index=from_round_index,
            to_round_index=to_round_index,
            movements=movements,
            total_transitions=len(round_edges),
        )

        top_movements.append(top_movement)

        logger.info(
            f"Round {from_round_index} -> {to_round_index}: "
            f"{len(movements)} top movements from {len(round_edges)} total transitions"
        )

    logger.info(f"Generated {len(top_movements)} top movement summaries")
    return top_movements


def assemble_discussion_report(sankey: SankeyGraph) -> DiscussionReport:
    """
    Assemble complete discussion report from a SankeyGraph.

    Orchestrates all report generation functions to create a comprehensive
    DiscussionReport entity.

    Args:
        sankey: Complete SankeyGraph with columns, nodes, and edges

    Returns:
        Complete DiscussionReport with all sections

    Validates:
        FR-034: System generates discussion report including final SankeyGraph
        FR-038: Report is exportable in structured format
        SC-008: Reports include all required sections 100% of the time
    """
    logger.info(f"Assembling discussion report for discussion {sankey.discussion_id}")

    # Generate all report sections
    cluster_summaries = generate_cluster_summaries(sankey)
    dropout_curve = generate_dropout_curve(sankey)
    top_movements = generate_top_movements(sankey, top_n=5)

    # Assemble final report
    report = DiscussionReport(
        discussion_id=sankey.discussion_id,
        sankey_graph=sankey,
        cluster_summaries=cluster_summaries,
        dropout_curve=dropout_curve,
        top_movements=top_movements,
    )

    logger.info(
        f"Discussion report assembled: {len(cluster_summaries)} rounds, "
        f"{report.get_total_dropout()} total dropout, "
        f"{len(top_movements)} round transitions"
    )

    return report
