"""
Unit tests for pytest fixtures.

Validates that all test fixtures are properly configured and work as expected.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from src.events.event_bus import EventBus


@pytest.mark.unit
async def test_db_session_fixture(db_session: AsyncSession):
    """Test that db_session fixture provides a working async session."""
    assert db_session is not None
    assert isinstance(db_session, AsyncSession)

    # Test that we can execute a simple query
    result = await db_session.execute("SELECT 1 as test_value")
    row = result.fetchone()
    assert row is not None
    assert row[0] == 1


@pytest.mark.unit
async def test_redis_client_fixture(redis_client: aioredis.Redis):
    """Test that redis_client fixture provides a working Redis client."""
    assert redis_client is not None

    # Test basic Redis operations
    await redis_client.set("test_key", "test_value")
    value = await redis_client.get("test_key")
    assert value == "test_value"

    # Test that database is clean at start (fixture flushes before test)
    keys = await redis_client.keys("*")
    assert len(keys) == 1  # Only our test key should exist


@pytest.mark.unit
async def test_event_bus_fixture(event_bus: EventBus):
    """Test that event_bus fixture provides a working event bus."""
    assert event_bus is not None
    assert isinstance(event_bus, EventBus)

    # Test event emission and subscription
    received_events = []

    async def test_handler(event_data: dict):
        received_events.append(event_data)

    event_bus.subscribe("test.event", test_handler)
    await event_bus.emit("test.event", {"message": "test"})

    # Give event time to propagate
    import asyncio
    await asyncio.sleep(0.1)

    assert len(received_events) == 1
    assert received_events[0]["message"] == "test"


@pytest.mark.unit
def test_discussion_factory(test_discussion):
    """Test that test_discussion factory creates valid discussion data."""
    discussion = test_discussion()

    assert "discussion_id" in discussion
    assert "community_id" in discussion
    assert discussion["mode"] == "HOST_DEFINED"
    assert discussion["total_rounds"] == 3
    assert discussion["status"] == "CREATED"

    # Test with overrides
    custom_discussion = test_discussion(
        community_id=999,
        total_rounds=5,
        status="ACTIVE"
    )
    assert custom_discussion["community_id"] == 999
    assert custom_discussion["total_rounds"] == 5
    assert custom_discussion["status"] == "ACTIVE"


@pytest.mark.unit
def test_round_factory(test_round):
    """Test that test_round factory creates valid round data."""
    round_data = test_round()

    assert "round_id" in round_data
    assert "discussion_id" in round_data
    assert round_data["round_num"] == 1
    assert round_data["status"] == "PENDING"
    assert "question_text" in round_data
    assert round_data["submission_window_duration_sec"] == 300

    # Test with overrides
    custom_round = test_round(
        round_num=3,
        question_text="Custom question?",
        status="ACTIVE"
    )
    assert custom_round["round_num"] == 3
    assert custom_round["question_text"] == "Custom question?"
    assert custom_round["status"] == "ACTIVE"


@pytest.mark.unit
def test_participant_factory(test_participant):
    """Test that test_participant factory creates valid participant data."""
    participant = test_participant()

    assert "participant_id" in participant
    assert "discussion_id" in participant
    assert "user_id" in participant
    assert participant["first_round"] == 1
    assert participant["last_round"] is None
    assert participant["dropout_reason"] is None

    # Test with overrides
    custom_participant = test_participant(
        first_round=2,
        last_round=5,
        dropout_reason="NO_SUBMISSION"
    )
    assert custom_participant["first_round"] == 2
    assert custom_participant["last_round"] == 5
    assert custom_participant["dropout_reason"] == "NO_SUBMISSION"


@pytest.mark.unit
def test_sample_text_fixtures(sample_submission_text, sample_summary_text):
    """Test that text fixtures provide valid sample text."""
    assert isinstance(sample_submission_text, str)
    assert len(sample_submission_text) > 0
    assert isinstance(sample_summary_text, str)
    assert len(sample_summary_text) > 0


@pytest.mark.unit
async def test_fixture_isolation(db_session: AsyncSession, redis_client: aioredis.Redis):
    """
    Test that fixtures provide proper test isolation.

    Each test should get a fresh session and clean Redis database.
    """
    # Set some data in Redis
    await redis_client.set("isolation_test", "value1")

    # Execute a simple query in database
    result = await db_session.execute("SELECT 1")
    assert result.fetchone() is not None

    # This test should not interfere with other tests
    # The fixtures ensure cleanup happens automatically


@pytest.mark.unit
async def test_fixture_isolation_second_test(redis_client: aioredis.Redis):
    """
    Second isolation test to verify Redis is cleaned between tests.

    This should run after test_fixture_isolation and should NOT see
    the 'isolation_test' key set in the previous test.
    """
    value = await redis_client.get("isolation_test")
    assert value is None  # Previous test's data should be cleaned up
