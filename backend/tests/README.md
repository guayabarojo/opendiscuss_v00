# OpenDiscuss Backend Tests

Quick reference guide for writing tests in the OpenDiscuss backend.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures (DB, Redis, Event Bus, Factories)
├── README.md               # This file
├── unit/                   # Fast, isolated unit tests
│   ├── test_fixtures.py    # Fixture validation tests
│   └── ...
├── integration/            # Tests requiring services (DB, Redis)
│   └── ...
└── contract/              # Sub-protocol integration tests
    └── ...
```

## Available Fixtures

### Infrastructure Fixtures

#### `db_session` (async)
Provides an async database session with automatic transaction rollback.

```python
async def test_database_operation(db_session: AsyncSession):
    # Use db_session for database operations
    result = await db_session.execute("SELECT 1")
    assert result.fetchone() is not None
```

#### `redis_client` (async)
Provides a Redis client with automatic database cleanup.

```python
async def test_redis_operation(redis_client: aioredis.Redis):
    await redis_client.set("key", "value")
    value = await redis_client.get("key")
    assert value == "value"
```

#### `event_bus` (async)
Provides an event bus instance for testing event-driven functionality.

```python
async def test_event_emission(event_bus: EventBus):
    received_events = []

    async def handler(event_data: dict):
        received_events.append(event_data)

    event_bus.subscribe("test.event", handler)
    await event_bus.emit("test.event", {"data": "test"})

    await asyncio.sleep(0.1)  # Allow event propagation
    assert len(received_events) == 1
```

### Data Factory Fixtures

#### `test_discussion`
Factory for creating test Discussion data.

```python
def test_discussion_creation(test_discussion):
    # Create with defaults
    discussion = test_discussion()
    assert discussion["mode"] == "HOST_DEFINED"

    # Create with overrides
    custom = test_discussion(
        community_id=123,
        total_rounds=5,
        status="ACTIVE"
    )
    assert custom["total_rounds"] == 5
```

#### `test_round`
Factory for creating test Round data.

```python
def test_round_creation(test_round):
    round_data = test_round(
        round_num=2,
        question_text="What do you think?",
        status="ACTIVE"
    )
    assert round_data["round_num"] == 2
```

#### `test_participant`
Factory for creating test Participant data.

```python
def test_participant_creation(test_participant):
    participant = test_participant(
        first_round=1,
        last_round=5,
        dropout_reason="NO_SUBMISSION"
    )
    assert participant["last_round"] == 5
```

### Helper Fixtures

#### `sample_submission_text`
Provides realistic submission text for testing.

```python
def test_text_processing(sample_submission_text):
    assert len(sample_submission_text) > 0
    # Use in your tests
```

#### `sample_summary_text`
Provides realistic summary text for testing.

```python
def test_summary_processing(sample_summary_text):
    assert len(sample_summary_text) > 0
    # Use in your tests
```

## Writing Tests

### Unit Test Example

```python
import pytest
from src.services.some_service import SomeService

@pytest.mark.unit
async def test_some_service_method(db_session: AsyncSession):
    """Test that SomeService.method works correctly."""
    service = SomeService(db_session)

    result = await service.some_method()

    assert result is not None
    assert result.status == "success"
```

### Integration Test Example

```python
import pytest
from src.models.discussion import Discussion

@pytest.mark.integration
async def test_discussion_lifecycle(
    db_session: AsyncSession,
    redis_client: aioredis.Redis,
    test_discussion
):
    """Test complete discussion creation and activation."""
    # Create discussion data
    discussion_data = test_discussion(status="DRAFT")

    # Save to database
    discussion = Discussion(**discussion_data)
    db_session.add(discussion)
    await db_session.flush()

    # Verify it was saved
    result = await db_session.execute(
        select(Discussion).where(Discussion.discussion_id == discussion.discussion_id)
    )
    saved = result.scalar_one()

    assert saved.status == "DRAFT"
```

### Contract Test Example

```python
import pytest
from src.events.event_types import SubmissionWindowClosedEvent

@pytest.mark.contract
async def test_submission_to_summary_contract(event_bus: EventBus):
    """Test that submission_window.closed event has correct schema."""
    received_events = []

    async def handler(event: dict):
        received_events.append(event)

    event_bus.subscribe("submission_window.closed", handler)

    # Emit event with expected schema
    event_data = {
        "discussion_id": "disc-123",
        "round_id": "round-456",
        "submissions": [
            {"submission_id": "sub-1", "participant_id": "part-1"}
        ]
    }

    await event_bus.emit("submission_window.closed", event_data)
    await asyncio.sleep(0.1)

    # Validate received event matches contract
    assert len(received_events) == 1
    assert "discussion_id" in received_events[0]
    assert "round_id" in received_events[0]
    assert "submissions" in received_events[0]
```

## Test Markers

Use markers to organize and filter tests:

```python
@pytest.mark.unit        # Fast, isolated unit test
@pytest.mark.integration # Requires services (DB, Redis)
@pytest.mark.contract    # Sub-protocol integration test
@pytest.mark.slow        # Test that takes several seconds
@pytest.mark.timing      # Timing-sensitive test
```

## Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run specific test file
pytest tests/unit/test_fixtures.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src --cov-report=html

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run only tests matching pattern
pytest -k "test_discussion"
```

## Test Isolation

All fixtures provide proper test isolation:

1. **Database**: Each test runs in a transaction that is rolled back
2. **Redis**: Database is flushed before and after each test
3. **Event Bus**: Fresh instance with no handlers per test
4. **Factories**: Each call generates unique IDs

You don't need to manually clean up - fixtures handle it automatically!

## Best Practices

### 1. Use Appropriate Markers
```python
@pytest.mark.unit  # For fast, isolated tests
@pytest.mark.integration  # For tests requiring services
```

### 2. Name Tests Descriptively
```python
# Good
async def test_discussion_creation_with_multiple_rounds()

# Bad
async def test_disc()
```

### 3. Use Fixtures for Setup
```python
# Good - uses fixture
async def test_something(test_discussion, db_session):
    discussion = test_discussion(total_rounds=3)
    # test logic

# Bad - manual setup
async def test_something(db_session):
    discussion = {"discussion_id": "123", ...}  # brittle
```

### 4. Test One Thing Per Test
```python
# Good
async def test_discussion_can_be_created()
async def test_discussion_can_be_activated()

# Bad - testing multiple things
async def test_discussion_creation_and_activation_and_completion()
```

### 5. Use Async/Await Properly
```python
# Good
async def test_async_operation(db_session):
    result = await some_async_function()

# Bad - missing await
async def test_async_operation(db_session):
    result = some_async_function()  # Returns coroutine, not result!
```

### 6. Add Docstrings
```python
async def test_discussion_activation(db_session, test_discussion):
    """
    Test that a discussion can transition from DRAFT to ACTIVE status.

    Verifies:
    1. Discussion starts in DRAFT status
    2. Activation changes status to ACTIVE
    3. Timestamp is updated
    """
    # test implementation
```

## Troubleshooting

### "Database connection failed"
Ensure PostgreSQL is running and test database exists:
```bash
psql -c "CREATE DATABASE opendiscuss_test;"
```

### "Redis connection refused"
Ensure Redis is running:
```bash
redis-cli ping  # Should return PONG
```

### "Coroutine was never awaited"
Make sure to use `await` with async functions:
```python
# Good
result = await async_function()

# Bad
result = async_function()  # Returns coroutine
```

### "No module named 'src'"
Run tests from the backend directory:
```bash
cd backend
pytest
```

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-Asyncio](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Redis Async](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html)

## Examples

See `tests/unit/test_fixtures.py` for complete examples of using all fixtures.
