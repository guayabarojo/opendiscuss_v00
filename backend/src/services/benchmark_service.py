"""
Performance Benchmark Service (T075)

Measures round processing time and tracks performance metrics:
- submission_close → clustering_complete → sankey_complete latency
- p95/p99 latencies for sub-protocol transitions
- End-to-end round completion time
- Total discussion execution time

Stores metrics in Redis for real-time monitoring and analysis.
"""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional, Dict, List
from uuid import UUID

import redis.asyncio as aioredis
from pydantic import BaseModel

from src.config import settings
from src.events.event_bus import get_event_bus
from src.events.event_types import (
    SubmissionWindowClosedEvent,
    SummarizationCompleteEvent,
    ClusteringCompleteEvent,
    SankeyCompleteEvent,
    RoundCompleteEvent,
)

logger = logging.getLogger(__name__)


class RoundMetrics(BaseModel):
    """Metrics for a single round."""

    round_id: UUID
    discussion_id: UUID
    round_num: int

    # Timing checkpoints
    submission_closed_at: Optional[datetime] = None
    summarization_complete_at: Optional[datetime] = None
    clustering_complete_at: Optional[datetime] = None
    sankey_complete_at: Optional[datetime] = None
    round_complete_at: Optional[datetime] = None

    # Latencies (milliseconds)
    submission_to_clustering_ms: Optional[int] = None
    clustering_to_sankey_ms: Optional[int] = None
    submission_to_sankey_ms: Optional[int] = None
    total_round_processing_ms: Optional[int] = None

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
    }


class PerformanceBenchmarkService:
    """
    Service for measuring and tracking discussion protocol performance (T075).

    Features:
    - Track sub-protocol transition latencies
    - Calculate p95/p99 percentiles for performance monitoring
    - Store metrics in Redis for real-time access
    - Emit performance alerts when thresholds exceeded

    Constitutional Principle:
    - Synchronous Deliberation (Principle VI): Verify <60 minute total time
      and ~10 minute per-round processing to maintain time-boxed execution.
    """

    METRICS_KEY_PREFIX = "perf:round:"
    LATENCY_HISTORY_KEY = "perf:latencies"
    MAX_HISTORY_SIZE = 1000  # Keep last 1000 measurements

    def __init__(self, redis_url: Optional[str] = None) -> None:
        """
        Initialize performance benchmark service.

        Args:
            redis_url: Redis connection URL, defaults to settings.redis_url
        """
        self._redis_url = redis_url or str(settings.redis_url)
        self._redis: Optional[aioredis.Redis] = None

        # In-memory tracking for active rounds
        self._active_rounds: Dict[UUID, RoundMetrics] = {}

        # Latency history for percentile calculation
        self._submission_to_clustering_latencies: deque[int] = deque(maxlen=self.MAX_HISTORY_SIZE)
        self._clustering_to_sankey_latencies: deque[int] = deque(maxlen=self.MAX_HISTORY_SIZE)
        self._total_round_latencies: deque[int] = deque(maxlen=self.MAX_HISTORY_SIZE)

        # Event subscriptions
        self._subscribed = False

    async def connect(self) -> None:
        """
        Connect to Redis and subscribe to performance-related events.

        Raises:
            ConnectionError: If connection fails
        """
        if self._redis is not None:
            logger.warning("PerformanceBenchmarkService already connected")
            return

        try:
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )

            await self._redis.ping()
            logger.info(f"PerformanceBenchmarkService connected to Redis at {self._redis_url}")

            # Subscribe to performance-related events
            await self._subscribe_to_events()

        except Exception as e:
            logger.error(f"Failed to connect PerformanceBenchmarkService: {e}")
            raise ConnectionError(f"PerformanceBenchmarkService connection failed") from e

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._subscribed = False

        logger.info("PerformanceBenchmarkService disconnected from Redis")

    async def _subscribe_to_events(self) -> None:
        """Subscribe to sub-protocol completion events for timing measurement."""
        if self._subscribed:
            return

        event_bus = await get_event_bus()

        # Subscribe to all sub-protocol transition events
        await event_bus.subscribe("submission_window.closed", self._on_submission_closed)
        await event_bus.subscribe("summarization.complete", self._on_summarization_complete)
        await event_bus.subscribe("clustering.complete", self._on_clustering_complete)
        await event_bus.subscribe("sankey.complete", self._on_sankey_complete)
        await event_bus.subscribe("round.complete", self._on_round_complete)

        self._subscribed = True
        logger.info("PerformanceBenchmarkService subscribed to performance events")

    async def _on_submission_closed(self, event: SubmissionWindowClosedEvent) -> None:
        """Record submission window closure timestamp."""
        round_id = event.round_id

        if round_id not in self._active_rounds:
            self._active_rounds[round_id] = RoundMetrics(
                round_id=round_id,
                discussion_id=UUID("00000000-0000-0000-0000-000000000000"),  # Will be updated
                round_num=0,  # Will be updated
            )

        metrics = self._active_rounds[round_id]
        metrics.submission_closed_at = event.timestamp

        logger.debug(f"Recorded submission_closed for round {round_id}")

    async def _on_summarization_complete(self, event: SummarizationCompleteEvent) -> None:
        """Record summarization completion timestamp."""
        round_id = event.round_id

        if round_id not in self._active_rounds:
            logger.warning(f"Summarization complete for unknown round {round_id}")
            return

        metrics = self._active_rounds[round_id]
        metrics.summarization_complete_at = event.timestamp

        logger.debug(f"Recorded summarization_complete for round {round_id}")

    async def _on_clustering_complete(self, event: ClusteringCompleteEvent) -> None:
        """Record clustering completion timestamp and calculate latencies."""
        round_id = event.round_id

        if round_id not in self._active_rounds:
            logger.warning(f"Clustering complete for unknown round {round_id}")
            return

        metrics = self._active_rounds[round_id]
        metrics.clustering_complete_at = event.timestamp

        # Calculate submission → clustering latency
        if metrics.submission_closed_at and metrics.clustering_complete_at:
            latency_ms = int(
                (metrics.clustering_complete_at - metrics.submission_closed_at).total_seconds() * 1000
            )
            metrics.submission_to_clustering_ms = latency_ms
            self._submission_to_clustering_latencies.append(latency_ms)

            logger.info(
                f"Round {round_id}: submission → clustering = {latency_ms}ms"
            )

        logger.debug(f"Recorded clustering_complete for round {round_id}")

    async def _on_sankey_complete(self, event: SankeyCompleteEvent) -> None:
        """Record Sankey completion timestamp and calculate latencies."""
        round_id = event.round_id

        if round_id not in self._active_rounds:
            logger.warning(f"Sankey complete for unknown round {round_id}")
            return

        metrics = self._active_rounds[round_id]
        metrics.sankey_complete_at = event.timestamp

        # Calculate clustering → sankey latency
        if metrics.clustering_complete_at and metrics.sankey_complete_at:
            latency_ms = int(
                (metrics.sankey_complete_at - metrics.clustering_complete_at).total_seconds() * 1000
            )
            metrics.clustering_to_sankey_ms = latency_ms
            self._clustering_to_sankey_latencies.append(latency_ms)

            logger.info(
                f"Round {round_id}: clustering → sankey = {latency_ms}ms"
            )

        # Calculate submission → sankey total latency
        if metrics.submission_closed_at and metrics.sankey_complete_at:
            total_latency_ms = int(
                (metrics.sankey_complete_at - metrics.submission_closed_at).total_seconds() * 1000
            )
            metrics.submission_to_sankey_ms = total_latency_ms

            logger.info(
                f"Round {round_id}: submission → sankey (total) = {total_latency_ms}ms"
            )

        logger.debug(f"Recorded sankey_complete for round {round_id}")

    async def _on_round_complete(self, event: RoundCompleteEvent) -> None:
        """Record round completion and finalize metrics."""
        round_id = event.round_id

        if round_id not in self._active_rounds:
            logger.warning(f"Round complete for unknown round {round_id}")
            return

        metrics = self._active_rounds[round_id]
        metrics.round_complete_at = event.timestamp

        # Calculate total round processing time
        if metrics.submission_closed_at and metrics.round_complete_at:
            total_ms = int(
                (metrics.round_complete_at - metrics.submission_closed_at).total_seconds() * 1000
            )
            metrics.total_round_processing_ms = total_ms
            self._total_round_latencies.append(total_ms)

            logger.info(
                f"Round {round_id}: total processing time = {total_ms}ms "
                f"({total_ms / 1000:.2f}s)"
            )

        # Store metrics in Redis
        await self._store_metrics(metrics)

        # Calculate and log percentiles
        p95_sub_to_clust, p99_sub_to_clust = self._calculate_percentiles(
            self._submission_to_clustering_latencies
        )
        p95_clust_to_sankey, p99_clust_to_sankey = self._calculate_percentiles(
            self._clustering_to_sankey_latencies
        )
        p95_total, p99_total = self._calculate_percentiles(self._total_round_latencies)

        logger.info(
            f"Performance percentiles - "
            f"submission→clustering: p95={p95_sub_to_clust}ms, p99={p99_sub_to_clust}ms | "
            f"clustering→sankey: p95={p95_clust_to_sankey}ms, p99={p99_clust_to_sankey}ms | "
            f"total: p95={p95_total}ms, p99={p99_total}ms"
        )

        # Check if performance thresholds exceeded (10 minutes per round target)
        if metrics.total_round_processing_ms and metrics.total_round_processing_ms > 600000:
            logger.warning(
                f"Round {round_id} exceeded 10-minute processing target: "
                f"{metrics.total_round_processing_ms}ms"
            )

        # Clean up from active rounds
        del self._active_rounds[round_id]

        logger.debug(f"Finalized metrics for round {round_id}")

    async def _store_metrics(self, metrics: RoundMetrics) -> None:
        """
        Store round metrics in Redis for monitoring.

        Args:
            metrics: RoundMetrics to store
        """
        if not self._redis:
            logger.warning("Cannot store metrics: not connected to Redis")
            return

        try:
            key = f"{self.METRICS_KEY_PREFIX}{metrics.round_id}"
            value = metrics.model_dump_json()

            # Store with 24-hour TTL
            await self._redis.setex(key, 86400, value)

            logger.debug(f"Stored metrics for round {metrics.round_id} in Redis")

        except Exception as e:
            logger.error(f"Failed to store metrics in Redis: {e}", exc_info=True)

    def _calculate_percentiles(self, values: deque[int]) -> tuple[int, int]:
        """
        Calculate p95 and p99 percentiles.

        Args:
            values: Deque of integer values

        Returns:
            Tuple of (p95, p99)
        """
        if not values:
            return (0, 0)

        sorted_values = sorted(values)
        count = len(sorted_values)

        p95_index = int(count * 0.95)
        p95 = sorted_values[min(p95_index, count - 1)]

        p99_index = int(count * 0.99)
        p99 = sorted_values[min(p99_index, count - 1)]

        return (p95, p99)

    async def get_round_metrics(self, round_id: UUID) -> Optional[RoundMetrics]:
        """
        Retrieve stored metrics for a specific round.

        Args:
            round_id: UUID of the round

        Returns:
            RoundMetrics if found, None otherwise
        """
        if not self._redis:
            raise ConnectionError("Not connected to Redis")

        try:
            key = f"{self.METRICS_KEY_PREFIX}{round_id}"
            value = await self._redis.get(key)

            if not value:
                return None

            return RoundMetrics.model_validate_json(value)

        except Exception as e:
            logger.error(f"Failed to retrieve metrics for round {round_id}: {e}")
            return None

    def get_performance_summary(self) -> Dict[str, any]:
        """
        Get summary of current performance metrics.

        Returns:
            Dictionary with performance statistics:
            - submission_to_clustering_p95_ms
            - submission_to_clustering_p99_ms
            - clustering_to_sankey_p95_ms
            - clustering_to_sankey_p99_ms
            - total_round_p95_ms
            - total_round_p99_ms
            - sample_counts
        """
        p95_sub_to_clust, p99_sub_to_clust = self._calculate_percentiles(
            self._submission_to_clustering_latencies
        )
        p95_clust_to_sankey, p99_clust_to_sankey = self._calculate_percentiles(
            self._clustering_to_sankey_latencies
        )
        p95_total, p99_total = self._calculate_percentiles(self._total_round_latencies)

        return {
            "submission_to_clustering_p95_ms": p95_sub_to_clust,
            "submission_to_clustering_p99_ms": p99_sub_to_clust,
            "clustering_to_sankey_p95_ms": p95_clust_to_sankey,
            "clustering_to_sankey_p99_ms": p99_clust_to_sankey,
            "total_round_p95_ms": p95_total,
            "total_round_p99_ms": p99_total,
            "sample_counts": {
                "submission_to_clustering": len(self._submission_to_clustering_latencies),
                "clustering_to_sankey": len(self._clustering_to_sankey_latencies),
                "total_round": len(self._total_round_latencies),
            },
        }

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


# Global benchmark service instance
_benchmark_service: Optional[PerformanceBenchmarkService] = None


async def get_benchmark_service() -> PerformanceBenchmarkService:
    """
    Get or create the global benchmark service instance.

    Returns:
        PerformanceBenchmarkService: The global instance

    Raises:
        ConnectionError: If connection to Redis fails
    """
    global _benchmark_service

    if _benchmark_service is None:
        _benchmark_service = PerformanceBenchmarkService()
        await _benchmark_service.connect()

    return _benchmark_service


async def close_benchmark_service() -> None:
    """Close the global benchmark service instance."""
    global _benchmark_service

    if _benchmark_service is not None:
        await _benchmark_service.disconnect()
        _benchmark_service = None
