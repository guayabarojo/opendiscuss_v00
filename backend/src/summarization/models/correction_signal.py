"""
CorrectionSignal model for Spec 003 Summarization & Approval Protocol.

Captures participant feedback after 2 rejections to improve final regeneration.
"""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from ...database import Base


class ReasonTag(enum.Enum):
    """
    Structured reason tags for correction signals.

    These tags help the LLM focus regeneration on specific issues.
    """
    WRONG_CRUX = "wrong_crux"                # Summary misidentified core point
    TOO_VAGUE = "too_vague"                  # Summary lacks specificity
    MISREPRESENTS_ME = "misrepresents_me"    # Summary changes participant's stance
    MISSED_CONSTRAINT = "missed_constraint"  # Summary omitted key constraint
    MISSED_SOLUTION = "missed_solution"      # Summary omitted proposed solution
    OTHER = "other"                          # Freeform feedback


class CorrectionSignal(Base):
    """
    CorrectionSignal entity for Spec 003.

    Stores participant feedback after 2 automatic regenerations fail.
    Used to guide final regeneration attempt (regen_count=3).

    Attributes:
        signal_id: Unique identifier for this correction signal
        summary_id: Foreign key to summary being corrected
        reason_tag: Structured reason for rejection
        feedback_text: Optional freeform feedback (max 240 chars)
        created_at: Signal submission timestamp
    """
    __tablename__ = "correction_signals"

    # Primary Key
    signal_id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )

    # Foreign Key
    summary_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("summaries.summary_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Correction Content
    reason_tag = Column(
        Enum(ReasonTag),
        nullable=False,
    )
    feedback_text = Column(
        String(240),  # Max 240 chars (Twitter-style constraint)
        nullable=True,
    )

    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    summary = relationship("Summary", back_populates="correction_signals")

    def __repr__(self) -> str:
        return (
            f"<CorrectionSignal(signal_id={self.signal_id}, "
            f"reason_tag={self.reason_tag.value})>"
        )
