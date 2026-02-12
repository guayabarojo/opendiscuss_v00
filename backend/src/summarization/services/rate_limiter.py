"""
Rate Limiter for LLM API Calls

Implements token bucket rate limiting to prevent API quota exhaustion.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T101)
"""

import asyncio
import logging
import time
from typing import Optional

import redis.asyncio as redis

from backend.src.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for LLM API calls."""

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        max_requests_per_minute: int = 60,
        burst_allowance: int = 10,
    ):
        """
        Initialize rate limiter.

        Args:
            redis_client: Redis client for distributed rate limiting
            max_requests_per_minute: Maximum API calls per minute
            burst_allowance: Additional calls allowed in burst
        """
        self.redis_client = redis_client
        self.max_requests = max_requests_per_minute
        self.burst_allowance = burst_allowance
        self.rate_limit_key_prefix = "ratelimit:llm"

    async def _ensure_redis(self) -> redis.Redis:
        """Ensure Redis client is initialized."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(
                str(settings.redis_url),
                encoding="utf-8",
                decode_responses=True,
            )
        return self.redis_client

    async def acquire(self, resource_id: str = "global") -> bool:
        """
        Acquire permission to make an LLM API call.

        Uses token bucket algorithm with Redis for distributed limiting.

        Args:
            resource_id: Identifier for rate limit scope (default: "global")

        Returns:
            True if request is allowed, False if rate limited
        """
        try:
            client = await self._ensure_redis()
            key = f"{self.rate_limit_key_prefix}:{resource_id}"
            now = time.time()

            # Token bucket algorithm
            # Each minute adds max_requests tokens
            # Burst allows up to max_requests + burst_allowance tokens

            # Get current token count and last refill time
            pipe = client.pipeline()
            pipe.get(f"{key}:tokens")
            pipe.get(f"{key}:last_refill")
            results = await pipe.execute()

            current_tokens = float(results[0] or self.max_requests)
            last_refill = float(results[1] or now)

            # Calculate tokens to add based on time elapsed
            time_elapsed = now - last_refill
            tokens_to_add = (time_elapsed / 60.0) * self.max_requests

            # Update token count
            new_tokens = min(
                current_tokens + tokens_to_add,
                self.max_requests + self.burst_allowance,
            )

            # Check if we can consume a token
            if new_tokens >= 1.0:
                # Consume token
                new_tokens -= 1.0

                # Update Redis
                pipe = client.pipeline()
                pipe.setex(f"{key}:tokens", 120, str(new_tokens))
                pipe.setex(f"{key}:last_refill", 120, str(now))
                await pipe.execute()

                logger.debug(
                    f"Rate limit check passed for {resource_id}",
                    extra={
                        "resource_id": resource_id,
                        "tokens_remaining": new_tokens,
                    },
                )

                return True
            else:
                # Rate limited
                wait_time = (1.0 - new_tokens) / self.max_requests * 60.0

                logger.warning(
                    f"Rate limit exceeded for {resource_id}",
                    extra={
                        "resource_id": resource_id,
                        "tokens_remaining": new_tokens,
                        "estimated_wait_seconds": wait_time,
                    },
                )

                return False

        except Exception as e:
            logger.error(
                f"Error checking rate limit: {e}",
                extra={"error": str(e), "resource_id": resource_id},
                exc_info=True,
            )
            # Fail open - allow request if rate limiter fails
            return True

    async def wait_if_needed(self, resource_id: str = "global", max_wait_seconds: float = 5.0):
        """
        Wait until rate limit allows request (with timeout).

        Args:
            resource_id: Identifier for rate limit scope
            max_wait_seconds: Maximum time to wait

        Raises:
            TimeoutError: If wait exceeds max_wait_seconds
        """
        start_time = time.time()

        while True:
            if await self.acquire(resource_id):
                return

            elapsed = time.time() - start_time
            if elapsed >= max_wait_seconds:
                raise TimeoutError(
                    f"Rate limit wait timeout after {elapsed:.2f}s for {resource_id}"
                )

            # Wait a bit before retry
            await asyncio.sleep(0.1)

    async def get_current_tokens(self, resource_id: str = "global") -> float:
        """
        Get current token count for resource.

        Args:
            resource_id: Identifier for rate limit scope

        Returns:
            Current token count
        """
        try:
            client = await self._ensure_redis()
            key = f"{self.rate_limit_key_prefix}:{resource_id}"

            tokens = await client.get(f"{key}:tokens")
            return float(tokens) if tokens else self.max_requests

        except Exception as e:
            logger.error(f"Error getting token count: {e}")
            return self.max_requests

    async def reset(self, resource_id: str = "global"):
        """Reset rate limit for resource."""
        try:
            client = await self._ensure_redis()
            key = f"{self.rate_limit_key_prefix}:{resource_id}"

            pipe = client.pipeline()
            pipe.delete(f"{key}:tokens")
            pipe.delete(f"{key}:last_refill")
            await pipe.execute()

            logger.info(f"Rate limit reset for {resource_id}")

        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")

    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
