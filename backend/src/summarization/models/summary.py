"""
Summary model and status enum for Spec 003 Summarization & Approval Protocol.

Implements FSM for summary lifecycle and tracks regeneration attempts.
"""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from ...database import Base


class SummaryStatus(str, enum.Enum):
    """
    Summary status finite state machine.

    State transitions:
    - PENDING_REVIEW → APPROVED (user approves)
    - PENDING_REVIEW → REJECTED (user rejects, regen_count < 2)
    - PENDING_REVIEW → REJECTED_FINAL (user rejects after correction signal, regen_count = 3)
    - PENDING_REVIEW → DISALLOWED_CONTENT (illegal content detected)
    - PENDING_REVIEW → APPROVAL_TIMEOUT (approval deadline exceeded)
    - APPROVED → SUPERSEDED (newer approval exists for same participant)
    """
    PENDING_REVIEW = "pending_review"  # Initial state after generation
    APPROVED = "approved"              # User approved, eligible for clustering
    REJECTED = "rejected"              # User rejected, regeneration triggered
    REJECTED_FINAL = "rejected_final"  # Final rejection after correction signal
    DISALLOWED_CONTENT = "disallowed_content"  # Illegal content detected
    APPROVAL_TIMEOUT = "approval_timeout"      # Deadline exceeded
    SUPERSEDED = "superseded"          # Replaced by newer approval


class Summary(Base):
    """
    Summary entity for Spec 003.

    Stores LLM-generated summaries of participant input with approval status.
    Each summary is tied to a specific submission and participant.

    Constitutional Principles:
    - Intent Fidelity: This is the approval gate - only APPROVED summaries proceed
    - Temporal Transparency: Tracks approved_at for last-approved-wins
    - Parallel-First: Independent summaries per participant

    Attributes:
        summary_id: Unique identifier for this summary
        submission_id: Foreign key to original submission
        participant_id: Foreign key to participant who submitted input
        round_id: Foreign key to discussion round
        summary_text: LLM-generated summary (max 500 chars, 1-2 sentences)
        status: Current status in FSM
        regen_count: Number of regenerations (0-3, bounded retry)
        safety_flags: List of safety concerns (e.g., ["profanity_neutralized"])
        created_at: Initial generation timestamp
        approved_at: Approval timestamp (NULL until approved)
    """
    __tablename__ = "summaries"

    # Primary Key
    summary_id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )

    # Foreign Keys
    submission_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("submissions.submission_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("participants.participant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("rounds.round_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Summary Content
    summary_text = Column(
        String(500),  # Max 500 chars (1-2 sentences)
        nullable=False,
    )

    # Status Management (FSM)
    status = Column(
        Enum(SummaryStatus, name="summarystatus", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SummaryStatus.PENDING_REVIEW,
        index=True,
    )

    # Regeneration Tracking (bounded retry: max 3 attempts)
    regen_count = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # Safety Filtering
    safety_flags = Column(
        ARRAY(String),  # e.g., ["profanity_neutralized", "threat_detected"]
        nullable=True,
        default=list,
    )

    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    approved_at = Column(
        DateTime,
        nullable=True,
        index=True,  # Critical for last-approved-wins queries
    )

    # Relationships
    submission = relationship("Submission", back_populates="summaries")
    participant = relationship("Participant", back_populates="summaries")
    round = relationship("Round", back_populates="summaries")
    correction_signals = relationship(
        "CorrectionSignal",
        back_populates="summary",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Summary(summary_id={self.summary_id}, "
            f"status={self.status.value}, "
            f"regen_count={self.regen_count})>"
        )
