"""
Cluster Quality Metrics Model

Tracks clustering quality metrics per round for continuous monitoring
and improvement validation.

Data Model Compliance:
- PERSISTED entity (metrics stored for historical analysis)
- One metric record per round (created after clustering completes)
- Immutable after creation (quality metrics are snapshots)

Use Cases:
- Monitor clustering quality over time
- Validate improvements after parameter tuning
- Identify rounds with poor semantic grouping
- Track near-duplicate trends
"""

from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.database import Base


class ClusterQualityMetric(Base):
    """
    Quality metrics for a clustering result.

    Lifecycle:
    - Created: After clustering workflow completes
    - Read: For monitoring dashboards, quality reports
    - Updated: Never (immutable snapshot)
    - Deleted: When round is deleted (CASCADE)

    Metrics:
    - silhouette_score: [-1, 1], higher = better separated clusters
    - davies_bouldin_index: [0, ∞], lower = better separated clusters
    - near_duplicate_count: Number of high-similarity cluster pairs (>0.8)
    - singleton_count: Number of single-member clusters (minority preservation)
    - within_cluster_cohesion: Average semantic similarity within clusters
    """

    __tablename__ = "cluster_quality_metrics"

    # Primary Key
    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Key
    round_id = Column(
        UUID(as_uuid=True),
        ForeignKey("rounds.round_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Quality Metrics
    silhouette_score = Column(
        Float,
        nullable=True,
        comment="Silhouette score: [-1, 1], higher is better"
    )

    davies_bouldin_index = Column(
        Float,
        nullable=True,
        comment="Davies-Bouldin index: [0, ∞], lower is better"
    )

    near_duplicate_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Count of cluster pairs with >0.8 similarity"
    )

    singleton_count = Column(
        Integer,
        nullable=False,
        comment="Number of single-member clusters"
    )

    avg_cluster_size = Column(
        Float,
        nullable=False,
        comment="Average participants per cluster"
    )

    min_within_cluster_cohesion = Column(
        Float,
        nullable=True,
        comment="Minimum intra-cluster similarity"
    )

    max_within_cluster_cohesion = Column(
        Float,
        nullable=True,
        comment="Maximum intra-cluster similarity"
    )

    avg_within_cluster_cohesion = Column(
        Float,
        nullable=True,
        comment="Average intra-cluster similarity"
    )

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    round = relationship("Round", back_populates="cluster_quality_metrics")

    # Indexes
    __table_args__ = (
        Index("idx_quality_metrics_round", "round_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ClusterQualityMetric(round={self.round_id}, "
            f"silhouette={self.silhouette_score:.3f}, "
            f"db_index={self.davies_bouldin_index:.3f}, "
            f"near_duplicates={self.near_duplicate_count})>"
        )

    def is_good_quality(self) -> bool:
        """
        Check if clustering quality is acceptable.

        Criteria:
        - Silhouette score > 0.4
        - Davies-Bouldin index < 1.5
        - Near-duplicate count < 5 per round

        Returns:
            bool: True if quality is acceptable, False otherwise
        """
        return (
            self.silhouette_score is not None
            and self.silhouette_score > 0.4
            and self.davies_bouldin_index is not None
            and self.davies_bouldin_index < 1.5
            and self.near_duplicate_count < 5
        )

    def has_over_fragmentation(self) -> bool:
        """
        Check if clustering shows signs of over-fragmentation.

        Indicators:
        - High near-duplicate count (>10)
        - Very high silhouette score (>0.7) with many near-duplicates

        Returns:
            bool: True if over-fragmented, False otherwise
        """
        return (
            self.near_duplicate_count > 10
            or (
                self.silhouette_score is not None
                and self.silhouette_score > 0.7
                and self.near_duplicate_count > 5
            )
        )
