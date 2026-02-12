"""
Redis-based timing service for scheduled window closures.

Uses Redis sorted sets for efficient time-based scheduling with 50ms polling.
Achieves ±100ms timing precision as per constitutional requirements.
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

import redis.asyncio as aioredis

from src.config import settings
from src.events.event_bus import get_event_bus
from src.events.event_types import SubmissionWindowClosedEvent, TimingViolationEvent

logger = logging.getLogger(__name__)


class TimingService:
    """
    Timing service for scheduling and enforcing submission window closures.

    Features:
    - Redis sorted set for O(log N) scheduled closure tracking
    - 50ms polling for ±100ms precision
    - Graceful connection failure handling
    - Automatic emission of closure events
    - Timing violation detection and reporting
    """

    SORTED_SET_KEY = "timing:scheduled_closures"
    POLL_INTERVAL_MS = 50  # 50ms polling as per requirements

    def __init__(self, redis_url: Optional[str] = None) -> None:
        """
        Initialize timing service with Redis connection.

        Args:
            redis_url: Redis connection URL, defaults to settings.redis_url
        """
        self._redis_url = redis_url or str(settings.redis_url)
        self._redis: Optional[aioredis.Redis] = None
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._is_running = False
        self._max_retries = 5
        self._retry_delay_base = 1.0  # seconds
        self._poll_interval = self.POLL_INTERVAL_MS / 1000.0  # Convert to seconds

        # T074: Timing metrics for precision tracking
        self._drift_history: deque[int] = deque(maxlen=1000)  # Store last 1000 drift measurements

    async def connect(self) -> None:
        """
        Establish connection to Redis.

        Raises:
            ConnectionError: If connection fails after max retries
        """
        if self._redis is not None:
            logger.warning("TimingService already connected, skipping reconnection")
            return

        retry_count = 0
        last_error: Optional[Exception] = None

        while retry_count < self._max_retries:
            try:
                self._redis = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=False,  # We want bytes for UUID handling
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                )

                # Test connection
                await self._redis.ping()

                logger.info(f"TimingService connected to Redis at {self._redis_url}")
                return

            except Exception as e:
                last_error = e
                retry_count += 1
                delay = self._retry_delay_base * (2 ** (retry_count - 1))
                logger.warning(
                    f"TimingService connection attempt {retry_count}/{self._max_retries} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        error_msg = f"TimingService failed to connect after {self._max_retries} attempts"
        logger.error(f"{error_msg}: {last_error}")
        raise ConnectionError(error_msg) from last_error

    async def disconnect(self) -> None:
        """Disconnect from Redis and stop worker task."""
        await self.stop_worker()

        if self._redis:
            await self._redis.close()
            self._redis = None

        logger.info("TimingService disconnected from Redis")

    async def schedule_closure(self, round_id: UUID, close_at: datetime) -> None:
        """
        Schedule a submission window closure.

        Args:
            round_id: Unique identifier for the round
            close_at: UTC datetime when window should close

        Raises:
            ConnectionError: If not connected to Redis
            ValueError: If close_at is in the past
        """
        if not self._redis:
            raise ConnectionError("TimingService not connected to Redis")

        # Validate close_at is in the future
        now = datetime.now(timezone.utc)
        if close_at <= now:
            raise ValueError(
                f"Cannot schedule closure in the past. close_at={close_at}, now={now}"
            )

        # Convert to timestamp (score for sorted set)
        timestamp = close_at.timestamp()

        # Store round_id as member with timestamp as score
        round_id_bytes = str(round_id).encode("utf-8")
        await self._redis.zadd(
            self.SORTED_SET_KEY,
            {round_id_bytes: timestamp},
        )

        time_until = (close_at - now).total_seconds()
        logger.info(
            f"Scheduled closure for round {round_id} at {close_at} "
            f"(in {time_until:.2f}s)"
        )

    async def cancel_closure(self, round_id: UUID) -> bool:
        """
        Cancel a scheduled submission window closure.

        Args:
            round_id: Unique identifier for the round

        Returns:
            True if closure was cancelled, False if not found

        Raises:
            ConnectionError: If not connected to Redis
        """
        if not self._redis:
            raise ConnectionError("TimingService not connected to Redis")

        round_id_bytes = str(round_id).encode("utf-8")
        removed = await self._redis.zrem(self.SORTED_SET_KEY, round_id_bytes)

        if removed > 0:
            logger.info(f"Cancelled closure for round {round_id}")
            return True
        else:
            logger.warning(f"No scheduled closure found for round {round_id}")
            return False

    async def check_closures(self) -> None:
        """
        Check for expired windows and emit closure events.

        This is called by the worker task every 50ms.

        Raises:
            ConnectionError: If not connected to Redis
        """
        if not self._redis:
            raise ConnectionError("TimingService not connected to Redis")

        now = datetime.now(timezone.utc)
        current_timestamp = now.timestamp()

        # Query sorted set for all members with score <= current_timestamp
        # ZRANGEBYSCORE returns members with scores in range
        expired_entries = await self._redis.zrangebyscore(
            self.SORTED_SET_KEY,
            min="-inf",
            max=current_timestamp,
            withscores=True,
        )

        if not expired_entries:
            return

        # Process each expired entry
        for i in range(0, len(expired_entries), 2):
            round_id_bytes = expired_entries[i]
            scheduled_timestamp = float(expired_entries[i + 1])

            try:
                round_id = UUID(round_id_bytes.decode("utf-8"))
                scheduled_close_at = datetime.fromtimestamp(
                    scheduled_timestamp, tz=timezone.utc
                )

                # Calculate timing drift
                actual_close_at = now
                drift_ms = int(
                    (actual_close_at - scheduled_close_at).total_seconds() * 1000
                )

                # Remove from sorted set (closure processed)
                await self._redis.zrem(self.SORTED_SET_KEY, round_id_bytes)

                # Emit closure event (sub-protocols will handle the actual closure)
                event_bus = await get_event_bus()
                await event_bus.emit(
                    "submission_window.closed",
                    SubmissionWindowClosedEvent(
                        round_id=round_id,
                        submissions=[],  # Actual submissions populated by round service
                        timestamp=actual_close_at,
                    ),
                )

                logger.info(
                    f"Window closed for round {round_id}. "
                    f"Scheduled: {scheduled_close_at}, "
                    f"Actual: {actual_close_at}, "
                    f"Drift: {drift_ms}ms"
                )

                # T074: Enforce timing precision
                await self.enforce_precision(
                    round_id=round_id,
                    scheduled_close_at=scheduled_close_at,
                    actual_close_at=actual_close_at,
                    drift_ms=drift_ms,
                )

            except Exception as e:
                logger.error(
                    f"Error processing closure for {round_id_bytes}: {e}",
                    exc_info=True,
                )
                # Continue processing other closures even if one fails

    async def enforce_precision(
        self,
        round_id: UUID,
        scheduled_close_at: datetime,
        actual_close_at: datetime,
        drift_ms: int,
    ) -> None:
        """
        Enforce timing precision validation (T074).

        Verifies window closure is within ±100ms precision threshold.
        Logs timing violations and emits timing.violation events.
        Tracks timing accuracy metrics for p95/p99 percentile analysis.

        Args:
            round_id: UUID of the round
            scheduled_close_at: Scheduled closure time
            actual_close_at: Actual closure time
            drift_ms: Timing drift in milliseconds (positive = late, negative = early)

        Constitutional Principle:
        - Synchronous Deliberation (Principle VI): Enforce strict timing constraints
          to maintain time-boxed execution and prevent gaming/coordination.
        """
        # Record drift for percentile tracking
        self._drift_history.append(abs(drift_ms))

        # Check if precision threshold exceeded
        if abs(drift_ms) > settings.timing_precision_ms:
            # Calculate current percentile metrics
            p95, p99 = self.get_timing_percentiles()

            logger.warning(
                f"Timing precision violation for round {round_id}: "
                f"drift={drift_ms}ms, threshold=±{settings.timing_precision_ms}ms, "
                f"p95={p95}ms, p99={p99}ms"
            )

            # Emit timing violation event
            event_bus = await get_event_bus()
            await event_bus.emit(
                "timing.violation",
                TimingViolationEvent(
                    round_id=round_id,
                    expected_close_at=scheduled_close_at,
                    actual_close_at=actual_close_at,
                    drift_ms=drift_ms,
                    timestamp=actual_close_at,
                ),
            )

            # Log drift metrics for monitoring
            logger.info(
                f"Timing metrics - Round {round_id}: "
                f"drift={drift_ms}ms, p95={p95}ms, p99={p99}ms, "
                f"samples={len(self._drift_history)}"
            )
        else:
            logger.debug(
                f"Timing precision OK for round {round_id}: "
                f"drift={drift_ms}ms (within ±{settings.timing_precision_ms}ms)"
            )

    def get_timing_percentiles(self) -> tuple[int, int]:
        """
        Calculate p95 and p99 timing accuracy percentiles (T074).

        Returns:
            Tuple of (p95_ms, p99_ms) percentile drift values

        Example:
            p95, p99 = service.get_timing_percentiles()
            # p95 = 85ms, p99 = 120ms
        """
        if not self._drift_history:
            return (0, 0)

        # Sort drift values for percentile calculation
        sorted_drifts = sorted(self._drift_history)
        count = len(sorted_drifts)

        # Calculate p95 index (95th percentile)
        p95_index = int(count * 0.95)
        p95 = sorted_drifts[min(p95_index, count - 1)]

        # Calculate p99 index (99th percentile)
        p99_index = int(count * 0.99)
        p99 = sorted_drifts[min(p99_index, count - 1)]

        return (p95, p99)

    def get_timing_metrics(self) -> dict[str, int]:
        """
        Get comprehensive timing metrics for monitoring (T074).

        Returns:
            Dictionary with timing statistics:
            - sample_count: Number of recorded drift measurements
            - min_drift_ms: Minimum observed drift
            - max_drift_ms: Maximum observed drift
            - avg_drift_ms: Average drift
            - p95_drift_ms: 95th percentile drift
            - p99_drift_ms: 99th percentile drift
        """
        if not self._drift_history:
            return {
                "sample_count": 0,
                "min_drift_ms": 0,
                "max_drift_ms": 0,
                "avg_drift_ms": 0,
                "p95_drift_ms": 0,
                "p99_drift_ms": 0,
            }

        sorted_drifts = sorted(self._drift_history)
        count = len(sorted_drifts)

        p95, p99 = self.get_timing_percentiles()

        return {
            "sample_count": count,
            "min_drift_ms": sorted_drifts[0],
            "max_drift_ms": sorted_drifts[-1],
            "avg_drift_ms": sum(self._drift_history) // count,
            "p95_drift_ms": p95,
            "p99_drift_ms": p99,
        }

    async def start_worker(self) -> None:
        """
        Start the background worker task that polls for closures.

        The worker runs continuously until stop_worker() is called.
        """
        if self._is_running:
            logger.warning("TimingService worker already running")
            return

        if not self._redis:
            raise ConnectionError("Must connect before starting worker")

        self._is_running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info(
            f"TimingService worker started (polling every {self.POLL_INTERVAL_MS}ms)"
        )

    async def stop_worker(self) -> None:
        """Stop the background worker task."""
        if not self._is_running:
            return

        self._is_running = False

        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        logger.info("TimingService worker stopped")

    async def _worker_loop(self) -> None:
        """
        Internal worker loop that polls for closures every 50ms.

        Runs continuously until cancelled or an unrecoverable error occurs.
        """
        logger.info("TimingService worker loop started")

        try:
            while self._is_running:
                try:
                    await self.check_closures()
                except Exception as e:
                    logger.error(f"Error in worker loop: {e}", exc_info=True)
                    # Continue running - transient errors shouldn't kill the worker

                # Sleep for poll interval
                await asyncio.sleep(self._poll_interval)

        except asyncio.CancelledError:
            logger.info("TimingService worker loop cancelled")
            raise

        except Exception as e:
            logger.error(f"Fatal error in worker loop: {e}", exc_info=True)
            self._is_running = False
            raise

    async def get_scheduled_count(self) -> int:
        """
        Get the number of scheduled closures.

        Returns:
            Number of pending closures

        Raises:
            ConnectionError: If not connected to Redis
        """
        if not self._redis:
            raise ConnectionError("TimingService not connected to Redis")

        return await self._redis.zcard(self.SORTED_SET_KEY)

    async def get_next_closure(self) -> Optional[tuple[UUID, datetime]]:
        """
        Get the next scheduled closure.

        Returns:
            Tuple of (round_id, close_at) if any scheduled, None otherwise

        Raises:
            ConnectionError: If not connected to Redis
        """
        if not self._redis:
            raise ConnectionError("TimingService not connected to Redis")

        # Get the member with the lowest score (earliest time)
        result = await self._redis.zrange(
            self.SORTED_SET_KEY,
            start=0,
            end=0,
            withscores=True,
        )

        if not result:
            return None

        round_id_bytes = result[0]
        timestamp = float(result[1])

        round_id = UUID(round_id_bytes.decode("utf-8"))
        close_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)

        return (round_id, close_at)

    def is_running(self) -> bool:
        """Check if the worker task is running."""
        return self._is_running

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


# Global timing service instance
_timing_service: Optional[TimingService] = None


async def get_timing_service() -> TimingService:
    """
    Get or create the global timing service instance.

    Returns:
        TimingService: The global timing service instance

    Raises:
        ConnectionError: If connection to Redis fails
    """
    global _timing_service

    if _timing_service is None:
        _timing_service = TimingService()
        await _timing_service.connect()
        await _timing_service.start_worker()

    return _timing_service


async def close_timing_service() -> None:
    """Close the global timing service instance."""
    global _timing_service

    if _timing_service is not None:
        await _timing_service.disconnect()
        _timing_service = None
