"""
Monitoring and observability for clustering and alignment operations (Spec 004: T078).

Provides structured logging for:
- Clustering latency tracking
- Cluster distribution metrics
- Singleton cluster count
- Alignment match rate
- Performance warnings for slow operations

All metrics are logged as structured JSON for easy aggregation and analysis.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ClusteringMetrics:
    """Metrics collected during clustering operation."""
    round_id: str
    start_time_ms: float
    end_time_ms: float
    approved_summary_count: int
    cluster_count: int
    total_participants: int
    singleton_count: int
    min_cluster_size: int
    max_cluster_size: int
    avg_cluster_size: float
    embedding_generation_ms: float
    hdbscan_clustering_ms: float
    centroid_computation_ms: float
    persistence_ms: float

    @property
    def total_latency_ms(self) -> float:
        """Total end-to-end clustering latency."""
        return self.end_time_ms - self.start_time_ms

    @property
    def singleton_percentage(self) -> float:
        """Percentage of participants in singleton clusters."""
        if self.total_participants == 0:
            return 0.0
        return (self.singleton_count / self.total_participants) * 100


@dataclass
class AlignmentMetrics:
    """Metrics collected during alignment operation."""
    discussion_id: str
    round_r: int
    round_r1: int
    start_time_ms: float
    end_time_ms: float
    cluster_count_r: int
    cluster_count_r1: int
    match_count: int
    similarity_threshold: float
    min_similarity_found: float
    max_similarity_found: float
    avg_similarity_matched: float
    unmatched_clusters: int

    @property
    def total_latency_ms(self) -> float:
        """Total end-to-end alignment latency."""
        return self.end_time_ms - self.start_time_ms

    @property
    def match_rate(self) -> float:
        """Percentage of clusters that found matches above threshold."""
        total_clusters = self.cluster_count_r + self.cluster_count_r1
        if total_clusters == 0:
            return 0.0
        return (self.match_count / total_clusters) * 100


class ClusteringMonitor:
    """Monitor and log clustering operations for observability."""

    def __init__(self, latency_threshold_ms: int = 5000):
        """
        Initialize clustering monitor.

        Args:
            latency_threshold_ms: Latency threshold for warning logs (default 5000ms)
        """
        self.latency_threshold_ms = latency_threshold_ms
        self.timers: Dict[str, float] = {}
        self.stages: Dict[str, Dict[str, float]] = {}

    def start_operation(self, operation_id: str, round_id: str) -> None:
        """
        Start timing a clustering operation.

        Args:
            operation_id: Unique operation ID for correlation
            round_id: Round being clustered
        """
        self.timers[operation_id] = time.time()
        self.stages[operation_id] = {
            "round_id": round_id,
            "operation_start": time.time()
        }
        logger.info(
            "Clustering operation started",
            extra={
                "operation_id": operation_id,
                "round_id": round_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def record_stage(self, operation_id: str, stage_name: str) -> float:
        """
        Record completion of a clustering stage and return elapsed time.

        Args:
            operation_id: Operation to record stage for
            stage_name: Name of the stage (e.g., 'embedding', 'hdbscan', 'centroid')

        Returns:
            Elapsed time in milliseconds for this stage
        """
        if operation_id not in self.stages:
            logger.warning(f"Recording stage for unknown operation: {operation_id}")
            return 0.0

        current_time = time.time()
        stage_data = self.stages[operation_id]

        # Calculate stage duration
        if "last_stage_time" in stage_data:
            stage_duration_ms = (current_time - stage_data["last_stage_time"]) * 1000
        else:
            stage_duration_ms = (current_time - stage_data["operation_start"]) * 1000

        stage_data["last_stage_time"] = current_time
        stage_data[f"{stage_name}_ms"] = stage_duration_ms

        logger.debug(
            f"Clustering stage completed: {stage_name}",
            extra={
                "operation_id": operation_id,
                "stage": stage_name,
                "duration_ms": stage_duration_ms,
            }
        )

        return stage_duration_ms

    def log_clustering_metrics(self, metrics: ClusteringMetrics) -> None:
        """
        Log comprehensive clustering metrics.

        Args:
            metrics: ClusteringMetrics object with all collected metrics
        """
        # Determine log level based on latency
        is_slow = metrics.total_latency_ms > self.latency_threshold_ms

        log_context = {
            "event": "clustering.completed",
            "operation_type": "clustering",
            "round_id": metrics.round_id,
            "metrics": {
                "total_latency_ms": metrics.total_latency_ms,
                "approved_summary_count": metrics.approved_summary_count,
                "cluster_count": metrics.cluster_count,
                "total_participants": metrics.total_participants,
                "singleton_count": metrics.singleton_count,
                "singleton_percentage": metrics.singleton_percentage,
                "min_cluster_size": metrics.min_cluster_size,
                "max_cluster_size": metrics.max_cluster_size,
                "avg_cluster_size": metrics.avg_cluster_size,
                "stage_breakdown_ms": {
                    "embedding_generation": metrics.embedding_generation_ms,
                    "hdbscan_clustering": metrics.hdbscan_clustering_ms,
                    "centroid_computation": metrics.centroid_computation_ms,
                    "persistence": metrics.persistence_ms,
                }
            }
        }

        if is_slow:
            logger.warning(
                f"Clustering latency exceeded threshold ({metrics.total_latency_ms}ms > {self.latency_threshold_ms}ms)",
                extra=log_context
            )
        else:
            logger.info(
                f"Clustering completed successfully ({metrics.cluster_count} clusters, "
                f"{metrics.total_latency_ms}ms total)",
                extra=log_context
            )

        # Log distribution analysis
        self._log_cluster_distribution(metrics)

    def _log_cluster_distribution(self, metrics: ClusteringMetrics) -> None:
        """
        Log cluster distribution for observability.

        Args:
            metrics: ClusteringMetrics with distribution info
        """
        logger.debug(
            "Cluster distribution analysis",
            extra={
                "round_id": metrics.round_id,
                "distribution": {
                    "min_cluster_size": metrics.min_cluster_size,
                    "max_cluster_size": metrics.max_cluster_size,
                    "avg_cluster_size": metrics.avg_cluster_size,
                    "singleton_count": metrics.singleton_count,
                    "singleton_percentage": metrics.singleton_percentage,
                }
            }
        )

    def log_clustering_error(
        self,
        operation_id: str,
        round_id: str,
        error: Exception,
        stage: str = "unknown"
    ) -> None:
        """
        Log clustering operation failure.

        Args:
            operation_id: Operation that failed
            round_id: Round being processed
            error: Exception that occurred
            stage: Stage where error occurred
        """
        elapsed_ms = (time.time() - self.timers.get(operation_id, time.time())) * 1000
        logger.error(
            f"Clustering operation failed at stage '{stage}'",
            extra={
                "operation_id": operation_id,
                "round_id": round_id,
                "stage": stage,
                "error": str(error),
                "elapsed_ms": elapsed_ms,
                "error_type": type(error).__name__,
            },
            exc_info=True
        )

        # Clean up timers
        self.timers.pop(operation_id, None)
        self.stages.pop(operation_id, None)


class AlignmentMonitor:
    """Monitor and log alignment operations for observability."""

    def __init__(self, latency_threshold_ms: int = 1000):
        """
        Initialize alignment monitor.

        Args:
            latency_threshold_ms: Latency threshold for warning logs (default 1000ms)
        """
        self.latency_threshold_ms = latency_threshold_ms
        self.timers: Dict[str, float] = {}

    def start_operation(
        self,
        operation_id: str,
        discussion_id: str,
        round_r: int,
        round_r1: int
    ) -> None:
        """
        Start timing an alignment operation.

        Args:
            operation_id: Unique operation ID for correlation
            discussion_id: Discussion being aligned
            round_r: Earlier round
            round_r1: Later round
        """
        self.timers[operation_id] = time.time()
        logger.info(
            "Alignment operation started",
            extra={
                "operation_id": operation_id,
                "discussion_id": discussion_id,
                "round_pair": f"r{round_r}→r{round_r1}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def log_alignment_metrics(self, metrics: AlignmentMetrics) -> None:
        """
        Log comprehensive alignment metrics.

        Args:
            metrics: AlignmentMetrics object with all collected metrics
        """
        # Determine log level based on latency
        is_slow = metrics.total_latency_ms > self.latency_threshold_ms

        log_context = {
            "event": "alignment.completed",
            "operation_type": "alignment",
            "discussion_id": metrics.discussion_id,
            "round_pair": f"r{metrics.round_r}→r{metrics.round_r1}",
            "metrics": {
                "total_latency_ms": metrics.total_latency_ms,
                "cluster_count_r": metrics.cluster_count_r,
                "cluster_count_r1": metrics.cluster_count_r1,
                "match_count": metrics.match_count,
                "match_rate": metrics.match_rate,
                "unmatched_clusters": metrics.unmatched_clusters,
                "similarity_threshold": metrics.similarity_threshold,
                "similarity_range": {
                    "min": metrics.min_similarity_found,
                    "max": metrics.max_similarity_found,
                    "avg_matched": metrics.avg_similarity_matched,
                }
            }
        }

        if is_slow:
            logger.warning(
                f"Alignment latency exceeded threshold ({metrics.total_latency_ms}ms > {self.latency_threshold_ms}ms)",
                extra=log_context
            )
        else:
            logger.info(
                f"Alignment completed successfully ({metrics.match_count} matches, "
                f"{metrics.match_rate:.1f}% match rate, {metrics.total_latency_ms}ms total)",
                extra=log_context
            )

    def log_alignment_error(
        self,
        operation_id: str,
        discussion_id: str,
        round_r: int,
        round_r1: int,
        error: Exception
    ) -> None:
        """
        Log alignment operation failure.

        Args:
            operation_id: Operation that failed
            discussion_id: Discussion being processed
            round_r: Earlier round
            round_r1: Later round
            error: Exception that occurred
        """
        elapsed_ms = (time.time() - self.timers.get(operation_id, time.time())) * 1000
        logger.error(
            f"Alignment operation failed",
            extra={
                "operation_id": operation_id,
                "discussion_id": discussion_id,
                "round_pair": f"r{round_r}→r{round_r1}",
                "error": str(error),
                "elapsed_ms": elapsed_ms,
                "error_type": type(error).__name__,
            },
            exc_info=True
        )

        # Clean up timers
        self.timers.pop(operation_id, None)


# Global monitor instances
clustering_monitor = ClusteringMonitor(latency_threshold_ms=5000)
alignment_monitor = AlignmentMonitor(latency_threshold_ms=1000)
