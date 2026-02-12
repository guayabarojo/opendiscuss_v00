"""
Performance Monitoring for Summary Generation

Tracks p95 latency, throughput, and success rates.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T102)
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    """Latency metrics for an operation."""

    count: int = 0
    total_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    durations: deque = field(default_factory=lambda: deque(maxlen=1000))

    def record(self, duration: float):
        """Record a duration measurement."""
        self.count += 1
        self.total_duration += duration
        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)
        self.durations.append(duration)

    @property
    def average(self) -> float:
        """Calculate average duration."""
        return self.total_duration / self.count if self.count > 0 else 0.0

    @property
    def p95(self) -> float:
        """Calculate 95th percentile duration."""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        index = int(len(sorted_durations) * 0.95)
        return sorted_durations[index] if index < len(sorted_durations) else sorted_durations[-1]

    @property
    def p99(self) -> float:
        """Calculate 99th percentile duration."""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        index = int(len(sorted_durations) * 0.99)
        return sorted_durations[index] if index < len(sorted_durations) else sorted_durations[-1]


class PerformanceMonitor:
    """Monitor performance metrics for summarization operations."""

    def __init__(self):
        """Initialize performance monitor."""
        self.generation_metrics = LatencyMetrics()
        self.approval_metrics = LatencyMetrics()
        self.regeneration_metrics = LatencyMetrics()
        self.llm_call_metrics = LatencyMetrics()

        self.success_count = 0
        self.failure_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

        self.start_time = datetime.utcnow()

    def record_generation(self, duration: float, success: bool = True):
        """Record summary generation metrics."""
        self.generation_metrics.record(duration)

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        # Check if p95 exceeds SLA (<3 seconds)
        if self.generation_metrics.p95 > 3.0:
            logger.warning(
                f"Generation p95 latency exceeds SLA: {self.generation_metrics.p95:.2f}s",
                extra={
                    "p95_latency": self.generation_metrics.p95,
                    "sla_target": 3.0,
                    "average_latency": self.generation_metrics.average,
                },
            )

    def record_approval(self, duration: float):
        """Record approval operation metrics."""
        self.approval_metrics.record(duration)

    def record_regeneration(self, duration: float, success: bool = True):
        """Record regeneration metrics."""
        self.regeneration_metrics.record(duration)

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

    def record_llm_call(self, duration: float):
        """Record LLM API call metrics."""
        self.llm_call_metrics.record(duration)

    def record_cache_hit(self):
        """Record cache hit."""
        self.cache_hits += 1

    def record_cache_miss(self):
        """Record cache miss."""
        self.cache_misses += 1

    def get_metrics(self) -> Dict:
        """
        Get current performance metrics.

        Returns:
            Dictionary with all performance metrics
        """
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        throughput = self.success_count / uptime if uptime > 0 else 0.0

        cache_hit_rate = (
            self.cache_hits / (self.cache_hits + self.cache_misses) * 100
            if (self.cache_hits + self.cache_misses) > 0
            else 0.0
        )

        return {
            "uptime_seconds": uptime,
            "generation": {
                "count": self.generation_metrics.count,
                "average_seconds": round(self.generation_metrics.average, 3),
                "p95_seconds": round(self.generation_metrics.p95, 3),
                "p99_seconds": round(self.generation_metrics.p99, 3),
                "min_seconds": round(self.generation_metrics.min_duration, 3),
                "max_seconds": round(self.generation_metrics.max_duration, 3),
                "sla_compliant": self.generation_metrics.p95 < 3.0,
            },
            "approval": {
                "count": self.approval_metrics.count,
                "average_seconds": round(self.approval_metrics.average, 3),
                "p95_seconds": round(self.approval_metrics.p95, 3),
            },
            "regeneration": {
                "count": self.regeneration_metrics.count,
                "average_seconds": round(self.regeneration_metrics.average, 3),
                "p95_seconds": round(self.regeneration_metrics.p95, 3),
            },
            "llm_calls": {
                "count": self.llm_call_metrics.count,
                "average_seconds": round(self.llm_call_metrics.average, 3),
                "p95_seconds": round(self.llm_call_metrics.p95, 3),
            },
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate_percent": round(cache_hit_rate, 2),
            },
            "reliability": {
                "success_count": self.success_count,
                "failure_count": self.failure_count,
                "success_rate_percent": round(
                    self.success_count / (self.success_count + self.failure_count) * 100
                    if (self.success_count + self.failure_count) > 0
                    else 0.0,
                    2,
                ),
            },
            "throughput": {
                "successful_operations_per_second": round(throughput, 3),
            },
        }

    def log_metrics(self):
        """Log current metrics."""
        metrics = self.get_metrics()
        logger.info(
            "Performance metrics",
            extra={"metrics": metrics},
        )

    def reset(self):
        """Reset all metrics."""
        self.generation_metrics = LatencyMetrics()
        self.approval_metrics = LatencyMetrics()
        self.regeneration_metrics = LatencyMetrics()
        self.llm_call_metrics = LatencyMetrics()

        self.success_count = 0
        self.failure_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

        self.start_time = datetime.utcnow()

        logger.info("Performance metrics reset")


# Global monitor instance
performance_monitor = PerformanceMonitor()
