"""
API documentation configuration for OpenDiscuss Discussion Protocol.

Configures OpenAPI/Swagger documentation with contract schemas from
specs/001-discussion-protocol/contracts/discussion-api.yaml.

Task: T090 - API documentation generator
"""

from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def load_contract_schemas() -> dict[str, Any]:
    """
    Load API contract schemas from discussion-api.yaml.

    Returns:
        dict: Contract schemas including components and paths
    """
    contract_path = Path(__file__).parent.parent.parent / "specs" / "001-discussion-protocol" / "contracts" / "discussion-api.yaml"

    if not contract_path.exists():
        # Fallback if running from different directory structure
        contract_path = Path(__file__).parent.parent.parent.parent / "specs" / "001-discussion-protocol" / "contracts" / "discussion-api.yaml"

    if not contract_path.exists():
        print(f"Warning: Contract file not found at {contract_path}")
        return {}

    with open(contract_path, "r") as f:
        contract = yaml.safe_load(f)

    return contract


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    """
    Generate custom OpenAPI schema with contract schemas.

    Merges FastAPI-generated schema with contract definitions from
    discussion-api.yaml.

    Args:
        app: FastAPI application instance

    Returns:
        dict: Complete OpenAPI schema
    """
    if app.openapi_schema:
        return app.openapi_schema

    # Generate base OpenAPI schema from FastAPI
    openapi_schema = get_openapi(
        title="OpenDiscuss Discussion Protocol API",
        version="1.0.0",
        description="""
# OpenDiscuss Discussion Protocol

System Spine for OpenDiscuss - Orchestrates multi-round, time-boxed discussions with parallel input collection.

## Constitutional Principles

This API implements the OpenDiscuss Constitutional Principles v1.0.0:

1. **Parallel-First Architecture**: All participant input collected simultaneously
2. **Intent Fidelity**: 100% approval required before aggregation
3. **Semantic Accuracy**: Preserve minority views, no forced merging
4. **Temporal Transparency**: Flows represent actual participant movement
5. **Community-Bounded**: All discussions occur within communities
6. **Synchronous Deliberation**: Time-boxed rounds (3-6 min submission windows)
7. **Representation Not Adjudication**: No voting, ranking, or forced convergence

## Key Features

- **Multi-Round Discussions**: Support for 3-5 round discussions
- **Real-Time Coordination**: Sub-protocol coordination via event bus
- **Sankey Visualization**: Temporal representation of collective thinking
- **Constitutional Compliance**: All endpoints validate constitutional invariants

## Architecture

- **Backend**: FastAPI (Python 3.11+), SQLAlchemy, PostgreSQL
- **Caching**: Redis for timing coordination
- **Events**: Async event bus for sub-protocol handoffs

## Quick Start

1. Create a discussion: `POST /api/v1/discussions`
2. Start the discussion: `POST /api/v1/discussions/{id}/start`
3. Monitor round status: `GET /api/v1/rounds/{id}/status`
4. Advance rounds: `POST /api/v1/discussions/{id}/advance`
5. View final report: `GET /api/v1/discussions/{id}/report`

For detailed usage examples, see `/backend/docs/` directory.
        """,
        routes=app.routes,
        tags=[
            {
                "name": "discussions",
                "description": "Discussion lifecycle operations (create, start, advance, terminate, report)",
            },
            {
                "name": "rounds",
                "description": "Round state and timing queries for countdown timers",
            },
            {
                "name": "participants",
                "description": "Participant registration and dropout tracking",
            },
            {
                "name": "submissions",
                "description": "Submission handling with rate limiting (US3)",
            },
            {
                "name": "health",
                "description": "Health check and service status endpoints",
            },
        ],
    )

    # Load contract schemas
    contract = load_contract_schemas()

    # Merge contract components if available
    if contract and "components" in contract:
        # Merge schemas
        if "schemas" in contract["components"]:
            if "components" not in openapi_schema:
                openapi_schema["components"] = {}
            if "schemas" not in openapi_schema["components"]:
                openapi_schema["components"]["schemas"] = {}

            # Add contract schemas (discussion-api.yaml definitions)
            openapi_schema["components"]["schemas"].update(
                contract["components"]["schemas"]
            )

        # Merge responses
        if "responses" in contract["components"]:
            if "responses" not in openapi_schema["components"]:
                openapi_schema["components"]["responses"] = {}

            openapi_schema["components"]["responses"].update(
                contract["components"]["responses"]
            )

        # Merge parameters
        if "parameters" in contract["components"]:
            if "parameters" not in openapi_schema["components"]:
                openapi_schema["components"]["parameters"] = {}

            openapi_schema["components"]["parameters"].update(
                contract["components"]["parameters"]
            )

    # Add security schemes
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}

    openapi_schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT bearer token authentication",
    }

    # Add security requirement
    openapi_schema["security"] = [{"BearerAuth": []}]

    # Add servers
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Local development server",
        },
        {
            "url": "http://localhost:8000/api/v1",
            "description": "Local development API v1",
        },
        {
            "url": "https://api.opendiscuss.example/v1",
            "description": "Production API (example)",
        },
    ]

    # Add external documentation
    openapi_schema["externalDocs"] = {
        "description": "OpenDiscuss Constitution",
        "url": "https://github.com/opendiscuss/opendiscuss/blob/main/.specify/memory/constitution.md",
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def configure_documentation(app: FastAPI) -> None:
    """
    Configure API documentation for FastAPI application.

    Sets up:
    - Swagger UI at /docs
    - ReDoc at /redoc
    - Custom OpenAPI schema with contract definitions

    Args:
        app: FastAPI application instance

    Usage:
        from src.docs import configure_documentation
        configure_documentation(app)
    """
    # Replace default OpenAPI schema generator
    app.openapi = lambda: custom_openapi(app)

    print("API documentation configured:")
    print("  - Swagger UI: http://localhost:8000/docs")
    print("  - ReDoc: http://localhost:8000/redoc")
    print("  - OpenAPI JSON: http://localhost:8000/openapi.json")
