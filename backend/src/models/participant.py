"""Participant model - Identity tracker for participant movement across rounds."""
from sqlalchemy import Column, Integer, Enum as SQLEnum, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from datetime import datetime
from typing import Optional
import uuid

from . import BaseModel
from .protocol_state import DropoutReason


class Participant(BaseModel):
    """
    Participant entity tracking user participation across discussion rounds.

    Decouples user identity from discussion-scoped participation. The
    participant_id is used by sub-protocols (Specs 2-6) to preserve privacy,
    while user_id is NEVER exposed to sub-protocols.

    Attributes:
        participant_id: Discussion-scoped unique identifier (UUID primary key)
        discussion_id: Parent discussion UUID (foreign key)
        user_id: User account UUID (NOT exposed to sub-protocols)
        first_round: Round number of first submission
        last_round: Round number of last submission (NULL if still active)
        dropout_reason: Reason for dropout (NULL if still active)
        created_at: First submission timestamp

    Relationships:
        discussion: Many-to-one with Discussion
        user: Many-to-one with User (future)
        submissions: One-to-many with Submission
        approved_summaries: One-to-many with ApprovedSummary

    Privacy Notes:
        - user_id is NEVER passed to sub-protocols (Specs 2-6)
        - Sub-protocols use only participant_id
        - LLM services log participant_id, not user_id

    Validation Rules:
        - (discussion_id, user_id) must be unique
        - first_round <= last_round (if last_round not NULL)
        - dropout_reason must be NULL if last_round is NULL
        - user_id must be validated against community membership before creation
    """

    __tablename__ = "participants"

    # Primary Key
    participant_id = Column(
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
    user_id = Column(UUID(as_uuid=True), nullable=False)

    # Core Fields
    first_round = Column(Integer, nullable=False)
    last_round = Column(Integer, nullable=True)
    dropout_reason = Column(
        SQLEnum(DropoutReason, name="dropout_reason"),
        nullable=True
    )

    # Relationships
    discussion = relationship("Discussion", back_populates="participants")
    submissions = relationship(
        "Submission",
        back_populates="participant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    approved_summaries = relationship(
        "ApprovedSummary",
        back_populates="participant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    summaries = relationship(
        "Summary",
        back_populates="participant",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Indexes and Constraints
    __table_args__ = (
        Index(
            "ix_participants_discussion_user",
            "discussion_id",
            "user_id",
            unique=True
        ),
        Index("ix_participants_user", "user_id"),
        CheckConstraint(
            "first_round >= 1",
            name="ck_participants_first_round_positive"
        ),
        CheckConstraint(
            "last_round IS NULL OR last_round >= first_round",
            name="ck_participants_last_round_after_first"
        ),
        CheckConstraint(
            "(last_round IS NULL AND dropout_reason IS NULL) OR "
            "(last_round IS NOT NULL AND dropout_reason IS NOT NULL)",
            name="ck_participants_dropout_consistency"
        ),
    )

    def __init__(
        self,
        discussion_id: uuid.UUID,
        user_id: uuid.UUID,
        first_round: int,
        **kwargs
    ):
        """
        Initialize a new Participant.

        Args:
            discussion_id: UUID of parent discussion
            user_id: UUID of user account (validated against community membership)
            first_round: Round number of first submission (1-indexed)

        Raises:
            ValueError: If first_round < 1
        """
        if first_round < 1:
            raise ValueError(f"first_round must be >= 1, got {first_round}")

        super().__init__(**kwargs)
        self.participant_id = kwargs.get('participant_id', uuid.uuid4())
        self.discussion_id = discussion_id
        self.user_id = user_id
        self.first_round = first_round
        self.last_round = None
        self.dropout_reason = None

    @validates('first_round')
    def _validate_first_round(self, key: str, value: int) -> int:
        """
        Validate first_round is positive.

        Args:
            key: Column name
            value: Round number

        Returns:
            Validated round number

        Raises:
            ValueError: If round number < 1
        """
        if value < 1:
            raise ValueError(f"first_round must be >= 1, got {value}")
        return value

    @validates('last_round')
    def _validate_last_round(self, key: str, value: Optional[int]) -> Optional[int]:
        """
        Validate last_round >= first_round.

        Args:
            key: Column name
            value: Round number or None

        Returns:
            Validated round number

        Raises:
            ValueError: If last_round < first_round
        """
        if value is not None and value < self.first_round:
            raise ValueError(
                f"last_round ({value}) must be >= first_round ({self.first_round})"
            )
        return value

    def mark_dropout(self, reason: DropoutReason, round_num: int) -> None:
        """
        Mark participant as dropped out.

        Sets last_round and dropout_reason. Participant is considered inactive
        after this point but can potentially re-enter in future rounds.

        Args:
            reason: Reason for dropout
            round_num: Round number where dropout occurred

        Raises:
            ValueError: If already marked as dropout or round_num invalid
        """
        if self.last_round is not None:
            raise ValueError(
                f"Participant already marked as dropout at round {self.last_round}"
            )

        if round_num < self.first_round:
            raise ValueError(
                f"Dropout round ({round_num}) must be >= first_round ({self.first_round})"
            )

        self.last_round = round_num
        self.dropout_reason = reason
        self.updated_at = datetime.utcnow()

    def is_active(self) -> bool:
        """
        Check if participant is currently active.

        Returns:
            True if last_round is NULL (not dropped out), False otherwise
        """
        return self.last_round is None

    def is_active_in_round(self, round_num: int) -> bool:
        """
        Check if participant is active in a specific round.

        A participant is active in a round if:
        - round_num >= first_round
        - last_round is NULL OR round_num <= last_round

        Args:
            round_num: Round number to check

        Returns:
            True if participant is active in the specified round
        """
        if round_num < self.first_round:
            return False

        if self.last_round is None:
            return True

        return round_num <= self.last_round

    def get_round_span(self) -> tuple[int, Optional[int]]:
        """
        Get the range of rounds this participant was active.

        Returns:
            Tuple of (first_round, last_round)
        """
        return (self.first_round, self.last_round)

    def validate(self) -> None:
        """
        Validate participant state consistency.

        Checks:
        - first_round >= 1
        - last_round >= first_round (if not NULL)
        - dropout_reason consistency with last_round

        Raises:
            ValueError: If validation fails
        """
        if self.first_round < 1:
            raise ValueError(f"first_round must be >= 1, got {self.first_round}")

        if self.last_round is not None:
            if self.last_round < self.first_round:
                raise ValueError(
                    f"last_round ({self.last_round}) must be >= "
                    f"first_round ({self.first_round})"
                )

        # Check dropout_reason consistency
        if self.last_round is None and self.dropout_reason is not None:
            raise ValueError(
                "dropout_reason must be NULL when last_round is NULL (participant still active)"
            )

        if self.last_round is not None and self.dropout_reason is None:
            raise ValueError(
                "dropout_reason must be set when last_round is set (participant dropped out)"
            )

    def __repr__(self) -> str:
        status = "active" if self.is_active() else f"dropout@{self.last_round}"
        return (
            f"<Participant(id={self.participant_id}, "
            f"discussion={self.discussion_id}, "
            f"rounds={self.first_round}-{self.last_round or '?'}, "
            f"status={status})>"
        )
