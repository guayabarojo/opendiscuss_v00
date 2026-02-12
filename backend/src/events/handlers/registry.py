"""
Event handler registration module.

Provides centralized registration of all event handlers with the event bus.
Should be called during application startup to establish event subscriptions.
"""

import logging

from src.events.event_bus import EventBus
from .submission_complete import register_submission_complete_handler
from .summarization_complete import register_summarization_complete_handler
from .clustering_complete import register_clustering_complete_handler
from .sankey_complete import register_sankey_complete_handler

logger = logging.getLogger(__name__)


async def register_all_handlers(event_bus: EventBus) -> None:
    """
    Register all event handlers with the event bus.

    This should be called during application startup, after the event bus
    is connected and before any events are emitted.

    Handlers registered:
    - submission_window.closed → handle_submission_complete (T037)
    - summarization.complete → handle_summarization_complete (T038)
    - clustering.complete → handle_clustering_complete (T039)
    - sankey.complete → handle_sankey_complete (T040)

    Args:
        event_bus: Connected EventBus instance

    Raises:
        RuntimeError: If registration fails for any handler
    """
    logger.info("Registering all event handlers...")

    try:
        # Register Phase 3 handlers (Discussion Protocol state transitions)
        await register_submission_complete_handler(event_bus)
        await register_summarization_complete_handler(event_bus)
        await register_clustering_complete_handler(event_bus)
        await register_sankey_complete_handler(event_bus)

        logger.info("All event handlers registered successfully")

    except Exception as e:
        logger.error(f"Failed to register event handlers: {e}", exc_info=True)
        raise RuntimeError("Event handler registration failed") from e
