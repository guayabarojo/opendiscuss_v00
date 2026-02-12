"""
Structured logging configuration for OpenDiscuss Discussion Protocol.

Uses JSON structured logging with trace IDs for request correlation.
Configures uvicorn to use structured logging format.
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variables for storing correlation IDs across async contexts
trace_id_ctx_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
discussion_id_ctx_var: ContextVar[Optional[str]] = ContextVar("discussion_id", default=None)
round_id_ctx_var: ContextVar[Optional[str]] = ContextVar("round_id", default=None)
question_id_ctx_var: ContextVar[Optional[str]] = ContextVar("question_id", default=None)
sequence_id_ctx_var: ContextVar[Optional[str]] = ContextVar("sequence_id", default=None)


# ============================================================================
# JSON Formatter
# ============================================================================


class JSONFormatter(logging.Formatter):
    """
    JSON structured log formatter.

    Outputs logs in the format:
    {
        "timestamp": "ISO8601",
        "level": "INFO",
        "service": "opendiscuss-backend",
        "trace_id": "uuid",
        "message": "log message",
        "context": {...additional fields...}
    }
    """

    def __init__(self, service_name: str = "opendiscuss-backend") -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        import json

        # Build base log structure
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "message": record.getMessage(),
        }

        # Add trace ID if available
        trace_id = trace_id_ctx_var.get()
        if trace_id:
            log_data["trace_id"] = trace_id

        # Add discussion_id if available (for correlation across services)
        discussion_id = discussion_id_ctx_var.get()
        if discussion_id:
            log_data["discussion_id"] = discussion_id

        # Add round_id if available (for tracking round-specific operations)
        round_id = round_id_ctx_var.get()
        if round_id:
            log_data["round_id"] = round_id

        # Add question_id if available (for tracking question-specific operations)
        question_id = question_id_ctx_var.get()
        if question_id:
            log_data["question_id"] = question_id

        # Add sequence_id if available (for tracking question sequence operations)
        sequence_id = sequence_id_ctx_var.get()
        if sequence_id:
            log_data["sequence_id"] = sequence_id

        # Add logger name
        log_data["logger"] = record.name

        # Add context from extra fields
        context: Dict[str, Any] = {}

        # Collect extra fields (excluding standard logging attributes)
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                context[key] = value

        # Add exception info if present
        if record.exc_info:
            context["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None,
            }

        # Add context to log data if not empty
        if context:
            log_data["context"] = context

        return json.dumps(log_data)


# ============================================================================
# Logging Configuration
# ============================================================================


def configure_logging(log_level: str = "INFO", service_name: str = "opendiscuss-backend") -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        service_name: Service name to include in logs
    """
    # Create JSON formatter
    json_formatter = JSONFormatter(service_name=service_name)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)

    # Configure uvicorn loggers to use JSON format
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.addHandler(console_handler)
        logger.propagate = False

    # Configure application logger
    app_logger = logging.getLogger("opendiscuss")
    app_logger.setLevel(log_level.upper())


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    The logger will automatically include trace_id in all log messages
    when called within a request context.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"opendiscuss.{name}")


# ============================================================================
# Trace ID Middleware
# ============================================================================


class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds trace_id to all requests for correlation.

    - Generates a unique trace_id for each request
    - Stores trace_id in context variable for access across async contexts
    - Adds X-Trace-ID header to all responses
    - Logs request start and completion with trace_id
    """

    def __init__(self, app: FastAPI) -> None:
        super().__init__(app)
        self.logger = get_logger(__name__)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process request and add trace_id."""
        # Generate or extract trace_id
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())

        # Store trace_id in context variable
        trace_id_ctx_var.set(trace_id)

        # Log request start
        self.logger.info(
            "Request started",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
            },
        )

        try:
            # Process request
            response = await call_next(request)

            # Add trace_id to response headers
            response.headers["X-Trace-ID"] = trace_id

            # Log request completion
            self.logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )

            return response

        except Exception as exc:
            # Log exception
            self.logger.error(
                "Request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                },
                exc_info=True,
            )
            raise

        finally:
            # Clear trace_id from context
            trace_id_ctx_var.set(None)


# ============================================================================
# Uvicorn Configuration
# ============================================================================


def get_uvicorn_log_config(log_level: str = "INFO") -> Dict[str, Any]:
    """
    Get uvicorn logging configuration with JSON structured logging.

    Use this when starting uvicorn:
    ```
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_config=get_uvicorn_log_config(settings.log_level)
    )
    ```

    Args:
        log_level: Logging level

    Returns:
        Uvicorn log config dict
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "src.logging_config.JSONFormatter",
                "service_name": "opendiscuss-backend",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["console"],
                "level": log_level.upper(),
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": log_level.upper(),
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": log_level.upper(),
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": log_level.upper(),
        },
    }


# ============================================================================
# Helper Functions
# ============================================================================


def get_trace_id() -> Optional[str]:
    """
    Get the current trace_id from context.

    Returns:
        Current trace_id or None if not in request context
    """
    return trace_id_ctx_var.get()


def set_trace_id(trace_id: str) -> None:
    """
    Set the trace_id in context.

    Useful for background tasks or event handlers that should
    maintain trace context.

    Args:
        trace_id: Trace ID to set
    """
    trace_id_ctx_var.set(trace_id)


def get_discussion_id() -> Optional[str]:
    """
    Get the current discussion_id from context.

    Returns:
        Current discussion_id or None if not set
    """
    return discussion_id_ctx_var.get()


def set_discussion_id(discussion_id: str) -> None:
    """
    Set the discussion_id in context for log correlation.

    Should be called when processing operations related to a specific discussion.

    Args:
        discussion_id: Discussion ID to set
    """
    discussion_id_ctx_var.set(discussion_id)


def get_round_id() -> Optional[str]:
    """
    Get the current round_id from context.

    Returns:
        Current round_id or None if not set
    """
    return round_id_ctx_var.get()


def set_round_id(round_id: str) -> None:
    """
    Set the round_id in context for log correlation.

    Should be called when processing operations related to a specific round.

    Args:
        round_id: Round ID to set
    """
    round_id_ctx_var.set(round_id)


def get_question_id() -> Optional[str]:
    """
    Get the current question_id from context.

    Returns:
        Current question_id or None if not set
    """
    return question_id_ctx_var.get()


def set_question_id(question_id: str) -> None:
    """
    Set the question_id in context for log correlation.

    Should be called when processing operations related to a specific question.

    Args:
        question_id: Question ID to set
    """
    question_id_ctx_var.set(question_id)


def get_sequence_id() -> Optional[str]:
    """
    Get the current sequence_id from context.

    Returns:
        Current sequence_id or None if not set
    """
    return sequence_id_ctx_var.get()


def set_sequence_id(sequence_id: str) -> None:
    """
    Set the sequence_id in context for log correlation.

    Should be called when processing operations related to a question sequence.

    Args:
        sequence_id: Sequence ID to set
    """
    sequence_id_ctx_var.set(sequence_id)


def clear_correlation_context() -> None:
    """
    Clear all correlation IDs from context.

    Useful for cleanup in background tasks or between operations.
    """
    trace_id_ctx_var.set(None)
    discussion_id_ctx_var.set(None)
    round_id_ctx_var.set(None)
    question_id_ctx_var.set(None)
    sequence_id_ctx_var.set(None)


# ============================================================================
# Default Logger Instance
# ============================================================================

# Create default logger for backward compatibility
logger = get_logger("default")
