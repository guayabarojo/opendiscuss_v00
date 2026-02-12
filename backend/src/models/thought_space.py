from sqlalchemy import Column, String, Integer, Float, ForeignKey, Index, JSON, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, foreign
import uuid
from datetime import datetime

from . import BaseModel

class ThoughtSpace(BaseModel):
    """
    Semantic cluster of approved summaries within a round.
    Represents a coherent idea from participant consensus.

    Constitutional Guarantee (Semantic Accuracy - Principle III):
    - Singleton clusters (member_count = 1) are preserved (no forced merging)
    - No minimum cluster size constraint
    """
    __tablename__ = "thought_spaces"

    # Primary Key
    cluster_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    # Foreign Keys
    round_id = Column(UUID(as_uuid=True), ForeignKey("rounds.round_id"), nullable=False)

    # Core Fields
    label_summary = Column(String(200), nullable=False)  # Medoid text (actual participant language)
    centroid_vector = Column(JSON, nullable=True)  # Embedding vector for future semantic alignment
    member_count = Column(Integer, nullable=False)  # Number of participants in this cluster
    member_pct = Column(Float, nullable=False)  # Percentage of round participants (0.0-1.0)

    # Display Fields (cosmetic only, does NOT affect clustering or flows)
    display_group_id = Column(UUID(as_uuid=True), nullable=True)  # Hybrid alignment ID for cross-round display

    # Relationships
    round = relationship("Round", back_populates="thought_spaces")
    approved_summaries = relationship(
        "ApprovedSummary",
        primaryjoin="ThoughtSpace.cluster_id == foreign(ApprovedSummary.cluster_id)",
        back_populates="thought_space",
        overlaps="label_summary_obj"
    )
    outgoing_flows = relationship(
        "Flow",
        primaryjoin="ThoughtSpace.cluster_id == foreign(Flow.source_cluster_id)",
        viewonly=True
    )
    incoming_flows = relationship(
        "Flow",
        primaryjoin="ThoughtSpace.cluster_id == foreign(Flow.target_cluster_id)",
        viewonly=True
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("member_count >= 1", name="check_member_count_positive"),
        CheckConstraint("member_pct >= 0.0 AND member_pct <= 1.0", name="check_member_pct_range"),
        CheckConstraint("char_length(label_summary) <= 200", name="check_label_summary_length"),
        Index("ix_thought_spaces_round_id", "round_id"),  # Fast round queries
    )

    def __repr__(self):
        return f"<ThoughtSpace(cluster_id={self.cluster_id}, round_id={self.round_id}, label='{self.label_summary[:50]}...', members={self.member_count}, pct={self.member_pct:.2%})>"

    def validate_member_pct_sum(self, session):
        """
        Validate that member_pct sums to 1.0 (±0.001 tolerance) across all ThoughtSpaces in the round.

        This is a constitutional requirement to ensure 100% participant coverage.
        """
        from sqlalchemy import func
        total_pct = session.query(func.sum(ThoughtSpace.member_pct)).filter(
            ThoughtSpace.round_id == self.round_id
        ).scalar()

        if total_pct is None:
            return True  # No other clusters yet

        tolerance = 0.001
        if abs(total_pct - 1.0) > tolerance:
            raise ValueError(
                f"ThoughtSpace member_pct sum validation failed: "
                f"total={total_pct:.6f}, expected=1.0 (±{tolerance})"
            )
        return True

    def validate_member_count(self, session):
        """
        Validate that member_count equals the actual count of ApprovedSummaries with this cluster_id.
        """
        from . import ApprovedSummary
        actual_count = session.query(ApprovedSummary).filter(
            ApprovedSummary.cluster_id == self.cluster_id
        ).count()

        if actual_count != self.member_count:
            raise ValueError(
                f"ThoughtSpace member_count validation failed: "
                f"stored={self.member_count}, actual={actual_count}"
            )
        return True

    def validate_label_is_participant_language(self):
        """
        Validate that label_summary is actual participant language (medoid method).

        This is enforced by Spec 4 (clustering protocol) and should never be AI-generated text.
        Note: This is a documentation method - actual enforcement happens in Spec 4.
        """
        # Validation happens at creation time in Spec 4
        # This method exists to document the constitutional requirement
        return True
