from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from . import Base

class ApprovedSummary(Base):
    """
    Canonical 1-2 sentence representation of a submission.

    Data Model Compliance:
    - PERSISTED entity (NOT ephemeral like Submission)
    - Only APPROVED summaries enter this table (Intent Fidelity - Principle II)
    - Exactly ONE per participant per round (last-approved-wins rule)
    - 100% assigned to clusters after clustering completes (Semantic Accuracy - Principle III)

    Constitutional Guarantees:
    - Intent Fidelity: Zero summaries with status != APPROVED
    - Semantic Accuracy: 100% participant coverage in clustering
    - Temporal Transparency: Flows computed from these summaries (not similarity)

    Privacy Note:
    - Uses participant_id (NOT user_id) to preserve participant privacy
    - submission_id set to NULL after ephemeral deletion (maintains referential integrity)
    """

    __tablename__ = "approved_summaries"

    # Primary Key
    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.participant_id"), nullable=False)
    round_id = Column(UUID(as_uuid=True), ForeignKey("rounds.round_id"), nullable=False)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("submissions.submission_id", ondelete="SET NULL"),
        nullable=True  # Set to NULL after ephemeral submission deletion
    )

    # Core Fields
    summary_text = Column(String(500), nullable=False)  # Max 500 chars, 1-2 sentences
    approved_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Clustering Assignment
    cluster_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clusters.cluster_id"),
        nullable=True  # NULL until clustering completes, then MUST be set
    )

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    participant = relationship("Participant", back_populates="approved_summaries")
    round = relationship("Round", back_populates="approved_summaries")
    submission = relationship("Submission", back_populates="approved_summary")
    cluster = relationship(
        "Cluster",
        foreign_keys=[cluster_id],
        back_populates="approved_summaries"
    )
    thought_space = relationship(
        "ThoughtSpace",
        primaryjoin="ApprovedSummary.cluster_id == ThoughtSpace.cluster_id",
        foreign_keys=[cluster_id],
        back_populates="approved_summaries",
        overlaps="cluster"
    )
    embedding = relationship("Embedding", back_populates="approved_summary", uselist=False)

    # Indexes for performance
    __table_args__ = (
        # Unique constraint: Exactly one approved summary per participant per round (last-approved-wins)
        Index("idx_approved_summary_round_participant", "round_id", "participant_id", unique=True),
        # Find all summaries in a thought space (for member count validation)
        Index("idx_approved_summary_cluster", "cluster_id"),
        # List all summaries for a round (for clustering input)
        Index("idx_approved_summary_round", "round_id"),
    )

    def assign_to_cluster(self, cluster_id: uuid.UUID) -> None:
        """
        Assign summary to a cluster.

        Called by clustering service (Spec 4) after semantic clustering completes.
        Constitutional guarantee: 100% of approved summaries MUST have cluster_id set.

        Args:
            cluster_id: UUID of the Cluster

        Raises:
            ValueError: If cluster_id is None (violates 100% coverage requirement)
        """
        if cluster_id is None:
            raise ValueError("cluster_id cannot be None - violates 100% participant coverage guarantee")

        self.cluster_id = cluster_id

    def is_clustered(self) -> bool:
        """
        Check if summary has been assigned to a cluster.

        Returns:
            True if cluster_id is set, False otherwise
        """
        return self.cluster_id is not None

    def __repr__(self) -> str:
        return (
            f"<ApprovedSummary(id={self.summary_id}, "
            f"participant={self.participant_id}, "
            f"round={self.round_id}, "
            f"cluster={self.cluster_id}, "
            f"approved_at={self.approved_at})>"
        )
