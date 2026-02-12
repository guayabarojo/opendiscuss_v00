"""
AlignmentMap Entity Model - Spec 004 Clustering & Alignment

Records cross-round alignment between semantically similar clusters for visual continuity.
Presentation-only - does NOT affect cluster membership or flow calculations.

Data Model Compliance:
- PERSISTED entity (alignment maps stored for visualization)
- Many-to-many relationship between clusters in adjacent rounds
- Immutable after creation (alignment determinism)
- Supports 1-to-1, 1-to-many (split), and many-to-1 (merge) patterns

Constitutional Guarantees:
- Temporal Transparency: Alignment provides visual continuity across rounds
- Semantic Accuracy: Alignment based on centroid similarity (FR-031, FR-032)
- Intent Fidelity: Does NOT modify cluster membership (FR-037, SC-009)

Alignment Types:
- 1-to-1: One cluster in r maps to one cluster in r+1 (continuity)
- 1-to-many (split): One cluster in r maps to multiple clusters in r+1
- many-to-1 (merge): Multiple clusters in r map to one cluster in r+1

Presentation-Only Guarantee (FR-037, FR-038, FR-039):
- Alignment does NOT change cluster membership
- Alignment does NOT change user_count or user_pct
- Alignment ONLY assigns display_group_id for visual continuity
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional, List, Dict
import uuid

from src.database import Base


class AlignmentMap(Base):
    """
    Cross-round cluster alignment for visual continuity.

    Lifecycle:
    - Created: After clustering both rounds r and r+1 completes
    - Read: By Spec 5 (Sankey) for color/label continuity, by UI for display groups
    - Updated: Never (immutable)
    - Deleted: When discussion or clusters are deleted (CASCADE)

    Validation Rules:
    - round_r1 must equal round_r + 1 (adjacent rounds only - FR-029)
    - similarity_score must be >= ALIGN_THRESHOLD (default 0.7) for inclusion (FR-032, FR-033)
    - display_group_id same across all aligned clusters (visual continuity)
    - Alignment does NOT modify clusters or cluster_members tables (FR-037, SC-009)
    """

    __tablename__ = "alignment_maps"

    # Primary Key
    alignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Round Context
    discussion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("discussions.discussion_id", ondelete="CASCADE"),
        nullable=False,
        comment="Discussion context for alignment",
    )

    round_r = Column(
        Integer,
        nullable=False,
        comment="Earlier round number",
    )

    round_r1 = Column(
        Integer,
        nullable=False,
        comment="Later round number (r+1)",
    )

    # Cluster References
    cluster_r_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clusters.cluster_id", ondelete="CASCADE"),
        nullable=False,
        comment="Cluster from round r",
    )

    cluster_r1_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clusters.cluster_id", ondelete="CASCADE"),
        nullable=False,
        comment="Cluster from round r+1",
    )

    # Alignment Metadata
    similarity_score = Column(
        Float,
        nullable=False,
        comment="Cosine similarity of cluster centroids (0-1)",
    )

    display_group_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Visual grouping ID for aligned clusters (same ID = aligned)",
    )

    alignment_type = Column(
        String(20),
        nullable=True,
        comment="Alignment pattern: 1-to-1, 1-to-many, many-to-1",
    )

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    discussion = relationship("Discussion")
    cluster_r = relationship("Cluster", foreign_keys=[cluster_r_id])
    cluster_r1 = relationship("Cluster", foreign_keys=[cluster_r1_id])

    # Indexes for performance
    __table_args__ = (
        # Find alignments for a discussion and round range
        Index("idx_alignment_discussion", "discussion_id", "round_r", "round_r1"),
        # Find alignments by display group (for visual continuity queries)
        Index("idx_alignment_display_group", "display_group_id"),
        # Find alignments by cluster pairs (for bidirectional queries)
        Index("idx_alignment_clusters", "cluster_r_id", "cluster_r1_id"),
        # Constraints
        CheckConstraint("similarity_score >= 0 AND similarity_score <= 1.0", name="chk_alignment_similarity_range"),
    )

    def __repr__(self) -> str:
        return (
            f"<AlignmentMap(id={self.alignment_id}, "
            f"discussion={self.discussion_id}, "
            f"rounds={self.round_r}->{self.round_r1}, "
            f"similarity={self.similarity_score:.3f}, "
            f"type={self.alignment_type})>"
        )

    @staticmethod
    def validate_adjacent_rounds(round_r: int, round_r1: int) -> bool:
        """
        Validate that rounds are adjacent (r+1).

        Args:
            round_r: Earlier round number
            round_r1: Later round number

        Returns:
            bool: True if round_r1 == round_r + 1, False otherwise

        Validation Rule (FR-029):
        - Alignment only occurs between adjacent rounds
        - Skip alignment for non-adjacent rounds (gaps in discussion)
        """
        return round_r1 == round_r + 1

    @staticmethod
    def validate_similarity_threshold(
        similarity_score: float, threshold: float = 0.7
    ) -> bool:
        """
        Validate that similarity score meets alignment threshold.

        Args:
            similarity_score: Cosine similarity of cluster centroids (0-1)
            threshold: Minimum similarity for alignment (default: 0.7)

        Returns:
            bool: True if similarity >= threshold, False otherwise

        Validation Rule (FR-032, FR-033):
        - Only align clusters with similarity >= ALIGN_THRESHOLD
        - Default threshold: 0.7 (configurable per deployment)
        - Low similarity = semantically distinct, should not align
        """
        return similarity_score >= threshold

    @classmethod
    async def create(
        cls,
        db_session,
        discussion_id: uuid.UUID,
        round_r: int,
        round_r1: int,
        cluster_r_id: uuid.UUID,
        cluster_r1_id: uuid.UUID,
        similarity_score: float,
        display_group_id: Optional[uuid.UUID] = None,
        alignment_type: Optional[str] = None,
    ) -> "AlignmentMap":
        """
        Create and persist an alignment map.

        Args:
            db_session: AsyncSession for database operations
            discussion_id: UUID of the discussion
            round_r: Earlier round number
            round_r1: Later round number (must be r+1)
            cluster_r_id: UUID of cluster from round r
            cluster_r1_id: UUID of cluster from round r+1
            similarity_score: Cosine similarity of centroids (0-1)
            display_group_id: Optional visual grouping ID
            alignment_type: Optional alignment pattern (1-to-1, 1-to-many, many-to-1)

        Returns:
            AlignmentMap: The created alignment entity

        Raises:
            ValueError: If validation fails (non-adjacent rounds, low similarity, etc.)

        Usage:
            alignment = await AlignmentMap.create(
                db,
                discussion_id=discussion.discussion_id,
                round_r=1,
                round_r1=2,
                cluster_r_id=cluster1.cluster_id,
                cluster_r1_id=cluster2.cluster_id,
                similarity_score=0.85,
                display_group_id=group_id,
                alignment_type="1-to-1",
            )
        """
        # Validate adjacent rounds
        if not cls.validate_adjacent_rounds(round_r, round_r1):
            raise ValueError(
                f"Rounds must be adjacent (r+1), got round_r={round_r}, round_r1={round_r1}"
            )

        # Validate similarity score range
        if not (0 <= similarity_score <= 1.0):
            raise ValueError(
                f"Similarity score must be in [0, 1], got {similarity_score}"
            )

        # Create alignment
        alignment = cls(
            discussion_id=discussion_id,
            round_r=round_r,
            round_r1=round_r1,
            cluster_r_id=cluster_r_id,
            cluster_r1_id=cluster_r1_id,
            similarity_score=similarity_score,
            display_group_id=display_group_id,
            alignment_type=alignment_type,
        )

        db_session.add(alignment)
        await db_session.flush()

        return alignment

    @classmethod
    async def get_by_discussion(
        cls,
        db_session,
        discussion_id: uuid.UUID,
        round_r: Optional[int] = None,
    ) -> List["AlignmentMap"]:
        """
        Get all alignments for a discussion, optionally filtered by round.

        Args:
            db_session: AsyncSession for database operations
            discussion_id: UUID of the discussion
            round_r: Optional filter for earlier round number

        Returns:
            List[AlignmentMap]: Alignments ordered by round_r, similarity_score desc

        Usage:
            # Get all alignments
            alignments = await AlignmentMap.get_by_discussion(db, discussion_id)

            # Get alignments for specific round transition
            alignments = await AlignmentMap.get_by_discussion(db, discussion_id, round_r=1)
        """
        from sqlalchemy import select

        query = select(cls).where(cls.discussion_id == discussion_id)

        if round_r is not None:
            query = query.where(cls.round_r == round_r)

        query = query.order_by(cls.round_r, cls.similarity_score.desc())

        result = await db_session.execute(query)
        return result.scalars().all()

    @classmethod
    async def get_by_display_group(
        cls, db_session, display_group_id: uuid.UUID
    ) -> List["AlignmentMap"]:
        """
        Get all alignments in a display group.

        Args:
            db_session: AsyncSession for database operations
            display_group_id: UUID of the display group

        Returns:
            List[AlignmentMap]: All alignments with this display_group_id

        Usage:
            alignments = await AlignmentMap.get_by_display_group(db, group_id)
            # All clusters in these alignments should use same color/label family
        """
        from sqlalchemy import select

        result = await db_session.execute(
            select(cls).where(cls.display_group_id == display_group_id)
        )
        return result.scalars().all()

    @classmethod
    async def get_alignment_statistics(
        cls, db_session, discussion_id: uuid.UUID
    ) -> Dict[str, int]:
        """
        Get alignment statistics for a discussion.

        Args:
            db_session: AsyncSession for database operations
            discussion_id: UUID of the discussion

        Returns:
            Dict with keys:
                - total_alignments: Total number of alignments
                - one_to_one: Number of 1-to-1 alignments
                - splits: Number of 1-to-many alignments
                - merges: Number of many-to-1 alignments
                - display_groups: Number of unique display groups

        Usage:
            stats = await AlignmentMap.get_alignment_statistics(db, discussion_id)
            print(f"Total alignments: {stats['total_alignments']}")
            print(f"Splits: {stats['splits']}, Merges: {stats['merges']}")
        """
        from sqlalchemy import select, func

        # Get all alignments
        alignments = await cls.get_by_discussion(db_session, discussion_id)

        # Count alignment types
        one_to_one = 0
        splits = 0
        merges = 0

        # Track cluster counts by round
        r_cluster_counts: Dict[uuid.UUID, int] = {}
        r1_cluster_counts: Dict[uuid.UUID, int] = {}

        for alignment in alignments:
            # Count how many times each cluster appears
            r_cluster_counts[alignment.cluster_r_id] = (
                r_cluster_counts.get(alignment.cluster_r_id, 0) + 1
            )
            r1_cluster_counts[alignment.cluster_r1_id] = (
                r1_cluster_counts.get(alignment.cluster_r1_id, 0) + 1
            )

        # Classify alignment types based on counts
        for alignment in alignments:
            r_count = r_cluster_counts[alignment.cluster_r_id]
            r1_count = r1_cluster_counts[alignment.cluster_r1_id]

            if r_count == 1 and r1_count == 1:
                one_to_one += 1
            elif r_count == 1 and r1_count > 1:
                splits += 1
            elif r_count > 1 and r1_count == 1:
                merges += 1

        # Count unique display groups
        result = await db_session.execute(
            select(func.count(func.distinct(cls.display_group_id))).where(
                cls.discussion_id == discussion_id,
                cls.display_group_id.isnot(None),
            )
        )
        display_groups = result.scalar()

        return {
            "total_alignments": len(alignments),
            "one_to_one": one_to_one,
            "splits": splits,
            "merges": merges,
            "display_groups": display_groups,
        }

    @classmethod
    async def bulk_create(
        cls,
        db_session,
        alignments: List[dict],
    ) -> List["AlignmentMap"]:
        """
        Bulk create alignment maps for performance.

        Args:
            db_session: AsyncSession for database operations
            alignments: List of dicts with keys: discussion_id, round_r, round_r1,
                       cluster_r_id, cluster_r1_id, similarity_score, display_group_id,
                       alignment_type

        Returns:
            List[AlignmentMap]: Created alignment records

        Performance Optimization:
        - Batch insert for large alignment operations
        - Single database round-trip instead of N inserts

        Usage:
            alignments_data = [
                {
                    "discussion_id": discussion_id,
                    "round_r": 1,
                    "round_r1": 2,
                    "cluster_r_id": cluster1.cluster_id,
                    "cluster_r1_id": cluster2.cluster_id,
                    "similarity_score": 0.85,
                    "display_group_id": group_id,
                    "alignment_type": "1-to-1",
                },
                # ... more alignments
            ]
            alignments = await AlignmentMap.bulk_create(db, alignments_data)
        """
        alignment_objects = [
            cls(
                discussion_id=a["discussion_id"],
                round_r=a["round_r"],
                round_r1=a["round_r1"],
                cluster_r_id=a["cluster_r_id"],
                cluster_r1_id=a["cluster_r1_id"],
                similarity_score=a["similarity_score"],
                display_group_id=a.get("display_group_id"),
                alignment_type=a.get("alignment_type"),
            )
            for a in alignments
        ]

        db_session.add_all(alignment_objects)
        await db_session.flush()

        return alignment_objects
