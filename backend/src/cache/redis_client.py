"""
Redis client for LLM response caching (Spec 003).

Provides connection management and cache operations with TTL=3600 (1 hour).
"""

import json
import hashlib
from typing import Any, Optional

import redis.asyncio as aioredis

from ..config import settings
from ..logging_config import logger


# Global Redis client instance
_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    """
    Get or create Redis client for LLM response caching.

    Uses connection pooling for optimal performance.
    Configured with decode_responses=False for binary safety.

    Returns:
        aioredis.Redis: Async Redis client instance

    Raises:
        redis.ConnectionError: If Redis connection fails
    """
    global _redis_client

    if _redis_client is None:
        try:
            _redis_client = await aioredis.from_url(
                str(settings.redis_url),
                encoding="utf-8",
                decode_responses=False,  # Handle binary data
                max_connections=50,      # Connection pool size
                socket_timeout=5.0,      # Socket timeout (seconds)
                socket_connect_timeout=5.0,
            )
            # Test connection
            await _redis_client.ping()
            logger.info("Redis client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    return _redis_client


async def close_redis_client() -> None:
    """
    Close Redis connection on application shutdown.

    Closes connection pool and releases resources.
    """
    global _redis_client

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")


def generate_cache_key(prompt: str, model: str, params: dict[str, Any]) -> str:
    """
    Generate deterministic cache key for LLM request.

    Uses SHA256 hash of prompt + model + params for stable keys.

    Args:
        prompt: The LLM prompt text
        model: Model identifier (e.g., "gpt-4-turbo")
        params: Additional parameters (temperature, max_tokens, etc.)

    Returns:
        str: Cache key in format "llm:{hash}"
    """
    # Serialize parameters deterministically
    cache_input = {
        "prompt": prompt,
        "model": model,
        "params": dict(sorted(params.items())),
    }
    serialized = json.dumps(cache_input, sort_keys=True)

    # Generate SHA256 hash
    hash_obj = hashlib.sha256(serialized.encode("utf-8"))
    cache_hash = hash_obj.hexdigest()

    return f"llm:{cache_hash}"


async def get_cached_response(
    prompt: str, model: str, params: dict[str, Any]
) -> Optional[str]:
    """
    Get cached LLM response if available.

    Args:
        prompt: The LLM prompt text
        model: Model identifier
        params: Request parameters

    Returns:
        Optional[str]: Cached response text, or None if cache miss

    Raises:
        redis.RedisError: If Redis operation fails
    """
    try:
        client = await get_redis_client()
        cache_key = generate_cache_key(prompt, model, params)

        cached = await client.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for key: {cache_key}")
            return cached.decode("utf-8")

        logger.debug(f"Cache miss for key: {cache_key}")
        return None

    except Exception as e:
        logger.warning(f"Redis get failed: {e}. Proceeding without cache.")
        return None


async def set_cached_response(
    prompt: str,
    model: str,
    params: dict[str, Any],
    response: str,
    ttl: int = 3600,
) -> None:
    """
    Store LLM response in cache with TTL.

    Args:
        prompt: The LLM prompt text
        model: Model identifier
        params: Request parameters
        response: LLM response text to cache
        ttl: Time-to-live in seconds (default: 3600 = 1 hour)

    Raises:
        redis.RedisError: If Redis operation fails
    """
    try:
        client = await get_redis_client()
        cache_key = generate_cache_key(prompt, model, params)

        await client.set(
            cache_key,
            response.encode("utf-8"),
            ex=ttl,
        )
        logger.debug(f"Cached response for key: {cache_key} (TTL: {ttl}s)")

    except Exception as e:
        logger.warning(f"Redis set failed: {e}. Proceeding without cache.")
