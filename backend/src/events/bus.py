"""
Event bus for Input Collection Protocol.
Publishes events: submission.created, summary.approved, summarization.completed
"""

from typing import Dict, Any, List, Callable
from datetime import datetime
from uuid import UUID
import asyncio


class Event:
    """Base event class."""
    def __init__(self, event_type: str, payload: Dict[str, Any]):
        self.event_type = event_type
        self.payload = payload
        self.timestamp = datetime.utcnow()


class EventBus:
    """Simple in-memory event bus."""

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Publish an event asynchronously."""
        event = Event(event_type, payload)

        if event_type in self._handlers:
            tasks = [handler(event) for handler in self._handlers[event_type]]
            await asyncio.gather(*tasks, return_exceptions=True)

    def publish_sync(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Publish an event synchronously (for non-async contexts)."""
        asyncio.create_task(self.publish(event_type, payload))


# Global singleton instance
event_bus = EventBus()


# Event type constants
EVENT_SUBMISSION_CREATED = "submission.created"
EVENT_SUMMARY_APPROVED = "summary.approved"
EVENT_SUMMARIZATION_COMPLETED = "summarization.completed"

# Spec 003: Summarization & Approval Events
EVENT_SUMMARY_GENERATED = "summary.generated"          # Summary generated, pending review
EVENT_SUMMARY_REJECTED = "summary.rejected"            # Summary rejected, regeneration triggered
EVENT_SUMMARY_APPROVED_FINAL = "summary.approved"      # Summary approved (forwarded to clustering)
EVENT_CORRECTION_SIGNAL = "correction_signal.provided" # Correction signal submitted
EVENT_SUMMARY_REJECTED_FINAL = "summary.rejected_final" # Final rejection after correction
EVENT_APPROVAL_TIMEOUT = "approval.timeout"            # Approval deadline exceeded
