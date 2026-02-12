"""Discussion model - Container for bounded synchronous deliberation event."""
from sqlalchemy import Column, String, Integer, Enum as SQLEnum, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional
import uuid

from . import BaseModel
from .protocol_state import DiscussionStatus, DiscussionMode, DiscussionTimingMode


class Discussion(BaseModel):
    """
    Discussion entity representing a bounded, synchronous deliberation event.

    A Discussion contains multiple Rounds and tracks Participants across the
    discussion lifecycle. State transitions are enforced through methods.

    Attributes:
        discussion_id: Unique identifier (UUID primary key)
        community_id: Owning community identifier
        mode: Discussion mode (HOST_DEFINED | AUTO_GENERATED)
        total_rounds: Maximum rounds (1-10, set at creation)
        status: Current lifecycle state
        started_at: First round start timestamp (NULL until started)
        completed_at: Final report generation timestamp
        terminated_reason: Reason if status=TERMINATED
        host_user_id: User who created the discussion
        created_at: Creation timestamp
        updated_at: Last update timestamp

    Relationships:
        rounds: One-to-many with Round
        participants: One-to-many with Participant

    State Machine:
        CREATED → ACTIVE (via start())
        ACTIVE → COMPLETED (via complete())
        ACTIVE → TERMINATED (via terminate())
    """

    __tablename__ = "discussions"

    # Primary Key
    discussion_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    community_id = Column(UUID(as_uuid=True), nullable=False)
    host_user_id = Column(UUID(as_uuid=True), nullable=False)

    # Core Fields
    mode = Column(
        SQLEnum(DiscussionMode, name="discussion_mode"),
        nullable=False
    )
    total_rounds = Column(Integer, nullable=False)
    current_round_num = Column(
        Integer,
        nullable=False,
        default=0,
        comment="0 if not started, 1-N for active rounds"
    )
    status = Column(
        SQLEnum(DiscussionStatus, name="discussion_status"),
        nullable=False,
        default=DiscussionStatus.CREATED
    )

    # Timing Mode Fields
    timing_mode = Column(
        SQLEnum(DiscussionTimingMode, name="discussion_timing_mode"),
        nullable=False,
        default=DiscussionTimingMode.SYNCHRONOUS
    )
    round_duration_hours = Column(
        Integer,
        nullable=True,
        comment="For async mode: soft deadline in hours"
    )
    min_submissions_for_advance = Column(
        Integer,
        nullable=True,
        comment="For async mode: auto-advance threshold"
    )
    auto_advance_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="For async mode: enable auto-close when conditions met"
    )

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Optional Fields
    terminated_reason = Column(String(500), nullable=True)

    # Relationships
    question_sequence = relationship(
        "QuestionSequence",
        back_populates="discussion",
        uselist=False,
        cascade="all, delete-orphan"
    )
    rounds = relationship(
        "Round",
        back_populates="discussion",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    participants = relationship(
        "Participant",
        back_populates="discussion",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Indexes
    __table_args__ = (
        Index("ix_discussions_community_created", "community_id", "created_at"),
        Index("ix_discussions_host_created", "host_user_id", "created_at"),
        Index("ix_discussions_status", "status"),
    )

    def __init__(
        self,
        community_id: uuid.UUID,
        host_user_id: uuid.UUID,
        mode: DiscussionMode,
        total_rounds: int,
        timing_mode: DiscussionTimingMode = DiscussionTimingMode.SYNCHRONOUS,
        round_duration_hours: Optional[int] = None,
        min_submissions_for_advance: Optional[int] = None,
        auto_advance_enabled: bool = False,
        **kwargs
    ):
        """
        Initialize a new Discussion.

        Args:
            community_id: UUID of the owning community
            host_user_id: UUID of the user creating the discussion
            mode: Discussion mode (HOST_DEFINED or AUTO_GENERATED)
            total_rounds: Maximum number of rounds (1-10)
            timing_mode: Timing mode (SYNCHRONOUS or ASYNCHRONOUS)
            round_duration_hours: For async mode, soft deadline in hours
            min_submissions_for_advance: For async mode, auto-advance threshold
            auto_advance_enabled: For async mode, enable auto-close

        Raises:
            ValueError: If total_rounds not in range [1, 10]
        """
        if not 1 <= total_rounds <= 10:
            raise ValueError(f"total_rounds must be between 1 and 10, got {total_rounds}")

        super().__init__(**kwargs)
        self.discussion_id = kwargs.get('discussion_id', uuid.uuid4())
        self.community_id = community_id
        self.host_user_id = host_user_id
        self.mode = mode
        self.total_rounds = total_rounds
        self.status = DiscussionStatus.CREATED
        self.timing_mode = timing_mode
        self.round_duration_hours = round_duration_hours
        self.min_submissions_for_advance = min_submissions_for_advance
        self.auto_advance_enabled = auto_advance_enabled

    def start(self) -> None:
        """
        Transition discussion from CREATED to ACTIVE.

        Sets started_at timestamp. Can only be called when status=CREATED.

        Raises:
            ValueError: If status is not CREATED
        """
        if self.status != DiscussionStatus.CREATED:
            raise ValueError(
                f"Cannot start discussion in status {self.status}. "
                f"Must be in CREATED status."
            )

        self.status = DiscussionStatus.ACTIVE
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def complete(self) -> None:
        """
        Transition discussion from ACTIVE to COMPLETED.

        Sets completed_at timestamp. Can only be called when status=ACTIVE
        and all rounds are COMPLETE.

        Raises:
            ValueError: If status is not ACTIVE or rounds not all complete
        """
        if self.status != DiscussionStatus.ACTIVE:
            raise ValueError(
                f"Cannot complete discussion in status {self.status}. "
                f"Must be in ACTIVE status."
            )

        # Validate all rounds are complete
        from .protocol_state import RoundStatus
        incomplete_rounds = [
            r for r in self.rounds
            if r.status != RoundStatus.COMPLETE
        ]
        if incomplete_rounds:
            raise ValueError(
                f"Cannot complete discussion: {len(incomplete_rounds)} rounds "
                f"are not COMPLETE"
            )

        self.status = DiscussionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def terminate(self, reason: str) -> None:
        """
        Transition discussion from ACTIVE to TERMINATED.

        Sets completed_at timestamp and terminated_reason. Can only be called
        when status=ACTIVE.

        Args:
            reason: Human-readable reason for termination

        Raises:
            ValueError: If status is not ACTIVE
        """
        if self.status != DiscussionStatus.ACTIVE:
            raise ValueError(
                f"Cannot terminate discussion in status {self.status}. "
                f"Must be in ACTIVE status."
            )

        self.status = DiscussionStatus.TERMINATED
        self.terminated_reason = reason
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    @property
    def is_ready_for_advancement(self) -> bool:
        """
        Check if discussion is ready to advance to the next round (T060).

        Returns True if:
        - Discussion is ACTIVE
        - Current round exists and is COMPLETE
        - Not at final round yet

        Returns:
            bool: True if ready for advancement, False otherwise
        """
        # Must be ACTIVE
        if self.status != DiscussionStatus.ACTIVE:
            return False

        # Must not be at final round
        if self.current_round_num >= self.total_rounds:
            return False

        # Get current round
        from .protocol_state import RoundStatus
        current_round = next(
            (r for r in self.rounds if r.round_num == self.current_round_num),
            None
        )

        if current_round is None:
            return False

        # Current round must be COMPLETE (includes Sankey completion)
        return current_round.status == RoundStatus.COMPLETE

    def validate(self) -> None:
        """
        Validate discussion state consistency.

        Checks:
        - total_rounds in range [1, 10]
        - started_at NULL when status=CREATED
        - completed_at NULL unless status in (COMPLETED, TERMINATED)
        - mode cannot change after start

        Raises:
            ValueError: If validation fails
        """
        if not 1 <= self.total_rounds <= 10:
            raise ValueError(f"total_rounds must be 1-10, got {self.total_rounds}")

        if self.status == DiscussionStatus.CREATED and self.started_at is not None:
            raise ValueError("started_at must be NULL when status=CREATED")

        if self.status == DiscussionStatus.ACTIVE and self.started_at is None:
            raise ValueError("started_at must be set when status=ACTIVE")

        if self.status not in (DiscussionStatus.COMPLETED, DiscussionStatus.TERMINATED):
            if self.completed_at is not None:
                raise ValueError(
                    f"completed_at must be NULL when status={self.status}"
                )

    def __repr__(self) -> str:
        return (
            f"<Discussion(id={self.discussion_id}, "
            f"mode={self.mode}, "
            f"status={self.status}, "
            f"rounds={self.total_rounds})>"
        )
