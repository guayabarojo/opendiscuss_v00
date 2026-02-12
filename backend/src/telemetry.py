"""
OpenTelemetry instrumentation for OpenDiscuss Discussion Protocol.

Provides distributed tracing and metrics for observability:
- Trace spans for state transitions
- Event emission tracking
- Sub-protocol handoff instrumentation
- Custom metrics (round processing time, participant counts)
- Configurable exporters for monitoring backends
"""

from contextvars import ContextVar
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)

# Context variable for storing current span
current_span_ctx: ContextVar[Optional[trace.Span]] = ContextVar("current_span", default=None)


# ============================================================================
# Initialization
# ============================================================================


def init_telemetry(
    service_name: str = "opendiscuss-backend",
    service_version: str = "1.0.0",
    otlp_endpoint: Optional[str] = None,
    enable_console_export: bool = False,
) -> None:
    """
    Initialize OpenTelemetry tracing and metrics.

    Args:
        service_name: Name of the service for resource identification
        service_version: Version of the service
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
        enable_console_export: Enable console exporter for debugging
    """
    if not settings.enable_telemetry:
        logger.info("OpenTelemetry instrumentation disabled by configuration")
        return

    # Create resource for service identification
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "service.environment": settings.environment,
        }
    )

    # Initialize tracing
    _init_tracing(resource, otlp_endpoint, enable_console_export)

    # Initialize metrics
    _init_metrics(resource, otlp_endpoint)

    logger.info(
        "OpenTelemetry instrumentation initialized",
        extra={
            "service_name": service_name,
            "service_version": service_version,
            "otlp_endpoint": otlp_endpoint,
            "environment": settings.environment,
        },
    )


def _init_tracing(
    resource: Resource,
    otlp_endpoint: Optional[str],
    enable_console: bool,
) -> None:
    """Initialize distributed tracing."""
    # Create tracer provider
    tracer_provider = TracerProvider(resource=resource)

    # Add OTLP exporter if endpoint provided
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info(f"OTLP trace exporter configured: {otlp_endpoint}")

    # Add console exporter for debugging
    if enable_console:
        console_exporter = ConsoleSpanExporter()
        tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("Console trace exporter enabled")

    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)


def _init_metrics(resource: Resource, otlp_endpoint: Optional[str]) -> None:
    """Initialize metrics collection."""
    if otlp_endpoint:
        # Create OTLP metric exporter
        metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
        metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60000)

        # Create meter provider
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        logger.info(f"OTLP metric exporter configured: {otlp_endpoint}")


# ============================================================================
# Tracer and Meter
# ============================================================================


def get_tracer(name: str = "opendiscuss") -> trace.Tracer:
    """
    Get a tracer for creating spans.

    Args:
        name: Tracer name (typically module or component name)

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


def get_meter(name: str = "opendiscuss") -> metrics.Meter:
    """
    Get a meter for creating metrics.

    Args:
        name: Meter name (typically module or component name)

    Returns:
        Meter instance
    """
    return metrics.get_meter(name)


# ============================================================================
# Custom Metrics
# ============================================================================


class DiscussionMetrics:
    """
    Custom metrics for discussion protocol operations.

    Tracks:
    - Round processing time (submission close to round complete)
    - Participant counts per discussion
    - State transition counts
    - Event emission counts
    - Sub-protocol handoff latency
    """

    def __init__(self) -> None:
        """Initialize discussion metrics."""
        self.meter = get_meter("opendiscuss.discussion")

        # Counters
        self.discussion_created = self.meter.create_counter(
            "discussion.created",
            description="Number of discussions created",
            unit="1",
        )

        self.round_completed = self.meter.create_counter(
            "round.completed",
            description="Number of rounds completed",
            unit="1",
        )

        self.state_transition = self.meter.create_counter(
            "state.transition",
            description="Number of state transitions",
            unit="1",
        )

        self.event_emitted = self.meter.create_counter(
            "event.emitted",
            description="Number of events emitted",
            unit="1",
        )

        self.event_handler_error = self.meter.create_counter(
            "event.handler.error",
            description="Number of event handler errors",
            unit="1",
        )

        # Histograms
        self.round_processing_time = self.meter.create_histogram(
            "round.processing_time",
            description="Round processing time from submission close to round complete",
            unit="ms",
        )

        self.submission_window_duration = self.meter.create_histogram(
            "submission.window_duration",
            description="Actual submission window duration",
            unit="ms",
        )

        self.subprotocol_handoff_latency = self.meter.create_histogram(
            "subprotocol.handoff_latency",
            description="Latency between sub-protocol transitions",
            unit="ms",
        )

        # Gauges (UpDownCounter)
        self.active_discussions = self.meter.create_up_down_counter(
            "discussion.active",
            description="Number of active discussions",
            unit="1",
        )

        self.participants_per_round = self.meter.create_histogram(
            "round.participants",
            description="Number of participants per round",
            unit="1",
        )

    def record_discussion_created(self, community_id: str, total_rounds: int) -> None:
        """Record discussion creation."""
        self.discussion_created.add(
            1,
            attributes={
                "community_id": community_id,
                "total_rounds": str(total_rounds),
            },
        )
        self.active_discussions.add(1, attributes={"community_id": community_id})

    def record_discussion_completed(self, community_id: str) -> None:
        """Record discussion completion."""
        self.active_discussions.add(-1, attributes={"community_id": community_id})

    def record_round_completed(self, discussion_id: str, round_num: int) -> None:
        """Record round completion."""
        self.round_completed.add(
            1,
            attributes={
                "discussion_id": discussion_id,
                "round_num": str(round_num),
            },
        )

    def record_state_transition(
        self,
        entity_type: str,
        from_state: str,
        to_state: str,
    ) -> None:
        """Record state transition."""
        self.state_transition.add(
            1,
            attributes={
                "entity_type": entity_type,
                "from_state": from_state,
                "to_state": to_state,
            },
        )

    def record_event_emitted(self, event_type: str) -> None:
        """Record event emission."""
        self.event_emitted.add(1, attributes={"event_type": event_type})

    def record_event_handler_error(self, event_type: str, error_type: str) -> None:
        """Record event handler error."""
        self.event_handler_error.add(
            1,
            attributes={
                "event_type": event_type,
                "error_type": error_type,
            },
        )

    def record_round_processing_time(
        self,
        discussion_id: str,
        round_num: int,
        duration_ms: float,
    ) -> None:
        """Record round processing time."""
        self.round_processing_time.record(
            duration_ms,
            attributes={
                "discussion_id": discussion_id,
                "round_num": str(round_num),
            },
        )

    def record_submission_window_duration(
        self,
        round_id: str,
        duration_ms: float,
    ) -> None:
        """Record submission window duration."""
        self.submission_window_duration.record(
            duration_ms,
            attributes={"round_id": round_id},
        )

    def record_subprotocol_handoff(
        self,
        from_protocol: str,
        to_protocol: str,
        latency_ms: float,
    ) -> None:
        """Record sub-protocol handoff latency."""
        self.subprotocol_handoff_latency.record(
            latency_ms,
            attributes={
                "from_protocol": from_protocol,
                "to_protocol": to_protocol,
            },
        )

    def record_participants_per_round(self, round_id: str, count: int) -> None:
        """Record participant count for a round."""
        self.participants_per_round.record(
            count,
            attributes={"round_id": round_id},
        )


# Global metrics instance
_metrics: Optional[DiscussionMetrics] = None


def get_metrics() -> DiscussionMetrics:
    """
    Get the global metrics instance.

    Returns:
        DiscussionMetrics instance
    """
    global _metrics
    if _metrics is None:
        _metrics = DiscussionMetrics()
    return _metrics


# ============================================================================
# Span Helpers
# ============================================================================


def create_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
) -> trace.Span:
    """
    Create a new span for tracing.

    Args:
        name: Span name (e.g., "round.transition", "event.emit")
        attributes: Optional span attributes
        kind: Span kind (INTERNAL, CLIENT, SERVER, etc.)

    Returns:
        Span instance (use as context manager)
    """
    tracer = get_tracer()
    span = tracer.start_span(name, kind=kind)

    if attributes:
        for key, value in attributes.items():
            # Convert UUID to string
            if isinstance(value, UUID):
                value = str(value)
            span.set_attribute(key, value)

    return span


def trace_state_transition(
    entity_type: str,
    entity_id: str,
    from_state: str,
    to_state: str,
) -> trace.Span:
    """
    Create a span for state transition tracing.

    Args:
        entity_type: Type of entity (Discussion, Round)
        entity_id: Entity identifier
        from_state: Current state
        to_state: Target state

    Returns:
        Span instance (use as context manager)
    """
    span = create_span(
        f"{entity_type.lower()}.state_transition",
        attributes={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "from_state": from_state,
            "to_state": to_state,
        },
    )

    # Record metric
    metrics = get_metrics()
    metrics.record_state_transition(entity_type, from_state, to_state)

    return span


def trace_event_emission(event_type: str, payload: Dict[str, Any]) -> trace.Span:
    """
    Create a span for event emission tracing.

    Args:
        event_type: Event type identifier
        payload: Event payload (limited attributes for span)

    Returns:
        Span instance (use as context manager)
    """
    # Extract key attributes from payload
    attributes = {
        "event_type": event_type,
    }

    # Add discussion_id and round_id if present
    if "discussion_id" in payload:
        attributes["discussion_id"] = str(payload["discussion_id"])
    if "round_id" in payload:
        attributes["round_id"] = str(payload["round_id"])

    span = create_span(
        "event.emit",
        attributes=attributes,
        kind=trace.SpanKind.PRODUCER,
    )

    # Record metric
    metrics = get_metrics()
    metrics.record_event_emitted(event_type)

    return span


def trace_subprotocol_handoff(
    from_protocol: str,
    to_protocol: str,
    round_id: str,
) -> trace.Span:
    """
    Create a span for sub-protocol handoff tracing.

    Args:
        from_protocol: Source sub-protocol name
        to_protocol: Target sub-protocol name
        round_id: Round identifier

    Returns:
        Span instance (use as context manager)
    """
    span = create_span(
        "subprotocol.handoff",
        attributes={
            "from_protocol": from_protocol,
            "to_protocol": to_protocol,
            "round_id": round_id,
        },
    )

    return span


def set_span_error(span: trace.Span, error: Exception) -> None:
    """
    Mark span as error with exception details.

    Args:
        span: Span to mark as error
        error: Exception that occurred
    """
    span.set_status(Status(StatusCode.ERROR, str(error)))
    span.record_exception(error)


# ============================================================================
# Context Manager for Round Processing
# ============================================================================


class RoundProcessingSpan:
    """
    Context manager for tracking round processing time.

    Automatically records processing time metrics when exiting context.
    """

    def __init__(self, discussion_id: UUID, round_id: UUID, round_num: int):
        """
        Initialize round processing span.

        Args:
            discussion_id: Discussion identifier
            round_id: Round identifier
            round_num: Round number
        """
        self.discussion_id = str(discussion_id)
        self.round_id = str(round_id)
        self.round_num = round_num
        self.start_time = datetime.now()
        self.span: Optional[trace.Span] = None

    def __enter__(self) -> "RoundProcessingSpan":
        """Enter context and start span."""
        self.span = create_span(
            "round.processing",
            attributes={
                "discussion_id": self.discussion_id,
                "round_id": self.round_id,
                "round_num": str(self.round_num),
            },
        )
        self.span.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context, record metrics, and end span."""
        # Calculate processing time
        end_time = datetime.now()
        duration_ms = (end_time - self.start_time).total_seconds() * 1000

        # Record metric
        metrics = get_metrics()
        metrics.record_round_processing_time(
            self.discussion_id,
            self.round_num,
            duration_ms,
        )

        # Set span attribute
        if self.span:
            self.span.set_attribute("processing_time_ms", duration_ms)

            # Mark error if exception occurred
            if exc_val:
                set_span_error(self.span, exc_val)

            self.span.__exit__(exc_type, exc_val, exc_tb)


# ============================================================================
# Instrumentation Decorators
# ============================================================================


def traced(
    name: Optional[str] = None,
    attributes: Optional[Callable[[Any, tuple, dict], Dict[str, Any]]] = None,
) -> Callable:
    """
    Decorator for automatic function tracing.

    Args:
        name: Optional span name (defaults to function name)
        attributes: Optional function to extract attributes from function args

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__name__}"

        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            span_attrs = attributes(func, args, kwargs) if attributes else {}
            with create_span(span_name, span_attrs):
                return await func(*args, **kwargs)

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            span_attrs = attributes(func, args, kwargs) if attributes else {}
            with create_span(span_name, span_attrs):
                return func(*args, **kwargs)

        # Preserve async/sync nature of function
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
