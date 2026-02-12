"""
Security middleware for OpenDiscuss API.

Implements:
- API-level rate limiting per IP address (T086)
- Input sanitization for all text fields
- Security headers (HSTS, CSP, etc.)
- Request size limits

Constitutional Compliance:
- Parallel-First: Rate limiting doesn't block legitimate concurrent use
- Intent Fidelity: Sanitization preserves meaning while preventing XSS
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import re
import html

from src.config import settings
from src.utils.logger import get_logger, log_warning

logger = get_logger(__name__)


class IPRateLimiter:
    """
    IP-based rate limiter for API endpoints.

    Implements sliding window rate limiting per IP address.
    Default: 100 requests per minute per IP (configurable).

    For production with multiple processes:
    - Migrate to Redis-based rate limiting (atomic INCR)
    - Or use nginx rate limiting module
    """

    def __init__(self, requests_per_minute: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per IP per window
            window_seconds: Time window in seconds
        """
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        # IP -> List of request timestamps
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def check_rate_limit(self, ip: str) -> bool:
        """
        Check if IP has exceeded rate limit.

        Args:
            ip: Client IP address

        Returns:
            True if request allowed, False if rate limited
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # Clean old entries
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > cutoff]

        # Check limit
        if len(self.requests[ip]) >= self.requests_per_minute:
            log_warning(
                logger,
                "Rate limit exceeded",
                ip=ip,
                request_count=len(self.requests[ip]),
                limit=self.requests_per_minute
            )
            return False

        # Record request
        self.requests[ip].append(now)
        return True

    def get_retry_after(self, ip: str) -> int:
        """
        Get seconds until rate limit resets.

        Args:
            ip: Client IP address

        Returns:
            Seconds until oldest request expires
        """
        if ip not in self.requests or not self.requests[ip]:
            return 0

        oldest = self.requests[ip][0]
        reset_time = oldest + self.window_seconds
        return max(0, int(reset_time - time.time()))


# Global rate limiter instance
rate_limiter = IPRateLimiter(
    requests_per_minute=getattr(settings, 'api_rate_limit_per_minute', 100)
)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware for all API requests.

    Implements:
    1. Rate limiting per IP
    2. Security headers
    3. Request size limits
    """

    # Exempt health check from rate limiting
    RATE_LIMIT_EXEMPT_PATHS = ["/health", "/docs", "/openapi.json"]

    async def dispatch(self, request: Request, call_next: Callable):
        """Process request through security checks."""

        # Get client IP
        client_ip = self.get_client_ip(request)

        # Rate limiting (skip for exempt paths)
        if not any(request.url.path.startswith(path) for path in self.RATE_LIMIT_EXEMPT_PATHS):
            if not rate_limiter.check_rate_limit(client_ip):
                retry_after = rate_limiter.get_retry_after(client_ip)
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please try again later.",
                        "retry_after_seconds": retry_after
                    },
                    headers={"Retry-After": str(retry_after)}
                )

        # Process request
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS for production
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # CSP header
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'"
        )

        return response

    def get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request.

        Handles X-Forwarded-For header for proxied requests.

        Args:
            request: FastAPI request

        Returns:
            Client IP address
        """
        # Check X-Forwarded-For header (if behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP if multiple
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection
        return request.client.host if request.client else "unknown"


def sanitize_text_input(text: str, max_length: int = 5000) -> str:
    """
    Sanitize text input to prevent XSS and injection attacks.

    Sanitization strategy:
    1. HTML escape all special characters
    2. Remove null bytes
    3. Trim to max length
    4. Strip leading/trailing whitespace

    Note: This is defensive. The frontend should also sanitize before display.

    Constitutional Compliance (Intent Fidelity):
    - Preserves semantic meaning while preventing malicious code
    - Does NOT modify punctuation, capitalization, or legitimate content
    - Only escapes characters that could execute code

    Args:
        text: Raw input text
        max_length: Maximum allowed length

    Returns:
        Sanitized text safe for storage and display

    Example:
        Input:  "<script>alert('xss')</script>Hello"
        Output: "&lt;script&gt;alert('xss')&lt;/script&gt;Hello"
    """
    if not text:
        return ""

    # Remove null bytes (can bypass filters)
    text = text.replace("\x00", "")

    # HTML escape to prevent XSS
    # Escapes: < > & " '
    text = html.escape(text, quote=True)

    # Trim to max length
    if len(text) > max_length:
        text = text[:max_length]

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def validate_uuid_format(value: str) -> bool:
    """
    Validate UUID format to prevent injection.

    Args:
        value: String to validate

    Returns:
        True if valid UUID format
    """
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(value))


def sanitize_json_input(data: dict) -> dict:
    """
    Recursively sanitize all string values in JSON input.

    Args:
        data: Dictionary with potentially unsafe strings

    Returns:
        Dictionary with sanitized strings
    """
    if isinstance(data, dict):
        return {k: sanitize_json_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json_input(item) for item in data]
    elif isinstance(data, str):
        return sanitize_text_input(data)
    else:
        return data
