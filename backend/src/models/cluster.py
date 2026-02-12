"""
Cluster Entity Model - Spec 004 Clustering & Alignment

Represents a semantic grouping of approved summaries (thought space).
Core aggregation unit for Sankey visualization in Spec 5.

Data Model Compliance:
- PERSISTED entity (clusters stored for visualization)
- One-to-many with ClusterMember (cluster has multiple members)
- Immutable after creation (clustering determinism)
- Centroids stored for cross-round alignment (FR-026, FR-027)

Constitutional Guarantees:
- Semantic Accuracy Over Aesthetics: No minimum cluster size, singletons preserved (FR-012, SC-004)
- Intent Fidelity: Every participant assigned to exactly one cluster (FR-016, SC-003)
- Temporal Transparency: user_pct sum across clusters = 1.0 (FR-019, SC-005)

Cluster Types:
- Regular Cluster: user_count >= 2 (normal semantic grouping)
- Singleton Cluster: user_count = 1 (outlier converted per FR-014)
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import numpy as np
from typing import Optional, List

from src.database import Base


class Cluster(Base):
    """
    Semantic cluster of approved summaries (thought space).

    Lifecycle:
    - Created: After HDBSCAN clustering completes for a round
    - Read: By Spec 5 (Sankey Construction) for visualization, by alignment service
    - Updated: Never (immutable once created)
    - Deleted: When round is deleted (CASCADE)

    Validation Rules:
    - user_count equals number of unique user_id in cluster_members (FR-018)
    - user_pct sum across all clusters in round must equal 1.0 ± 0.0001 (FR-019, SC-005)
    - label_summary_id must be a member of this cluster (medoid is a cluster member)
    - centroid_vector must be mean of member embedding vectors (FR-027)
    - cluster_id unique within round (may reuse across rounds per FR-041)

    Invariants:
    - Every participant assigned to exactly one cluster per round (FR-016, SC-003)
    - No minimum cluster size enforced (FR-012, SC-004)
    - All clusters visible (no hiding of singletons per FR-015)
    """

    __tablename__ = "clusters"

    # Primary Key
    cluster_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    round_id = Column(
        UUID(as_uuid=True),
        ForeignKey("rounds.round_id", ondelete="CASCADE"),
        nullable=False,
    )

    label_summary_id = Column(
        UUID(as_uuid=True),
        ForeignKey("approved_summaries.summary_id"),
        nullable=False,
        comment="Medoid summary used as cluster label (actual participant text)",
    )

    # Core Fields
    user_count = Column(
        Integer,
        nullable=False,
        comment="Number of participants in this cluster",
    )

    user_pct = Column(
        Float,
        nullable=False,
        comment="Percentage of total participants (sum across round = 1.0)",
    )

    centroid_vector = Column(
        String,  # Stored as pgvector type in migration
        nullable=False,
        comment="Mean embedding vector of member summaries (384-dim)",
    )

    display_group_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Visual grouping ID for cross-round alignment continuity (from AlignmentMap)",
    )

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    round = relationship("Round", back_populates="clusters")
    label_summary = relationship("ApprovedSummary", foreign_keys=[label_summary_id], overlaps="approved_summaries")
    members = relationship("ClusterMember", back_populates="cluster", cascade="all, delete-orphan")
    approved_summaries = relationship("ApprovedSummary", foreign_keys="ApprovedSummary.cluster_id", back_populates="cluster", overlaps="label_summary")
    outgoing_flows = relationship("Flow", foreign_keys="Flow.source_cluster_id", back_populates="source_cluster")
    incoming_flows = relationship("Flow", foreign_keys="Flow.target_cluster_id", back_populates="target_cluster")

    # Indexes for performance
    __table_args__ = (
        # Find all clusters in a round (for visualization, percentage sum validation)
        Index("idx_clusters_round", "round_id"),
        # Find cluster by label summary (for medoid validation)
        Index("idx_clusters_label_summary", "label_summary_id"),
        # Find clusters by display group (for alignment visual continuity)
        Index("idx_clusters_display_group", "display_group_id"),
        # Constraints
        CheckConstraint("user_count > 0", name="chk_cluster_user_count_positive"),
        CheckConstraint("user_pct > 0 AND user_pct <= 1.0", name="chk_cluster_user_pct_range"),
    )

    def __repr__(self) -> str:
        return (
            f"<Cluster(id={self.cluster_id}, "
            f"round={self.round_id}, "
            f"user_count={self.user_count}, "
            f"user_pct={self.user_pct:.3f}, "
            f"display_group={self.display_group_id})>"
        )

    def is_singleton(self) -> bool:
        """
        Check if this is a singleton cluster (outlier converted).

        Returns:
            bool: True if user_count = 1, False otherwise

        Constitutional Guarantee (FR-014, FR-015):
        - Outliers (HDBSCAN noise points) converted to singleton clusters
        - All singletons visible (no hiding for aesthetics)
        """
        return self.user_count == 1

    def get_centroid_as_numpy(self) -> np.ndarray:
        """
        Get centroid vector as NumPy array.

        Returns:
            np.ndarray: 384-dimensional centroid vector

        Usage:
            cluster = db.query(Cluster).first()
            centroid = cluster.get_centroid_as_numpy()
            # Use for alignment similarity computation
        """
        # Remove brackets and split by comma
        vector_str = self.centroid_vector.strip("[]")
        values = [float(v.strip()) for v in vector_str.split(",")]
        return np.array(values, dtype=np.float32)

    def set_centroid_from_numpy(self, centroid: np.ndarray) -> None:
        """
        Set centroid vector from NumPy array.

        Args:
            centroid: 384-dimensional NumPy array (mean of member embeddings)

        Raises:
            ValueError: If centroid dimensions are invalid
            RuntimeError: If centroid already set (immutability check)

        Validation Rule (FR-027):
        - Centroid must be mean of member embedding vectors
        - 384 dimensions (same as SBERT embeddings)
        """
        if self.centroid_vector is not None:
            raise RuntimeError(
                "Centroid is immutable - cannot modify after creation. "
                "Clusters are immutable once persisted."
            )

        if centroid.shape != (384,):
            raise ValueError(f"Centroid must be 384-dimensional, got {centroid.shape}")

        # Serialize to pgvector format
        centroid_list = centroid.tolist()
        self.centroid_vector = "[" + ",".join(str(v) for v in centroid_list) + "]"

    @classmethod
    async def validate_percentage_sum(
        cls, db_session, round_id: uuid.UUID, tolerance: float = 0.0001
    ) -> bool:
        """
        Validate that user_pct sum for all clusters in a round equals 1.0.

        Args:
            db_session: AsyncSession for database operations
            round_id: UUID of the round
            tolerance: Acceptable deviation from 1.0 (default: 0.0001)

        Returns:
            bool: True if sum is within tolerance of 1.0, False otherwise

        Validation Rule (FR-019, SC-005):
        - Sum of user_pct across all clusters in a round must equal 1.0 ± 0.0001
        - Constitutional guarantee: 100% participant coverage
        """
        from sqlalchemy import select, func

        result = await db_session.execute(
            select(func.sum(cls.user_pct)).where(cls.round_id == round_id)
        )
        total_pct = result.scalar()

        if total_pct is None:
            return False  # No clusters found

        return abs(total_pct - 1.0) < tolerance

    @classmethod
    async def get_by_round(cls, db_session, round_id: uuid.UUID) -> List["Cluster"]:
        """
        Retrieve all clusters for a round.

        Args:
            db_session: AsyncSession for database operations
            round_id: UUID of the round

        Returns:
            List[Cluster]: All clusters in the round, ordered by user_count descending

        Usage:
            clusters = await Cluster.get_by_round(db, round_id)
            for cluster in clusters:
                print(f"Cluster {cluster.cluster_id}: {cluster.user_count} users")
        """
        from sqlalchemy import select

        result = await db_session.execute(
            select(cls)
            .where(cls.round_id == round_id)
            .order_by(cls.user_count.desc())
        )
        return result.scalars().all()

    @classmethod
    async def get_by_id(cls, db_session, cluster_id: uuid.UUID) -> Optional["Cluster"]:
        """
        Retrieve cluster by cluster_id.

        Args:
            db_session: AsyncSession for database operations
            cluster_id: UUID of the cluster

        Returns:
            Cluster if found, None otherwise

        Usage:
            cluster = await Cluster.get_by_id(db, cluster_id)
            if cluster:
                print(f"Cluster has {cluster.user_count} members")
        """
        from sqlalchemy import select

        result = await db_session.execute(
            select(cls).where(cls.cluster_id == cluster_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def create(
        cls,
        db_session,
        round_id: uuid.UUID,
        user_count: int,
        user_pct: float,
        label_summary_id: uuid.UUID,
        centroid_vector: np.ndarray,
        display_group_id: Optional[uuid.UUID] = None,
    ) -> "Cluster":
        """
        Create and persist a new cluster.

        Args:
            db_session: AsyncSession for database operations
            round_id: UUID of the round
            user_count: Number of participants in cluster
            user_pct: Percentage of total participants
            label_summary_id: UUID of medoid summary (cluster label)
            centroid_vector: 384-dimensional mean embedding vector
            display_group_id: Optional visual grouping ID (from alignment)

        Returns:
            Cluster: The created cluster entity

        Raises:
            ValueError: If validation fails (user_count <= 0, user_pct out of range, etc.)

        Usage:
            cluster = await Cluster.create(
                db,
                round_id=round_id,
                user_count=5,
                user_pct=0.25,
                label_summary_id=medoid_id,
                centroid_vector=centroid,
            )
        """
        # Validate inputs
        if user_count <= 0:
            raise ValueError(f"user_count must be positive, got {user_count}")

        if not (0 < user_pct <= 1.0):
            raise ValueError(f"user_pct must be in (0, 1.0], got {user_pct}")

        if centroid_vector.shape != (384,):
            raise ValueError(f"Centroid must be 384-dimensional, got {centroid_vector.shape}")

        # Create cluster
        cluster = cls(
            round_id=round_id,
            user_count=user_count,
            user_pct=user_pct,
            label_summary_id=label_summary_id,
            display_group_id=display_group_id,
        )
        cluster.set_centroid_from_numpy(centroid_vector)

        db_session.add(cluster)
        await db_session.flush()  # Flush to get generated cluster_id

        return cluster

    async def update_display_group(
        self, db_session, display_group_id: uuid.UUID
    ) -> None:
        """
        Update display_group_id for cross-round visual continuity.

        Args:
            db_session: AsyncSession for database operations
            display_group_id: UUID of the display group (from alignment)

        Validation Rule (FR-037, FR-038, FR-039):
        - Alignment is presentation-only
        - Does NOT modify cluster membership or user_count/user_pct
        - Only updates display_group_id for visual continuity

        Usage:
            await cluster.update_display_group(db, display_group_id)
        """
        self.display_group_id = display_group_id
        await db_session.flush()
