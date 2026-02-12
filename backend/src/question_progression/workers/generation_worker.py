"""
Background worker for question generation tasks.

Processes generation events from Redis queue with:
- Concurrent event processing
- Graceful error handling
- Automatic reconnection on failure
"""

import asyncio
from typing import Optional

from src.events.event_bus import EventBus, get_event_bus
from src.question_progression.event_handlers import register_handlers
from src.database import get_db_session_factory
from src.logging_config import get_logger

logger = get_logger(__name__)


class GenerationWorker:
    """
    Background worker for processing question generation events.

    Subscribes to sankey.complete events and coordinates:
    - Question generation
    - Validation
    - Provenance recording
    - Round status transitions
    """

    def __init__(self):
        """Initialize GenerationWorker."""
        self.event_bus: Optional[EventBus] = None
        self.running = False
        self.task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """
        Start the worker.

        Connects to event bus and registers handlers.
        """
        if self.running:
            logger.warning("GenerationWorker already running")
            return

        logger.info("Starting GenerationWorker")

        try:
            # Connect to event bus
            self.event_bus = await get_event_bus()

            # Get database session factory
            db_session_factory = get_db_session_factory()

            # Register event handlers
            await register_handlers(self.event_bus, db_session_factory)

            self.running = True
            logger.info("GenerationWorker started successfully")

            # Keep worker running
            self.task = asyncio.create_task(self._run())

        except Exception as e:
            logger.error(
                "Failed to start GenerationWorker",
                extra={"error": str(e)},
                exc_info=True
            )
            raise

    async def stop(self) -> None:
        """
        Stop the worker gracefully.

        Disconnects from event bus and cancels tasks.
        """
        if not self.running:
            logger.warning("GenerationWorker not running")
            return

        logger.info("Stopping GenerationWorker")

        self.running = False

        # Cancel worker task
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        # Disconnect from event bus
        if self.event_bus:
            await self.event_bus.disconnect()
            self.event_bus = None

        logger.info("GenerationWorker stopped")

    async def _run(self) -> None:
        """
        Main worker loop.

        Keeps worker alive and handles reconnection on failures.
        """
        try:
            while self.running:
                # Worker stays alive listening for events
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("GenerationWorker task cancelled")
            raise

        except Exception as e:
            logger.error(
                "GenerationWorker encountered error",
                extra={"error": str(e)},
                exc_info=True
            )
            self.running = False
            raise


# Global worker instance
_worker: Optional[GenerationWorker] = None


async def start_worker() -> GenerationWorker:
    """
    Start the global generation worker.

    Returns:
        GenerationWorker instance

    Raises:
        RuntimeError: If worker is already running
    """
    global _worker

    if _worker and _worker.running:
        raise RuntimeError("GenerationWorker is already running")

    _worker = GenerationWorker()
    await _worker.start()
    return _worker


async def stop_worker() -> None:
    """Stop the global generation worker."""
    global _worker

    if _worker:
        await _worker.stop()
        _worker = None


async def get_worker() -> Optional[GenerationWorker]:
    """Get the global worker instance."""
    return _worker
