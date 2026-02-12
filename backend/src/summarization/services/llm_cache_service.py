"""
LLM Response Caching Service

Implements Redis-based caching for LLM responses to reduce API costs and improve performance.
Cache key format: "llm:summary:{hash(input_text + prompt_version)}"
TTL: 3600 seconds (1 hour)

Spec Reference: Spec 003 - Summarization & Approval Protocol (T086)
"""

import hashlib
import json
import logging
from typing import Optional

import redis.asyncio as redis
from pydantic import BaseModel

from ...config import settings

logger = logging.getLogger(__name__)


class CachedLLMResponse(BaseModel):
    """Cached LLM response structure."""

    summary_text: str
    model_used: str
    prompt_version: str
    cached_at: float


class LLMCacheService:
    """Service for caching LLM responses in Redis."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize LLM cache service.

        Args:
            redis_client: Redis client instance (optional, creates new if not provided)
        """
        self.redis_client = redis_client
        self.ttl_seconds = settings.llm_cache_ttl_seconds
        self.cache_prefix = "llm:summary"

    async def _ensure_redis(self) -> redis.Redis:
        """Ensure Redis client is initialized."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(
                str(settings.redis_url),
                encoding="utf-8",
                decode_responses=True,
            )
        return self.redis_client

    def _generate_cache_key(
        self,
        input_text: str,
        prompt_version: str,
        model_name: str,
    ) -> str:
        """
        Generate cache key from input text, prompt version, and model.

        Args:
            input_text: Raw participant input text
            prompt_version: Version identifier for prompt template
            model_name: LLM model name (e.g., "gpt-4-turbo")

        Returns:
            Cache key string
        """
        # Create hash of input + prompt + model for deterministic caching
        cache_input = f"{input_text}|{prompt_version}|{model_name}"
        content_hash = hashlib.sha256(cache_input.encode()).hexdigest()[:16]
        return f"{self.cache_prefix}:{content_hash}"

    async def get_cached_summary(
        self,
        input_text: str,
        prompt_version: str,
        model_name: str,
    ) -> Optional[CachedLLMResponse]:
        """
        Retrieve cached LLM response if available.

        Args:
            input_text: Raw participant input text
            prompt_version: Version identifier for prompt template
            model_name: LLM model name

        Returns:
            Cached response if found, None otherwise
        """
        try:
            client = await self._ensure_redis()
            cache_key = self._generate_cache_key(input_text, prompt_version, model_name)

            cached_data = await client.get(cache_key)
            if cached_data:
                logger.info(
                    f"LLM cache HIT for key={cache_key}",
                    extra={"cache_key": cache_key, "model": model_name},
                )
                cached_dict = json.loads(cached_data)
                return CachedLLMResponse(**cached_dict)

            logger.debug(
                f"LLM cache MISS for key={cache_key}",
                extra={"cache_key": cache_key, "model": model_name},
            )
            return None

        except Exception as e:
            logger.error(
                f"Error retrieving from LLM cache: {e}",
                extra={"error": str(e), "input_length": len(input_text)},
                exc_info=True,
            )
            # Fail open - return None to proceed with LLM call
            return None

    async def cache_summary(
        self,
        input_text: str,
        prompt_version: str,
        model_name: str,
        summary_text: str,
        cached_at: float,
    ) -> bool:
        """
        Cache LLM response for future requests.

        Args:
            input_text: Raw participant input text
            prompt_version: Version identifier for prompt template
            model_name: LLM model name
            summary_text: Generated summary text
            cached_at: Unix timestamp when cached

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            client = await self._ensure_redis()
            cache_key = self._generate_cache_key(input_text, prompt_version, model_name)

            cached_response = CachedLLMResponse(
                summary_text=summary_text,
                model_used=model_name,
                prompt_version=prompt_version,
                cached_at=cached_at,
            )

            await client.setex(
                cache_key,
                self.ttl_seconds,
                cached_response.model_dump_json(),
            )

            logger.info(
                f"LLM response cached with key={cache_key}, TTL={self.ttl_seconds}s",
                extra={
                    "cache_key": cache_key,
                    "model": model_name,
                    "ttl": self.ttl_seconds,
                },
            )
            return True

        except Exception as e:
            logger.error(
                f"Error caching LLM response: {e}",
                extra={"error": str(e), "model": model_name},
                exc_info=True,
            )
            # Fail open - don't block on cache errors
            return False

    async def invalidate_cache(
        self,
        input_text: str,
        prompt_version: str,
        model_name: str,
    ) -> bool:
        """
        Invalidate cached LLM response.

        Args:
            input_text: Raw participant input text
            prompt_version: Version identifier for prompt template
            model_name: LLM model name

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            client = await self._ensure_redis()
            cache_key = self._generate_cache_key(input_text, prompt_version, model_name)

            deleted = await client.delete(cache_key)
            if deleted:
                logger.info(
                    f"LLM cache invalidated for key={cache_key}",
                    extra={"cache_key": cache_key},
                )
            return bool(deleted)

        except Exception as e:
            logger.error(
                f"Error invalidating LLM cache: {e}",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    async def get_cache_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats (hit_rate, total_keys, memory_usage)
        """
        try:
            client = await self._ensure_redis()
            info = await client.info("stats")

            # Calculate hit rate
            keyspace_hits = info.get("keyspace_hits", 0)
            keyspace_misses = info.get("keyspace_misses", 0)
            total_requests = keyspace_hits + keyspace_misses

            hit_rate = (
                (keyspace_hits / total_requests * 100) if total_requests > 0 else 0.0
            )

            # Count LLM cache keys
            cursor = 0
            llm_cache_keys = 0
            while True:
                cursor, keys = await client.scan(
                    cursor, match=f"{self.cache_prefix}:*", count=100
                )
                llm_cache_keys += len(keys)
                if cursor == 0:
                    break

            return {
                "hit_rate": round(hit_rate, 2),
                "total_llm_cache_keys": llm_cache_keys,
                "keyspace_hits": keyspace_hits,
                "keyspace_misses": keyspace_misses,
            }

        except Exception as e:
            logger.error(
                f"Error retrieving cache stats: {e}",
                extra={"error": str(e)},
                exc_info=True,
            )
            return {
                "hit_rate": 0.0,
                "total_llm_cache_keys": 0,
                "error": str(e),
            }

    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
