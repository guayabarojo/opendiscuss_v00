"""
Database connection and session management for OpenDiscuss.

Provides async SQLAlchemy engine, session factory, and FastAPI dependency
for database access throughout the application.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from .config import settings

# SQLAlchemy declarative base for all models
Base = declarative_base()

# Global async engine instance
engine: AsyncEngine | None = None

# Global async session factory
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get or create the async SQLAlchemy engine with optimized connection pooling.

    Pool Configuration (T086):
    - pool_size: 20-50 connections based on load testing (default: 20)
    - max_overflow: Additional connections beyond pool (default: 10)
    - pool_pre_ping: Health check before using connections
    - pool_recycle: Recycle connections after 3600s (1 hour)
    - pool_timeout: Wait up to 30s for available connection

    Returns:
        AsyncEngine: The async database engine with optimized pooling
    """
    global engine
    if engine is None:
        engine = create_async_engine(
            str(settings.database_url),
            echo=False,  # Set to True for SQL query logging in development
            pool_pre_ping=True,  # Verify connections before using (health check)
            pool_size=settings.db_pool_size,  # Core pool size (default: 20)
            max_overflow=settings.db_max_overflow,  # Overflow connections (default: 10)
            pool_recycle=3600,  # Recycle connections after 1 hour (prevent stale connections)
            pool_timeout=30,  # Wait up to 30 seconds for available connection
            future=True,
        )
    return engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get or create the async session factory.

    Returns:
        async_sessionmaker: Factory for creating async database sessions
    """
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        AsyncSessionLocal = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # Prevent lazy loading errors after commit
            autoflush=False,  # Manual control over flush timing
            autocommit=False,  # Explicit transaction management
        )
    return AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session management.

    Provides an async context manager that yields a database session
    and ensures proper cleanup (commit on success, rollback on error).

    Usage:
        @router.get("/example")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            # Use db session here
            pass

    Yields:
        AsyncSession: Database session for request handling
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database connection on application startup.

    Creates the async engine and session factory. Does NOT create tables
    (use Alembic migrations for schema management).
    """
    get_engine()
    get_session_factory()


async def close_db() -> None:
    """
    Close database connection on application shutdown.

    Disposes of the async engine and releases all connections.
    """
    global engine, AsyncSessionLocal

    if engine is not None:
        await engine.dispose()
        engine = None

    AsyncSessionLocal = None
