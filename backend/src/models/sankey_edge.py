"""
Sankey Edge Entity - Represents participant movement between thought spaces

An Edge connects two nodes (clusters) in adjacent rounds, with width proportional
to the number of participants who moved from one cluster to another. Edges are
computed from actual participant assignments across rounds.

Constitutional Compliance:
- Temporal Transparency: Edges computed from actual participant movement, not similarity
- Semantic Accuracy: Edge widths reflect real behavioral transitions
- Movement-Based: Uses participant tracking data from Spec 004
"""

from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator


class SankeyEdge(BaseModel):
    """
    Represents participant flow between two clusters in adjacent rounds.

    Attributes:
        from_round_index: Source round index (0-indexed)
        to_round_index: Destination round index (must be from_round_index + 1)
        from_cluster_id: Source cluster UUID (from Spec 004)
        to_cluster_id: Destination cluster UUID (from Spec 004)
        user_count: Number of participants who made this transition
        pct_of_from: Optional percentage of source cluster that moved to destination
        pct_of_to: Optional percentage of destination cluster that came from source

    Invariants:
        - to_round_index == from_round_index + 1 (only adjacent rounds)
        - user_count >= 1 (edge exists only if at least 1 participant moved)
        - 0.0 < pct_of_from <= 1.0 (if provided)
        - 0.0 < pct_of_to <= 1.0 (if provided)
    """

    from_round_index: int = Field(
        ...,
        ge=0,
        description="Source round index (0-indexed, 0 = first round)"
    )

    to_round_index: int = Field(
        ...,
        ge=1,
        description="Destination round index (must be from_round_index + 1)"
    )

    from_cluster_id: UUID = Field(
        ...,
        description="Source cluster UUID (from Spec 004 clusters table)"
    )

    to_cluster_id: UUID = Field(
        ...,
        description="Destination cluster UUID (from Spec 004 clusters table)"
    )

    user_count: int = Field(
        ...,
        ge=1,
        description="Number of participants who moved from source to destination"
    )

    pct_of_from: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=1.0,
        description="Percentage of source cluster that moved to destination (optional)"
    )

    pct_of_to: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=1.0,
        description="Percentage of destination cluster that came from source (optional)"
    )

    @model_validator(mode='after')
    def validate_adjacent_rounds(self):
        """
        Validate that edge connects adjacent rounds only.

        Sankey edges only exist between consecutive rounds (r → r+1).
        This enforces temporal ordering and prevents skip-round connections.
        """
        if self.to_round_index != self.from_round_index + 1:
            raise ValueError(
                f"Edge must connect adjacent rounds: "
                f"to_round_index ({self.to_round_index}) must equal "
                f"from_round_index ({self.from_round_index}) + 1"
            )
        return self

    @field_validator("user_count")
    @classmethod
    def validate_user_count(cls, v: int) -> int:
        """
        Validate that at least 1 participant moved along this edge.

        Edges with zero participants should not exist in the graph.
        """
        if v < 1:
            raise ValueError(f"user_count must be at least 1, got {v}")
        return v

    @field_validator("from_cluster_id", "to_cluster_id")
    @classmethod
    def validate_cluster_ids_not_empty(cls, v: UUID) -> UUID:
        """
        Validate that cluster UUIDs are not nil/empty.

        Every edge must reference valid clusters from Spec 004.
        """
        if v is None:
            raise ValueError("cluster_id cannot be None")
        return v

    def is_self_loop(self) -> bool:
        """
        Check if this edge represents a self-loop (same cluster ID across rounds).

        Note: This should generally not happen unless Spec 004 reuses cluster IDs
        across rounds, which violates round independence. Included for defensive
        programming.

        Returns:
            True if from_cluster_id == to_cluster_id, False otherwise
        """
        return self.from_cluster_id == self.to_cluster_id

    def is_split_edge(self, source_total: int) -> bool:
        """
        Check if this edge is part of a split (1-to-many mapping).

        A split occurs when a single source cluster feeds multiple destination
        clusters in the next round.

        Args:
            source_total: Total participants in the source cluster

        Returns:
            True if this edge represents < 100% of source cluster, False otherwise
        """
        if source_total <= 0:
            return False
        return self.user_count < source_total

    def is_merge_edge(self, dest_total: int) -> bool:
        """
        Check if this edge is part of a merge (many-to-1 mapping).

        A merge occurs when multiple source clusters feed a single destination
        cluster in the next round.

        Args:
            dest_total: Total participants in the destination cluster

        Returns:
            True if this edge represents < 100% of destination cluster, False otherwise
        """
        if dest_total <= 0:
            return False
        return self.user_count < dest_total

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "from_round_index": 0,
                    "to_round_index": 1,
                    "from_cluster_id": "123e4567-e89b-12d3-a456-426614174000",
                    "to_cluster_id": "223e4567-e89b-12d3-a456-426614174001",
                    "user_count": 5,
                    "pct_of_from": 0.42,
                    "pct_of_to": 0.36
                },
                {
                    "from_round_index": 1,
                    "to_round_index": 2,
                    "from_cluster_id": "323e4567-e89b-12d3-a456-426614174002",
                    "to_cluster_id": "423e4567-e89b-12d3-a456-426614174003",
                    "user_count": 1,
                    "pct_of_from": None,
                    "pct_of_to": None
                }
            ]
        }
    }
