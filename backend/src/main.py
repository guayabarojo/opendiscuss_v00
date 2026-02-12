"""
FastAPI application factory for OpenDiscuss.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.services.timer_service import timer_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup: Initialize database and Redis
    from src.database import init_db, close_db
    from src.cache import get_redis_client, close_redis_client
    from src.events.event_bus import get_event_bus, close_event_bus
    from src.services.event_service import get_clustering_event_service, close_clustering_event_service

    await init_db()
    await get_redis_client()  # Initialize Redis connection

    # Initialize event bus and register handlers
    event_bus = await get_event_bus()

    # Initialize clustering event service (Spec 4)
    clustering_event_service = await get_clustering_event_service()
    await clustering_event_service.register_handlers()

    await timer_service.start()

    yield

    # Shutdown: Close connections
    await timer_service.stop()
    await close_clustering_event_service()
    await close_event_bus()
    await close_redis_client()
    await close_db()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    # Enhanced OpenAPI documentation (T083)
    app = FastAPI(
        title="OpenDiscuss Discussion Protocol API",
        version="1.0.0",
        description="""
        ## OpenDiscuss Discussion Protocol API

        Parallel, non-reactive discussion protocol for communities.

        ### Specification Coverage
        - **Spec 001**: Discussion Protocol (Coordination)
        - **Spec 002**: Input Collection Protocol (Text & Voice Submissions)
        - **Spec 003**: Micro-Summarization & Approval
        - **Spec 004**: Clustering & Sankey Visualization
        - **Spec 006**: Question Progression

        ### Key Features
        - **Parallel-First Architecture**: Non-reactive input collection
        - **Synchronous Deliberation**: Time-bounded submission windows
        - **Intent Fidelity**: LLM summarization with participant approval
        - **Temporal Transparency**: Stable participant tracking across rounds
        - **Ephemeral Raw Data**: Text retained only during summarization

        ### Constitutional Principles
        All endpoints comply with constitutional principles defined in
        `.specify/memory/constitution.md`:
        - Independent, non-reactive participation
        - Explicit approval gates for all AI-generated content
        - Stable identity tracking for movement analysis
        - Ephemeral raw data retention

        ### Getting Started
        See `/docs` for interactive API documentation and `/api/v1/health` for status.

        ### Rate Limiting
        - Per-participant submission limits: 3 per round (configurable)
        - API rate limit: 100 requests/minute per IP (configurable)

        ### Authentication
        Most endpoints require JWT bearer token with `participant_id` claim.
        """,
        contact={
            "name": "OpenDiscuss Protocol Suite",
            "url": "https://github.com/opendiscuss",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        lifespan=lifespan,
        # Enhanced response documentation (T083)
        responses={
            400: {
                "description": "Bad Request - Invalid input",
                "content": {
                    "application/json": {
                        "example": {
                            "error": "VALIDATION_FAILED",
                            "message": "Submission text exceeds maximum length",
                            "details": {"max_length": 5000, "actual_length": 5234}
                        }
                    }
                }
            },
            403: {
                "description": "Forbidden - Rate limit exceeded",
                "content": {
                    "application/json": {
                        "example": {
                            "error": "RATE_LIMIT_EXCEEDED",
                            "message": "You have reached the maximum of 3 submissions for this round",
                            "details": {"submissions_count": 3, "max_allowed": 3}
                        }
                    }
                }
            },
            422: {
                "description": "Unprocessable Entity - Business logic violation",
                "content": {
                    "application/json": {
                        "example": {
                            "error": "OUTSIDE_WINDOW",
                            "message": "Submission window has not opened yet",
                            "details": {
                                "window_start": "2026-01-29T14:00:00Z",
                                "current_time": "2026-01-29T13:59:00Z",
                                "status": "BEFORE_WINDOW"
                            }
                        }
                    }
                }
            },
            429: {
                "description": "Too Many Requests - IP rate limit exceeded",
                "content": {
                    "application/json": {
                        "example": {
                            "error": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please try again later.",
                            "retry_after_seconds": 30
                        }
                    }
                }
            },
            500: {
                "description": "Internal Server Error",
                "content": {
                    "application/json": {
                        "example": {
                            "error": "INTERNAL_ERROR",
                            "message": "An unexpected error occurred"
                        }
                    }
                }
            }
        }
    )

    # Configure middleware stack (T018)
    # Order matters: outermost to innermost
    # 1. Error handling (catches all exceptions)
    # 2. Request logging (logs all requests/responses)
    # 3. Structured logging context
    # 4. CORS (must be after error handlers)
    # 5. Security (rate limiting, headers)

    # Error handling middleware (T018)
    from src.middleware.middleware import (
        ErrorHandlingMiddleware,
        RequestLoggingMiddleware,
        StructuredLoggingMiddleware,
    )
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(StructuredLoggingMiddleware)

    # CORS middleware (T086: Security hardening, T018: Extensible for clustering/alignment)
    # Temporarily allow all origins for debugging
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins temporarily
        allow_credentials=False,  # Must be False when origins is "*"
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
        max_age=600,  # Cache preflight for 10 minutes
    )

    # Security middleware (T086: Rate limiting and security headers)
    from src.middleware.security import SecurityMiddleware
    app.add_middleware(SecurityMiddleware)

    # Authentication middleware (T080: JWT bearer token validation per api-spec.yaml securitySchemes)
    from src.middleware.auth import BearerAuthMiddleware
    app.add_middleware(BearerAuthMiddleware)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc)}
        )

    # Health endpoint
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "input-collection"}

    # Register API routes (T017)
    from src.api.routes import voice, windows
    from src.api.websocket import timer
    from src.summarization.api import summary_router

    # Spec 001-002: Input Collection
    app.include_router(voice.router, prefix="/api/v1")
    app.include_router(windows.router, prefix="/api/v1")
    app.include_router(timer.router)

    # Spec 003: Micro-Summarization & Approval
    app.include_router(summary_router, prefix="/api/v1")

    # Spec 001: Discussion Protocol - Discussion Management
    try:
        from src.api.discussion_routes import router as discussion_router
        app.include_router(discussion_router, prefix="/api/v1", tags=["discussions"])
    except ImportError:
        pass

    # Spec 001: Discussion Protocol - Round Management
    try:
        from src.api.round_routes import router as round_router
        app.include_router(round_router, prefix="/api/v1", tags=["rounds"])
    except ImportError:
        pass

    # Spec 002: Submission Management
    try:
        from src.api.submission_routes import router as submission_router
        app.include_router(submission_router, prefix="/api/v1", tags=["submissions"])
    except ImportError:
        pass

    # Spec 004: Clustering & Alignment (T017: Add routers for later implementation)
    # Clustering router - implements T029-T033 (US1)
    try:
        from src.api.routes.clustering import router as clustering_router
        app.include_router(clustering_router, prefix="/api/v1", tags=["clustering"])
    except ImportError:
        # Will be implemented in T029-T033
        pass

    # Alignment router - implements T055-T058 (US4)
    try:
        from src.api.routes.alignment import router as alignment_router
        app.include_router(alignment_router, prefix="/api/v1", tags=["alignment"])
    except ImportError:
        # Will be implemented in T055-T058
        pass

    # Spec 005: Sankey Construction (T015: Sankey diagram API)
    try:
        from src.api.routes.sankey import router as sankey_router
        app.include_router(sankey_router, prefix="/api/v1", tags=["sankey"])
    except ImportError:
        # Routes exist but service implementations will be added in Phase 3 (US1)
        pass

    # Spec 005: Discussion Reports (US5: Report generation API)
    try:
        from src.api.routes.report import router as report_router
        app.include_router(report_router, prefix="/api/v1", tags=["reports"])
    except ImportError:
        # Will be implemented in US5
        pass

    # Participant Data API (for debugging and transparency)
    try:
        from src.api.routes.participant_data import router as participant_data_router
        app.include_router(participant_data_router, prefix="/api/v1", tags=["participant-data"])
    except ImportError:
        pass

    return app


# Create app instance
app = create_app()
