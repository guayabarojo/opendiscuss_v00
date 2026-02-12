"""
Sankey Invariants Validator - Validates critical Sankey diagram invariants

This module provides validation functions for ensuring the Sankey diagram
maintains its mathematical and logical invariants throughout construction.

Constitutional Compliance:
- Semantic Accuracy: 100% participant coverage validation
- Temporal Transparency: Edge totals match actual participant movement
- Representation Not Adjudication: No synthetic nodes (dropout handled naturally)
"""

from typing import Dict, List, Set, Tuple
from uuid import UUID
import logging

from ..models.sankey_column import SankeyColumn
from ..models.sankey_edge import SankeyEdge
from ..models.sankey_graph import SankeyGraph
from ..models.sankey_node import SankeyNode

logger = logging.getLogger(__name__)


class SankeyInvariantValidator:
    """
    Validates critical invariants for Sankey diagram construction.

    Success Criteria Validated:
    - SC-002: 100% edge accuracy (matches participant movement)
    - SC-003: 100% participant coverage (all assigned to clusters)
    - SC-005: Percentage sums = 1.0 ± 0.0001 per column
    - SC-011: No synthetic "dropout" or "no response" nodes
    """

    PERCENTAGE_TOLERANCE = 0.0001  # 0.01% tolerance for SC-005

    @staticmethod
    def validate_percentage_sum(column: SankeyColumn) -> Tuple[bool, str]:
        """
        Validate that sum of node user_pct equals 1.0 within tolerance.

        Args:
            column: Column to validate

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            SC-005: Percentage sum validation with sub-0.01% tolerance
        """
        if not column.nodes:
            return False, "Column has no nodes"

        total_pct = sum(node.user_pct for node in column.nodes)
        tolerance = SankeyInvariantValidator.PERCENTAGE_TOLERANCE

        if abs(total_pct - 1.0) > tolerance:
            error_msg = (
                f"Column {column.round_index}: Sum of node user_pct = {total_pct:.6f}, "
                f"expected 1.0 ± {tolerance} (difference: {abs(total_pct - 1.0):.6f})"
            )
            logger.error(error_msg)
            return False, error_msg

        logger.debug(
            f"Column {column.round_index}: Percentage sum = {total_pct:.6f} (valid)"
        )
        return True, ""

    @staticmethod
    def validate_edge_totals(
        edges: List[SankeyEdge],
        from_column: SankeyColumn,
        to_column: SankeyColumn,
        participant_assignments: Dict[UUID, Tuple[UUID, UUID]]
    ) -> Tuple[bool, str]:
        """
        Validate that edge totals match actual participant intersection.

        Args:
            edges: List of edges between from_column and to_column
            from_column: Source column
            to_column: Destination column
            participant_assignments: Dict mapping user_id to (from_cluster_id, to_cluster_id)

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            SC-002: 100% edge accuracy (edge counts match participant movement)
            FR-040: Edge totals validation
        """
        if not edges:
            # No edges is valid for single-round or if all participants dropped out
            logger.debug(
                f"No edges between rounds {from_column.round_index} and {to_column.round_index}"
            )
            return True, ""

        # Sum edge user_counts
        total_edge_count = sum(edge.user_count for edge in edges)

        # Count actual participants who continued (intersection)
        continuing_participants = len(participant_assignments)

        if total_edge_count != continuing_participants:
            error_msg = (
                f"Edges from round {from_column.round_index} to {to_column.round_index}: "
                f"Total edge user_count = {total_edge_count}, "
                f"expected {continuing_participants} (actual continuing participants)"
            )
            logger.error(error_msg)
            return False, error_msg

        logger.debug(
            f"Edges from round {from_column.round_index} to {to_column.round_index}: "
            f"Total edge count = {total_edge_count} (matches intersection)"
        )
        return True, ""

    @staticmethod
    def validate_coverage(
        column: SankeyColumn,
        expected_participant_ids: Set[UUID]
    ) -> Tuple[bool, str]:
        """
        Validate that all expected participants are assigned to clusters.

        Args:
            column: Column to validate
            expected_participant_ids: Set of participant UUIDs expected in this round

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            SC-003: 100% participant coverage
            FR-016: Every participant assigned to exactly one cluster
        """
        # Note: This validation requires access to participant-to-cluster mappings
        # which come from Spec 004 cluster_members table. In practice, this is
        # validated by checking that sum of node.user_count equals expected count.

        expected_count = len(expected_participant_ids)
        actual_count = sum(node.user_count for node in column.nodes)

        if actual_count != expected_count:
            error_msg = (
                f"Column {column.round_index}: Total node user_count = {actual_count}, "
                f"expected {expected_count} (100% coverage required)"
            )
            logger.error(error_msg)
            return False, error_msg

        if column.total_participants != expected_count:
            error_msg = (
                f"Column {column.round_index}: total_participants = {column.total_participants}, "
                f"expected {expected_count}"
            )
            logger.error(error_msg)
            return False, error_msg

        logger.debug(
            f"Column {column.round_index}: Coverage = {actual_count}/{expected_count} (100%)"
        )
        return True, ""

    @staticmethod
    def validate_no_synthetic_nodes(columns: List[SankeyColumn]) -> Tuple[bool, str]:
        """
        Validate that no synthetic "dropout" or "no response" nodes exist.

        Args:
            columns: List of columns to validate

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            SC-011: No synthetic nodes (dropout handled via natural shrinkage)
            FR-020: No "dropout" nodes
            FR-021: No "no response" nodes
        """
        synthetic_keywords = [
            "dropout",
            "no response",
            "did not submit",
            "no submission",
            "inactive",
            "[system]",
            "[no participation]"
        ]

        for column in columns:
            for node in column.nodes:
                label_lower = node.label_summary.lower()
                for keyword in synthetic_keywords:
                    if keyword in label_lower:
                        error_msg = (
                            f"Column {column.round_index}: Synthetic node detected - "
                            f"label contains '{keyword}': {node.label_summary[:100]}"
                        )
                        logger.error(error_msg)
                        return False, error_msg

        logger.debug("No synthetic nodes detected in any column")
        return True, ""

    @staticmethod
    def validate_natural_shrinkage(
        columns: List[SankeyColumn],
        edges_by_round: Dict[int, List[SankeyEdge]]
    ) -> Tuple[bool, str]:
        """
        Validate that dropout results in natural flow mass shrinkage.

        Args:
            columns: List of columns ordered by round_index
            edges_by_round: Dict mapping from_round_index to list of edges

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            FR-021: Total edge width shrinks when dropout occurs
            FR-022: Dropout visible through flow narrowing
            FR-023: No cross-round renormalization
        """
        if len(columns) < 2:
            # Single-round discussion, no shrinkage to validate
            return True, ""

        for i in range(len(columns) - 1):
            from_column = columns[i]
            to_column = columns[i + 1]
            edges = edges_by_round.get(i, [])

            # If participants dropped out, total edge count should be less than
            # source column participant count
            if to_column.total_participants < from_column.total_participants:
                # Dropout occurred
                total_edge_count = sum(edge.user_count for edge in edges)

                if total_edge_count > to_column.total_participants:
                    error_msg = (
                        f"Rounds {i} to {i+1}: Dropout detected "
                        f"({from_column.total_participants} → {to_column.total_participants}), "
                        f"but total edge count = {total_edge_count} exceeds destination "
                        f"participant count (indicates cross-round renormalization)"
                    )
                    logger.error(error_msg)
                    return False, error_msg

                logger.debug(
                    f"Rounds {i} to {i+1}: Natural shrinkage validated - "
                    f"{from_column.total_participants} → {to_column.total_participants}, "
                    f"edge total = {total_edge_count}"
                )

        return True, ""

    @staticmethod
    def validate_alignment_invariance(
        sankey_before: SankeyGraph,
        sankey_after: SankeyGraph
    ) -> Tuple[bool, str]:
        """
        Validate that alignment metadata does NOT change edge counts.

        Args:
            sankey_before: SankeyGraph before alignment integration
            sankey_after: SankeyGraph after alignment integration

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            SC-006: Alignment invariance (edge counts unchanged)
            FR-026: Alignment metadata does not affect edge computation
        """
        # Check edge counts
        if len(sankey_before.edges) != len(sankey_after.edges):
            error_msg = (
                f"Alignment changed edge count: "
                f"{len(sankey_before.edges)} → {len(sankey_after.edges)}"
            )
            logger.error(error_msg)
            return False, error_msg

        # Check individual edge user_counts
        edges_before = {
            (e.from_cluster_id, e.to_cluster_id): e.user_count
            for e in sankey_before.edges
        }
        edges_after = {
            (e.from_cluster_id, e.to_cluster_id): e.user_count
            for e in sankey_after.edges
        }

        for key, count_before in edges_before.items():
            count_after = edges_after.get(key)
            if count_after is None:
                error_msg = (
                    f"Alignment removed edge: {key[0]} → {key[1]}"
                )
                logger.error(error_msg)
                return False, error_msg

            if count_before != count_after:
                error_msg = (
                    f"Alignment changed edge user_count: "
                    f"{key[0]} → {key[1]}: {count_before} → {count_after}"
                )
                logger.error(error_msg)
                return False, error_msg

        logger.info("Alignment invariance validated: edge counts unchanged")
        return True, ""

    @staticmethod
    def validate_all(
        sankey_graph: SankeyGraph,
        participant_assignments_by_round: Dict[int, Set[UUID]] = None,
        movement_data: Dict[int, Dict[UUID, Tuple[UUID, UUID]]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Run all invariant validations on a SankeyGraph.

        Args:
            sankey_graph: SankeyGraph to validate
            participant_assignments_by_round: Optional dict mapping round_index to set of participant UUIDs
            movement_data: Optional dict mapping from_round_index to participant movements

        Returns:
            Tuple of (all_valid, list_of_errors)
        """
        errors = []

        # Validate percentage sums for all columns
        for column in sankey_graph.columns:
            is_valid, error_msg = SankeyInvariantValidator.validate_percentage_sum(column)
            if not is_valid:
                errors.append(error_msg)

        # Validate no synthetic nodes
        is_valid, error_msg = SankeyInvariantValidator.validate_no_synthetic_nodes(
            sankey_graph.columns
        )
        if not is_valid:
            errors.append(error_msg)

        # Validate natural shrinkage
        edges_by_round = {}
        for edge in sankey_graph.edges:
            edges_by_round.setdefault(edge.from_round_index, []).append(edge)

        is_valid, error_msg = SankeyInvariantValidator.validate_natural_shrinkage(
            sankey_graph.columns,
            edges_by_round
        )
        if not is_valid:
            errors.append(error_msg)

        # Validate coverage if participant data provided
        if participant_assignments_by_round:
            for round_index, expected_ids in participant_assignments_by_round.items():
                if round_index < len(sankey_graph.columns):
                    column = sankey_graph.columns[round_index]
                    is_valid, error_msg = SankeyInvariantValidator.validate_coverage(
                        column,
                        expected_ids
                    )
                    if not is_valid:
                        errors.append(error_msg)

        # Validate edge totals if movement data provided
        if movement_data:
            for from_round_index, movements in movement_data.items():
                if from_round_index + 1 < len(sankey_graph.columns):
                    from_column = sankey_graph.columns[from_round_index]
                    to_column = sankey_graph.columns[from_round_index + 1]
                    edges = edges_by_round.get(from_round_index, [])

                    is_valid, error_msg = SankeyInvariantValidator.validate_edge_totals(
                        edges,
                        from_column,
                        to_column,
                        movements
                    )
                    if not is_valid:
                        errors.append(error_msg)

        all_valid = len(errors) == 0
        if all_valid:
            logger.info("All Sankey invariants validated successfully")
        else:
            logger.error(f"Sankey invariant validation failed with {len(errors)} errors")

        return all_valid, errors
