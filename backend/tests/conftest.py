"""
Pytest fixtures for OpenDiscuss testing.

Provides shared fixtures for database sessions, Redis clients, event bus,
and test data factories. Ensures proper test isolation and cleanup.
"""

import asyncio
from typing import AsyncGenerator, Callable, Any
from datetime import datetime, timedelta
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text
import redis.asyncio as aioredis
from httpx import AsyncClient

from src.database import Base
from src.config import settings
from src.events.event_bus import EventBus
from src.main import app

# Import all models to ensure they're registered with Base.metadata
import src.models  # noqa: F401
# Import models to register them with SQLAlchemy Base
from src import models


# ============================================================================
# Test Database Configuration
# ============================================================================

# Use same database as dev but with different schema prefix
# This is a workaround for environments where test database creation is restricted
# In production test environments, use a separate database
TEST_DATABASE_URL = str(settings.database_url)  # Use same database for now
TEST_REDIS_URL = str(settings.redis_url).replace("/0", "/1")  # Use Redis DB 1 for tests


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an instance of the default event loop for the test session.

    This fixture ensures that async tests can run properly and that
    the event loop is closed after all tests complete.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create test database engine for the entire test session.

    Uses NullPool to avoid connection pool issues during testing.
    Does NOT drop/recreate tables - preserves existing schema including modality column.
    Uses truncate for cleanup instead (see db_session fixture).
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
        future=True,
    )

    # Ensure enum types exist (idempotent - won't fail if they already exist)
    async with engine.begin() as conn:
        # summarystatus: For Summary table (Spec 003)
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE summarystatus AS ENUM (
                  'pending_review', 'approved', 'rejected', 'rejected_final',
                  'disallowed_content', 'approval_timeout', 'superseded'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))

        # submissionsummarystatus: For Submission table
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE submissionsummarystatus AS ENUM (
                  'pending', 'approved', 'rejected', 'superseded', 'approval_timeout'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))

        # reasontag: For CorrectionSignal table (Spec 003)
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE reasontag AS ENUM (
                  'wrong_crux', 'too_vague', 'misrepresents_me',
                  'missed_constraint', 'missed_solution', 'other'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))

        # submissionmodality: For Submission table
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE submissionmodality AS ENUM ('text', 'voice');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))

        # Create tables if they don't exist (preserves existing schema)
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a fresh database session for each test function.

    Provides transaction isolation - each test gets a clean session
    that is rolled back after the test completes, ensuring test isolation.

    Usage:
        async def test_something(db_session: AsyncSession):
            # Use db_session for database operations
            result = await db_session.execute(...)
    """
    # Create async session factory
    async_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # Clean up all committed data before the test to ensure test isolation
    # This is necessary because some tests commit data and we want
    # each test to start with a clean database
    async with async_session_factory() as cleanup_session:
        try:
            from sqlalchemy import text
            # Get all table names and truncate them in reverse order to handle foreign keys
            for table in reversed(Base.metadata.sorted_tables):
                await cleanup_session.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
            await cleanup_session.commit()
        except Exception:
            # Ignore cleanup errors (tables might be empty)
            await cleanup_session.rollback()

    async with async_session_factory() as session:
        yield session
        # Rollback any uncommitted changes after test (if there are any)
        try:
            await session.rollback()
        except Exception:
            # Transaction may have already been committed/rolled back
            pass


# ============================================================================
# Redis Fixtures
# ============================================================================


@pytest_asyncio.fixture(scope="function")
async def redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    """
    Create Redis client for testing.

    Uses a separate Redis database (DB 1) to avoid conflicts with
    development data. Flushes the test database before and after each test.

    Usage:
        async def test_redis_operation(redis_client: aioredis.Redis):
            await redis_client.set("test_key", "test_value")
            value = await redis_client.get("test_key")
    """
    client = aioredis.from_url(
        TEST_REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )

    # Clear test database before test
    await client.flushdb()

    yield client

    # Clear test database after test
    await client.flushdb()
    await client.close()


# ============================================================================
# Event Bus Fixtures
# ============================================================================


@pytest_asyncio.fixture(scope="function")
async def event_bus(redis_client: aioredis.Redis) -> AsyncGenerator[EventBus, None]:
    """
    Create event bus instance for testing.

    Provides a fresh event bus with no subscribed handlers for each test.
    Automatically cleans up handlers and connections after test completes.

    Usage:
        async def test_event_emission(event_bus: EventBus):
            received_events = []

            async def handler(event):
                received_events.append(event)

            event_bus.subscribe("test.event", handler)
            await event_bus.emit("test.event", {"data": "test"})
    """
    bus = EventBus(redis_client=redis_client)

    yield bus

    # Cleanup: unsubscribe all handlers
    await bus.shutdown()


# ============================================================================
# HTTP Client Fixtures
# ============================================================================


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create async HTTP client for testing FastAPI endpoints.

    Provides an httpx AsyncClient configured to test the FastAPI app
    with proper database session injection.

    Usage:
        async def test_endpoint(async_client: AsyncClient):
            response = await async_client.get("/api/v1/endpoint")
            assert response.status_code == 200
    """
    # Override database dependency to use test session
    from src.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Clear overrides
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def async_session(db_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """
    Alias for db_session to match naming convention in tests.

    Some tests use async_session instead of db_session for clarity.
    """
    yield db_session


# ============================================================================
# Test Data Factory Fixtures
# ============================================================================


@pytest.fixture
def test_discussion() -> Callable[..., dict[str, Any]]:
    """
    Factory fixture for creating test Discussion data.

    Returns a callable that generates Discussion dictionaries with
    default or custom values. Does NOT save to database - use with
    db_session to persist.

    Usage:
        def test_something(test_discussion):
            discussion_data = test_discussion(
                community_id=123,
                total_rounds=3
            )
            # Use discussion_data in test
    """

    def _create_discussion(**overrides: Any) -> dict[str, Any]:
        """Create test discussion data with optional overrides."""
        default_data = {
            "discussion_id": str(uuid.uuid4()),
            "community_id": str(uuid.uuid4()),
            "mode": "HOST_DEFINED",
            "total_rounds": 3,
            "status": "CREATED",
            "host_user_id": str(uuid.uuid4()),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        default_data.update(overrides)
        return default_data

    return _create_discussion


@pytest.fixture
def test_round() -> Callable[..., dict[str, Any]]:
    """
    Factory fixture for creating test Round data.

    Returns a callable that generates Round dictionaries with
    default or custom values. Does NOT save to database - use with
    db_session to persist.

    Usage:
        def test_something(test_round):
            round_data = test_round(
                discussion_id="disc-123",
                round_num=1,
                question_text="What do you think?"
            )
    """

    def _create_round(**overrides: Any) -> dict[str, Any]:
        """Create test round data with optional overrides."""
        default_data = {
            "round_id": str(uuid.uuid4()),
            "discussion_id": str(uuid.uuid4()),
            "round_num": 1,
            "question_text": "What are your thoughts on this topic?",
            "status": "PENDING",
            "submission_window_start": None,
            "submission_window_end": None,
            "submission_window_duration_sec": 300,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        default_data.update(overrides)
        return default_data

    return _create_round


@pytest.fixture
def test_participant() -> Callable[..., dict[str, Any]]:
    """
    Factory fixture for creating test Participant data.

    Returns a callable that generates Participant dictionaries with
    default or custom values. Does NOT save to database - use with
    db_session to persist.

    Usage:
        def test_something(test_participant):
            participant_data = test_participant(
                discussion_id="disc-123",
                user_id="user-456"
            )
    """

    def _create_participant(**overrides: Any) -> dict[str, Any]:
        """Create test participant data with optional overrides."""
        default_data = {
            "participant_id": str(uuid.uuid4()),
            "discussion_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "first_round": 1,
            "last_round": None,
            "dropout_reason": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        default_data.update(overrides)
        return default_data

    return _create_participant


# ============================================================================
# Additional Helper Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def mock_api_key(monkeypatch):
    """
    Mock API keys for all tests.

    Prevents tests from failing due to missing API key configuration.
    Uses autouse=True to apply to all tests automatically.
    """
    monkeypatch.setattr(settings, "claude_api_key", "sk-ant-test-key-123")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-key-123")
    monkeypatch.setattr(settings, "openai_moderation_enabled", False)


@pytest.fixture
def freeze_time() -> Callable[[datetime], datetime]:
    """
    Fixture to help with time-dependent tests.

    Returns a callable that can be used to get consistent timestamps
    in tests, useful for testing timing windows and deadlines.

    Usage:
        def test_timing(freeze_time):
            now = freeze_time(datetime(2026, 1, 29, 12, 0, 0))
            # Use 'now' for consistent time in test
    """

    def _freeze_time(target_time: datetime | None = None) -> datetime:
        """Return a fixed datetime for testing."""
        return target_time if target_time else datetime.utcnow()

    return _freeze_time


@pytest.fixture
def sample_submission_text() -> str:
    """
    Fixture providing sample submission text for testing.

    Returns a realistic submission text that can be used in tests
    involving submissions, summaries, or text processing.
    """
    return (
        "I think we should focus on improving communication between teams. "
        "Regular standups and better documentation would help everyone stay aligned. "
        "We could also benefit from more cross-functional collaboration."
    )


@pytest.fixture
def sample_summary_text() -> str:
    """
    Fixture providing sample summary text for testing.

    Returns a realistic summary text that can be used in tests
    involving approved summaries or clustering.
    """
    return (
        "Focus on team communication improvements through regular standups, "
        "better documentation, and increased cross-functional collaboration."
    )


@pytest_asyncio.fixture(scope="function")
async def sample_discussion(db_session: AsyncSession):
    """
    Create and persist a sample Discussion object for testing.

    Returns a Discussion model object that has been added to the database.
    """
    from src.models import Discussion
    from src.models.protocol_state import DiscussionMode

    discussion = Discussion(
        discussion_id=uuid.uuid4(),
        community_id=uuid.uuid4(),
        host_user_id=uuid.uuid4(),
        mode=DiscussionMode.HOST_DEFINED,
        total_rounds=1
    )
    db_session.add(discussion)
    await db_session.commit()
    await db_session.refresh(discussion)
    return discussion


@pytest_asyncio.fixture(scope="function")
async def sample_round(db_session: AsyncSession, sample_discussion):
    """
    Create and persist a sample Round object for testing.

    Depends on sample_discussion fixture. Returns a Round model object
    that has been added to the database.
    """
    from src.models import Round

    round_obj = Round(
        round_id=uuid.uuid4(),
        discussion_id=sample_discussion.discussion_id,
        round_num=1,
        question_text="What are your thoughts on this topic?",
        submission_window_duration_sec=300,
    )
    db_session.add(round_obj)
    await db_session.commit()
    await db_session.refresh(round_obj)
    return round_obj


@pytest_asyncio.fixture(scope="function")
async def sample_participant(db_session: AsyncSession, sample_discussion):
    """
    Create and persist a sample Participant object for testing.

    Depends on sample_discussion fixture. Returns a Participant model object
    that has been added to the database.
    """
    from src.models import Participant

    participant = Participant(
        participant_id=uuid.uuid4(),
        discussion_id=sample_discussion.discussion_id,
        user_id=uuid.uuid4(),
        first_round=1,
    )
    db_session.add(participant)
    await db_session.commit()
    await db_session.refresh(participant)
    return participant


@pytest.fixture
def mock_llm_summary(mocker):
    """
    Mock the LLM summary generation function for safety filtering tests.

    Prevents actual OpenAI API calls during testing and returns a
    deterministic summary text for consistent test results.

    Usage:
        async def test_something(db_session, mock_llm_summary):
            # LLM calls will be mocked automatically
            service = SummarizationService(db_session)
            summary = await service.generate_summary(submission_id)
    """
    return mocker.patch(
        'src.summarization.services.summarization_service.generate_summary_llm',
        return_value="This is a test summary."
    )


@pytest.fixture
def mock_llm_generate(mocker):
    """
    Mock the LLM generation function for correction signal tests.

    Prevents actual OpenAI API calls during testing and returns a
    deterministic summary text for consistent test results.

    Usage:
        async def test_something(db_session, mock_llm_generate):
            # LLM calls will be mocked automatically
            service = SummarizationService(db_session)
            summary = await service.generate_summary(submission_id)
    """
    return mocker.patch(
        'src.llm.openai_client.generate_summary_llm',
        return_value="This is a regenerated summary based on correction feedback."
    )


# Aliases for commonly used fixtures
@pytest_asyncio.fixture(scope="function")
async def round_obj(sample_round):
    """Alias for sample_round for consistency with test naming."""
    return sample_round


@pytest_asyncio.fixture(scope="function")
async def participant(sample_participant):
    """Alias for sample_participant for consistency with test naming."""
    return sample_participant


# ============================================================================
# Marks and Configuration
# ============================================================================

# Custom pytest marks for organizing tests
pytest.register_assert_rewrite("tests")  # Enable better assertion introspection


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires services)"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "contract: mark test as contract test (sub-protocol integration)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (may take several seconds)"
    )
    config.addinivalue_line(
        "markers", "timing: mark test as timing-sensitive (requires precise timing)"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test (requires real services and --e2e flag)"
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to skip e2e tests unless --e2e flag is provided.

    E2E tests are expensive and require real external services (Claude API).
    They are skipped by default to avoid accidental API costs.
    """
    if not config.getoption("--e2e", default=False):
        skip_e2e = pytest.mark.skip(reason="need --e2e option to run e2e tests")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="run end-to-end tests (requires real services, incurs API costs)"
    )
