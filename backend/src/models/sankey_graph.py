"""
SankeyGraph Entity - Complete Sankey diagram data structure

The SankeyGraph is the top-level entity representing the entire multi-round
discussion visualization. It contains all columns (rounds), nodes (thought spaces),
and edges (participant movements).

Constitutional Compliance:
- Temporal Transparency: Preserves temporal ordering of rounds
- Semantic Accuracy: All clusters represented as nodes (100% coverage)
- Movement-Based: Edges computed from actual participant transitions
- Representation Not Adjudication: Pure visualization, no rankings or scores
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator

from .sankey_column import SankeyColumn
from .sankey_edge import SankeyEdge


class SankeyGraph(BaseModel):
    """
    Complete Sankey diagram for a multi-round discussion.

    Attributes:
        discussion_id: Discussion UUID (from Spec 001)
        rounds: List of round UUIDs in temporal order
        columns: List of columns (one per round) with nodes
        edges: List of edges connecting nodes in adjacent rounds
        created_at: Timestamp when graph was constructed
        metadata: Optional additional metadata (e.g., construction time, algorithm version)

    Invariants:
        - len(columns) == len(rounds) (one column per round)
        - All edges reference valid rounds (from_round_index and to_round_index within bounds)
        - All edges connect adjacent rounds only (to_round_index == from_round_index + 1)
        - Columns are ordered by round_index (0, 1, 2, ...)
        - No duplicate edges (same from_cluster_id and to_cluster_id)
    """

    discussion_id: UUID = Field(
        ...,
        description="Discussion UUID (from Spec 001 discussions table)"
    )

    rounds: List[UUID] = Field(
        ...,
        min_length=1,
        description="List of round UUIDs in temporal order (first round at index 0)"
    )

    columns: List[SankeyColumn] = Field(
        ...,
        min_length=1,
        description="List of columns (one per round), ordered by round_index"
    )

    edges: List[SankeyEdge] = Field(
        default_factory=list,
        description="List of edges connecting nodes in adjacent rounds (empty for single-round)"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when this graph was constructed"
    )

    metadata: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional metadata (construction_time_ms, algorithm_version, etc.)"
    )

    @field_validator("rounds")
    @classmethod
    def validate_rounds_not_empty(cls, v: List[UUID]) -> List[UUID]:
        """
        Validate that there is at least one round.

        A discussion without rounds should not have a Sankey graph.
        """
        if not v or len(v) == 0:
            raise ValueError("Discussion must have at least one round")
        return v

    @field_validator("columns")
    @classmethod
    def validate_columns_not_empty(cls, v: List[SankeyColumn]) -> List[SankeyColumn]:
        """
        Validate that there is at least one column.

        A Sankey graph must have at least one column (even for single-round).
        """
        if not v or len(v) == 0:
            raise ValueError("SankeyGraph must have at least one column")
        return v

    @model_validator(mode='after')
    def validate_columns_match_rounds(self):
        """
        Validate that number of columns equals number of rounds.

        This is a critical structural invariant - there must be exactly one
        column per round.
        """
        if len(self.columns) != len(self.rounds):
            raise ValueError(
                f"Number of columns ({len(self.columns)}) must equal "
                f"number of rounds ({len(self.rounds)})"
            )
        return self

    @model_validator(mode='after')
    def validate_column_ordering(self):
        """
        Validate that columns are ordered by round_index (0, 1, 2, ...).

        Columns must be in temporal order for correct Sankey rendering.
        """
        for i, column in enumerate(self.columns):
            if column.round_index != i:
                raise ValueError(
                    f"Column at index {i} has round_index {column.round_index}, "
                    f"expected {i}. Columns must be ordered by round_index."
                )
        return self

    @model_validator(mode='after')
    def validate_edge_round_references(self):
        """
        Validate that all edges reference valid round indices.

        Every edge must reference existing columns (rounds) in the graph.
        """
        max_round_index = len(self.columns) - 1

        for edge in self.edges:
            if edge.from_round_index < 0 or edge.from_round_index > max_round_index:
                raise ValueError(
                    f"Edge from_round_index {edge.from_round_index} is out of bounds. "
                    f"Valid range: [0, {max_round_index}]"
                )
            if edge.to_round_index < 0 or edge.to_round_index > max_round_index:
                raise ValueError(
                    f"Edge to_round_index {edge.to_round_index} is out of bounds. "
                    f"Valid range: [0, {max_round_index}]"
                )

        return self

    @model_validator(mode='after')
    def validate_edges_for_single_round(self):
        """
        Validate that single-round graphs have no edges.

        A discussion with only one round cannot have edges (no transitions).
        """
        if len(self.columns) == 1 and len(self.edges) > 0:
            raise ValueError(
                f"Single-round graph cannot have edges, got {len(self.edges)} edges"
            )
        return self

    def get_column(self, round_index: int) -> SankeyColumn | None:
        """
        Get column by round index.

        Args:
            round_index: Round index (0-indexed)

        Returns:
            SankeyColumn if found, None if out of bounds
        """
        if round_index < 0 or round_index >= len(self.columns):
            return None
        return self.columns[round_index]

    def get_edges_from_round(self, round_index: int) -> List[SankeyEdge]:
        """
        Get all edges originating from a specific round.

        Args:
            round_index: Source round index

        Returns:
            List of edges with from_round_index == round_index
        """
        return [edge for edge in self.edges if edge.from_round_index == round_index]

    def get_edges_to_round(self, round_index: int) -> List[SankeyEdge]:
        """
        Get all edges terminating at a specific round.

        Args:
            round_index: Destination round index

        Returns:
            List of edges with to_round_index == round_index
        """
        return [edge for edge in self.edges if edge.to_round_index == round_index]

    def get_total_participants(self) -> int:
        """
        Get total unique participants across all rounds.

        Note: This may not equal the sum of column.total_participants due to dropout.

        Returns:
            Maximum participant count across all columns
        """
        if not self.columns:
            return 0
        return max(col.total_participants for col in self.columns)

    def get_dropout_rate(self) -> float:
        """
        Calculate overall dropout rate from first to last round.

        Returns:
            Dropout rate as percentage (0.0 to 1.0), or 0.0 for single-round
        """
        if len(self.columns) < 2:
            return 0.0

        first_round_participants = self.columns[0].total_participants
        last_round_participants = self.columns[-1].total_participants

        if first_round_participants == 0:
            return 0.0

        dropout_count = first_round_participants - last_round_participants
        return dropout_count / first_round_participants

    def get_round_count(self) -> int:
        """
        Get number of rounds in this discussion.

        Returns:
            Number of columns/rounds
        """
        return len(self.columns)

    def get_edge_count(self) -> int:
        """
        Get total number of edges in this graph.

        Returns:
            Number of participant movement edges
        """
        return len(self.edges)

    def get_total_node_count(self) -> int:
        """
        Get total number of nodes across all columns.

        Returns:
            Sum of nodes in all columns
        """
        return sum(len(col.nodes) for col in self.columns)

    def is_single_round(self) -> bool:
        """
        Check if this is a single-round discussion.

        Returns:
            True if only one round, False otherwise
        """
        return len(self.columns) == 1

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "discussion_id": "987fcdeb-51a2-43d1-b987-123456789abc",
                    "rounds": [
                        "123e4567-e89b-12d3-a456-426614174000",
                        "223e4567-e89b-12d3-a456-426614174001"
                    ],
                    "columns": [
                        {
                            "round_index": 0,
                            "nodes": [
                                {
                                    "node_id": "n1",
                                    "cluster_id": "c1",
                                    "label_summary": "Climate action",
                                    "user_count": 12,
                                    "user_pct": 0.6,
                                    "display_group_id": None
                                },
                                {
                                    "node_id": "n2",
                                    "cluster_id": "c2",
                                    "label_summary": "Economic growth",
                                    "user_count": 8,
                                    "user_pct": 0.4,
                                    "display_group_id": None
                                }
                            ],
                            "total_participants": 20
                        }
                    ],
                    "edges": [],
                    "created_at": "2026-02-05T12:00:00Z",
                    "metadata": {
                        "construction_time_ms": "450",
                        "algorithm_version": "1.0"
                    }
                }
            ]
        }
    }
