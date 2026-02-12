"""
Performance metrics and monitoring for OpenDiscuss.

Tracks:
- Submission processing latency (T084)
- Concurrent submission handling
- 95th percentile response times
- Ephemeral data cleanup success rates (T085)

Constitutional Compliance:
- Temporal Transparency: Accurate timing metrics
- Parallel-First: Monitor concurrent operation performance
"""

import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Optional, Deque
import statistics

from src.utils.logger import get_logger, log_performance

logger = get_logger(__name__)


class PerformanceMetrics:
    """
    Track performance metrics for API operations.

    Maintains rolling window of latency measurements for percentile calculations.
    """

    def __init__(self, window_size: int = 1000):
        """
        Initialize metrics tracker.

        Args:
            window_size: Number of measurements to keep for percentile calculation
        """
        self.window_size = window_size

        # Operation -> deque of latency measurements (ms)
        self.latencies: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=window_size))

        # Operation -> count
        self.counts: Dict[str, int] = defaultdict(int)

        # Operation -> total time (for average)
        self.totals: Dict[str, float] = defaultdict(float)

        # Concurrent operations counter
        self.concurrent_operations: Dict[str, int] = defaultdict(int)

        # Peak concurrent operations
        self.peak_concurrent: Dict[str, int] = defaultdict(int)

    def record_latency(self, operation: str, duration_ms: float, **context):
        """
        Record operation latency.

        Args:
            operation: Operation name (e.g., "submission_processing", "transcription")
            duration_ms: Duration in milliseconds
            **context: Additional context to log
        """
        self.latencies[operation].append(duration_ms)
        self.counts[operation] += 1
        self.totals[operation] += duration_ms

        # Log if above threshold (>1000ms warning)
        if duration_ms > 1000:
            logger.warning(f"Slow operation: {operation}", extra={
                "duration_ms": duration_ms,
                "context": context
            })

        # Log performance metrics
        log_performance(logger, operation, duration_ms, **context)

    def start_operation(self, operation: str):
        """
        Mark operation as started (for concurrent tracking).

        Args:
            operation: Operation name
        """
        self.concurrent_operations[operation] += 1

        # Update peak
        if self.concurrent_operations[operation] > self.peak_concurrent[operation]:
            self.peak_concurrent[operation] = self.concurrent_operations[operation]

    def end_operation(self, operation: str):
        """
        Mark operation as completed (for concurrent tracking).

        Args:
            operation: Operation name
        """
        if self.concurrent_operations[operation] > 0:
            self.concurrent_operations[operation] -= 1

    def get_percentile(self, operation: str, percentile: int = 95) -> Optional[float]:
        """
        Calculate percentile latency for operation.

        Args:
            operation: Operation name
            percentile: Percentile to calculate (e.g., 95 for p95)

        Returns:
            Percentile latency in milliseconds, or None if no data
        """
        if operation not in self.latencies or not self.latencies[operation]:
            return None

        latencies = list(self.latencies[operation])
        if not latencies:
            return None

        # Use statistics.quantiles for accurate percentile calculation
        try:
            # quantiles returns p25, p50, p75 by default
            # For p95, we need to specify n=100
            quantiles = statistics.quantiles(latencies, n=100)
            # quantiles[94] is the 95th percentile (0-indexed)
            return quantiles[percentile - 1]
        except statistics.StatisticsError:
            # Not enough data
            return None

    def get_average(self, operation: str) -> Optional[float]:
        """
        Get average latency for operation.

        Args:
            operation: Operation name

        Returns:
            Average latency in milliseconds, or None if no data
        """
        if self.counts[operation] == 0:
            return None
        return self.totals[operation] / self.counts[operation]

    def get_stats(self, operation: str) -> Dict:
        """
        Get comprehensive stats for operation.

        Args:
            operation: Operation name

        Returns:
            Dictionary with count, avg, p50, p95, p99, concurrent, peak
        """
        if operation not in self.latencies:
            return {}

        latencies = list(self.latencies[operation])
        if not latencies:
            return {"count": 0}

        return {
            "count": self.counts[operation],
            "avg_ms": self.get_average(operation),
            "p50_ms": statistics.median(latencies) if latencies else None,
            "p95_ms": self.get_percentile(operation, 95),
            "p99_ms": self.get_percentile(operation, 99),
            "min_ms": min(latencies) if latencies else None,
            "max_ms": max(latencies) if latencies else None,
            "concurrent_now": self.concurrent_operations[operation],
            "peak_concurrent": self.peak_concurrent[operation],
        }

    def log_summary(self):
        """Log summary of all tracked operations."""
        for operation in self.latencies.keys():
            stats = self.get_stats(operation)
            logger.info(f"Performance summary: {operation}", extra={
                "context": {
                    "operation": operation,
                    **stats
                }
            })


class CleanupMetrics:
    """
    Track ephemeral data cleanup metrics (T085).

    Monitors:
    - Cleanup success/failure rates
    - TTL expiration counts
    - Cleanup latency
    """

    def __init__(self):
        """Initialize cleanup metrics."""
        self.cleanup_attempts = 0
        self.cleanup_successes = 0
        self.cleanup_failures = 0
        self.ttl_expirations = 0
        self.items_cleaned = 0

        # Track cleanup reasons
        self.cleanup_reasons: Dict[str, int] = defaultdict(int)

    def record_cleanup(self, success: bool, items_count: int, reason: str, duration_ms: float):
        """
        Record cleanup operation.

        Args:
            success: Whether cleanup succeeded
            items_count: Number of items cleaned
            reason: Cleanup reason (e.g., "summarization_complete", "ttl_expired")
            duration_ms: Cleanup duration in milliseconds
        """
        self.cleanup_attempts += 1

        if success:
            self.cleanup_successes += 1
            self.items_cleaned += items_count
        else:
            self.cleanup_failures += 1

        self.cleanup_reasons[reason] += 1

        # Log cleanup operation
        logger.info("Ephemeral data cleanup", extra={
            "context": {
                "success": success,
                "items_cleaned": items_count,
                "reason": reason,
                "duration_ms": duration_ms
            }
        })

    def record_ttl_expiration(self, items_count: int):
        """
        Record TTL-based expiration.

        Args:
            items_count: Number of items expired
        """
        self.ttl_expirations += items_count

        logger.info("TTL expiration cleanup", extra={
            "context": {
                "items_expired": items_count
            }
        })

    def get_success_rate(self) -> float:
        """
        Calculate cleanup success rate.

        Returns:
            Success rate as percentage (0-100)
        """
        if self.cleanup_attempts == 0:
            return 100.0  # No failures yet

        return (self.cleanup_successes / self.cleanup_attempts) * 100

    def get_stats(self) -> Dict:
        """
        Get comprehensive cleanup stats.

        Returns:
            Dictionary with cleanup metrics
        """
        return {
            "cleanup_attempts": self.cleanup_attempts,
            "cleanup_successes": self.cleanup_successes,
            "cleanup_failures": self.cleanup_failures,
            "success_rate_percent": self.get_success_rate(),
            "ttl_expirations": self.ttl_expirations,
            "total_items_cleaned": self.items_cleaned,
            "cleanup_reasons": dict(self.cleanup_reasons),
        }

    def log_summary(self):
        """Log cleanup metrics summary."""
        stats = self.get_stats()
        logger.info("Cleanup metrics summary", extra={
            "context": stats
        })


# Global metrics instances
performance_metrics = PerformanceMetrics()
cleanup_metrics = CleanupMetrics()


class OperationTimer:
    """
    Context manager for timing operations with automatic metrics recording.

    Usage:
        with OperationTimer("submission_processing", participant_id=p_id):
            # ... do work ...
            pass
        # Automatically records duration and tracks concurrency
    """

    def __init__(self, operation: str, **context):
        """
        Initialize operation timer.

        Args:
            operation: Operation name
            **context: Context to include in metrics
        """
        self.operation = operation
        self.context = context
        self.start_time = None

    def __enter__(self):
        """Start timer and mark operation as concurrent."""
        self.start_time = time.time()
        performance_metrics.start_operation(self.operation)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Record duration and end concurrent tracking."""
        duration_ms = (time.time() - self.start_time) * 1000
        performance_metrics.end_operation(self.operation)
        performance_metrics.record_latency(self.operation, duration_ms, **self.context)
        return False  # Don't suppress exceptions
