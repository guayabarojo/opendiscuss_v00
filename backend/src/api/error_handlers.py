"""
Error handling middleware and custom exceptions for OpenDiscuss Discussion Protocol.

Provides standardized error responses per OpenAPI spec (discussion-api.yaml).
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


# ============================================================================
# Custom Exception Classes
# ============================================================================


class DiscussionNotFoundException(Exception):
    """Raised when a discussion is not found by ID."""

    def __init__(self, discussion_id: str) -> None:
        self.discussion_id = discussion_id
        super().__init__(f"Discussion not found: {discussion_id}")


class RoundNotFoundException(Exception):
    """Raised when a round is not found by ID."""

    def __init__(self, round_id: str) -> None:
        self.round_id = round_id
        super().__init__(f"Round not found: {round_id}")


class ParticipantNotFoundException(Exception):
    """Raised when a participant is not found by ID."""

    def __init__(self, participant_id: str) -> None:
        self.participant_id = participant_id
        super().__init__(f"Participant not found: {participant_id}")


class InvalidStateTransitionException(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(
        self, entity_type: str, entity_id: str, from_state: str, to_state: str, reason: str
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(
            f"Invalid {entity_type} state transition for {entity_id}: "
            f"{from_state} -> {to_state}. Reason: {reason}"
        )


class TimingViolationException(Exception):
    """Raised when a timing constraint is violated."""

    def __init__(self, operation: str, reason: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.operation = operation
        self.reason = reason
        self.details = details or {}
        super().__init__(f"Timing violation in {operation}: {reason}")


class RateLimitExceededException(Exception):
    """Raised when rate limit is exceeded (e.g., > 3 submissions per round)."""

    def __init__(
        self, resource: str, limit: int, current: int, reset_at: Optional[datetime] = None
    ) -> None:
        self.resource = resource
        self.limit = limit
        self.current = current
        self.reset_at = reset_at
        super().__init__(
            f"Rate limit exceeded for {resource}: {current}/{limit} "
            f"(resets at {reset_at.isoformat() if reset_at else 'N/A'})"
        )


class UnauthorizedException(Exception):
    """Raised when a user is not authorized to perform an operation."""

    def __init__(self, operation: str, reason: str) -> None:
        self.operation = operation
        self.reason = reason
        super().__init__(f"Unauthorized: {operation}. Reason: {reason}")


# ============================================================================
# Error Response Builder
# ============================================================================


def build_error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """
    Build standardized error response per OpenAPI spec.

    Format:
    {
        "error": "error_code",
        "message": "Human readable message",
        "details": {...},
        "timestamp": "ISO8601"
    }
    """
    response_body = {
        "error": error_code,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if details:
        response_body["details"] = details

    return JSONResponse(status_code=status_code, content=response_body)


# ============================================================================
# Exception Handlers
# ============================================================================


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle FastAPI HTTPException."""
    # If detail is already a dict (structured error), return it as-is
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # Otherwise, use the standard error response format
    return build_error_response(
        error_code=f"http_{exc.status_code}",
        message=exc.detail,
        status_code=exc.status_code,
        details={"path": str(request.url)},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic ValidationError from request validation."""
    errors = exc.errors()
    return build_error_response(
        error_code="validation_error",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={
            "errors": errors,
            "body": exc.body,
            "path": str(request.url),
        },
    )


async def pydantic_validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle Pydantic ValidationError from internal operations."""
    return build_error_response(
        error_code="validation_error",
        message="Data validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={
            "errors": exc.errors(),
            "path": str(request.url),
        },
    )


async def discussion_not_found_handler(
    request: Request, exc: DiscussionNotFoundException
) -> JSONResponse:
    """Handle DiscussionNotFoundException."""
    return build_error_response(
        error_code="discussion_not_found",
        message=str(exc),
        status_code=status.HTTP_404_NOT_FOUND,
        details={
            "discussion_id": exc.discussion_id,
            "path": str(request.url),
        },
    )


async def round_not_found_handler(request: Request, exc: RoundNotFoundException) -> JSONResponse:
    """Handle RoundNotFoundException."""
    return build_error_response(
        error_code="round_not_found",
        message=str(exc),
        status_code=status.HTTP_404_NOT_FOUND,
        details={
            "round_id": exc.round_id,
            "path": str(request.url),
        },
    )


async def participant_not_found_handler(
    request: Request, exc: ParticipantNotFoundException
) -> JSONResponse:
    """Handle ParticipantNotFoundException."""
    return build_error_response(
        error_code="participant_not_found",
        message=str(exc),
        status_code=status.HTTP_404_NOT_FOUND,
        details={
            "participant_id": exc.participant_id,
            "path": str(request.url),
        },
    )


async def invalid_state_transition_handler(
    request: Request, exc: InvalidStateTransitionException
) -> JSONResponse:
    """Handle InvalidStateTransitionException."""
    return build_error_response(
        error_code="invalid_state_transition",
        message=str(exc),
        status_code=status.HTTP_400_BAD_REQUEST,
        details={
            "entity_type": exc.entity_type,
            "entity_id": exc.entity_id,
            "from_state": exc.from_state,
            "to_state": exc.to_state,
            "reason": exc.reason,
            "path": str(request.url),
        },
    )


async def timing_violation_handler(request: Request, exc: TimingViolationException) -> JSONResponse:
    """Handle TimingViolationException."""
    return build_error_response(
        error_code="timing_violation",
        message=str(exc),
        status_code=status.HTTP_400_BAD_REQUEST,
        details={
            "operation": exc.operation,
            "reason": exc.reason,
            **exc.details,
            "path": str(request.url),
        },
    )


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceededException
) -> JSONResponse:
    """Handle RateLimitExceededException."""
    details = {
        "resource": exc.resource,
        "limit": exc.limit,
        "current": exc.current,
        "path": str(request.url),
    }

    if exc.reset_at:
        details["reset_at"] = exc.reset_at.isoformat()

    return build_error_response(
        error_code="rate_limit_exceeded",
        message=str(exc),
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        details=details,
    )


async def unauthorized_exception_handler(
    request: Request, exc: UnauthorizedException
) -> JSONResponse:
    """Handle UnauthorizedException."""
    return build_error_response(
        error_code="unauthorized",
        message=str(exc),
        status_code=status.HTTP_403_FORBIDDEN,
        details={
            "operation": exc.operation,
            "reason": exc.reason,
            "path": str(request.url),
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    # Log the full exception for debugging
    import traceback

    traceback.print_exc()

    return build_error_response(
        error_code="internal_server_error",
        message="An unexpected error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details={
            "path": str(request.url),
            "exception_type": type(exc).__name__,
        },
    )


# ============================================================================
# Registration Function
# ============================================================================


def register_error_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI application.

    Call this during application initialization in main.py.
    """
    # HTTP exceptions
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)

    # Custom domain exceptions
    app.add_exception_handler(DiscussionNotFoundException, discussion_not_found_handler)
    app.add_exception_handler(RoundNotFoundException, round_not_found_handler)
    app.add_exception_handler(ParticipantNotFoundException, participant_not_found_handler)
    app.add_exception_handler(InvalidStateTransitionException, invalid_state_transition_handler)
    app.add_exception_handler(TimingViolationException, timing_violation_handler)
    app.add_exception_handler(RateLimitExceededException, rate_limit_exceeded_handler)
    app.add_exception_handler(UnauthorizedException, unauthorized_exception_handler)

    # Catch-all for unhandled exceptions
    app.add_exception_handler(Exception, generic_exception_handler)
