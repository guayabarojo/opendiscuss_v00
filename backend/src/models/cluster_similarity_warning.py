"""
Cluster Similarity Warning Model

Tracks near-duplicate cluster pairs for human review.
Supports continuous quality improvement and manual intervention.

Data Model Compliance:
- PERSISTED entity (warnings stored for review workflow)
- Created when near-duplicate pairs detected (similarity > 0.8)
- Supports human review and decision tracking

Constitutional Compliance:
- FR-013 (No Forced Merging): Warnings are suggestions only, NOT automatic merging
- Requires explicit human review and decision before any action
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from typing import Optional

from src.database import Base


class ClusterSimilarityWarning(Base):
    """
    Warning record for near-duplicate cluster pairs.

    Lifecycle:
    - Created: After clustering quality metrics computed
    - Read: By quality review dashboard, human reviewers
    - Updated: When human review decision recorded
    - Deleted: When round is deleted (CASCADE)

    Human Review Workflow:
    1. Warning created with reviewed=False
    2. Human reviews cluster pair
    3. Human makes decision: 'merge', 'keep_separate', 'defer'
    4. Decision and notes stored, reviewed=True
    """

    __tablename__ = "cluster_similarity_warnings"

    # Primary Key
    warning_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    round_id = Column(
        UUID(as_uuid=True),
        ForeignKey("rounds.round_id", ondelete="CASCADE"),
        nullable=False,
    )

    cluster_i_id = Column(
        UUID(as_uuid=True),
        ForeignKey("thought_spaces.cluster_id", ondelete="CASCADE"),
        nullable=False,
        comment="First cluster in similar pair"
    )

    cluster_j_id = Column(
        UUID(as_uuid=True),
        ForeignKey("thought_spaces.cluster_id", ondelete="CASCADE"),
        nullable=False,
        comment="Second cluster in similar pair"
    )

    # Similarity Metrics
    similarity_score = Column(
        Float,
        nullable=False,
        comment="Cosine similarity between cluster centroids"
    )

    # Cluster Info (denormalized for review UI)
    cluster_i_label = Column(
        Text,
        nullable=True,
        comment="Label text for cluster i"
    )

    cluster_j_label = Column(
        Text,
        nullable=True,
        comment="Label text for cluster j"
    )

    cluster_i_size = Column(
        Integer,
        nullable=False,
        comment="Member count for cluster i"
    )

    cluster_j_size = Column(
        Integer,
        nullable=False,
        comment="Member count for cluster j"
    )

    # Review Workflow
    reviewed = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Has this warning been reviewed by a human?"
    )

    review_decision = Column(
        String(50),
        nullable=True,
        comment="Human decision: merge, keep_separate, defer"
    )

    review_notes = Column(
        Text,
        nullable=True,
        comment="Optional notes from human review"
    )

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    round = relationship("Round", back_populates="cluster_similarity_warnings")
    cluster_i = relationship(
        "ThoughtSpace",
        foreign_keys=[cluster_i_id],
        viewonly=True
    )
    cluster_j = relationship(
        "ThoughtSpace",
        foreign_keys=[cluster_j_id],
        viewonly=True
    )

    # Indexes
    __table_args__ = (
        Index("idx_similarity_warnings_round", "round_id"),
        Index("idx_similarity_warnings_reviewed", "reviewed"),
        Index("idx_similarity_warnings_similarity", "similarity_score"),
    )

    def __repr__(self) -> str:
        return (
            f"<ClusterSimilarityWarning(round={self.round_id}, "
            f"similarity={self.similarity_score:.3f}, "
            f"reviewed={self.reviewed})>"
        )

    def mark_reviewed(
        self,
        decision: str,
        notes: Optional[str] = None
    ) -> None:
        """
        Mark warning as reviewed with decision.

        Args:
            decision: One of 'merge', 'keep_separate', 'defer'
            notes: Optional review notes

        Raises:
            ValueError: If decision is not valid
        """
        valid_decisions = ['merge', 'keep_separate', 'defer']
        if decision not in valid_decisions:
            raise ValueError(
                f"Invalid decision '{decision}'. "
                f"Must be one of: {', '.join(valid_decisions)}"
            )

        self.reviewed = True
        self.review_decision = decision
        self.review_notes = notes

    def is_high_severity(self) -> bool:
        """
        Check if this is a high-severity warning.

        High severity criteria:
        - Similarity > 0.95 (near-perfect duplicates)
        - Large clusters (both > 5 members)

        Returns:
            bool: True if high severity, False otherwise
        """
        return (
            self.similarity_score > 0.95
            or (self.cluster_i_size > 5 and self.cluster_j_size > 5)
        )

    def get_severity_level(self) -> str:
        """
        Get severity level for prioritization.

        Returns:
            str: 'critical', 'high', 'medium', 'low'
        """
        if self.similarity_score >= 0.98:
            return 'critical'  # Near-perfect duplicates
        elif self.similarity_score >= 0.90:
            return 'high'
        elif self.similarity_score >= 0.85:
            return 'medium'
        else:
            return 'low'
