"""
Discussion Report Entities - Comprehensive post-discussion analysis

The DiscussionReport combines the SankeyGraph visualization with statistical
summaries, participant dropout tracking, and top movement identification.
This is the primary artifact exported for analysis and archival.

Constitutional Compliance:
- Representation Not Adjudication: Reports show data without rankings or judgments
- Temporal Transparency: Dropout curve shows honest participant engagement
- Intent Fidelity: All summaries from actual participant text
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from .sankey_graph import SankeyGraph


class ClusterInfo(BaseModel):
    """
    Basic information about a single cluster within a round.

    Attributes:
        cluster_id: Cluster UUID from Spec 004
        label: Medoid summary text
        user_count: Number of participants
        user_pct: Percentage of round participants
    """

    cluster_id: UUID = Field(
        ...,
        description="Cluster UUID from Spec 004"
    )

    label: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Medoid summary text (actual participant language)"
    )

    user_count: int = Field(
        ...,
        ge=1,
        description="Number of participants in this cluster"
    )

    user_pct: float = Field(
        ...,
        gt=0.0,
        le=1.0,
        description="Percentage of round participants in this cluster"
    )


class RoundClusterSummary(BaseModel):
    """
    Summary of all clusters within a single round.

    Attributes:
        round_index: Round number (0-indexed)
        round_id: Round UUID from Spec 001
        total_participants: Total participants in this round
        cluster_count: Number of distinct clusters
        clusters: List of cluster details
        singleton_count: Number of singleton (outlier) clusters
        largest_cluster_pct: Percentage in largest cluster
    """

    round_index: int = Field(
        ...,
        ge=0,
        description="Round number (0-indexed, 0 = first round)"
    )

    round_id: UUID = Field(
        ...,
        description="Round UUID from Spec 001 rounds table"
    )

    total_participants: int = Field(
        ...,
        ge=1,
        description="Total unique participants in this round"
    )

    cluster_count: int = Field(
        ...,
        ge=1,
        description="Number of distinct thought spaces (clusters)"
    )

    clusters: List[ClusterInfo] = Field(
        ...,
        min_length=1,
        description="List of clusters in this round, ordered by user_count DESC"
    )

    singleton_count: int = Field(
        ...,
        ge=0,
        description="Number of singleton (outlier) clusters (user_count = 1)"
    )

    largest_cluster_pct: float = Field(
        ...,
        gt=0.0,
        le=1.0,
        description="Percentage of participants in the largest cluster"
    )


class DropoutPoint(BaseModel):
    """
    Participant count for a single round (for dropout curve).

    Attributes:
        round_index: Round number (0-indexed)
        participant_count: Number of participants who submitted in this round
    """

    round_index: int = Field(
        ...,
        ge=0,
        description="Round number (0-indexed)"
    )

    participant_count: int = Field(
        ...,
        ge=0,
        description="Number of participants who submitted in this round"
    )


class MovementDetail(BaseModel):
    """
    Details about a specific participant movement between clusters.

    Attributes:
        from_cluster_id: Source cluster UUID
        from_label: Source cluster label (truncated)
        to_cluster_id: Destination cluster UUID
        to_label: Destination cluster label (truncated)
        participant_count: Number of participants who made this transition
        pct_of_from: Percentage of source cluster that moved to destination
        pct_of_to: Percentage of destination cluster that came from source
    """

    from_cluster_id: UUID = Field(
        ...,
        description="Source cluster UUID"
    )

    from_label: str = Field(
        ...,
        max_length=100,
        description="Source cluster label (truncated for display)"
    )

    to_cluster_id: UUID = Field(
        ...,
        description="Destination cluster UUID"
    )

    to_label: str = Field(
        ...,
        max_length=100,
        description="Destination cluster label (truncated for display)"
    )

    participant_count: int = Field(
        ...,
        ge=1,
        description="Number of participants who made this transition"
    )

    pct_of_from: float = Field(
        ...,
        gt=0.0,
        le=1.0,
        description="Percentage of source cluster that moved to destination"
    )

    pct_of_to: float = Field(
        ...,
        gt=0.0,
        le=1.0,
        description="Percentage of destination cluster that came from source"
    )


class TopMovement(BaseModel):
    """
    Top participant movements for a specific round transition.

    Attributes:
        from_round_index: Source round index
        to_round_index: Destination round index (from_round_index + 1)
        movements: List of top movements (up to 5), ordered by participant_count DESC
        total_transitions: Total number of distinct transitions between these rounds
    """

    from_round_index: int = Field(
        ...,
        ge=0,
        description="Source round index"
    )

    to_round_index: int = Field(
        ...,
        ge=1,
        description="Destination round index (must be from_round_index + 1)"
    )

    movements: List[MovementDetail] = Field(
        ...,
        max_length=5,
        description="List of top movements, ordered by participant_count DESC (max 5)"
    )

    total_transitions: int = Field(
        ...,
        ge=0,
        description="Total number of distinct cluster-to-cluster transitions"
    )


class DiscussionReport(BaseModel):
    """
    Comprehensive discussion report with Sankey diagram and statistics.

    This is the primary artifact for post-discussion analysis and archival.
    Combines visual representation (SankeyGraph) with quantitative summaries.

    Attributes:
        discussion_id: Discussion UUID
        sankey_graph: Complete Sankey diagram with nodes and edges
        cluster_summaries: Per-round cluster statistics
        dropout_curve: Participant counts per round (for dropout visualization)
        top_movements: Top participant transitions between rounds
        generated_at: Report generation timestamp
        export_format: Format version for compatibility (e.g., "json-v1")
    """

    discussion_id: UUID = Field(
        ...,
        description="Discussion UUID from Spec 001"
    )

    sankey_graph: SankeyGraph = Field(
        ...,
        description="Complete Sankey diagram with columns, nodes, and edges"
    )

    cluster_summaries: List[RoundClusterSummary] = Field(
        ...,
        min_length=1,
        description="Per-round cluster statistics, ordered by round_index"
    )

    dropout_curve: List[DropoutPoint] = Field(
        ...,
        min_length=1,
        description="Participant counts per round for dropout visualization"
    )

    top_movements: List[TopMovement] = Field(
        default_factory=list,
        description="Top participant transitions for each round pair (empty for single-round)"
    )

    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Report generation timestamp"
    )

    export_format: str = Field(
        default="json-v1",
        description="Format version for compatibility (e.g., 'json-v1')"
    )

    def get_total_rounds(self) -> int:
        """
        Get total number of rounds in this discussion.

        Returns:
            Number of rounds
        """
        return len(self.cluster_summaries)

    def get_initial_participants(self) -> int:
        """
        Get number of participants in first round.

        Returns:
            Participant count in round 0
        """
        if not self.cluster_summaries:
            return 0
        return self.cluster_summaries[0].total_participants

    def get_final_participants(self) -> int:
        """
        Get number of participants in last round.

        Returns:
            Participant count in final round
        """
        if not self.cluster_summaries:
            return 0
        return self.cluster_summaries[-1].total_participants

    def get_total_dropout(self) -> int:
        """
        Calculate total participant dropout (first round - last round).

        Returns:
            Number of participants who dropped out
        """
        return self.get_initial_participants() - self.get_final_participants()

    def get_dropout_rate(self) -> float:
        """
        Calculate dropout rate as percentage.

        Returns:
            Dropout rate (0.0 to 1.0), or 0.0 if no initial participants
        """
        initial = self.get_initial_participants()
        if initial == 0:
            return 0.0
        return self.get_total_dropout() / initial

    def get_average_cluster_count(self) -> float:
        """
        Calculate average number of clusters per round.

        Returns:
            Average cluster count across all rounds
        """
        if not self.cluster_summaries:
            return 0.0
        total_clusters = sum(summary.cluster_count for summary in self.cluster_summaries)
        return total_clusters / len(self.cluster_summaries)

    def get_total_singleton_count(self) -> int:
        """
        Calculate total singleton (outlier) clusters across all rounds.

        Returns:
            Total number of singleton clusters
        """
        return sum(summary.singleton_count for summary in self.cluster_summaries)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "discussion_id": "987fcdeb-51a2-43d1-b987-123456789abc",
                    "sankey_graph": {
                        "discussion_id": "987fcdeb-51a2-43d1-b987-123456789abc",
                        "rounds": ["r1"],
                        "columns": [
                            {
                                "round_index": 0,
                                "nodes": [],
                                "total_participants": 20
                            }
                        ],
                        "edges": [],
                        "created_at": "2026-02-05T12:00:00Z",
                        "metadata": {}
                    },
                    "cluster_summaries": [
                        {
                            "round_index": 0,
                            "round_id": "r1",
                            "total_participants": 20,
                            "cluster_count": 3,
                            "clusters": [],
                            "singleton_count": 1,
                            "largest_cluster_pct": 0.6
                        }
                    ],
                    "dropout_curve": [
                        {"round_index": 0, "participant_count": 20}
                    ],
                    "top_movements": [],
                    "generated_at": "2026-02-05T12:05:00Z",
                    "export_format": "json-v1"
                }
            ]
        }
    }
