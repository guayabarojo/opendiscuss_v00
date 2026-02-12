from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid
from enum import Enum

from . import Base

class SubmissionModality(str, Enum):
    """Submission input modality"""
    TEXT = "text"
    VOICE = "voice"

class SummaryStatus(str, Enum):
    """Status of submission's summary in the approval workflow"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    APPROVAL_TIMEOUT = "approval_timeout"

class Submission(Base):
    """
    EPHEMERAL entity representing raw participant input for a round.

    Data Model Compliance:
    - TTL-based deletion: Deleted after summary approval + 5 min grace period
    - Rate limiting: Max 3 submissions per participant per round (enforced by service layer)
    - Last-approved-wins: Previous submissions marked SUPERSEDED when new summary approved

    Privacy Note:
    - Uses participant_id (NOT user_id) to preserve participant privacy
    - LLM services log participant_id, never user_id
    """

    __tablename__ = "submissions"

    # Primary Key
    submission_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.participant_id"), nullable=False)
    round_id = Column(UUID(as_uuid=True), ForeignKey("rounds.round_id"), nullable=False)

    # Core Fields
    submission_text = Column(Text, nullable=False)  # Max 2000 chars enforced by validation
    modality = Column(SQLEnum(SubmissionModality, name="submissionmodality", values_callable=lambda x: [e.value for e in x]), nullable=False, default=SubmissionModality.TEXT)
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    summary_status = Column(SQLEnum(SummaryStatus, name="submissionsummarystatus", values_callable=lambda x: [e.value for e in x]), nullable=False, default=SummaryStatus.PENDING)

    # TTL Management
    deleted_at = Column(DateTime, nullable=True)  # Soft delete timestamp for TTL cleanup

    # Relationships
    participant = relationship("Participant", back_populates="submissions")
    round = relationship("Round", back_populates="submissions")
    approved_summary = relationship("ApprovedSummary", back_populates="submission", uselist=False)
    summaries = relationship("Summary", back_populates="submission", cascade="all, delete-orphan")

    # Indexes for performance
    __table_args__ = (
        Index("idx_submission_round_participant_time", "round_id", "participant_id", "submitted_at"),
        Index("idx_submission_deleted_at", "deleted_at"),  # For TTL cleanup jobs
    )

    def mark_for_deletion(self) -> None:
        """
        Mark submission for deletion by TTL cleanup job.

        Called when:
        1. Summary is approved (5-minute grace period before cleanup)
        2. Round approval_deadline expires (cleanup unapproved submissions)
        3. Discussion transitions to COMPLETED or TERMINATED
        """
        self.deleted_at = datetime.utcnow()

    def is_eligible_for_cleanup(self, grace_period_minutes: int = 5) -> bool:
        """
        Check if submission can be deleted by cleanup job.

        Args:
            grace_period_minutes: Minutes to wait after marking before actual deletion

        Returns:
            True if deleted_at + grace_period < now
        """
        if self.deleted_at is None:
            return False

        cleanup_threshold = self.deleted_at + timedelta(minutes=grace_period_minutes)
        return datetime.utcnow() >= cleanup_threshold

    def __repr__(self) -> str:
        return (
            f"<Submission(id={self.submission_id}, "
            f"participant={self.participant_id}, "
            f"round={self.round_id}, "
            f"status={self.summary_status}, "
            f"modality={self.modality})>"
        )
