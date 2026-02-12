"""
Cleanup event handlers for Input Collection Protocol.
Subscribes to summarization.completed to delete ephemeral raw submissions.
"""

from uuid import UUID
import time

from src.events.bus import event_bus, Event, EVENT_SUMMARIZATION_COMPLETED
from src.services.ephemeral_storage import ephemeral_storage
from src.utils.logger import get_logger
from src.utils.metrics import cleanup_metrics

logger = get_logger(__name__)


async def on_summarization_completed(event: Event) -> None:
    """
    Handle summarization.completed event (T033, T085).

    Deletes raw submissions from ephemeral storage once summarization is done.
    Records cleanup metrics for monitoring.

    Event payload:
        - round_id: UUID of completed round
        - submission_ids: List of submission UUIDs
    """
    start_time = time.time()
    items_cleaned = 0

    try:
        submission_ids = event.payload.get("submission_ids", [])
        round_id = event.payload.get("round_id")

        for submission_id_str in submission_ids:
            submission_id = UUID(submission_id_str)
            ephemeral_storage.delete_raw_submission(submission_id)
            items_cleaned += 1

        # Record cleanup metrics (T085)
        duration_ms = (time.time() - start_time) * 1000
        cleanup_metrics.record_cleanup(
            success=True,
            items_count=items_cleaned,
            reason="summarization_complete",
            duration_ms=duration_ms
        )

        logger.info(
            f"Cleaned up {items_cleaned} raw submissions for round {round_id}",
            extra={
                "context": {
                    "round_id": round_id,
                    "items_cleaned": items_cleaned,
                    "duration_ms": duration_ms
                }
            }
        )

    except Exception as e:
        # Record failed cleanup (T085)
        duration_ms = (time.time() - start_time) * 1000
        cleanup_metrics.record_cleanup(
            success=False,
            items_count=items_cleaned,
            reason="summarization_complete",
            duration_ms=duration_ms
        )

        logger.error(
            f"Error cleaning up raw submissions: {e}",
            exc_info=True,
            extra={
                "context": {
                    "round_id": event.payload.get("round_id"),
                    "items_cleaned_before_error": items_cleaned
                }
            }
        )


# Subscribe to event on module load
event_bus.subscribe(EVENT_SUMMARIZATION_COMPLETED, on_summarization_completed)
