"""
Sankey Node Entity - Represents a thought space (cluster) in a specific round

A Node corresponds to a single cluster from Spec 004, with width proportional to
the number of participants in that cluster. Nodes are organized into columns
(one column per round).

Constitutional Compliance:
- Semantic Accuracy Over Aesthetics: All clusters preserved as nodes, no merging
- Intent Fidelity: Uses label_summary from Spec 004 medoid (actual participant text)
- Temporal Transparency: user_pct calculated per-round (no normalization across rounds)
"""

from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class SankeyNode(BaseModel):
    """
    Represents a single thought space (cluster) within a round column.

    Attributes:
        node_id: Unique identifier for this node (typically cluster_id from Spec 004)
        cluster_id: Reference to the cluster entity from Spec 004
        label_summary: Text label for this node (medoid summary from Spec 004)
        user_count: Number of participants in this cluster (must be >= 1)
        user_pct: Percentage of round participants in this cluster (0.0 to 1.0]
        display_group_id: Optional alignment group ID for color continuity (from Spec 004 alignment)

    Invariants:
        - user_count >= 1 (even singleton outliers have 1 participant)
        - 0.0 < user_pct <= 1.0 (percentage must be positive and at most 100%)
        - label_summary is non-empty (every cluster has a medoid label)
    """

    node_id: UUID = Field(
        ...,
        description="Unique identifier for this node (cluster_id from Spec 004)"
    )

    cluster_id: UUID = Field(
        ...,
        description="Reference to the cluster entity in Spec 004 database"
    )

    label_summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Human-readable label from cluster medoid (actual participant text)"
    )

    user_count: int = Field(
        ...,
        ge=1,
        description="Number of participants in this cluster (positive integer)"
    )

    user_pct: float = Field(
        ...,
        gt=0.0,
        le=1.0,
        description="Percentage of round participants in this cluster (0.0, 1.0]"
    )

    display_group_id: Optional[UUID] = Field(
        default=None,
        description="Alignment group ID for visual continuity across rounds (nullable)"
    )

    @field_validator("user_pct")
    @classmethod
    def validate_user_pct(cls, v: float) -> float:
        """
        Validate that user_pct is in valid range (0.0, 1.0].

        This validation is redundant with Field constraints but provides
        explicit error messages for debugging.
        """
        if v <= 0.0:
            raise ValueError(f"user_pct must be positive, got {v}")
        if v > 1.0:
            raise ValueError(f"user_pct cannot exceed 1.0, got {v}")
        return v

    @field_validator("user_count")
    @classmethod
    def validate_user_count(cls, v: int) -> int:
        """
        Validate that user_count is at least 1.

        Even singleton outlier clusters must have exactly 1 participant.
        """
        if v < 1:
            raise ValueError(f"user_count must be at least 1, got {v}")
        return v

    @field_validator("label_summary")
    @classmethod
    def validate_label_summary(cls, v: str) -> str:
        """
        Validate that label_summary is non-empty.

        Every cluster must have a medoid-based label from Spec 004.
        """
        if not v or not v.strip():
            raise ValueError("label_summary cannot be empty")
        return v.strip()

    def is_singleton(self) -> bool:
        """
        Check if this node represents a singleton outlier cluster.

        Returns:
            True if user_count == 1 (outlier), False otherwise
        """
        return self.user_count == 1

    def is_minority(self, total_participants: int) -> bool:
        """
        Check if this node represents a minority cluster (< 5% of round).

        Args:
            total_participants: Total number of participants in the round

        Returns:
            True if cluster has < 5% of participants, False otherwise
        """
        if total_participants <= 0:
            return False
        return (self.user_count / total_participants) < 0.05

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "node_id": "123e4567-e89b-12d3-a456-426614174000",
                    "cluster_id": "123e4567-e89b-12d3-a456-426614174000",
                    "label_summary": "We should focus on climate change mitigation",
                    "user_count": 12,
                    "user_pct": 0.24,
                    "display_group_id": "987fcdeb-51a2-43d1-b987-123456789abc"
                },
                {
                    "node_id": "223e4567-e89b-12d3-a456-426614174001",
                    "cluster_id": "223e4567-e89b-12d3-a456-426614174001",
                    "label_summary": "Economic growth is the priority",
                    "user_count": 1,
                    "user_pct": 0.02,
                    "display_group_id": None
                }
            ]
        }
    }
