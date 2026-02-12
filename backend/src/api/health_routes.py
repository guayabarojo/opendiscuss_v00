"""
Health check endpoints for OpenDiscuss Discussion Protocol.

Provides Kubernetes-compatible liveness and readiness probes:
- GET /health: Basic liveness check (returns 200 if app running)
- GET /health/ready: Readiness check (validates database, Redis, event bus)

Follows best practices:
- Non-blocking with 5-second timeout
- Includes version and build info
- Structured response format
"""

import asyncio
import time
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.config import settings
from src.database import get_engine
from src.events.event_bus import get_event_bus
from src.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])

# Version info (should be set at build time)
SERVICE_VERSION = "1.0.0"
BUILD_TIMESTAMP = None  # Set by CI/CD or at startup


# ============================================================================
# Response Models
# ============================================================================


class HealthStatus(BaseModel):
    """Basic health status response."""

    status: str
    service: str
    version: str
    timestamp: float


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    status: str
    latency_ms: float = 0.0
    error: str = None


class ReadinessStatus(BaseModel):
    """Detailed readiness check response."""

    status: str
    service: str
    version: str
    timestamp: float
    checks: Dict[str, ComponentHealth]


# ============================================================================
# Health Check Functions
# ============================================================================


async def check_database_health(timeout: float = 5.0) -> ComponentHealth:
    """
    Check database connectivity.

    Args:
        timeout: Maximum time to wait for response (seconds)

    Returns:
        ComponentHealth with status and latency
    """
    start_time = time.time()

    try:
        # Get engine and execute simple query
        engine = get_engine()

        # Use asyncio.timeout to enforce timeout (Python 3.11+)
        async with asyncio.timeout(timeout):
            async with engine.connect() as conn:
                # Simple ping query
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
                latency_ms = (time.time() - start_time) * 1000

                return ComponentHealth(
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                )

    except asyncio.TimeoutError:
        latency_ms = timeout * 1000
        logger.error(
            "Database health check timed out",
            extra={"timeout_ms": latency_ms},
        )
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=f"Connection timeout after {timeout}s",
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(
            "Database health check failed",
            extra={"error": str(e), "latency_ms": latency_ms},
            exc_info=True,
        )
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e),
        )


async def check_redis_health(timeout: float = 5.0) -> ComponentHealth:
    """
    Check Redis connectivity via event bus.

    Args:
        timeout: Maximum time to wait for response (seconds)

    Returns:
        ComponentHealth with status and latency
    """
    start_time = time.time()

    try:
        # Get event bus and check health
        event_bus = await get_event_bus()

        # Use asyncio.wait_for to enforce timeout
        async with asyncio.timeout(timeout):
            is_healthy = await event_bus.health_check()
            latency_ms = (time.time() - start_time) * 1000

            if is_healthy:
                return ComponentHealth(
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                )
            else:
                return ComponentHealth(
                    status="unhealthy",
                    latency_ms=round(latency_ms, 2),
                    error="Redis ping failed",
                )

    except asyncio.TimeoutError:
        latency_ms = timeout * 1000
        logger.error(
            "Redis health check timed out",
            extra={"timeout_ms": latency_ms},
        )
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=f"Connection timeout after {timeout}s",
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(
            "Redis health check failed",
            extra={"error": str(e), "latency_ms": latency_ms},
            exc_info=True,
        )
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e),
        )


async def check_event_bus_health(timeout: float = 5.0) -> ComponentHealth:
    """
    Check event bus connectivity and subscription status.

    Args:
        timeout: Maximum time to wait for response (seconds)

    Returns:
        ComponentHealth with status and latency
    """
    start_time = time.time()

    try:
        # Get event bus
        event_bus = await get_event_bus()

        # Use asyncio.wait_for to enforce timeout
        async with asyncio.timeout(timeout):
            is_connected = event_bus.is_connected()
            latency_ms = (time.time() - start_time) * 1000

            if is_connected:
                return ComponentHealth(
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                )
            else:
                return ComponentHealth(
                    status="unhealthy",
                    latency_ms=round(latency_ms, 2),
                    error="Event bus not connected",
                )

    except asyncio.TimeoutError:
        latency_ms = timeout * 1000
        logger.error(
            "Event bus health check timed out",
            extra={"timeout_ms": latency_ms},
        )
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=f"Connection timeout after {timeout}s",
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(
            "Event bus health check failed",
            extra={"error": str(e), "latency_ms": latency_ms},
            exc_info=True,
        )
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e),
        )


# ============================================================================
# Health Check Endpoints
# ============================================================================


@router.get("/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
    Basic liveness probe.

    Returns 200 if the application is running. Does not check dependencies.
    Use this for Kubernetes liveness probes.

    Returns:
        HealthStatus with basic service info
    """
    return HealthStatus(
        status="healthy",
        service="opendiscuss-discussion-protocol",
        version=SERVICE_VERSION,
        timestamp=time.time(),
    )


@router.get("/health/ready", response_model=ReadinessStatus)
async def readiness_check() -> ReadinessStatus:
    """
    Readiness probe with dependency checks.

    Validates connectivity to:
    - PostgreSQL database
    - Redis (via event bus)
    - Event bus (pub/sub)

    Returns 200 if all dependencies are healthy, 503 otherwise.
    Use this for Kubernetes readiness probes.

    Returns:
        ReadinessStatus with detailed component health

    Raises:
        HTTPException: 503 if any component is unhealthy
    """
    logger.debug("Starting readiness check")

    # Check all components with 5-second timeout
    check_timeout = 5.0

    # Run checks in parallel
    database_check, redis_check, event_bus_check = await asyncio.gather(
        check_database_health(timeout=check_timeout),
        check_redis_health(timeout=check_timeout),
        check_event_bus_health(timeout=check_timeout),
        return_exceptions=True,
    )

    # Handle exceptions from gather
    checks: Dict[str, ComponentHealth] = {}

    if isinstance(database_check, Exception):
        checks["database"] = ComponentHealth(
            status="unhealthy",
            error=str(database_check),
        )
    else:
        checks["database"] = database_check

    if isinstance(redis_check, Exception):
        checks["redis"] = ComponentHealth(
            status="unhealthy",
            error=str(redis_check),
        )
    else:
        checks["redis"] = redis_check

    if isinstance(event_bus_check, Exception):
        checks["event_bus"] = ComponentHealth(
            status="unhealthy",
            error=str(event_bus_check),
        )
    else:
        checks["event_bus"] = event_bus_check

    # Determine overall status
    all_healthy = all(check.status == "healthy" for check in checks.values())
    overall_status = "ready" if all_healthy else "not_ready"

    response = ReadinessStatus(
        status=overall_status,
        service="opendiscuss-discussion-protocol",
        version=SERVICE_VERSION,
        timestamp=time.time(),
        checks=checks,
    )

    # Log readiness status
    if all_healthy:
        logger.info(
            "Readiness check passed",
            extra={
                "database_latency_ms": checks["database"].latency_ms,
                "redis_latency_ms": checks["redis"].latency_ms,
                "event_bus_latency_ms": checks["event_bus"].latency_ms,
            },
        )
    else:
        unhealthy_components = [
            name for name, check in checks.items() if check.status != "healthy"
        ]
        logger.warning(
            "Readiness check failed",
            extra={
                "unhealthy_components": unhealthy_components,
            },
        )

    # Return 503 if not ready
    if not all_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump(),
        )

    return response


@router.get("/health/startup", response_model=HealthStatus)
async def startup_check() -> HealthStatus:
    """
    Startup probe for Kubernetes.

    Similar to liveness but used during initial startup phase.
    Can be more lenient with timeouts than readiness.

    Returns:
        HealthStatus with basic service info
    """
    return HealthStatus(
        status="healthy",
        service="opendiscuss-discussion-protocol",
        version=SERVICE_VERSION,
        timestamp=time.time(),
    )
