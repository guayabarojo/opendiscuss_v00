"""
Event service for Spec 4 Clustering & Alignment Protocol.

Provides Redis pub/sub functionality for event publishing and subscription,
specifically handling the summarization.complete event from Spec 3 to trigger
clustering workflows.

This service extends the existing Redis client from Spec 3 and integrates
with the global EventBus for protocol coordination.

Tasks Implemented:
- T034: clustering.completed event publisher with Redis channel opendiscuss.clustering.completed
- T035: Logging for event publishing with timestamps
"""

import logging
from typing import Any, Callable, Coroutine, Dict, Optional, List
from uuid import UUID
from datetime import datetime
import json

from src.cache.redis_client import get_redis_client
from src.events.event_bus import EventBus, get_event_bus
from src.events.event_types import SummarizationCompleteEvent

logger = logging.getLogger(__name__)


class ClusteringEventService:
    """
    Event service for Clustering & Alignment Protocol.

    Handles event-driven coordination with Spec 3 (Summarization & Approval)
    by subscribing to summarization.complete events and triggering clustering.
    """

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        """
        Initialize clustering event service.

        Args:
            event_bus: EventBus instance, defaults to global event bus
        """
        self._event_bus = event_bus
        self._redis_client = None
        self._is_initialized = False

    async def initialize(self) -> None:
        """
        Initialize event service connections.

        Establishes Redis connection and EventBus subscription.

        Raises:
            ConnectionError: If Redis or EventBus connection fails
        """
        if self._is_initialized:
            logger.warning("ClusteringEventService already initialized")
            return

        try:
            # Get Redis client for pub/sub operations
            self._redis_client = await get_redis_client()
            logger.info("ClusteringEventService: Redis client initialized")

            # Get or create EventBus instance
            if self._event_bus is None:
                self._event_bus = await get_event_bus()
            logger.info("ClusteringEventService: EventBus connected")

            self._is_initialized = True
            logger.info("ClusteringEventService initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize ClusteringEventService: {e}", exc_info=True)
            raise ConnectionError("ClusteringEventService initialization failed") from e

    async def publish(self, channel: str, payload: Dict[str, Any]) -> None:
        """
        Publish an event to a Redis channel.

        Used for publishing clustering.completed and alignment.completed events
        to downstream services (e.g., Spec 5 - Sankey Diagrams).

        Args:
            channel: Redis channel name (e.g., "opendiscuss.clustering.completed")
            payload: Event payload dictionary

        Raises:
            RuntimeError: If service not initialized
            redis.RedisError: If publish fails (logged but not raised)
        """
        if not self._is_initialized or not self._redis_client:
            error_msg = "Cannot publish: ClusteringEventService not initialized"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            import json

            message = json.dumps(payload)
            await self._redis_client.publish(channel, message)

            logger.debug(f"Published event to channel {channel}: {payload}")

        except Exception as e:
            logger.error(f"Failed to publish to channel {channel}: {e}", exc_info=True)
            # Don't raise - publish should be fire-and-forget for resilience

    async def subscribe(
        self,
        channel: str,
        handler: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Subscribe to a Redis channel with a handler.

        Args:
            channel: Redis channel name to subscribe to
            handler: Async handler function that receives the event payload dict

        Raises:
            RuntimeError: If service not initialized
            redis.RedisError: If subscription fails
        """
        if not self._is_initialized or not self._redis_client:
            error_msg = "Cannot subscribe: ClusteringEventService not initialized"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            # Create pubsub instance
            pubsub = self._redis_client.pubsub()
            await pubsub.subscribe(channel)

            logger.info(f"Subscribed to Redis channel: {channel}")

            # Start listening for messages
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    import json

                    payload = json.loads(message["data"])
                    await handler(payload)

                except Exception as e:
                    logger.error(
                        f"Handler error for channel {channel}: {e}",
                        exc_info=True,
                    )
                    # Continue processing other messages even if one fails

        except Exception as e:
            logger.error(f"Failed to subscribe to channel {channel}: {e}", exc_info=True)
            raise

    async def on_summaries_approved_for_round(self, event: SummarizationCompleteEvent) -> None:
        """
        Handle summarization.complete event from Spec 3.

        Triggered when all participants have approved their summaries for a round.
        Initiates the clustering workflow to group approved summaries into thought spaces.

        Constitutional Enforcement:
        - Intent Fidelity: Only explicitly approved summaries enter clustering
        - Semantic Accuracy Over Aesthetics: No forced merging of distinct clusters

        Args:
            event: SummarizationCompleteEvent containing round_id and approved_summaries

        Raises:
            ValueError: If event validation fails
            RuntimeError: If clustering workflow fails
        """
        round_id = event.round_id
        approved_summaries = event.approved_summaries
        approved_count = len(approved_summaries)

        logger.info(
            f"ClusteringEventService: Received summarization.complete event for round {round_id} "
            f"with {approved_count} approved summaries"
        )

        # Validate event payload
        if approved_count == 0:
            logger.warning(
                f"Round {round_id}: No approved summaries to cluster. "
                f"Clustering workflow will not be triggered."
            )
            return

        try:
            # TODO: Trigger clustering workflow
            # This will be implemented in subsequent tasks (T019-T037)
            # Expected flow:
            # 1. Extract approved summary texts from event.approved_summaries
            # 2. Generate embeddings using embedding_service.py
            # 3. Run HDBSCAN clustering on embeddings
            # 4. Handle outliers as singleton clusters
            # 5. Compute centroids and cluster statistics
            # 6. Persist clusters to database
            # 7. Publish clustering.completed event

            logger.info(
                f"Round {round_id}: Clustering workflow triggered for {approved_count} summaries "
                f"(implementation pending - T019-T037)"
            )

            # For now, log the approved summaries for debugging
            logger.debug(
                f"Approved summaries for round {round_id}: "
                f"[{', '.join(str(s.summary_id) for s in approved_summaries)}]"
            )

        except Exception as e:
            logger.error(
                f"Failed to process summarization.complete for round {round_id}: {e}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Clustering event handler failed for round {round_id}"
            ) from e

    async def publish_clustering_completed(
        self,
        round_id: UUID,
        cluster_count: int,
        total_participants: int,
        singleton_count: int,
        processing_time_ms: float,
        cluster_ids: Optional[List[UUID]] = None,
        minority_cluster_count: Optional[int] = None,
    ) -> None:
        """
        Publish clustering.completed event to Redis channel.

        Implements T034: Publish clustering.completed event with required payload.
        Implements T041: Add minority_cluster_count metric to event payload.

        Publishes to Redis channel: opendiscuss.clustering.completed

        Event payload includes:
        - round_id: UUID of clustered round
        - cluster_count: Number of thought spaces created
        - total_participants: Total participants assigned to clusters
        - singleton_count: Number of singleton clusters (outliers converted)
        - processing_time_ms: Clustering computation duration
        - cluster_ids: Optional list of created cluster IDs
        - minority_cluster_count: Number of minority clusters (1-2 participants)

        Args:
            round_id: UUID of the round that was clustered
            cluster_count: Number of thought spaces created
            total_participants: Total number of participants
            singleton_count: Number of singleton clusters
            processing_time_ms: Clustering processing duration in milliseconds
            cluster_ids: Optional list of cluster UUIDs for reference
            minority_cluster_count: Number of minority clusters (1-2 participants)

        Raises:
            RuntimeError: If service not initialized
            ValueError: If payload validation fails

        Requirements:
            - T034: Publish to Redis channel opendiscuss.clustering.completed
            - T041: Track minority_cluster_count metric
            - Event schema from events.yaml: ClusteringCompletedPayload
        """
        if not self._is_initialized or not self._redis_client:
            error_msg = "Cannot publish clustering.completed: ClusteringEventService not initialized"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Validate inputs
        if cluster_count < 0:
            raise ValueError(f"cluster_count must be non-negative, got {cluster_count}")
        if total_participants <= 0:
            raise ValueError(f"total_participants must be positive, got {total_participants}")
        if singleton_count < 0:
            raise ValueError(f"singleton_count must be non-negative, got {singleton_count}")
        if processing_time_ms < 0:
            raise ValueError(f"processing_time_ms must be non-negative, got {processing_time_ms}")
        if minority_cluster_count is not None and minority_cluster_count < 0:
            raise ValueError(f"minority_cluster_count must be non-negative, got {minority_cluster_count}")

        try:
            # Create event payload (ClusteringCompletedEvent will be defined in later tasks)
            payload = {
                "round_id": str(round_id),
                "cluster_count": cluster_count,
                "total_participants": total_participants,
                "singleton_count": singleton_count,
                "processing_time_ms": int(processing_time_ms),
                "timestamp": datetime.utcnow().isoformat(),
            }

            if cluster_ids:
                payload["cluster_ids"] = [str(cid) for cid in cluster_ids]

            # T041: Add minority_cluster_count metric
            if minority_cluster_count is not None:
                payload["minority_cluster_count"] = minority_cluster_count

            # Publish to Redis channel
            channel = "opendiscuss.clustering.completed"
            message = json.dumps(payload)
            await self._redis_client.publish(channel, message)

            # Build log message with optional minority_cluster_count
            log_msg = (
                f"[EVENT:CLUSTERING_COMPLETED] Published to channel {channel} "
                f"round_id={round_id} "
                f"cluster_count={cluster_count} "
                f"total_participants={total_participants} "
                f"singleton_count={singleton_count} "
                f"processing_time_ms={processing_time_ms:.2f} "
            )
            if minority_cluster_count is not None:
                log_msg += f"minority_cluster_count={minority_cluster_count} "
            log_msg += f"timestamp={datetime.utcnow().isoformat()}"

            logger.info(log_msg)

        except ValueError as e:
            logger.error(f"[EVENT:CLUSTERING_COMPLETED_ERROR] Validation error: {e}")
            raise
        except Exception as e:
            logger.error(
                f"[EVENT:CLUSTERING_COMPLETED_ERROR] Failed to publish clustering.completed event: {e}",
                exc_info=True
            )
            # Don't raise - publish should be fire-and-forget for resilience

    async def publish_alignment_completed(
        self,
        discussion_id: UUID,
        round_r: int,
        round_r1: int,
        match_count: int,
        similarity_threshold: float,
        processing_time_ms: float,
        display_group_count: Optional[int] = None,
    ) -> None:
        """
        Publish alignment.completed event to Redis channel.

        Publishes to Redis channel: opendiscuss.alignment.completed

        Event payload includes:
        - discussion_id: Discussion context
        - round_r: Earlier round number
        - round_r1: Later round number (r+1)
        - match_count: Number of cluster pairs aligned
        - similarity_threshold: Threshold used for matching
        - processing_time_ms: Alignment computation duration
        - display_group_count: Number of unique display groups assigned

        Args:
            discussion_id: UUID of the discussion
            round_r: Earlier round number
            round_r1: Later round number
            match_count: Number of cluster pairs aligned
            similarity_threshold: Similarity threshold used
            processing_time_ms: Alignment processing duration in milliseconds
            display_group_count: Optional number of display groups created

        Raises:
            RuntimeError: If service not initialized
            ValueError: If payload validation fails
        """
        if not self._is_initialized or not self._redis_client:
            error_msg = "Cannot publish alignment.completed: ClusteringEventService not initialized"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Validate inputs
        if round_r < 0 or round_r1 < 0:
            raise ValueError(f"Round numbers must be non-negative: round_r={round_r}, round_r1={round_r1}")
        if round_r1 != round_r + 1:
            raise ValueError(f"Rounds must be adjacent: round_r={round_r}, round_r1={round_r1}")
        if match_count < 0:
            raise ValueError(f"match_count must be non-negative, got {match_count}")
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError(f"similarity_threshold must be in [0.0, 1.0], got {similarity_threshold}")
        if processing_time_ms < 0:
            raise ValueError(f"processing_time_ms must be non-negative, got {processing_time_ms}")

        try:
            # Create event payload (AlignmentCompletedEvent will be defined in later tasks)
            payload = {
                "discussion_id": str(discussion_id),
                "round_r": round_r,
                "round_r1": round_r1,
                "match_count": match_count,
                "similarity_threshold": similarity_threshold,
                "processing_time_ms": int(processing_time_ms),
                "timestamp": datetime.utcnow().isoformat(),
            }

            if display_group_count is not None:
                payload["display_group_count"] = display_group_count

            # Publish to Redis channel
            channel = "opendiscuss.alignment.completed"
            message = json.dumps(payload)
            await self._redis_client.publish(channel, message)

            logger.info(
                f"[EVENT:ALIGNMENT_COMPLETED] Published to channel {channel} "
                f"discussion_id={discussion_id} "
                f"round_r={round_r} "
                f"round_r1={round_r1} "
                f"match_count={match_count} "
                f"similarity_threshold={similarity_threshold:.2f} "
                f"processing_time_ms={processing_time_ms:.2f} "
                f"timestamp={datetime.utcnow().isoformat()}"
            )

        except ValueError as e:
            logger.error(f"[EVENT:ALIGNMENT_COMPLETED_ERROR] Validation error: {e}")
            raise
        except Exception as e:
            logger.error(
                f"[EVENT:ALIGNMENT_COMPLETED_ERROR] Failed to publish alignment.completed event: {e}",
                exc_info=True
            )
            # Don't raise - publish should be fire-and-forget for resilience

    async def register_handlers(self) -> None:
        """
        Register event handlers with the EventBus.

        Subscribes to summarization.complete event from Spec 3.

        Raises:
            RuntimeError: If service not initialized or registration fails
        """
        if not self._is_initialized or not self._event_bus:
            error_msg = "Cannot register handlers: ClusteringEventService not initialized"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            # Subscribe to summarization.complete event
            await self._event_bus.subscribe(
                event_type="summarization.complete",
                handler=self.on_summaries_approved_for_round,
            )

            logger.info(
                "ClusteringEventService: Registered handler for summarization.complete event"
            )

        except Exception as e:
            logger.error(f"Failed to register event handlers: {e}", exc_info=True)
            raise RuntimeError("Event handler registration failed") from e

    async def shutdown(self) -> None:
        """
        Shutdown event service and close connections.

        Closes Redis client and EventBus subscriptions.
        """
        if not self._is_initialized:
            return

        try:
            # EventBus and Redis client are managed globally
            # No explicit cleanup needed here
            self._is_initialized = False
            logger.info("ClusteringEventService shutdown complete")

        except Exception as e:
            logger.warning(f"Error during ClusteringEventService shutdown: {e}")


# Global singleton instance
_clustering_event_service: Optional[ClusteringEventService] = None


async def get_clustering_event_service() -> ClusteringEventService:
    """
    Get or create the global ClusteringEventService instance.

    Returns:
        ClusteringEventService: The global event service instance

    Raises:
        ConnectionError: If initialization fails
    """
    global _clustering_event_service

    if _clustering_event_service is None:
        _clustering_event_service = ClusteringEventService()
        await _clustering_event_service.initialize()

    return _clustering_event_service


async def close_clustering_event_service() -> None:
    """Close the global ClusteringEventService instance."""
    global _clustering_event_service

    if _clustering_event_service is not None:
        await _clustering_event_service.shutdown()
        _clustering_event_service = None
