"""
Event type schemas for the OpenDiscuss Discussion Protocol.

All events use Pydantic models for type safety and validation.
Events represent state transitions and protocol coordination points.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DiscussionStartedEvent(BaseModel):
    """Emitted when a discussion transitions to ACTIVE status."""

    discussion_id: UUID = Field(description="Unique identifier for the discussion")
    round_id: UUID = Field(description="Unique identifier for the first round")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when discussion started",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "discussion_id": "550e8400-e29b-41d4-a716-446655440000",
                "round_id": "660e8400-e29b-41d4-a716-446655440001",
                "timestamp": "2026-01-29T12:00:00Z",
            }
        }
    }


class SubmissionSummary(BaseModel):
    """Summary of a single submission for event payloads."""

    submission_id: UUID = Field(description="Unique identifier for the submission")
    participant_id: UUID = Field(description="Participant who submitted")
    submission_text: str = Field(description="Original submission text")
    modality: str = Field(description="Submission modality (text, voice, etc)")
    submitted_at: datetime = Field(description="UTC timestamp when submitted")


class SubmissionWindowClosedEvent(BaseModel):
    """Emitted when a round's submission window closes."""

    round_id: UUID = Field(description="Unique identifier for the round")
    submissions: List[SubmissionSummary] = Field(
        description="All submissions received during window"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when window closed",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "round_id": "660e8400-e29b-41d4-a716-446655440001",
                "submissions": [
                    {
                        "submission_id": "770e8400-e29b-41d4-a716-446655440002",
                        "participant_id": "880e8400-e29b-41d4-a716-446655440003",
                        "submission_text": "Sample submission text",
                        "modality": "text",
                        "submitted_at": "2026-01-29T12:05:00Z",
                    }
                ],
                "timestamp": "2026-01-29T12:06:00Z",
            }
        }
    }


class ApprovedSummarySummary(BaseModel):
    """Summary of an approved summary for event payloads."""

    summary_id: UUID = Field(description="Unique identifier for the summary")
    participant_id: UUID = Field(description="Participant who owns this summary")
    submission_id: UUID = Field(description="Original submission this summarizes")
    summary_text: str = Field(description="Approved summary text")
    approved_at: datetime = Field(description="UTC timestamp when approved")


class SummarizationCompleteEvent(BaseModel):
    """Emitted when summarization sub-protocol completes for a round."""

    round_id: UUID = Field(description="Unique identifier for the round")
    approved_summaries: List[ApprovedSummarySummary] = Field(
        description="All approved summaries for this round"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when summarization completed",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "round_id": "660e8400-e29b-41d4-a716-446655440001",
                "approved_summaries": [
                    {
                        "summary_id": "990e8400-e29b-41d4-a716-446655440004",
                        "participant_id": "880e8400-e29b-41d4-a716-446655440003",
                        "submission_id": "770e8400-e29b-41d4-a716-446655440002",
                        "summary_text": "Approved summary text",
                        "approved_at": "2026-01-29T12:08:00Z",
                    }
                ],
                "timestamp": "2026-01-29T12:10:00Z",
            }
        }
    }


class ThoughtSpaceSummary(BaseModel):
    """Summary of a thought space for event payloads."""

    cluster_id: UUID = Field(description="Unique identifier for the cluster")
    round_id: UUID = Field(description="Round this cluster belongs to")
    label_summary: str = Field(description="Human-readable label for this thought space")
    member_count: int = Field(description="Number of participants in this cluster")
    member_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentage of total participants in this cluster",
    )
    participant_ids: List[UUID] = Field(
        description="Participant IDs in this cluster for flow tracking"
    )


class ClusteringCompleteEvent(BaseModel):
    """Emitted when clustering sub-protocol completes for a round."""

    round_id: UUID = Field(description="Unique identifier for the round")
    thought_spaces: List[ThoughtSpaceSummary] = Field(
        description="All thought spaces discovered by clustering"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when clustering completed",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "round_id": "660e8400-e29b-41d4-a716-446655440001",
                "thought_spaces": [
                    {
                        "cluster_id": "aa0e8400-e29b-41d4-a716-446655440005",
                        "round_id": "660e8400-e29b-41d4-a716-446655440001",
                        "label_summary": "Focus on environmental sustainability",
                        "member_count": 15,
                        "member_pct": 30.0,
                        "participant_ids": ["880e8400-e29b-41d4-a716-446655440003"],
                    }
                ],
                "timestamp": "2026-01-29T12:12:00Z",
            }
        }
    }


class FlowEdge(BaseModel):
    """A single edge in the Sankey diagram representing participant flow."""

    source_cluster_id: UUID = Field(description="Source thought space cluster ID")
    target_cluster_id: UUID = Field(description="Target thought space cluster ID")
    participant_count: int = Field(description="Number of participants who moved")
    participant_ids: List[UUID] = Field(
        description="Actual participant IDs who moved (for validation)"
    )


class SankeyGraph(BaseModel):
    """Complete Sankey diagram data structure."""

    discussion_id: UUID = Field(description="Discussion this graph belongs to")
    rounds: List[UUID] = Field(description="Ordered list of round IDs (columns)")
    nodes: List[ThoughtSpaceSummary] = Field(
        description="All thought spaces across all rounds"
    )
    edges: List[FlowEdge] = Field(
        description="All flows between thought spaces across rounds"
    )
    total_participants: int = Field(description="Total unique participants")


class SankeyCompleteEvent(BaseModel):
    """Emitted when Sankey construction completes for a round."""

    round_id: UUID = Field(description="Round that triggered this Sankey update")
    sankey_graph: SankeyGraph = Field(description="Complete Sankey diagram data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when Sankey construction completed",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "round_id": "660e8400-e29b-41d4-a716-446655440001",
                "sankey_graph": {
                    "discussion_id": "550e8400-e29b-41d4-a716-446655440000",
                    "rounds": ["660e8400-e29b-41d4-a716-446655440001"],
                    "nodes": [
                        {
                            "cluster_id": "aa0e8400-e29b-41d4-a716-446655440005",
                            "round_id": "660e8400-e29b-41d4-a716-446655440001",
                            "label_summary": "Focus on environmental sustainability",
                            "member_count": 15,
                            "member_pct": 30.0,
                            "participant_ids": ["880e8400-e29b-41d4-a716-446655440003"],
                        }
                    ],
                    "edges": [],
                    "total_participants": 50,
                },
                "timestamp": "2026-01-29T12:14:00Z",
            }
        }
    }


class RoundStartedEvent(BaseModel):
    """Emitted when a round starts (submission window opens)."""

    discussion_id: UUID = Field(description="Unique identifier for the discussion")
    round_id: UUID = Field(description="Unique identifier for the round that started")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when round started",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "discussion_id": "550e8400-e29b-41d4-a716-446655440000",
                "round_id": "660e8400-e29b-41d4-a716-446655440001",
                "timestamp": "2026-01-29T12:00:00Z",
            }
        }
    }


class RoundCompleteEvent(BaseModel):
    """Emitted when a round fully completes (Sankey ready)."""

    round_id: UUID = Field(description="Unique identifier for the completed round")
    next_round_id: Optional[UUID] = Field(
        default=None,
        description="Next round ID if discussion continues, None if final round",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when round completed",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "round_id": "660e8400-e29b-41d4-a716-446655440001",
                "next_round_id": "660e8400-e29b-41d4-a716-446655440002",
                "timestamp": "2026-01-29T12:15:00Z",
            }
        }
    }


class TimingViolationEvent(BaseModel):
    """Emitted when timing precision exceeds acceptable threshold."""

    round_id: UUID = Field(description="Round where violation occurred")
    expected_close_at: datetime = Field(description="Scheduled closure time")
    actual_close_at: datetime = Field(description="Actual closure time")
    drift_ms: int = Field(description="Timing drift in milliseconds")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when violation detected",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "round_id": "660e8400-e29b-41d4-a716-446655440001",
                "expected_close_at": "2026-01-29T12:06:00.000Z",
                "actual_close_at": "2026-01-29T12:06:00.150Z",
                "drift_ms": 150,
                "timestamp": "2026-01-29T12:06:00.150Z",
            }
        }
    }


# Question Progression Protocol Events (Spec 006)

class QuestionReadyEvent(BaseModel):
    """Emitted when auto-generated question is ready (awaiting host approval)."""

    round_id: UUID = Field(description="Round that will use this question")
    question_id: UUID = Field(description="Auto-generated question ID")
    question_text: str = Field(description="Generated question text")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when question became ready",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "round_id": "660e8400-e29b-41d4-a716-446655440002",
                "question_id": "bb0e8400-e29b-41d4-a716-446655440006",
                "question_text": "What are the main challenges you foresee?",
                "timestamp": "2026-01-29T12:16:00Z",
            }
        }
    }


class QuestionGenerationFailedEvent(BaseModel):
    """Emitted when auto-generation fails after max retries."""

    round_id: UUID = Field(description="Round that needs a question")
    discussion_id: UUID = Field(description="Discussion ID for context")
    retry_count: int = Field(description="Number of retries attempted")
    last_error: str = Field(description="Last error message encountered")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when generation failed",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "round_id": "660e8400-e29b-41d4-a716-446655440002",
                "discussion_id": "550e8400-e29b-41d4-a716-446655440000",
                "retry_count": 3,
                "last_error": "Validation failed: question contains ranking keywords",
                "timestamp": "2026-01-29T12:16:30Z",
            }
        }
    }


# Clustering & Alignment Protocol Events (Spec 004)

class ClusteringCompletedEvent(BaseModel):
    """Emitted when clustering completes for a round (Spec 4 -> Spec 5)."""

    event_id: UUID = Field(description="Unique event identifier for idempotency")
    event_type: str = Field(
        default="clustering.completed",
        description="Event type constant"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event publication time (ISO8601)"
    )

    round_id: UUID = Field(description="Round that was clustered")
    cluster_count: int = Field(description="Number of thought spaces created")
    total_participants: int = Field(
        description="Total participants (should match summary_count from trigger event)"
    )
    singleton_count: int = Field(
        description="Number of singleton clusters (outliers converted)"
    )
    processing_time_ms: int = Field(
        description="Clustering duration (embedding + HDBSCAN + medoid + persist)"
    )
    completed_at: datetime = Field(
        description="Clustering completion timestamp (ISO8601)"
    )
    cluster_ids: Optional[List[UUID]] = Field(
        default=None,
        description="List of created cluster IDs (for reference)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "f2g3h4i5-5678-90ab-cdef-1234567890bc",
                "event_type": "clustering.completed",
                "timestamp": "2026-01-29T14:10:03.600Z",
                "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
                "cluster_count": 8,
                "total_participants": 95,
                "singleton_count": 2,
                "processing_time_ms": 3600,
                "completed_at": "2026-01-29T14:10:03.600Z",
                "cluster_ids": [
                    "c1234567-89ab-cdef-0123-456789abcdef",
                    "c2345678-89ab-cdef-0123-456789abcdef"
                ]
            }
        }
    }


class AlignmentCompletedEvent(BaseModel):
    """Emitted when cross-round alignment completes (Spec 4 -> Spec 5)."""

    event_id: UUID = Field(description="Unique event identifier for idempotency")
    event_type: str = Field(
        default="alignment.completed",
        description="Event type constant"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event publication time (ISO8601)"
    )

    discussion_id: UUID = Field(description="Discussion context")
    round_r: int = Field(description="Earlier round number")
    round_r1: int = Field(description="Later round number (r+1)")
    match_count: int = Field(
        description="Number of cluster pairs aligned (≥ threshold)"
    )
    similarity_threshold: float = Field(
        description="Threshold used (e.g., 0.7)"
    )
    processing_time_ms: int = Field(
        description="Alignment computation duration"
    )
    completed_at: datetime = Field(
        description="Alignment completion timestamp (ISO8601)"
    )
    display_group_count: Optional[int] = Field(
        default=None,
        description="Number of unique display groups assigned"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "g3h4i5j6-5678-90ab-cdef-1234567890cd",
                "event_type": "alignment.completed",
                "timestamp": "2026-01-29T14:15:04.100Z",
                "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
                "round_r": 1,
                "round_r1": 2,
                "match_count": 6,
                "similarity_threshold": 0.7,
                "processing_time_ms": 500,
                "completed_at": "2026-01-29T14:15:04.100Z",
                "display_group_count": 6
            }
        }
    }


# Type alias for all event types
EventType = (
    DiscussionStartedEvent
    | RoundStartedEvent
    | SubmissionWindowClosedEvent
    | SummarizationCompleteEvent
    | ClusteringCompleteEvent
    | SankeyCompleteEvent
    | RoundCompleteEvent
    | TimingViolationEvent
    | QuestionReadyEvent
    | QuestionGenerationFailedEvent
    | ClusteringCompletedEvent
    | AlignmentCompletedEvent
)

# Event type registry for dynamic lookups
EVENT_TYPE_REGISTRY = {
    "discussion.started": DiscussionStartedEvent,
    "round.started": RoundStartedEvent,
    "submission_window.closed": SubmissionWindowClosedEvent,
    "summarization.complete": SummarizationCompleteEvent,
    "clustering.complete": ClusteringCompleteEvent,
    "sankey.complete": SankeyCompleteEvent,
    "round.complete": RoundCompleteEvent,
    "timing.violation": TimingViolationEvent,
    # Question Progression (Spec 006)
    "question.ready": QuestionReadyEvent,
    "question.generation_failed": QuestionGenerationFailedEvent,
    # Clustering & Alignment Protocol (Spec 004)
    "clustering.completed": ClusteringCompletedEvent,
    "alignment.completed": AlignmentCompletedEvent,
}
