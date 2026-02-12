"""
Graph Structure Validator - Validates SankeyGraph structural integrity

This module provides validation functions for ensuring the SankeyGraph maintains
correct structural properties: column ordering, edge references, round consistency,
and no duplicate edges.

Constitutional Compliance:
- Temporal Transparency: Validates temporal ordering of columns
- Semantic Accuracy: Ensures all edges reference valid nodes/columns
- Representation Not Adjudication: Structural validation only, no content judgments
"""

from typing import Dict, List, Set, Tuple
from uuid import UUID
import logging

from ..models.sankey_graph import SankeyGraph
from ..models.sankey_column import SankeyColumn
from ..models.sankey_edge import SankeyEdge

logger = logging.getLogger(__name__)


class GraphStructureValidator:
    """
    Validates structural integrity of SankeyGraph.

    Success Criteria Validated:
    - SC-007: Column ordering (sequential 0, 1, 2, ...)
    - SC-008: Edge references (all edges point to valid clusters in valid columns)
    - SC-009: No duplicate edges (unique from_cluster_id + to_cluster_id pairs)
    - SC-010: Round consistency (len(columns) == len(rounds))
    """

    @staticmethod
    def validate_column_ordering(columns: List[SankeyColumn]) -> Tuple[bool, str]:
        """
        Validate that columns are ordered by round_index (0, 1, 2, ...).

        Args:
            columns: List of columns to validate

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            SC-007: Columns must be in sequential temporal order
            FR-012: Column ordering preserves round temporal sequence
        """
        if not columns:
            return False, "No columns provided for validation"

        for i, column in enumerate(columns):
            if column.round_index != i:
                error_msg = (
                    f"Column ordering violation: Expected round_index {i}, "
                    f"got {column.round_index} at position {i}"
                )
                logger.error(error_msg)
                return False, error_msg

        logger.debug(f"Column ordering validated: {len(columns)} columns in correct order")
        return True, ""

    @staticmethod
    def validate_edge_references(
        edges: List[SankeyEdge],
        columns: List[SankeyColumn]
    ) -> Tuple[bool, str]:
        """
        Validate that all edges reference valid clusters in valid columns.

        Args:
            edges: List of edges to validate
            columns: List of columns containing nodes

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            SC-008: All edges must reference existing clusters in valid columns
            FR-039: Edges only between adjacent rounds (handled by Edge model)
        """
        if not edges:
            # No edges is valid (single-round discussion)
            logger.debug("No edges to validate (single-round discussion)")
            return True, ""

        if not columns or len(columns) < 2:
            error_msg = (
                f"Cannot validate edges: Need at least 2 columns for edges, "
                f"got {len(columns) if columns else 0}"
            )
            logger.error(error_msg)
            return False, error_msg

        # Build index of valid cluster_ids per column
        cluster_ids_by_round: Dict[int, Set[UUID]] = {}
        for column in columns:
            cluster_ids_by_round[column.round_index] = {
                node.cluster_id for node in column.nodes
            }

        # Validate each edge
        for edge in edges:
            # Check from_round_index is valid
            if edge.from_round_index not in cluster_ids_by_round:
                error_msg = (
                    f"Edge references invalid from_round_index: {edge.from_round_index} "
                    f"(valid range: [0, {len(columns) - 1}])"
                )
                logger.error(error_msg)
                return False, error_msg

            # Check to_round_index is valid
            if edge.to_round_index not in cluster_ids_by_round:
                error_msg = (
                    f"Edge references invalid to_round_index: {edge.to_round_index} "
                    f"(valid range: [0, {len(columns) - 1}])"
                )
                logger.error(error_msg)
                return False, error_msg

            # Check from_cluster_id exists in from_round
            from_clusters = cluster_ids_by_round[edge.from_round_index]
            if edge.from_cluster_id not in from_clusters:
                error_msg = (
                    f"Edge references non-existent from_cluster_id: {edge.from_cluster_id} "
                    f"in round {edge.from_round_index}"
                )
                logger.error(error_msg)
                return False, error_msg

            # Check to_cluster_id exists in to_round
            to_clusters = cluster_ids_by_round[edge.to_round_index]
            if edge.to_cluster_id not in to_clusters:
                error_msg = (
                    f"Edge references non-existent to_cluster_id: {edge.to_cluster_id} "
                    f"in round {edge.to_round_index}"
                )
                logger.error(error_msg)
                return False, error_msg

        logger.debug(f"Edge references validated: {len(edges)} edges all reference valid clusters")
        return True, ""

    @staticmethod
    def validate_no_duplicate_edges(edges: List[SankeyEdge]) -> Tuple[bool, str]:
        """
        Validate that there are no duplicate edges.

        Args:
            edges: List of edges to validate

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            SC-009: Each (from_cluster_id, to_cluster_id) pair is unique
            FR-041: No duplicate participant movements (each edge represents unique transition)
        """
        if not edges:
            # No edges is valid
            return True, ""

        # Track unique edge keys
        seen_edges: Set[Tuple[UUID, UUID]] = set()
        duplicates: List[Tuple[UUID, UUID]] = []

        for edge in edges:
            edge_key = (edge.from_cluster_id, edge.to_cluster_id)
            if edge_key in seen_edges:
                duplicates.append(edge_key)
                logger.warning(
                    f"Duplicate edge detected: {edge.from_cluster_id} → {edge.to_cluster_id}"
                )
            else:
                seen_edges.add(edge_key)

        if duplicates:
            error_msg = (
                f"Found {len(duplicates)} duplicate edges: "
                f"{', '.join(f'{k[0]} → {k[1]}' for k in duplicates[:5])}"
            )
            if len(duplicates) > 5:
                error_msg += f" and {len(duplicates) - 5} more"
            logger.error(error_msg)
            return False, error_msg

        logger.debug(f"No duplicate edges: {len(edges)} unique edges")
        return True, ""

    @staticmethod
    def validate_round_consistency(
        columns: List[SankeyColumn],
        rounds: List[UUID]
    ) -> Tuple[bool, str]:
        """
        Validate that number of columns equals number of rounds.

        Args:
            columns: List of columns in the graph
            rounds: List of round UUIDs

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            SC-010: len(columns) == len(rounds) (one column per round)
            FR-011: One-to-one correspondence between columns and rounds
        """
        if not columns:
            return False, "No columns provided"

        if not rounds:
            return False, "No rounds provided"

        if len(columns) != len(rounds):
            error_msg = (
                f"Round consistency violation: {len(columns)} columns but "
                f"{len(rounds)} rounds (must be equal)"
            )
            logger.error(error_msg)
            return False, error_msg

        logger.debug(f"Round consistency validated: {len(columns)} columns = {len(rounds)} rounds")
        return True, ""

    @staticmethod
    def validate_adjacency(edges: List[SankeyEdge]) -> Tuple[bool, str]:
        """
        Validate that all edges connect adjacent rounds only.

        Args:
            edges: List of edges to validate

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            FR-039: Edges only between consecutive rounds (r → r+1)
            SC-012: No skip-round edges (prevents temporal confusion)

        Note:
            This is also validated at the Edge model level (to_round_index == from_round_index + 1),
            but we check again here for defense in depth.
        """
        if not edges:
            # No edges is valid
            return True, ""

        for edge in edges:
            if edge.to_round_index != edge.from_round_index + 1:
                error_msg = (
                    f"Adjacency violation: Edge connects non-adjacent rounds "
                    f"{edge.from_round_index} → {edge.to_round_index} "
                    f"(must be consecutive: r → r+1)"
                )
                logger.error(error_msg)
                return False, error_msg

        logger.debug(f"Adjacency validated: All {len(edges)} edges connect adjacent rounds")
        return True, ""

    @staticmethod
    def validate_single_round_no_edges(
        columns: List[SankeyColumn],
        edges: List[SankeyEdge]
    ) -> Tuple[bool, str]:
        """
        Validate that single-round graphs have no edges.

        Args:
            columns: List of columns in the graph
            edges: List of edges in the graph

        Returns:
            Tuple of (is_valid, error_message)

        Validates:
            SC-013: Single-round discussion cannot have edges (no transitions possible)
        """
        if len(columns) == 1 and len(edges) > 0:
            error_msg = (
                f"Single-round validation failure: 1 column but {len(edges)} edges "
                f"(single-round cannot have edges)"
            )
            logger.error(error_msg)
            return False, error_msg

        if len(columns) == 1:
            logger.debug("Single-round validation passed: 1 column, 0 edges")

        return True, ""

    @staticmethod
    def validate_all(sankey_graph: SankeyGraph) -> Tuple[bool, List[str]]:
        """
        Run all structural validations on a SankeyGraph.

        Args:
            sankey_graph: SankeyGraph to validate

        Returns:
            Tuple of (all_valid, list_of_errors)

        Validates:
            SC-007: Column ordering
            SC-008: Edge references
            SC-009: No duplicate edges
            SC-010: Round consistency
            SC-012: Adjacency
            SC-013: Single-round no edges
        """
        errors = []

        # Validate column ordering
        is_valid, error_msg = GraphStructureValidator.validate_column_ordering(
            sankey_graph.columns
        )
        if not is_valid:
            errors.append(error_msg)

        # Validate edge references
        is_valid, error_msg = GraphStructureValidator.validate_edge_references(
            sankey_graph.edges,
            sankey_graph.columns
        )
        if not is_valid:
            errors.append(error_msg)

        # Validate no duplicate edges
        is_valid, error_msg = GraphStructureValidator.validate_no_duplicate_edges(
            sankey_graph.edges
        )
        if not is_valid:
            errors.append(error_msg)

        # Validate round consistency
        is_valid, error_msg = GraphStructureValidator.validate_round_consistency(
            sankey_graph.columns,
            sankey_graph.rounds
        )
        if not is_valid:
            errors.append(error_msg)

        # Validate adjacency
        is_valid, error_msg = GraphStructureValidator.validate_adjacency(
            sankey_graph.edges
        )
        if not is_valid:
            errors.append(error_msg)

        # Validate single-round no edges
        is_valid, error_msg = GraphStructureValidator.validate_single_round_no_edges(
            sankey_graph.columns,
            sankey_graph.edges
        )
        if not is_valid:
            errors.append(error_msg)

        all_valid = len(errors) == 0
        if all_valid:
            logger.info("All graph structural validations passed")
        else:
            logger.error(f"Graph structural validation failed with {len(errors)} errors")

        return all_valid, errors
