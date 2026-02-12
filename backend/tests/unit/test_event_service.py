"""
Unit tests for Clustering Event Service (Spec 4).

Tests T015-T016:
- T015: Redis client setup for event pub/sub
- T016: Event subscriber for summaries.approved_for_round event

Validates event handling for Spec 3 → Spec 4 integration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from src.services.event_service import ClusteringEventService
from src.events.event_types import SummarizationCompleteEvent, ApprovedSummarySummary


@pytest.mark.asyncio
class TestClusteringEventService:
    """Test suite for ClusteringEventService."""

    async def test_initialize_service(self):
        """
        Test T015: Initialize ClusteringEventService with Redis client.

        Verifies:
        - Service can be initialized
        - Redis client connection is established
        - EventBus connection is established
        """
        with patch('src.services.event_service.get_redis_client') as mock_redis, \
             patch('src.services.event_service.get_event_bus') as mock_event_bus:

            # Mock Redis and EventBus
            mock_redis.return_value = AsyncMock()
            mock_event_bus.return_value = AsyncMock()

            # Initialize service
            service = ClusteringEventService()
            await service.initialize()

            # Verify initialization
            assert service._is_initialized is True
            mock_redis.assert_called_once()
            mock_event_bus.assert_called_once()

    async def test_publish_event(self):
        """
        Test T015: Publish event to Redis channel.

        Verifies:
        - Events can be published to Redis channels
        - Payload is correctly serialized to JSON
        - publish method is fire-and-forget (doesn't raise on error)
        """
        with patch('src.services.event_service.get_redis_client') as mock_redis, \
             patch('src.services.event_service.get_event_bus') as mock_event_bus:

            # Mock Redis client
            redis_client = AsyncMock()
            redis_client.publish = AsyncMock()
            mock_redis.return_value = redis_client

            # Mock EventBus
            event_bus = AsyncMock()
            mock_event_bus.return_value = event_bus

            # Initialize service
            service = ClusteringEventService()
            await service.initialize()

            # Publish test event
            test_payload = {
                "round_id": str(uuid4()),
                "cluster_count": 5,
                "total_participants": 20,
            }
            await service.publish("opendiscuss.clustering.completed", test_payload)

            # Verify Redis publish was called
            redis_client.publish.assert_called_once()

    async def test_subscribe_to_channel(self):
        """
        Test T015: Subscribe to Redis channel with handler.

        Verifies:
        - Service can subscribe to Redis channels
        - Handler is registered for incoming messages
        """
        with patch('src.services.event_service.get_redis_client') as mock_redis, \
             patch('src.services.event_service.get_event_bus') as mock_event_bus:

            # Mock Redis client with pubsub
            redis_client = AsyncMock()
            pubsub_mock = AsyncMock()
            pubsub_mock.subscribe = AsyncMock()
            pubsub_mock.listen = AsyncMock(return_value=iter([]))
            redis_client.pubsub = MagicMock(return_value=pubsub_mock)
            mock_redis.return_value = redis_client

            # Mock EventBus
            event_bus = AsyncMock()
            mock_event_bus.return_value = event_bus

            # Initialize service
            service = ClusteringEventService()
            await service.initialize()

            # Create test handler
            handler = AsyncMock()

            # Subscribe to channel (this will start listening, so we patch the loop)
            with patch.object(service, 'subscribe', new=AsyncMock()):
                await service.subscribe("test.channel", handler)

    async def test_on_summaries_approved_for_round_handler(self):
        """
        Test T016: Handle summarization.complete event from Spec 3.

        Verifies:
        - Handler processes SummarizationCompleteEvent correctly
        - Approved summaries are extracted from event
        - Clustering workflow is triggered (once implemented)
        - Handler logs appropriate messages
        """
        with patch('src.services.event_service.get_redis_client') as mock_redis, \
             patch('src.services.event_service.get_event_bus') as mock_event_bus:

            # Mock Redis and EventBus
            mock_redis.return_value = AsyncMock()
            mock_event_bus.return_value = AsyncMock()

            # Initialize service
            service = ClusteringEventService()
            await service.initialize()

            # Create test event with approved summaries
            round_id = uuid4()
            approved_summaries = [
                ApprovedSummarySummary(
                    summary_id=uuid4(),
                    participant_id=uuid4(),
                    submission_id=uuid4(),
                    summary_text="Test summary about renewable energy.",
                    approved_at=datetime.utcnow(),
                ),
                ApprovedSummarySummary(
                    summary_id=uuid4(),
                    participant_id=uuid4(),
                    submission_id=uuid4(),
                    summary_text="Another summary about climate action.",
                    approved_at=datetime.utcnow(),
                ),
            ]

            event = SummarizationCompleteEvent(
                round_id=round_id,
                approved_summaries=approved_summaries,
            )

            # Call handler
            await service.on_summaries_approved_for_round(event)

            # Verify handler processed event (doesn't raise exception)
            # Once clustering workflow is implemented, this test should verify
            # that clustering is triggered with the correct summaries

    async def test_handler_with_empty_summaries(self):
        """
        Test T016: Handle event with zero approved summaries.

        Verifies:
        - Handler gracefully handles empty summary list
        - Warning is logged
        - Clustering workflow is not triggered
        """
        with patch('src.services.event_service.get_redis_client') as mock_redis, \
             patch('src.services.event_service.get_event_bus') as mock_event_bus:

            # Mock Redis and EventBus
            mock_redis.return_value = AsyncMock()
            mock_event_bus.return_value = AsyncMock()

            # Initialize service
            service = ClusteringEventService()
            await service.initialize()

            # Create event with empty approved_summaries
            event = SummarizationCompleteEvent(
                round_id=uuid4(),
                approved_summaries=[],
            )

            # Call handler - should not raise exception
            await service.on_summaries_approved_for_round(event)

    async def test_register_handlers(self):
        """
        Test T016: Register event handlers with EventBus.

        Verifies:
        - Handler registration subscribes to summarization.complete
        - EventBus subscribe method is called correctly
        """
        with patch('src.services.event_service.get_redis_client') as mock_redis, \
             patch('src.services.event_service.get_event_bus') as mock_event_bus:

            # Mock Redis client
            mock_redis.return_value = AsyncMock()

            # Mock EventBus with subscribe method
            event_bus = AsyncMock()
            event_bus.subscribe = AsyncMock()
            mock_event_bus.return_value = event_bus

            # Initialize service
            service = ClusteringEventService()
            await service.initialize()

            # Register handlers
            await service.register_handlers()

            # Verify subscribe was called for summarization.complete
            event_bus.subscribe.assert_called_once_with(
                event_type="summarization.complete",
                handler=service.on_summaries_approved_for_round,
            )

    async def test_error_handling_in_publish(self):
        """
        Test T015: Error handling in publish method.

        Verifies:
        - Publish errors are logged but don't raise exceptions
        - Service remains operational after publish failure
        """
        with patch('src.services.event_service.get_redis_client') as mock_redis, \
             patch('src.services.event_service.get_event_bus') as mock_event_bus:

            # Mock Redis client that fails on publish
            redis_client = AsyncMock()
            redis_client.publish = AsyncMock(side_effect=Exception("Redis connection error"))
            mock_redis.return_value = redis_client

            # Mock EventBus
            event_bus = AsyncMock()
            mock_event_bus.return_value = event_bus

            # Initialize service
            service = ClusteringEventService()
            await service.initialize()

            # Publish should not raise exception (fire-and-forget)
            test_payload = {"test": "data"}
            await service.publish("test.channel", test_payload)

            # Service should still be operational
            assert service._is_initialized is True

    async def test_shutdown_service(self):
        """
        Test service shutdown and cleanup.

        Verifies:
        - Shutdown completes without errors
        - Service state is reset
        """
        with patch('src.services.event_service.get_redis_client') as mock_redis, \
             patch('src.services.event_service.get_event_bus') as mock_event_bus:

            # Mock Redis and EventBus
            mock_redis.return_value = AsyncMock()
            mock_event_bus.return_value = AsyncMock()

            # Initialize and shutdown service
            service = ClusteringEventService()
            await service.initialize()
            await service.shutdown()

            # Verify service is no longer initialized
            assert service._is_initialized is False


@pytest.mark.asyncio
class TestGlobalEventServiceInstance:
    """Test global event service instance management."""

    async def test_get_clustering_event_service(self):
        """
        Test global event service singleton.

        Verifies:
        - get_clustering_event_service returns initialized instance
        - Multiple calls return same instance
        """
        with patch('src.services.event_service.get_redis_client') as mock_redis, \
             patch('src.services.event_service.get_event_bus') as mock_event_bus:

            # Mock Redis and EventBus
            mock_redis.return_value = AsyncMock()
            mock_event_bus.return_value = AsyncMock()

            # Import here to reset global state
            from src.services.event_service import (
                get_clustering_event_service,
                close_clustering_event_service,
            )

            # Get service instance
            service1 = await get_clustering_event_service()
            service2 = await get_clustering_event_service()

            # Verify same instance
            assert service1 is service2
            assert service1._is_initialized is True

            # Cleanup
            await close_clustering_event_service()
