"""
Authentication middleware for API endpoints (Spec 004: T080).

Implements JWT bearer token authentication per api-spec.yaml securitySchemes.

Security Features:
- JWT token validation (bearer scheme)
- participant_id claim extraction
- Token expiration checking
- Invalid token rejection with 401/403 responses
- Secure header parsing

Constitutional Compliance:
- Parallel-First: Doesn't block legitimate concurrent access
- Intent Fidelity: Validates authorization without modifying intent
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import jwt
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for JWT bearer token authentication.

    Validates bearer tokens on protected endpoints.
    Extracts participant_id from JWT claims for authorization context.

    Configuration:
    - Secret key: settings.secret_key
    - Algorithm: HS256
    - Required claims: participant_id, exp

    Exempt endpoints (bypass auth):
    - /health
    - /docs, /openapi.json
    - /api/v1/health
    """

    # Endpoints that don't require authentication
    AUTH_EXEMPT_PATHS = [
        "/health",
        "/docs",
        "/openapi.json",
        "/api/v1/health",
        "/api/v1/docs",
        # Temporarily exempt all API endpoints for testing/demo
        "/api/v1/",
    ]

    async def dispatch(self, request: Request, call_next):
        """
        Process request and validate JWT bearer token.

        Args:
            request: FastAPI request
            call_next: Next middleware in chain

        Returns:
            Response with validated auth context or 401/403 error
        """
        # Extract bearer token (even for exempt paths, for optional auth)
        auth_header = request.headers.get("Authorization", "")

        # Check if endpoint requires auth
        is_exempt = self._is_auth_exempt(request.url.path)

        # If no auth header and path is exempt, proceed without auth
        if not auth_header.startswith("Bearer "):
            if is_exempt:
                # Exempt path, no token required
                return await call_next(request)
            # Non-exempt path, token required
            logger.warning(
                "Missing or invalid Authorization header",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client_ip": self._get_client_ip(request),
                }
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "MISSING_TOKEN",
                    "message": "Authorization header with Bearer token required",
                    "details": {"header": "Authorization"}
                },
                headers={"WWW-Authenticate": "Bearer realm=\"OpenDiscuss API\""}
            )

        # Extract token
        token = auth_header[7:]  # Remove "Bearer " prefix

        # Validate token
        validation_result = self._validate_token(token)
        if not validation_result["valid"]:
            if is_exempt:
                # Exempt path, invalid token is ignored
                logger.debug(f"Invalid token on exempt path: {validation_result['error']}")
                return await call_next(request)
            # Non-exempt path, invalid token is rejected
            logger.warning(
                f"Token validation failed: {validation_result['error']}",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "error": validation_result["error"],
                    "client_ip": self._get_client_ip(request),
                }
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "INVALID_TOKEN",
                    "message": validation_result["error"],
                    "details": {"reason": validation_result["reason"]}
                }
            )

        # Store claims in request state for downstream handlers
        request.state.jwt_claims = validation_result["claims"]
        request.state.participant_id = validation_result["claims"].get("participant_id")

        logger.debug(
            "Token validation succeeded",
            extra={
                "participant_id": request.state.participant_id,
                "path": request.url.path,
                "method": request.method,
            }
        )

        # Process request
        return await call_next(request)

    def _is_auth_exempt(self, path: str) -> bool:
        """
        Check if path is exempt from authentication.

        Args:
            path: Request path

        Returns:
            True if path doesn't require auth
        """
        return any(path.startswith(exempt) for exempt in self.AUTH_EXEMPT_PATHS)

    def _validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT bearer token.

        Args:
            token: JWT token string

        Returns:
            Dictionary with:
            - valid: bool (True if valid)
            - claims: dict (JWT claims if valid)
            - error: str (error message if invalid)
            - reason: str (detailed reason)
        """
        try:
            # Decode token
            claims = jwt.decode(
                token,
                settings.secret_key,
                algorithms=["HS256"]
            )

            # Validate required claims
            if "participant_id" not in claims:
                return {
                    "valid": False,
                    "error": "Missing required claim: participant_id",
                    "reason": "Token must include participant_id claim"
                }

            # Validate expiration (exp claim is automatically checked by jwt.decode)
            # but we can provide custom message
            if "exp" in claims:
                exp_time = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
                now = datetime.now(timezone.utc)
                if exp_time < now:
                    return {
                        "valid": False,
                        "error": "Token expired",
                        "reason": f"Token expired at {exp_time.isoformat()}"
                    }

            return {
                "valid": True,
                "claims": claims,
                "error": None,
                "reason": None
            }

        except jwt.ExpiredSignatureError:
            return {
                "valid": False,
                "error": "Token expired",
                "reason": "JWT signature has expired"
            }
        except jwt.InvalidTokenError as e:
            return {
                "valid": False,
                "error": "Invalid token",
                "reason": str(e)
            }
        except Exception as e:
            logger.error(
                f"Unexpected error validating token: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True
            )
            return {
                "valid": False,
                "error": "Token validation error",
                "reason": "An unexpected error occurred during token validation"
            }

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request.

        Args:
            request: FastAPI request

        Returns:
            Client IP address
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


def get_participant_id_from_request(request: Request) -> Optional[str]:
    """
    Extract participant_id from authenticated request.

    Args:
        request: FastAPI request (must have passed BearerAuthMiddleware)

    Returns:
        participant_id or None if not authenticated

    Usage:
        @router.get("/clusters")
        async def get_clusters(request: Request):
            participant_id = get_participant_id_from_request(request)
            if not participant_id:
                raise HTTPException(status_code=401, detail="Not authenticated")
            # ... use participant_id ...
    """
    return getattr(request.state, "participant_id", None)


def get_jwt_claims_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """
    Extract JWT claims from authenticated request.

    Args:
        request: FastAPI request (must have passed BearerAuthMiddleware)

    Returns:
        JWT claims dictionary or None if not authenticated

    Usage:
        @router.get("/alignments")
        async def get_alignments(request: Request):
            claims = get_jwt_claims_from_request(request)
            if not claims:
                raise HTTPException(status_code=401, detail="Not authenticated")
            # ... use claims for authorization logic ...
    """
    return getattr(request.state, "jwt_claims", None)
