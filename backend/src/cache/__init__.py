"""
Redis caching for LLM responses (Spec 003)
"""

from .redis_client import get_redis_client, close_redis_client

__all__ = [
    "get_redis_client",
    "close_redis_client",
]
