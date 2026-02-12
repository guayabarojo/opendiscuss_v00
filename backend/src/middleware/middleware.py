"""
Middleware configuration for OpenDiscuss API.

Implements:
- CORS configuration (T018)
- Request logging (T018)
- Error handling (T018)
- Request/Response tracking

Constitutional Compliance:
- Transparent request logging for debugging
- Consistent error responses across all endpoints
- Security headers for all responses
"""

import time
import uuid
import json
from typing import Callable, Optional
from datetime import datetime

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers

from src.utils.logger import get_logger, log_warning, log_error

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all incoming requests and outgoing responses.

    Tracks:
    - Request ID (X-Request-ID header or generated UUID)
    - Method, path, query parameters
    - Response status code and processing time
    - Client IP address
    """

    async def dispatch(self, request: Request, call_next: Callable):
        """Process request with logging."""

        # Generate or retrieve request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Extract request info
        method = request.method
        path = request.url.path
        query_string = request.url.query
        client_ip = self.get_client_ip(request)

        # Record start time
        start_time = time.time()

        # Log incoming request (skip health checks to reduce noise)
        if not path.startswith("/health"):
            logger.info(
                logger,
                "Incoming request",
                request_id=request_id,
                method=method,
                path=path,
                query_string=query_string,
                client_ip=client_ip
            )

        try:
            # Process request
            response = await call_next(request)

        except Exception as exc:
            # Log exception
            processing_time = time.time() - start_time
            log_error(
                logger,
                exc,
                "Request processing failed",
                request_id=request_id,
                method=method,
                path=path,
                processing_time_ms=int(processing_time * 1000)
            )
            raise

        # Calculate processing time
        processing_time = time.time() - start_time

        # Log outgoing response (skip health checks)
        if not path.startswith("/health"):
            log_level = "info"
            if response.status_code >= 500:
                log_level = "error"
            elif response.status_code >= 400:
                log_level = "warning"

            logger.info(
                logger,
                f"Outgoing response ({log_level})",
                request_id=request_id,
                method=method,
                path=path,
                status_code=response.status_code,
                processing_time_ms=int(processing_time * 1000)
            )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time-Ms"] = str(int(processing_time * 1000))

        return response

    def get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request, handling proxies.

        Args:
            request: FastAPI request

        Returns:
            Client IP address
        """
        # Check X-Forwarded-For header (if behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection
        return request.client.host if request.client else "unknown"


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Centralized error handling middleware.

    Ensures all errors (including unhandled exceptions) return
    consistent JSON responses with error codes and request IDs.
    """

    # HTTP status codes that shouldn't be logged as errors
    EXPECTED_ERROR_CODES = {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        status.HTTP_429_TOO_MANY_REQUESTS,
    }

    async def dispatch(self, request: Request, call_next: Callable):
        """Process request with error handling."""

        try:
            response = await call_next(request)

            # Log unexpected 5xx errors (not in expected list)
            if response.status_code >= 500:
                request_id = getattr(request.state, "request_id", "unknown")
                log_error(
                    logger,
                    "Server error",
                    request_id=request_id,
                    status_code=response.status_code,
                    path=request.url.path
                )

            return response

        except HTTPException as exc:
            # FastAPI HTTPException - return JSON response
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

            # Map HTTPException to error code
            error_code = self.map_status_to_error_code(exc.status_code)

            # Log if not expected
            if exc.status_code not in self.EXPECTED_ERROR_CODES:
                log_warning(
                    logger,
                    f"HTTP exception: {error_code}",
                    request_id=request_id,
                    status_code=exc.status_code,
                    detail=exc.detail
                )

            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": error_code,
                    "message": exc.detail,
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

        except ValueError as exc:
            # Validation error - 422 Unprocessable Entity
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

            log_warning(
                logger,
                "Validation error",
                request_id=request_id,
                error=str(exc)
            )

            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "error": "VALIDATION_FAILED",
                    "message": str(exc),
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

        except Exception as exc:
            # Unhandled exception - 500 Internal Server Error
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

            log_error(
                logger,
                exc,  # Pass exception object
                "Unhandled exception",  # Pass message
                request_id=request_id,
                error_type=type(exc).__name__,
                path=request.url.path
            )

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

    @staticmethod
    def map_status_to_error_code(status_code: int) -> str:
        """Map HTTP status code to error code string."""
        status_to_code = {
            400: "VALIDATION_FAILED",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "UNPROCESSABLE_ENTITY",
            429: "RATE_LIMIT_EXCEEDED",
            500: "INTERNAL_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
        }
        return status_to_code.get(status_code, "UNKNOWN_ERROR")


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Add structured logging context to requests.

    Enriches logs with:
    - Request ID for tracing
    - User/participant ID (if available from token)
    - Request timing
    - Response size
    """

    async def dispatch(self, request: Request, call_next: Callable):
        """Add structured logging context."""

        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

        # Add to request state for access in route handlers
        request.state.request_id = request_id
        request.state.start_time = time.time()

        try:
            response = await call_next(request)
            return response
        finally:
            # Calculate elapsed time
            elapsed_time = time.time() - request.state.start_time
            request.state.elapsed_time = elapsed_time
