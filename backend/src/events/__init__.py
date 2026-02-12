"""
Events module for OpenDiscuss Discussion Protocol.

Provides event bus for async pub/sub communication and typed event schemas.
"""

from src.events.event_bus import EventBus, get_event_bus, close_event_bus
from src.events.event_types import (
    # Event models
    DiscussionStartedEvent,
    SubmissionWindowClosedEvent,
    SummarizationCompleteEvent,
    ClusteringCompleteEvent,
    SankeyCompleteEvent,
    RoundCompleteEvent,
    TimingViolationEvent,
    # Supporting models
    SubmissionSummary,
    ApprovedSummarySummary,
    ThoughtSpaceSummary,
    FlowEdge,
    SankeyGraph,
    # Registry
    EVENT_TYPE_REGISTRY,
    EventType,
)

__all__ = [
    # Event bus
    "EventBus",
    "get_event_bus",
    "close_event_bus",
    # Event types
    "DiscussionStartedEvent",
    "SubmissionWindowClosedEvent",
    "SummarizationCompleteEvent",
    "ClusteringCompleteEvent",
    "SankeyCompleteEvent",
    "RoundCompleteEvent",
    "TimingViolationEvent",
    # Supporting models
    "SubmissionSummary",
    "ApprovedSummarySummary",
    "ThoughtSpaceSummary",
    "FlowEdge",
    "SankeyGraph",
    # Registry
    "EVENT_TYPE_REGISTRY",
    "EventType",
]
