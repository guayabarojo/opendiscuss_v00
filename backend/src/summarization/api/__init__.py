"""
API routes for summary generation and approval for Spec 003
"""

from fastapi import APIRouter
from .summary_routes import router as summary_routes_router
from .correction_routes import router as correction_routes_router

# Combine routers
summary_router = APIRouter()
summary_router.include_router(summary_routes_router)
summary_router.include_router(correction_routes_router)

__all__ = ["summary_router"]
