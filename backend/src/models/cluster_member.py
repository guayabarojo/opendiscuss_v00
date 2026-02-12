"""
ClusterMember Entity Model - Spec 004 Clustering & Alignment

Join table linking clusters to their member summaries and participants.
Enables 100% participant coverage validation and cluster membership queries.

Data Model Compliance:
- PERSISTED entity (cluster assignments stored)
- Many-to-many relationship resolver (Cluster <-> ApprovedSummary)
- Immutable after creation (clustering determinism)
- Composite primary key (cluster_id, summary_id)

Constitutional Guarantees:
- Intent Fidelity: Every participant assigned to exactly one cluster per round (FR-016, SC-003)
- Semantic Accuracy: 100% coverage - no participants excluded (FR-016)
- Temporal Transparency: Cluster membership transparent and queryable

Validation Rules:
- Each summary_id appears in exactly one cluster per round (FR-016)
- Each user_id appears in exactly one cluster per round (SC-003)
- All approved summaries for a round must be assigned (100% coverage)
"""

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from typing import List, Optional
import uuid

from src.database import Base


class ClusterMember(Base):
    """
    Cluster membership record linking summaries to clusters.

    Lifecycle:
    - Created: During cluster assignment after HDBSCAN completes
    - Read: For cluster member queries, user count calculation, medoid selection
    - Updated: Never (immutable)
    - Deleted: When cluster or summary is deleted (CASCADE)

    Query Patterns:
    - Get all members of a cluster (for member count, medoid selection)
    - Get cluster for a specific user in a round (for assignment validation)
    - Verify 100% coverage (total assigned users = total participants)
    """

    __tablename__ = "cluster_members"

    # Composite Primary Key
    cluster_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clusters.cluster_id", ondelete="CASCADE"),
        primary_key=True,
    )

    summary_id = Column(
        UUID(as_uuid=True),
        ForeignKey("approved_summaries.summary_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Denormalized for query performance (from approved_summaries)
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Participant who submitted this summary (denormalized from approved_summaries)",
    )

    # Relationships
    cluster = relationship("Cluster", back_populates="members")
    approved_summary = relationship("ApprovedSummary")

    # Indexes for performance
    __table_args__ = (
        # Find cluster by summary (for assignment validation)
        Index("idx_cluster_members_summary", "summary_id"),
        # Find cluster by user (for user assignment queries)
        Index("idx_cluster_members_user", "user_id"),
        # Find all members of a cluster (for member count, medoid selection)
        Index("idx_cluster_members_cluster", "cluster_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ClusterMember(cluster={self.cluster_id}, "
            f"summary={self.summary_id}, "
            f"user={self.user_id})>"
        )

    @classmethod
    async def create(
        cls,
        db_session,
        cluster_id: uuid.UUID,
        summary_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> "ClusterMember":
        """
        Create and persist a cluster membership record.

        Args:
            db_session: AsyncSession for database operations
            cluster_id: UUID of the cluster
            summary_id: UUID of the approved summary
            user_id: UUID of the participant

        Returns:
            ClusterMember: The created membership record

        Raises:
            ValueError: If member already exists for this (cluster, summary) pair

        Usage:
            member = await ClusterMember.create(
                db,
                cluster_id=cluster.cluster_id,
                summary_id=summary.summary_id,
                user_id=participant.participant_id,
            )
        """
        from sqlalchemy import select

        # Check if membership already exists (prevent duplicates)
        existing = await db_session.execute(
            select(cls).where(
                cls.cluster_id == cluster_id,
                cls.summary_id == summary_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(
                f"ClusterMember already exists for cluster {cluster_id}, "
                f"summary {summary_id}"
            )

        # Create membership
        member = cls(
            cluster_id=cluster_id,
            summary_id=summary_id,
            user_id=user_id,
        )

        db_session.add(member)
        await db_session.flush()

        return member

    @classmethod
    async def get_by_cluster(
        cls, db_session, cluster_id: uuid.UUID
    ) -> List["ClusterMember"]:
        """
        Get all members of a cluster.

        Args:
            db_session: AsyncSession for database operations
            cluster_id: UUID of the cluster

        Returns:
            List[ClusterMember]: All members in the cluster

        Usage:
            members = await ClusterMember.get_by_cluster(db, cluster_id)
            print(f"Cluster has {len(members)} members")
        """
        from sqlalchemy import select

        result = await db_session.execute(
            select(cls).where(cls.cluster_id == cluster_id)
        )
        return result.scalars().all()

    @classmethod
    async def get_by_summary(
        cls, db_session, summary_id: uuid.UUID
    ) -> Optional["ClusterMember"]:
        """
        Get cluster membership for a summary.

        Args:
            db_session: AsyncSession for database operations
            summary_id: UUID of the approved summary

        Returns:
            ClusterMember if found, None otherwise

        Validation Rule (FR-016):
        - Each summary appears in exactly one cluster per round
        - Returns None if summary not yet assigned (pre-clustering)

        Usage:
            member = await ClusterMember.get_by_summary(db, summary_id)
            if member:
                print(f"Summary assigned to cluster {member.cluster_id}")
        """
        from sqlalchemy import select

        result = await db_session.execute(
            select(cls).where(cls.summary_id == summary_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_user_and_round(
        cls, db_session, user_id: uuid.UUID, round_id: uuid.UUID
    ) -> Optional["ClusterMember"]:
        """
        Get cluster membership for a user in a specific round.

        Args:
            db_session: AsyncSession for database operations
            user_id: UUID of the participant
            round_id: UUID of the round

        Returns:
            ClusterMember if found, None otherwise

        Validation Rule (SC-003):
        - Each user appears in exactly one cluster per round
        - Returns None if user not yet assigned (pre-clustering)

        Usage:
            member = await ClusterMember.get_by_user_and_round(db, user_id, round_id)
            if member:
                print(f"User assigned to cluster {member.cluster_id}")
        """
        from sqlalchemy import select
        from .cluster import Cluster

        result = await db_session.execute(
            select(cls)
            .join(Cluster, cls.cluster_id == Cluster.cluster_id)
            .where(
                cls.user_id == user_id,
                Cluster.round_id == round_id,
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def validate_coverage(
        cls, db_session, round_id: uuid.UUID
    ) -> bool:
        """
        Validate that all participants in a round are assigned to clusters.

        Args:
            db_session: AsyncSession for database operations
            round_id: UUID of the round

        Returns:
            bool: True if 100% coverage, False otherwise

        Validation Rule (FR-016, SC-003):
        - Every approved summary for a round must have a cluster assignment
        - 100% participant coverage is a constitutional guarantee
        - No participants excluded from clustering

        Usage:
            coverage_ok = await ClusterMember.validate_coverage(db, round_id)
            if not coverage_ok:
                raise ValueError("Not all participants assigned to clusters")
        """
        from sqlalchemy import select, func
        from .approved_summary import ApprovedSummary
        from .cluster import Cluster

        # Count total approved summaries in round
        total_summaries = await db_session.execute(
            select(func.count(ApprovedSummary.summary_id)).where(
                ApprovedSummary.round_id == round_id
            )
        )
        total_count = total_summaries.scalar()

        # Count assigned summaries in round (via cluster membership)
        assigned_summaries = await db_session.execute(
            select(func.count(cls.summary_id))
            .join(Cluster, cls.cluster_id == Cluster.cluster_id)
            .where(Cluster.round_id == round_id)
        )
        assigned_count = assigned_summaries.scalar()

        # Must match for 100% coverage
        return total_count == assigned_count

    @classmethod
    async def get_cluster_user_count(
        cls, db_session, cluster_id: uuid.UUID
    ) -> int:
        """
        Get the number of unique users in a cluster.

        Args:
            db_session: AsyncSession for database operations
            cluster_id: UUID of the cluster

        Returns:
            int: Number of unique users in the cluster

        Validation Rule (FR-018):
        - Cluster.user_count must equal unique user_id count in members
        - Used for validation after clustering completes

        Usage:
            user_count = await ClusterMember.get_cluster_user_count(db, cluster_id)
            assert cluster.user_count == user_count, "User count mismatch"
        """
        from sqlalchemy import select, func

        result = await db_session.execute(
            select(func.count(func.distinct(cls.user_id))).where(
                cls.cluster_id == cluster_id
            )
        )
        return result.scalar()

    @classmethod
    async def bulk_create(
        cls,
        db_session,
        members: List[dict],
    ) -> List["ClusterMember"]:
        """
        Bulk create cluster members for performance.

        Args:
            db_session: AsyncSession for database operations
            members: List of dicts with keys: cluster_id, summary_id, user_id

        Returns:
            List[ClusterMember]: Created membership records

        Performance Optimization:
        - Batch insert for large clustering operations (100+ members)
        - Single database round-trip instead of N inserts

        Usage:
            members_data = [
                {
                    "cluster_id": cluster1.cluster_id,
                    "summary_id": summary1.summary_id,
                    "user_id": user1_id,
                },
                # ... more members
            ]
            members = await ClusterMember.bulk_create(db, members_data)
        """
        member_objects = [
            cls(
                cluster_id=m["cluster_id"],
                summary_id=m["summary_id"],
                user_id=m["user_id"],
            )
            for m in members
        ]

        db_session.add_all(member_objects)
        await db_session.flush()

        return member_objects
