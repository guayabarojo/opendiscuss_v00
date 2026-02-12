"""Round model - Timed phase within a discussion associated with one question."""
from sqlalchemy import Column, String, Integer, Enum as SQLEnum, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from datetime import datetime, timedelta
from typing import Optional
import uuid
import re

from . import BaseModel
from .protocol_state import RoundStatus


class Round(BaseModel):
    """
    Round entity representing a timed phase within a discussion.

    Each round has a question, submission window, and progresses through a
    state machine coordinating multiple sub-protocols (submission, summarization,
    clustering, Sankey building).

    Attributes:
        round_id: Unique identifier (UUID primary key)
        discussion_id: Parent discussion UUID (foreign key)
        round_num: Sequential round number (1-indexed)
        question_text: Validated question (10-200 chars, starts with What/How)
        status: Current round lifecycle state
        submission_window_start: Window opened timestamp
        submission_window_end: Window closed timestamp
        submission_window_duration_sec: Window duration (180-360 seconds)
        approval_deadline: Computed as window_end + 10 minutes
        completed_at: All sub-protocols finished timestamp
        created_at: Creation timestamp

    Relationships:
        discussion: Many-to-one with Discussion
        submissions: One-to-many with Submission
        approved_summaries: One-to-many with ApprovedSummary
        clusters: One-to-many with Cluster

    State Machine:
        PENDING → QUESTION_READY (AUTO mode only)
        PENDING/QUESTION_READY → SUBMISSION_OPEN
        SUBMISSION_OPEN → SUBMISSION_CLOSED
        SUBMISSION_CLOSED → SUMMARIZING
        SUMMARIZING → APPROVING
        APPROVING → CLUSTERING
        CLUSTERING → SANKEY_BUILDING
        SANKEY_BUILDING → COMPLETE
        Any state → FAILED
    """

    __tablename__ = "rounds"

    # Primary Key
    round_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    discussion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("discussions.discussion_id", ondelete="CASCADE"),
        nullable=False
    )
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.question_id", ondelete="CASCADE"),
        nullable=True
    )

    # Core Fields
    round_num = Column(Integer, nullable=False)
    question_text = Column(String(200), nullable=False)
    status = Column(
        SQLEnum(RoundStatus, name="round_status"),
        nullable=False,
        default=RoundStatus.PENDING
    )

    # Timing Fields
    submission_window_start = Column(DateTime, nullable=True)
    submission_window_end = Column(DateTime, nullable=True)
    submission_window_duration_sec = Column(Integer, nullable=False)
    approval_deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Dropout Analytics (T068 - User Story 5)
    dropout_count = Column(
        Integer,
        nullable=True,
        default=None,
        comment="Number of participants who dropped out before this round (NULL for round 1)"
    )

    # Relationships
    discussion = relationship("Discussion", back_populates="rounds")
    question = relationship("Question", back_populates="rounds")
    submissions = relationship(
        "Submission",
        back_populates="round",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    approved_summaries = relationship(
        "ApprovedSummary",
        back_populates="round",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    summaries = relationship(
        "Summary",
        back_populates="round",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    clusters = relationship(
        "Cluster",
        back_populates="round",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    thought_spaces = relationship(
        "ThoughtSpace",
        back_populates="round",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    cluster_quality_metrics = relationship(
        "ClusterQualityMetric",
        back_populates="round",
        cascade="all, delete-orphan",
        lazy="select"  # Lazy load to avoid issues if tables don't exist
    )
    cluster_similarity_warnings = relationship(
        "ClusterSimilarityWarning",
        back_populates="round",
        cascade="all, delete-orphan",
        lazy="select"  # Lazy load to avoid issues if tables don't exist
    )

    # Indexes and Constraints
    __table_args__ = (
        Index("ix_rounds_discussion_round_num", "discussion_id", "round_num", unique=True),
        Index("ix_rounds_status", "status"),
        Index("ix_rounds_approval_deadline", "approval_deadline"),
        CheckConstraint(
            "submission_window_duration_sec BETWEEN 180 AND 360",
            name="ck_rounds_window_duration"
        ),
        CheckConstraint(
            "round_num >= 1",
            name="ck_rounds_num_positive"
        ),
    )

    def __init__(
        self,
        discussion_id: uuid.UUID,
        round_num: int,
        question_text: str,
        submission_window_duration_sec: int,
        **kwargs
    ):
        """
        Initialize a new Round.

        Args:
            discussion_id: UUID of parent discussion
            round_num: Sequential round number (1-indexed)
            question_text: Question for this round
            submission_window_duration_sec: Window duration (180-360 seconds)

        Raises:
            ValueError: If validation fails
        """
        super().__init__(**kwargs)
        self.round_id = kwargs.get('round_id', uuid.uuid4())
        self.discussion_id = discussion_id
        self.round_num = round_num
        self.question_text = question_text  # SQLAlchemy validator will be called automatically
        self.submission_window_duration_sec = submission_window_duration_sec  # SQLAlchemy validator will be called automatically
        self.status = RoundStatus.PENDING

    # Note: Validation is handled in the question progression service and API layer
    # to avoid SQLAlchemy async context issues with @validates decorators

    def open_submission_window(self) -> None:
        """
        Open the submission window for this round.

        Transitions status from PENDING or QUESTION_READY to SUBMISSION_OPEN.
        Sets submission_window_start, computes submission_window_end and
        approval_deadline.

        If question_id is set, marks the question as immutable (Spec 006).

        Raises:
            ValueError: If status not PENDING or QUESTION_READY
        """
        if self.status not in (RoundStatus.PENDING, RoundStatus.QUESTION_READY):
            raise ValueError(
                f"Cannot open submission window from status {self.status}. "
                f"Must be PENDING or QUESTION_READY."
            )

        now = datetime.utcnow()
        self.status = RoundStatus.SUBMISSION_OPEN
        self.submission_window_start = now
        self.submission_window_end = now + timedelta(
            seconds=self.submission_window_duration_sec
        )
        # Approval deadline is 10 minutes after window closes
        self.approval_deadline = self.submission_window_end + timedelta(minutes=10)
        self.updated_at = now

        # Mark question as immutable if linked (Spec 006 integration)
        if self.question_id and self.question:
            self.question.mark_immutable()

    def close_submission_window(self) -> None:
        """
        Close the submission window.

        Transitions status from SUBMISSION_OPEN to SUBMISSION_CLOSED.

        Raises:
            ValueError: If status not SUBMISSION_OPEN
        """
        if self.status != RoundStatus.SUBMISSION_OPEN:
            raise ValueError(
                f"Cannot close submission window from status {self.status}. "
                f"Must be SUBMISSION_OPEN."
            )

        self.status = RoundStatus.SUBMISSION_CLOSED
        self.updated_at = datetime.utcnow()

    def advance_status(self, next_status: RoundStatus) -> None:
        """
        Advance round to next status in state machine.

        Validates state transitions according to the protocol state machine.

        Args:
            next_status: Target status

        Raises:
            ValueError: If transition is invalid
        """
        # Define valid transitions
        valid_transitions = {
            RoundStatus.PENDING: [RoundStatus.QUESTION_READY, RoundStatus.SUBMISSION_OPEN, RoundStatus.QUESTION_GENERATION_FAILED],
            RoundStatus.QUESTION_READY: [RoundStatus.SUBMISSION_OPEN],
            RoundStatus.QUESTION_GENERATION_FAILED: [RoundStatus.SUBMISSION_OPEN],  # After host provides manual question
            RoundStatus.SUBMISSION_OPEN: [RoundStatus.SUBMISSION_CLOSED],
            RoundStatus.SUBMISSION_CLOSED: [RoundStatus.SUMMARIZING],
            RoundStatus.SUMMARIZING: [RoundStatus.APPROVING],
            RoundStatus.APPROVING: [RoundStatus.CLUSTERING],
            RoundStatus.CLUSTERING: [RoundStatus.SANKEY_BUILDING],
            RoundStatus.SANKEY_BUILDING: [RoundStatus.COMPLETE],
        }

        # All states can transition to FAILED
        if next_status == RoundStatus.FAILED:
            self.status = next_status
            self.updated_at = datetime.utcnow()
            return

        # Check if transition is valid
        allowed = valid_transitions.get(self.status, [])
        if next_status not in allowed:
            raise ValueError(
                f"Invalid state transition: {self.status} → {next_status}. "
                f"Allowed transitions from {self.status}: {allowed}"
            )

        self.status = next_status

        # Set completed_at when reaching COMPLETE
        if next_status == RoundStatus.COMPLETE:
            self.completed_at = datetime.utcnow()

        self.updated_at = datetime.utcnow()

    def can_advance(self) -> tuple[bool, Optional[str]]:
        """
        Check if this round is ready for advancement to SUBMISSION_OPEN.

        Requirements for advancement (T057):
        1. Sankey must be complete (status = COMPLETE, which implies SANKEY_BUILDING finished)
        2. Question must be ready:
           - For HOST_DEFINED mode: question_text must be set
           - For AUTO_GENERATED mode: status must be QUESTION_READY

        Returns:
            Tuple of (can_advance: bool, reason: Optional[str])
            - (True, None) if ready to advance
            - (False, reason) if blocked with explanation

        Note: This method checks the current round's readiness. For HOST_DEFINED,
        the question should already be set at creation. For AUTO_GENERATED,
        the status transitions to QUESTION_READY after generation completes.
        """
        # Check 1: Must be in a pre-submission state
        if self.status == RoundStatus.PENDING:
            # For PENDING rounds, check if question is ready
            # HOST_DEFINED: question should be pre-populated (question_text is set at creation)
            # AUTO_GENERATED: needs to transition to QUESTION_READY first

            # Check discussion mode to determine question readiness criteria
            from .discussion import DiscussionMode
            if self.discussion and self.discussion.mode == DiscussionMode.AUTO_GENERATED:
                # For AUTO_GENERATED mode beyond round 1, we expect QUESTION_READY status
                if self.round_num > 1 and self.question_id is None:
                    return (False, "Waiting for question generation (status should be QUESTION_READY)")

            # For HOST_DEFINED or Round 1, question_text should be set
            if not self.question_text or len(self.question_text.strip()) == 0:
                return (False, "Question text not set")

            return (True, None)

        elif self.status == RoundStatus.QUESTION_READY:
            # AUTO_GENERATED mode: question has been generated and validated
            if not self.question_text or len(self.question_text.strip()) == 0:
                return (False, "Question text not set despite QUESTION_READY status")

            return (True, None)

        elif self.status == RoundStatus.QUESTION_GENERATION_FAILED:
            # Generation failed, waiting for host to provide manual question
            return (False, "Question generation failed - host must provide manual question")

        else:
            # Already past submission phase or in wrong state
            return (False, f"Round in {self.status.value} state - cannot advance from this state")

    def set_dropout_count(self, count: int) -> None:
        """
        Set the dropout count for this round.

        T068: Store dropout analytics in Round model.

        Args:
            count: Number of participants who dropped out before this round

        Raises:
            ValueError: If count is negative or if this is round 1
        """
        if count < 0:
            raise ValueError(f"dropout_count cannot be negative, got {count}")

        if self.round_num == 1:
            raise ValueError("Round 1 cannot have dropouts (no previous round)")

        self.dropout_count = count
        self.updated_at = datetime.utcnow()

    def get_dropout_rate(self, previous_round_participant_count: int) -> float:
        """
        Calculate dropout rate for this round.

        T068: Calculate dropout rate per round.

        Args:
            previous_round_participant_count: Number of participants in previous round

        Returns:
            Dropout rate (dropout_count / previous_count), 0.0 if no previous participants

        Raises:
            ValueError: If dropout_count is None
        """
        if self.dropout_count is None:
            raise ValueError("dropout_count not set - call set_dropout_count() first")

        if previous_round_participant_count == 0:
            return 0.0

        return self.dropout_count / previous_round_participant_count

    def validate(self) -> None:
        """
        Validate round state consistency.

        Checks:
        - round_num valid for parent discussion
        - question format valid
        - window duration in range
        - timing fields NULL when appropriate
        - approval_deadline correct

        Raises:
            ValueError: If validation fails
        """
        # Validate question
        self._validate_question('question_text', self.question_text)

        # Validate window duration
        self._validate_window_duration(
            'submission_window_duration_sec',
            self.submission_window_duration_sec
        )

        # Check timing fields consistency
        if self.status in (RoundStatus.PENDING, RoundStatus.QUESTION_READY):
            if self.submission_window_start is not None:
                raise ValueError(
                    f"submission_window_start must be NULL when status={self.status}"
                )

        # Validate approval_deadline computation
        if self.submission_window_end is not None and self.approval_deadline is not None:
            expected_deadline = self.submission_window_end + timedelta(minutes=10)
            # Allow small time drift (1 second)
            diff = abs((self.approval_deadline - expected_deadline).total_seconds())
            if diff > 1:
                raise ValueError(
                    f"approval_deadline must be window_end + 10 minutes, "
                    f"got {diff}s difference"
                )

    def __repr__(self) -> str:
        return (
            f"<Round(id={self.round_id}, "
            f"discussion={self.discussion_id}, "
            f"num={self.round_num}, "
            f"status={self.status})>"
        )
