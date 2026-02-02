"""
Structured JSON logging for OpenDiscuss.

Provides consistent, machine-readable logging across all services with:
- JSON formatted output for log aggregation systems
- Contextual metadata (request_id, participant_id, round_id, etc.)
- Performance metrics (duration, latency)
- Error tracking with stack traces
- Log level control via environment

Constitutional Compliance:
- Temporal Transparency: Timestamps on all log entries
- Intent Fidelity: Preserve context without interpretation
"""

import json
import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from src.config import settings


class StructuredJSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as structured JSON.

    Output format:
    {
        "timestamp": "2026-01-29T14:02:30.123Z",
        "level": "INFO",
        "logger": "src.services.input_collection",
        "message": "Submission accepted",
        "context": {
            "submission_id": "...",
            "participant_id": "...",
            "round_id": "...",
            ...
        },
        "duration_ms": 123,
        "error": {
            "type": "ValueError",
            "message": "...",
            "traceback": "..."
        }
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context metadata if present
        if hasattr(record, "context"):
            log_data["context"] = record.context

        # Add performance metrics if present
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms

        # Add error information if present
        if record.exc_info:
            log_data["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add custom fields from record
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "filename", "funcName",
                          "levelname", "levelno", "lineno", "module", "msecs",
                          "pathname", "process", "processName", "relativeCreated",
                          "thread", "threadName", "exc_info", "exc_text", "stack_info",
                          "context", "duration_ms", "latency_ms"]:
                log_data[key] = value

        return json.dumps(log_data, default=str)


def setup_logging() -> None:
    """
    Configure structured JSON logging for the application.

    Sets up:
    - Root logger with JSON formatting
    - Console handler for stdout
    - Log level from environment (default: INFO)
    """
    # Determine log level from settings
    log_level_str = getattr(settings, "LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(StructuredJSONFormatter())

    root_logger.addHandler(console_handler)

    # Log startup
    root_logger.info("Structured logging initialized", extra={
        "context": {
            "log_level": log_level_str,
            "format": "json",
        }
    })


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the specified module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance configured for structured logging

    Example:
        logger = get_logger(__name__)
        logger.info("Processing submission", extra={
            "context": {"submission_id": "..."}
        })
    """
    return logging.getLogger(name)


class LogContext:
    """
    Context manager for adding contextual metadata to all logs within a scope.

    Example:
        with LogContext(submission_id=sub_id, participant_id=part_id):
            logger.info("Processing submission")  # Includes both IDs
            service.process()  # All logs inside include context
    """

    def __init__(self, **context):
        """
        Initialize log context.

        Args:
            **context: Key-value pairs to add to log context
        """
        self.context = context
        self.old_factory = None

    def __enter__(self):
        """Enter context and inject metadata into log records."""
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            # Add or update context
            if hasattr(record, "context"):
                record.context.update(self.context)
            else:
                record.context = self.context.copy()
            return record

        self.old_factory = old_factory
        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and restore original log record factory."""
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


def log_performance(logger: logging.Logger, operation: str, duration_ms: float, **context):
    """
    Log performance metrics for an operation.

    Args:
        logger: Logger instance
        operation: Operation name (e.g., "submission_processing", "transcription")
        duration_ms: Duration in milliseconds
        **context: Additional context to include
    """
    logger.info(f"Performance: {operation}", extra={
        "duration_ms": duration_ms,
        "context": {
            "operation": operation,
            **context
        }
    })


def log_error(logger: logging.Logger, error: Exception, message: str, **context):
    """
    Log an error with full context and stack trace.

    Args:
        logger: Logger instance
        error: Exception that occurred
        message: Human-readable error message
        **context: Additional context to include
    """
    logger.error(message, exc_info=error, extra={
        "context": {
            "error_type": type(error).__name__,
            "error_message": str(error),
            **context
        }
    })


def log_info(logger: logging.Logger, message: str, **context):
    """
    Log an info message with context.

    Args:
        logger: Logger instance
        message: Info message
        **context: Additional context to include
    """
    logger.info(message, extra={"context": context})


def log_warning(logger: logging.Logger, message: str, **context):
    """
    Log a warning with context.

    Args:
        logger: Logger instance
        message: Warning message
        **context: Additional context to include
    """
    logger.warning(message, extra={"context": context})


def log_audit(logger: logging.Logger, action: str, **context):
    """
    Log an audit event (for tracking important state changes).

    Args:
        logger: Logger instance
        action: Action being audited (e.g., "submission_created", "summary_approved")
        **context: Context including actor, target, timestamp
    """
    logger.info(f"Audit: {action}", extra={
        "context": {
            "action": action,
            "audit": True,
            **context
        }
    })


# Request ID tracking for distributed tracing
_request_id_context: Optional[str] = None


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    Set the request ID for the current request context.

    Args:
        request_id: Optional request ID. If None, generates a new UUID.

    Returns:
        The request ID that was set
    """
    global _request_id_context
    _request_id_context = request_id or str(uuid4())
    return _request_id_context


def get_request_id() -> Optional[str]:
    """Get the current request ID."""
    return _request_id_context


def clear_request_id():
    """Clear the request ID context."""
    global _request_id_context
    _request_id_context = None


# Initialize logging on module import
# Call setup_logging() explicitly in main.py for better control
