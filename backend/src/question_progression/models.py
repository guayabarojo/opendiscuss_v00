"""
SQLAlchemy models for Question Progression Protocol (Spec 006).

Defines QuestionSequence, Question, and QuestionProvenance entities with
relationships, validation, and immutability guarantees.
"""
from sqlalchemy import Column, String, Integer, Float, Enum as SQLEnum, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from datetime import datetime
from typing import Optional, List
from enum import Enum
import uuid

from src.models import BaseModel


# Enums for Question Progression Protocol

class SequenceMode(str, Enum):
    """Mode for question sequence generation."""
    HOST_DEFINED = "HOST_DEFINED"
    AUTO_GENERATED = "AUTO_GENERATED"


class CompletionStatus(str, Enum):
    """Completion status for question sequence."""
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


class QuestionMode(str, Enum):
    """Mode for individual question (inherits from sequence or manual)."""
    HOST_DEFINED = "HOST_DEFINED"
    AUTO_GENERATED = "AUTO_GENERATED"


class ValidationStatus(str, Enum):
    """Validation status for question text."""
    VALID = "VALID"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


# Models

class QuestionSequence(BaseModel):
    """
    QuestionSequence entity representing ordered collection of questions for a discussion.

    In HOST_DEFINED mode, all questions are created at discussion creation.
    In AUTO_GENERATED mode, questions are added incrementally after each Sankey completes.

    Attributes:
        sequence_id: Unique identifier (UUID primary key)
        discussion_id: Parent discussion UUID (foreign key, unique)
        mode: Sequence mode (HOST_DEFINED | AUTO_GENERATED)
        total_questions: Fixed count for HOST mode (1-10), NULL for AUTO mode
        current_index: Index of current question (0-based)
        completion_status: IN_PROGRESS | COMPLETED | TERMINATED
        created_at: Sequence creation timestamp

    Relationships:
        discussion: Many-to-one with Discussion
        questions: One-to-many with Question
    """

    __tablename__ = "question_sequences"

    # Primary Key
    sequence_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    discussion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("discussions.discussion_id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Core Fields
    mode = Column(
        SQLEnum(SequenceMode, name="sequence_mode"),
        nullable=False
    )
    total_questions = Column(Integer, nullable=True)
    current_index = Column(Integer, nullable=False, default=0)
    completion_status = Column(
        SQLEnum(CompletionStatus, name="completion_status"),
        nullable=False,
        default=CompletionStatus.IN_PROGRESS
    )

    # Relationships
    discussion = relationship("Discussion", back_populates="question_sequence")
    questions = relationship(
        "Question",
        back_populates="sequence",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Question.question_order"
    )

    # Indexes and Constraints
    __table_args__ = (
        CheckConstraint('current_index >= 0', name='ck_question_sequences_index_non_negative'),
        CheckConstraint(
            "(mode = 'HOST_DEFINED' AND total_questions BETWEEN 1 AND 10) OR (mode = 'AUTO_GENERATED' AND total_questions IS NULL)",
            name='ck_question_sequences_total_questions_by_mode'
        ),
    )

    def __init__(
        self,
        discussion_id: uuid.UUID,
        mode: SequenceMode,
        total_questions: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize a new QuestionSequence.

        Args:
            discussion_id: UUID of parent discussion
            mode: Sequence mode (HOST_DEFINED or AUTO_GENERATED)
            total_questions: Fixed count for HOST mode (1-10), None for AUTO mode

        Raises:
            ValueError: If validation fails
        """
        super().__init__(**kwargs)
        self.sequence_id = kwargs.get('sequence_id', uuid.uuid4())
        self.discussion_id = discussion_id
        self.mode = mode
        self.total_questions = total_questions
        self.current_index = 0
        self.completion_status = CompletionStatus.IN_PROGRESS

        # Validate on initialization
        self._validate_total_questions(mode, total_questions)

    @staticmethod
    def _validate_total_questions(mode: SequenceMode, total_questions: Optional[int]) -> None:
        """
        Validate total_questions based on mode.

        Args:
            mode: Sequence mode
            total_questions: Total questions value

        Raises:
            ValueError: If validation fails
        """
        if mode == SequenceMode.HOST_DEFINED:
            if total_questions is None:
                raise ValueError("total_questions must be set for HOST_DEFINED mode")
            if not 1 <= total_questions <= 10:
                raise ValueError(f"total_questions must be 1-10 for HOST_DEFINED mode, got {total_questions}")
        elif mode == SequenceMode.AUTO_GENERATED:
            if total_questions is not None:
                raise ValueError("total_questions must be NULL for AUTO_GENERATED mode")

    def __repr__(self) -> str:
        return (
            f"<QuestionSequence(id={self.sequence_id}, "
            f"discussion={self.discussion_id}, "
            f"mode={self.mode}, "
            f"status={self.completion_status})>"
        )


class Question(BaseModel):
    """
    Question entity representing individual question within a sequence.

    Questions are validated against constitutional constraints (What/How only,
    no voting/ranking keywords, no binary choices). Once a round starts,
    questions become immutable.

    Attributes:
        question_id: Unique identifier (UUID primary key)
        sequence_id: Parent sequence UUID (foreign key)
        order: Sequential order (1-indexed)
        question_text: Validated question text (10-200 chars)
        mode: Question mode (HOST_DEFINED | AUTO_GENERATED)
        validation_status: VALID | REJECTED | PENDING
        created_at: Question creation timestamp
        immutable_since: Timestamp when question became immutable (round started)

    Relationships:
        sequence: Many-to-one with QuestionSequence
        provenance: One-to-one with QuestionProvenance (AUTO mode only)
        rounds: One-to-many with Round (rounds using this question)
    """

    __tablename__ = "questions"

    # Primary Key
    question_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    sequence_id = Column(
        UUID(as_uuid=True),
        ForeignKey("question_sequences.sequence_id", ondelete="CASCADE"),
        nullable=False
    )

    # Core Fields - renamed from 'order' to 'question_order' to avoid SQL reserved word
    question_order = Column("question_order", Integer, nullable=False)
    question_text = Column(String(200), nullable=False)
    mode = Column(
        SQLEnum(QuestionMode, name="question_mode"),
        nullable=False
    )
    validation_status = Column(
        SQLEnum(ValidationStatus, name="validation_status"),
        nullable=False,
        default=ValidationStatus.PENDING
    )
    immutable_since = Column(DateTime, nullable=True)

    # Relationships
    sequence = relationship("QuestionSequence", back_populates="questions")
    provenance = relationship(
        "QuestionProvenance",
        back_populates="question",
        uselist=False,
        cascade="all, delete-orphan"
    )
    rounds = relationship("Round", back_populates="question")

    # Indexes and Constraints
    __table_args__ = (
        Index("uq_questions_sequence_order", "sequence_id", "question_order", unique=True),
        CheckConstraint('question_order >= 1', name='ck_questions_order_positive'),
        CheckConstraint(
            'char_length(question_text) BETWEEN 10 AND 200',
            name='ck_questions_text_length'
        ),
    )

    def __init__(
        self,
        sequence_id: uuid.UUID,
        order: int,
        question_text: str,
        mode: QuestionMode,
        validation_status: ValidationStatus = ValidationStatus.PENDING,
        **kwargs
    ):
        """
        Initialize a new Question.

        Args:
            sequence_id: UUID of parent sequence
            order: Sequential order (1-indexed)
            question_text: Question text (10-200 chars)
            mode: Question mode (HOST_DEFINED or AUTO_GENERATED)
            validation_status: Validation status (default PENDING)

        Raises:
            ValueError: If validation fails
        """
        super().__init__(**kwargs)
        self.question_id = kwargs.get('question_id', uuid.uuid4())
        self.sequence_id = sequence_id
        self.question_order = order
        self.question_text = question_text
        self.mode = mode
        self.validation_status = validation_status
        self.immutable_since = None

        # Validate on initialization
        self._validate_order(order)
        self._validate_question_text(question_text)

    @property
    def order(self) -> int:
        """Alias for question_order for backward compatibility."""
        return self.question_order

    @staticmethod
    def _validate_order(order: int) -> None:
        """
        Validate order is positive.

        Args:
            order: Order value

        Raises:
            ValueError: If order < 1
        """
        if order < 1:
            raise ValueError(f"order must be >= 1, got {order}")

    @staticmethod
    def _validate_question_text(text: str) -> None:
        """
        Validate question text length.

        Args:
            text: Question text

        Raises:
            ValueError: If text length not in range [10, 200]
        """
        if not 10 <= len(text) <= 200:
            raise ValueError(
                f"question_text must be 10-200 characters, got {len(text)}"
            )

    def mark_immutable(self) -> None:
        """
        Mark question as immutable (called when round starts).

        Sets immutable_since timestamp to current UTC time.
        """
        if self.immutable_since is None:
            self.immutable_since = datetime.utcnow()
            self.updated_at = datetime.utcnow()

    def is_immutable(self) -> bool:
        """
        Check if question is immutable.

        Returns:
            True if question is immutable (round has started), False otherwise
        """
        return self.immutable_since is not None

    def __repr__(self) -> str:
        return (
            f"<Question(id={self.question_id}, "
            f"sequence={self.sequence_id}, "
            f"order={self.question_order}, "
            f"mode={self.mode}, "
            f"status={self.validation_status})>"
        )


class QuestionProvenance(BaseModel):
    """
    QuestionProvenance entity for tracking auto-generated question metadata.

    Supports audit, debugging, and quality monitoring for questions generated
    by the LLM-based question progression system.

    Attributes:
        provenance_id: Unique identifier (UUID primary key)
        question_id: Question UUID (foreign key, unique)
        generation_timestamp: When question was generated
        generation_latency_ms: Time from request to completion
        input_sankey_hash: SHA-256 of Sankey JSON (reproducibility)
        input_round_id: Round that triggered generation (FK)
        llm_model: Model identifier (e.g., "claude-sonnet-4-5")
        prompt_tokens: Token count for prompt
        completion_tokens: Token count for response
        retry_count: Number of retries (API failures)
        validation_attempts: Number of validation attempts
        previous_questions_count: Number of prior questions in context

    Relationships:
        question: One-to-one with Question
        input_round: Many-to-one with Round
    """

    __tablename__ = "question_provenance"

    # Primary Key
    provenance_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.question_id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    input_round_id = Column(
        UUID(as_uuid=True),
        ForeignKey("rounds.round_id", ondelete="CASCADE"),
        nullable=False
    )

    # Generation Metadata
    generation_timestamp = Column(DateTime, nullable=False)
    generation_latency_ms = Column(Float, nullable=False)
    input_sankey_hash = Column(String(64), nullable=False)

    # LLM Metadata
    llm_model = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)

    # Quality Metrics
    retry_count = Column(Integer, nullable=False, default=0)
    validation_attempts = Column(Integer, nullable=False, default=1)
    previous_questions_count = Column(Integer, nullable=False)

    # Relationships
    question = relationship("Question", back_populates="provenance")
    input_round = relationship("Round", foreign_keys=[input_round_id])

    # Indexes and Constraints
    __table_args__ = (
        Index("ix_question_provenance_input_round", "input_round_id"),
        Index("ix_question_provenance_timestamp", "generation_timestamp"),
        CheckConstraint('generation_latency_ms >= 0', name='ck_question_provenance_latency_non_negative'),
        CheckConstraint('prompt_tokens >= 0', name='ck_question_provenance_prompt_tokens_non_negative'),
        CheckConstraint('completion_tokens >= 0', name='ck_question_provenance_completion_tokens_non_negative'),
        CheckConstraint('retry_count >= 0', name='ck_question_provenance_retry_count_non_negative'),
        CheckConstraint('validation_attempts >= 1', name='ck_question_provenance_validation_attempts_positive'),
        CheckConstraint('previous_questions_count >= 0', name='ck_question_provenance_previous_count_non_negative'),
    )

    def __init__(
        self,
        question_id: uuid.UUID,
        input_round_id: uuid.UUID,
        generation_timestamp: datetime,
        generation_latency_ms: float,
        input_sankey_hash: str,
        llm_model: str,
        prompt_tokens: int,
        completion_tokens: int,
        retry_count: int = 0,
        validation_attempts: int = 1,
        previous_questions_count: int = 0,
        **kwargs
    ):
        """
        Initialize a new QuestionProvenance.

        Args:
            question_id: UUID of the question
            input_round_id: UUID of the round that triggered generation
            generation_timestamp: When question was generated
            generation_latency_ms: Time from request to completion
            input_sankey_hash: SHA-256 of Sankey JSON
            llm_model: Model identifier
            prompt_tokens: Token count for prompt
            completion_tokens: Token count for response
            retry_count: Number of retries (default 0)
            validation_attempts: Number of validation attempts (default 1)
            previous_questions_count: Number of prior questions (default 0)

        Raises:
            ValueError: If validation fails
        """
        super().__init__(**kwargs)
        self.provenance_id = kwargs.get('provenance_id', uuid.uuid4())
        self.question_id = question_id
        self.input_round_id = input_round_id
        self.generation_timestamp = generation_timestamp
        self.generation_latency_ms = generation_latency_ms
        self.input_sankey_hash = input_sankey_hash
        self.llm_model = llm_model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.retry_count = retry_count
        self.validation_attempts = validation_attempts
        self.previous_questions_count = previous_questions_count

    def __repr__(self) -> str:
        return (
            f"<QuestionProvenance(id={self.provenance_id}, "
            f"question={self.question_id}, "
            f"model={self.llm_model}, "
            f"latency={self.generation_latency_ms}ms)>"
        )
