"""
Sankey Column Entity - Represents a single round in the Sankey diagram

A Column contains all nodes (thought spaces/clusters) for a specific round,
organized vertically. The sum of all node user_pct values must equal 1.0
within tolerance.

Constitutional Compliance:
- Temporal Transparency: One column per round, preserves temporal ordering
- Semantic Accuracy: All clusters included as nodes (100% coverage)
- Intent Fidelity: Column shows actual participant distribution
"""

from typing import List
from pydantic import BaseModel, Field, field_validator, model_validator

from .sankey_node import SankeyNode


class SankeyColumn(BaseModel):
    """
    Represents all thought spaces (clusters) within a single round.

    Attributes:
        round_index: Round number (0-indexed, 0 = first round)
        nodes: List of nodes (clusters) in this round, ordered by user_count descending
        total_participants: Total number of unique participants in this round

    Invariants:
        - sum(node.user_pct for node in nodes) == 1.0 ± 0.0001 (percentage sum)
        - sum(node.user_count for node in nodes) == total_participants (coverage)
        - All node user_pct > 0.0 (no zero-width nodes)
        - len(nodes) >= 1 (at least one cluster per round)
    """

    round_index: int = Field(
        ...,
        ge=0,
        description="Round number (0-indexed, 0 = first round)"
    )

    nodes: List[SankeyNode] = Field(
        ...,
        min_length=1,
        description="List of nodes (clusters) in this round, typically ordered by user_count DESC"
    )

    total_participants: int = Field(
        ...,
        ge=1,
        description="Total number of unique participants in this round"
    )

    @field_validator("nodes")
    @classmethod
    def validate_nodes_not_empty(cls, v: List[SankeyNode]) -> List[SankeyNode]:
        """
        Validate that column has at least one node.

        Every round must have at least one cluster (even if all participants
        are in a single cluster).
        """
        if not v or len(v) == 0:
            raise ValueError("Column must have at least one node")
        return v

    @field_validator("total_participants")
    @classmethod
    def validate_total_participants(cls, v: int) -> int:
        """
        Validate that total_participants is positive.

        A round without participants should not exist.
        """
        if v < 1:
            raise ValueError(f"total_participants must be at least 1, got {v}")
        return v

    @model_validator(mode='after')
    def validate_percentage_sum(self):
        """
        Validate that sum of node user_pct equals 1.0 within tolerance.

        This is a critical invariant for Sankey diagram rendering - the sum
        of all node percentages must equal 100% (1.0) within 0.01% tolerance.

        SC-005: Percentage sum validation with sub-0.01% tolerance
        """
        if not self.nodes:
            raise ValueError("Cannot validate percentage sum with no nodes")

        total_pct = sum(node.user_pct for node in self.nodes)
        tolerance = 0.0001  # 0.01% tolerance

        if abs(total_pct - 1.0) > tolerance:
            raise ValueError(
                f"Sum of node user_pct must equal 1.0 ± {tolerance}, "
                f"got {total_pct:.6f} (difference: {abs(total_pct - 1.0):.6f})"
            )

        return self

    @model_validator(mode='after')
    def validate_user_count_sum(self):
        """
        Validate that sum of node user_count equals total_participants.

        This ensures 100% participant coverage - every participant must be
        assigned to exactly one cluster.

        SC-003: 100% participant coverage validation
        """
        if not self.nodes:
            raise ValueError("Cannot validate user count sum with no nodes")

        total_count = sum(node.user_count for node in self.nodes)

        if total_count != self.total_participants:
            raise ValueError(
                f"Sum of node user_count must equal total_participants, "
                f"got {total_count} != {self.total_participants}"
            )

        return self

    def get_node_by_cluster_id(self, cluster_id) -> SankeyNode | None:
        """
        Find node by cluster_id.

        Args:
            cluster_id: Cluster UUID to search for

        Returns:
            SankeyNode if found, None otherwise
        """
        for node in self.nodes:
            if node.cluster_id == cluster_id:
                return node
        return None

    def get_singleton_count(self) -> int:
        """
        Count number of singleton (outlier) nodes in this column.

        Returns:
            Number of nodes with user_count == 1
        """
        return sum(1 for node in self.nodes if node.is_singleton())

    def get_minority_count(self) -> int:
        """
        Count number of minority nodes (< 5% of participants) in this column.

        Returns:
            Number of nodes representing < 5% of round participants
        """
        return sum(1 for node in self.nodes if node.is_minority(self.total_participants))

    def get_largest_cluster_pct(self) -> float:
        """
        Get percentage of participants in the largest cluster.

        Returns:
            Maximum user_pct among all nodes (0.0 if no nodes)
        """
        if not self.nodes:
            return 0.0
        return max(node.user_pct for node in self.nodes)

    def sort_nodes_by_count(self, descending: bool = True) -> None:
        """
        Sort nodes by user_count.

        Args:
            descending: If True, sort largest to smallest (default)
        """
        self.nodes.sort(key=lambda n: n.user_count, reverse=descending)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "round_index": 0,
                    "nodes": [
                        {
                            "node_id": "123e4567-e89b-12d3-a456-426614174000",
                            "cluster_id": "123e4567-e89b-12d3-a456-426614174000",
                            "label_summary": "Focus on climate change",
                            "user_count": 12,
                            "user_pct": 0.60,
                            "display_group_id": None
                        },
                        {
                            "node_id": "223e4567-e89b-12d3-a456-426614174001",
                            "cluster_id": "223e4567-e89b-12d3-a456-426614174001",
                            "label_summary": "Prioritize economic growth",
                            "user_count": 8,
                            "user_pct": 0.40,
                            "display_group_id": None
                        }
                    ],
                    "total_participants": 20
                }
            ]
        }
    }
