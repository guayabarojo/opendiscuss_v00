"""
Async event bus implementation using Redis pub/sub.

Provides typed event emission and subscription for protocol coordination.
Handles connection failures gracefully with exponential backoff retry.
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Callable, Coroutine, Dict, List, Optional, Any

import redis.asyncio as aioredis
from pydantic import BaseModel, ValidationError

from src.config import settings
from src.events.event_types import EVENT_TYPE_REGISTRY, EventType

logger = logging.getLogger(__name__)


class EventBus:
    """
    Async event bus using Redis pub/sub for inter-service communication.

    Features:
    - Typed event system with Pydantic validation
    - Graceful connection failure handling
    - Multiple subscribers per event type
    - Automatic JSON serialization/deserialization
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        """
        Initialize event bus with Redis connection.

        Args:
            redis_url: Redis connection URL, defaults to settings.redis_url
        """
        self._redis_url = redis_url or str(settings.redis_url)
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._subscribers: Dict[str, List[Callable[[EventType], Coroutine[Any, Any, None]]]] = (
            defaultdict(list)
        )
        self._listener_task: Optional[asyncio.Task[None]] = None
        self._is_connected = False
        self._max_retries = 5
        self._retry_delay_base = 1.0  # seconds

    async def connect(self) -> None:
        """
        Establish connection to Redis and start pub/sub listener.

        Raises:
            redis.RedisError: If connection fails after max retries
        """
        if self._is_connected:
            logger.warning("EventBus already connected, skipping reconnection")
            return

        retry_count = 0
        last_error: Optional[Exception] = None

        while retry_count < self._max_retries:
            try:
                # Create Redis connection
                self._redis = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                )

                # Test connection
                await self._redis.ping()

                # Create pubsub instance
                self._pubsub = self._redis.pubsub()

                self._is_connected = True
                logger.info(f"EventBus connected to Redis at {self._redis_url}")
                return

            except Exception as e:
                last_error = e
                retry_count += 1
                delay = self._retry_delay_base * (2 ** (retry_count - 1))
                logger.warning(
                    f"EventBus connection attempt {retry_count}/{self._max_retries} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        error_msg = f"EventBus failed to connect after {self._max_retries} attempts"
        logger.error(f"{error_msg}: {last_error}")
        raise ConnectionError(error_msg) from last_error

    async def disconnect(self) -> None:
        """Disconnect from Redis and stop pub/sub listener."""
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None

        if self._redis:
            await self._redis.close()
            self._redis = None

        self._is_connected = False
        logger.info("EventBus disconnected from Redis")

    async def emit(self, event_type: str, payload: BaseModel) -> None:
        """
        Emit an event to all subscribers.

        Args:
            event_type: Event type identifier (e.g., "discussion.started")
            payload: Event payload as Pydantic model

        Raises:
            ValueError: If event_type is not registered
            redis.RedisError: If publish fails (logged but not raised)
        """
        if not self._is_connected or not self._redis:
            logger.error(f"Cannot emit event {event_type}: EventBus not connected")
            return

        if event_type not in EVENT_TYPE_REGISTRY:
            raise ValueError(
                f"Unknown event type: {event_type}. "
                f"Must be one of: {list(EVENT_TYPE_REGISTRY.keys())}"
            )

        # Validate payload type matches registry
        expected_type = EVENT_TYPE_REGISTRY[event_type]
        if not isinstance(payload, expected_type):
            raise TypeError(
                f"Event payload type mismatch for {event_type}. "
                f"Expected {expected_type.__name__}, got {type(payload).__name__}"
            )

        try:
            # Serialize to JSON
            message = json.dumps(payload.model_dump(mode="json"))

            # Publish to Redis channel
            channel = f"events:{event_type}"
            await self._redis.publish(channel, message)

            logger.debug(f"Emitted event {event_type} to channel {channel}")

        except Exception as e:
            logger.error(f"Failed to emit event {event_type}: {e}", exc_info=True)
            # Don't raise - we want emit to be fire-and-forget for resilience

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[EventType], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Subscribe to an event type with a handler.

        Args:
            event_type: Event type identifier (e.g., "discussion.started")
            handler: Async handler function that receives the event payload

        Raises:
            ValueError: If event_type is not registered
        """
        if event_type not in EVENT_TYPE_REGISTRY:
            raise ValueError(
                f"Unknown event type: {event_type}. "
                f"Must be one of: {list(EVENT_TYPE_REGISTRY.keys())}"
            )

        if not self._is_connected or not self._pubsub:
            logger.error(f"Cannot subscribe to {event_type}: EventBus not connected")
            return

        # Add handler to subscribers list
        self._subscribers[event_type].append(handler)

        # Subscribe to Redis channel
        channel = f"events:{event_type}"
        await self._pubsub.subscribe(channel)

        logger.info(f"Subscribed to event {event_type} on channel {channel}")

        # Start listener task if not already running
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        """
        Internal listener task that processes incoming pub/sub messages.

        Runs continuously until cancelled or connection fails.
        """
        if not self._pubsub:
            logger.error("Cannot start listener: pubsub not initialized")
            return

        logger.info("EventBus listener started")

        try:
            async for message in self._pubsub.listen():
                if message["type"] != "message":
                    # Skip subscription confirmations and other meta messages
                    continue

                channel = message["channel"]
                data = message["data"]

                # Extract event type from channel name
                if not channel.startswith("events:"):
                    continue

                event_type = channel[7:]  # Remove "events:" prefix

                if event_type not in self._subscribers:
                    # No handlers registered for this event
                    continue

                # Deserialize and validate payload
                try:
                    event_class = EVENT_TYPE_REGISTRY[event_type]
                    payload_dict = json.loads(data)
                    event = event_class.model_validate(payload_dict)

                except (json.JSONDecodeError, ValidationError) as e:
                    logger.error(
                        f"Failed to deserialize event {event_type}: {e}",
                        exc_info=True,
                    )
                    continue

                # Call all handlers for this event type
                handlers = self._subscribers[event_type]
                logger.debug(
                    f"Processing event {event_type} with {len(handlers)} handler(s)"
                )

                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error(
                            f"Handler error for event {event_type}: {e}",
                            exc_info=True,
                        )
                        # Continue processing other handlers even if one fails

        except asyncio.CancelledError:
            logger.info("EventBus listener cancelled")
            raise

        except Exception as e:
            logger.error(f"EventBus listener error: {e}", exc_info=True)
            self._is_connected = False
            raise

    def is_connected(self) -> bool:
        """Check if event bus is connected to Redis."""
        return self._is_connected

    async def health_check(self) -> bool:
        """
        Perform health check by pinging Redis.

        Returns:
            True if Redis is reachable, False otherwise
        """
        if not self._redis:
            return False

        try:
            await self._redis.ping()
            return True
        except Exception:
            return False


# Global event bus instance
_event_bus: Optional[EventBus] = None


async def get_event_bus() -> EventBus:
    """
    Get or create the global event bus instance.

    Returns:
        EventBus: The global event bus instance

    Raises:
        ConnectionError: If connection to Redis fails
    """
    global _event_bus

    if _event_bus is None:
        _event_bus = EventBus()
        await _event_bus.connect()

    return _event_bus


async def close_event_bus() -> None:
    """Close the global event bus instance."""
    global _event_bus

    if _event_bus is not None:
        await _event_bus.disconnect()
        _event_bus = None
