"""
Question sequence caching for performance optimization (T105).

Uses Redis for caching QuestionSequence entities with TTL.
Invalidates on sequence updates, discussion termination.
"""

import json
import pickle
from typing import Optional
from uuid import UUID
from datetime import timedelta

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)


class SequenceCache:
    """
    Cache for QuestionSequence entities.

    Features:
    - TTL: 10 minutes
    - Cache key: f"question_sequence:{discussion_id}"
    - Invalidation: On sequence update, discussion termination
    - Backend: Redis

    Usage:
        cache = SequenceCache()
        await cache.set(discussion_id, sequence_data)
        data = await cache.get(discussion_id)
        await cache.invalidate(discussion_id)
    """

    def __init__(self, redis_url: Optional[str] = None, ttl_seconds: int = 600):
        """
        Initialize SequenceCache.

        Args:
            redis_url: Redis connection URL (defaults to settings.redis_url)
            ttl_seconds: Cache TTL in seconds (default: 600 = 10 minutes)
        """
        self.redis_url = redis_url or str(settings.redis_url)
        self.ttl = timedelta(seconds=ttl_seconds)
        self.ttl_seconds = ttl_seconds
        self._redis: Optional[AsyncRedis] = None

    async def _get_redis(self) -> AsyncRedis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = AsyncRedis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False  # We'll handle pickle serialization
            )
        return self._redis

    def _make_key(self, discussion_id: UUID) -> str:
        """Generate cache key for discussion."""
        return f"question_sequence:{str(discussion_id)}"

    async def get(self, discussion_id: UUID) -> Optional[dict]:
        """
        Get cached sequence data for discussion.

        Args:
            discussion_id: Discussion UUID

        Returns:
            Cached sequence data dict or None if not found/expired
        """
        key = self._make_key(discussion_id)

        try:
            redis = await self._get_redis()
            data = await redis.get(key)

            if data:
                logger.debug(
                    "Cache hit for question sequence",
                    extra={"discussion_id": str(discussion_id)}
                )
                return pickle.loads(data)
            else:
                logger.debug(
                    "Cache miss for question sequence",
                    extra={"discussion_id": str(discussion_id)}
                )
                return None

        except Exception as e:
            logger.warning(
                "Failed to read from sequence cache",
                extra={"discussion_id": str(discussion_id), "error": str(e)},
                exc_info=True
            )
            return None

    async def set(self, discussion_id: UUID, sequence_data: dict) -> bool:
        """
        Cache sequence data for discussion.

        Args:
            discussion_id: Discussion UUID
            sequence_data: Sequence data to cache (serializable dict)

        Returns:
            True if cached successfully, False otherwise
        """
        key = self._make_key(discussion_id)

        try:
            redis = await self._get_redis()
            serialized = pickle.dumps(sequence_data)
            await redis.setex(key, self.ttl_seconds, serialized)

            logger.debug(
                "Cached question sequence",
                extra={
                    "discussion_id": str(discussion_id),
                    "ttl_seconds": self.ttl_seconds
                }
            )
            return True

        except Exception as e:
            logger.warning(
                "Failed to write to sequence cache",
                extra={"discussion_id": str(discussion_id), "error": str(e)},
                exc_info=True
            )
            return False

    async def invalidate(self, discussion_id: UUID) -> bool:
        """
        Invalidate cached sequence for discussion.

        Args:
            discussion_id: Discussion UUID

        Returns:
            True if invalidated successfully, False otherwise
        """
        key = self._make_key(discussion_id)

        try:
            redis = await self._get_redis()
            await redis.delete(key)

            logger.info(
                "Invalidated question sequence cache",
                extra={"discussion_id": str(discussion_id)}
            )
            return True

        except Exception as e:
            logger.warning(
                "Failed to invalidate sequence cache",
                extra={"discussion_id": str(discussion_id), "error": str(e)},
                exc_info=True
            )
            return False

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Global cache instance
sequence_cache = SequenceCache()
