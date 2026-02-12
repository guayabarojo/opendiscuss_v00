"""
Pydantic schemas for API request/response models.

Maps to OpenAPI spec in contracts/discussion-api.yaml.
Includes schemas for Input Collection Protocol - Spec 002.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Discussion Schemas
# ============================================================================


class CreateDiscussionRequest(BaseModel):
    """Request model for POST /discussions."""

    community_id: UUID = Field(..., description="UUID of the community hosting the discussion")
    mode: str = Field(
        ...,
        description="HOST_DEFINED: Host provides all questions upfront | AUTO_GENERATED: System generates questions from Sankey patterns",
    )
    total_rounds: int = Field(
        ...,
        ge=1,
        le=10,
        description="Maximum number of rounds (MVP: 3-5 recommended)",
    )
    questions: Optional[List[str]] = Field(
        None,
        description="Required for HOST_DEFINED mode, ignored for AUTO_GENERATED",
        min_length=1,
        max_length=10,
    )
    seed_question: Optional[str] = Field(
        None,
        description="Initial question for AUTO_GENERATED mode",
        min_length=10,
        max_length=200,
    )
    timing_mode: str = Field(
        default="SYNCHRONOUS",
        description="SYNCHRONOUS: Strict time windows | ASYNCHRONOUS: Flexible submission periods",
    )
    round_duration_hours: Optional[int] = Field(
        None,
        description="For async mode: soft deadline in hours (e.g., 24)",
        ge=1,
        le=168,
    )
    min_submissions_for_advance: Optional[int] = Field(
        None,
        description="For async mode: auto-advance when this many submissions received",
        ge=1,
    )
    auto_advance_enabled: bool = Field(
        default=False,
        description="For async mode: enable auto-close when conditions met",
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate mode is valid."""
        if v not in ("HOST_DEFINED", "AUTO_GENERATED"):
            raise ValueError("mode must be HOST_DEFINED or AUTO_GENERATED")
        return v

    @field_validator("timing_mode")
    @classmethod
    def validate_timing_mode(cls, v: str) -> str:
        """Validate timing mode is valid."""
        if v not in ("SYNCHRONOUS", "ASYNCHRONOUS"):
            raise ValueError("timing_mode must be SYNCHRONOUS or ASYNCHRONOUS")
        return v

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate questions if provided."""
        if v is not None:
            for q in v:
                if not (10 <= len(q) <= 200):
                    raise ValueError(
                        f"Each question must be 10-200 characters, got {len(q)} chars"
                    )
        return v

    model_config = {"from_attributes": True}


class RoundInfo(BaseModel):
    """Round information for Discussion response."""

    round_id: UUID
    round_num: int
    status: str

    model_config = {"from_attributes": True}


class DiscussionResponse(BaseModel):
    """Response model for Discussion entity."""

    discussion_id: UUID
    community_id: UUID
    mode: str
    total_rounds: int
    current_round_num: int = Field(
        ..., description="0 if not started, 1-N for active rounds"
    )
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    terminated_reason: Optional[str] = None
    host_user_id: UUID
    # Timing mode fields (async discussion support)
    timing_mode: Optional[str] = Field(
        default="SYNCHRONOUS",
        description="SYNCHRONOUS: Strict time windows | ASYNCHRONOUS: Flexible submission periods"
    )
    round_duration_hours: Optional[int] = Field(
        None,
        description="For async mode: soft deadline in hours"
    )
    min_submissions_for_advance: Optional[int] = Field(
        None,
        description="For async mode: auto-advance threshold"
    )
    auto_advance_enabled: Optional[bool] = Field(
        default=False,
        description="For async mode: enable auto-close when conditions met"
    )
    rounds: List[RoundInfo] = Field(
        default_factory=list,
        description="List of rounds with their UUIDs and status"
    )
    # Phase 6 - Advancement status (T062)
    advancement_status: Optional[str] = Field(
        None,
        description="READY | BLOCKED_SANKEY | BLOCKED_QUESTION | WAITING_GENERATION | NOT_APPLICABLE",
    )
    can_advance: Optional[bool] = Field(
        None, description="True if discussion can advance to next round"
    )
    blockers: Optional[List[str]] = Field(
        None, description="List of reasons blocking advancement (empty if ready)"
    )
    # Phase 7 - Closure information (T073)
    is_closed: bool = Field(
        default=False,
        description="True if discussion is COMPLETED or TERMINATED"
    )
    closure_reason: Optional[str] = Field(
        default=None,
        description="COMPLETED or TERMINATED if is_closed=True"
    )
    closure_message: Optional[str] = Field(
        default=None,
        description="User-friendly closure message"
    )

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Override to add computed fields for closure information and rounds."""
        # Create instance using parent validation
        instance = super().model_validate(obj, **kwargs)

        # Add rounds information
        if hasattr(obj, 'rounds') and obj.rounds:
            instance.rounds = [
                RoundInfo(
                    round_id=r.round_id,
                    round_num=r.round_num,
                    status=r.status.value if hasattr(r.status, 'value') else str(r.status)
                )
                for r in sorted(obj.rounds, key=lambda x: x.round_num)
            ]

        # Add closure information based on status
        if hasattr(obj, 'status'):
            status_value = obj.status.value if hasattr(obj.status, 'value') else str(obj.status)
            instance.is_closed = status_value in ('COMPLETED', 'TERMINATED')

            if instance.is_closed:
                instance.closure_reason = status_value
                if status_value == 'COMPLETED':
                    instance.closure_message = "Discussion has ended. All questions have been completed."
                elif status_value == 'TERMINATED':
                    term_reason = getattr(obj, 'terminated_reason', None) or 'No reason provided.'
                    instance.closure_message = f"Discussion has been terminated. {term_reason}"
        else:
            instance.is_closed = False

        return instance


class AdvancementResponse(BaseModel):
    """Response model for POST /discussions/{id}/advance (T058)."""

    discussion_id: UUID
    previous_round_num: int = Field(..., description="Round that was just completed")
    current_round_num: int = Field(..., description="New current round (just opened)")
    new_round_status: str = Field(
        ..., description="Status of the newly opened round (SUBMISSION_OPEN)"
    )
    submission_window_end: Optional[datetime] = Field(
        None, description="When the new round's submission window closes"
    )
    message: str = Field(..., description="Success message")

    model_config = {"from_attributes": True}


# ============================================================================
# Round Schemas
# ============================================================================


class RoundResponse(BaseModel):
    """Response model for Round entity."""

    round_id: UUID
    discussion_id: UUID
    round_num: int
    question_text: str
    status: str
    submission_window_duration_sec: int
    submission_window_start: Optional[datetime] = None
    submission_window_end: Optional[datetime] = None
    approval_deadline: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RoundStatusResponse(BaseModel):
    """Response model for GET /rounds/{id}/status."""

    round_id: UUID
    status: str
    question_text: str = Field(..., description="Current question for this round")
    current_time: datetime
    submission_window_end: Optional[datetime] = None
    approval_deadline: Optional[datetime] = None
    remaining_time_sec: Optional[int] = Field(
        None,
        description="Seconds remaining in current timed phase (null if not in timed phase)",
    )
    participant_stats: Optional[dict] = Field(
        None,
        description="Participant statistics (submitted_count, approved_count, pending_approval_count)",
    )

    model_config = {"from_attributes": True}


# ============================================================================
# Participant Schemas
# ============================================================================


class ParticipantResponse(BaseModel):
    """Response model for Participant entity."""

    participant_id: UUID
    discussion_id: UUID
    user_id: UUID = Field(..., description="User account ID (for admin/host use only)")
    first_round: int
    last_round: Optional[int] = None
    dropout_reason: Optional[str] = None
    is_active: bool = Field(..., description="True if participant has not dropped out")
    created_at: datetime

    model_config = {"from_attributes": True}


class ParticipantListResponse(BaseModel):
    """Response model for GET /discussions/{id}/participants."""

    participants: List[ParticipantResponse]
    total: int
    active_count: int
    dropout_count: int

    model_config = {"from_attributes": True}


# ============================================================================
# Sankey/Report Schemas
# ============================================================================


class ThoughtSpaceResponse(BaseModel):
    """Response model for a thought space in Sankey column."""

    cluster_id: UUID
    label: str
    member_count: int
    member_pct: float = Field(..., ge=0.0, le=1.0)

    model_config = {"from_attributes": True}


class SankeyColumnResponse(BaseModel):
    """Response model for a Sankey column (one round)."""

    round_num: int
    thought_spaces: List[ThoughtSpaceResponse]

    model_config = {"from_attributes": True}


class FlowResponse(BaseModel):
    """Response model for a flow between thought spaces."""

    flow_id: UUID
    source_cluster_id: UUID
    target_cluster_id: UUID
    participant_count: int

    model_config = {"from_attributes": True}


class SankeyDiagramResponse(BaseModel):
    """Response model for Sankey diagram."""

    columns: List[SankeyColumnResponse]
    flows: List[FlowResponse]

    model_config = {"from_attributes": True}


class DiscussionReportResponse(BaseModel):
    """Response model for GET /discussions/{id}/report."""

    discussion_id: UUID
    sankey_diagram: SankeyDiagramResponse
    metadata: dict

    model_config = {"from_attributes": True}


# ============================================================================
# Submission Schemas
# ============================================================================


class SubmitRequest(BaseModel):
    """Request model for POST /submissions."""

    participant_id: UUID = Field(..., description="UUID of the participant submitting")
    round_id: UUID = Field(..., description="UUID of the round to submit to")
    submission_text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Submission text (1-2000 characters)",
    )
    modality: str = Field(
        default="text",
        description="Submission modality (text or voice)",
    )

    @field_validator("modality")
    @classmethod
    def validate_modality(cls, v: str) -> str:
        """Validate modality is valid."""
        if v not in ("text", "voice"):
            raise ValueError("modality must be text or voice")
        return v

    model_config = {"from_attributes": True}


class SubmissionResponse(BaseModel):
    """Response model for submission operations."""

    submission_id: UUID
    participant_id: UUID
    round_id: UUID
    submission_text: str
    modality: str
    submitted_at: datetime
    summary_status: str
    remaining_submissions: int = Field(
        ...,
        description="Number of submissions remaining in this round (max 3 per round)",
    )

    model_config = {"from_attributes": True}


class SubmissionHistoryItem(BaseModel):
    """Single submission item in history."""

    submission_id: UUID
    submission_text: str
    modality: str
    submitted_at: datetime
    summary_status: str = Field(
        ...,
        description="Status: PENDING, APPROVED, SUPERSEDED, REJECTED, APPROVAL_TIMEOUT",
    )
    is_currently_approved: bool = Field(
        ...,
        description="True if this submission's summary is currently approved",
    )

    model_config = {"from_attributes": True}


class SubmissionHistoryResponse(BaseModel):
    """Response model for GET /submissions/history."""

    participant_id: UUID
    round_id: UUID
    submissions: List[SubmissionHistoryItem] = Field(
        ...,
        description="Submissions ordered by submitted_at DESC (most recent first)",
    )
    total_submissions: int
    remaining_submissions: int = Field(
        ...,
        description="Number of submissions remaining in this round (max 3 per round)",
    )

    model_config = {"from_attributes": True}


# ============================================================================
# Error Schemas
# ============================================================================


class ErrorResponse(BaseModel):
    """Standard error response per OpenAPI spec."""

    error: str
    message: str
    details: Optional[dict] = None
    timestamp: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ============================================================================
# Input Collection Protocol (Spec 002) - New Schemas
# ============================================================================


class SubmissionModality(str, Enum):
    """Submission modality for Input Collection Protocol."""
    TEXT = "TEXT"
    VOICE = "VOICE"


class SubmissionRequest(BaseModel):
    """Request to submit text or accept transcript (Spec 002)."""
    participant_id: UUID
    round_id: UUID
    text: str = Field(..., min_length=1, max_length=5000)
    modality: SubmissionModality = SubmissionModality.TEXT


class InputCollectionSubmissionResponse(BaseModel):
    """Response after successful submission (Spec 002)."""
    submission_id: UUID
    participant_id: UUID
    round_id: UUID
    timestamp: datetime
    modality: SubmissionModality
    counted: bool

    model_config = {"from_attributes": True}


class SubmissionListResponse(BaseModel):
    """Response for listing participant submissions in a round (T048)."""
    submissions: List[InputCollectionSubmissionResponse]
    total_count: int
    max_allowed: int
    can_submit_more: bool

    model_config = {"from_attributes": True}


class WindowStatus(BaseModel):
    """Submission window status (Spec 002)."""
    round_id: UUID
    is_open: bool
    window_start: datetime
    window_end: datetime
    remaining_seconds: Optional[int] = None


class TranscriptRequest(BaseModel):
    """Request to transcribe audio (Spec 002)."""
    participant_id: UUID
    round_id: UUID


class TranscriptResponse(BaseModel):
    """Response from transcription (Spec 002)."""
    transcript_id: UUID
    recording_id: UUID
    transcript_text: str
    latency_ms: float


class AcceptTranscriptRequest(BaseModel):
    """Request to accept transcript and create submission (Spec 002)."""
    transcript_id: UUID


class WindowStatusResponse(BaseModel):
    """Response for GET /rounds/{id}/window - Window enforcement (T053)."""
    round_id: UUID
    window_start: Optional[datetime] = Field(None, description="When submission window opens")
    window_end: Optional[datetime] = Field(None, description="When submission window closes")
    current_time: datetime = Field(..., description="Server-authoritative current time (UTC)")
    time_remaining_seconds: Optional[int] = Field(
        None,
        description="Seconds until window closes (null if not open)"
    )
    is_open: bool = Field(..., description="True if submissions are currently accepted")
    status: str = Field(
        ...,
        description="NOT_OPEN | BEFORE_WINDOW | OPEN | CLOSED"
    )
    round_status: str = Field(..., description="Current round status from state machine")

    model_config = {"from_attributes": True}


# ============================================================================
# Dropout Handling Schemas (T067 - User Story 5)
# ============================================================================


class DropoutReportResponse(BaseModel):
    """Response for GET /rounds/{id}/dropouts (T067)."""
    round_id: UUID = Field(..., description="UUID of the round")
    round_num: int = Field(..., description="Round number in discussion")
    dropout_participant_ids: List[UUID] = Field(
        ...,
        description="List of participant IDs who dropped out before this round"
    )
    dropout_count: int = Field(..., description="Number of participants who dropped out")
    previous_round_participant_count: int = Field(
        ...,
        description="Total participants in previous round (0 for round 1)"
    )
    dropout_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Dropout rate (dropout_count / previous_count)"
    )

    model_config = {"from_attributes": True}
