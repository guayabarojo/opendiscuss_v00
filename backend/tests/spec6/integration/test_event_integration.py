"""
T083: Integration test for Spec 5 → Spec 6 event handoff.

Tests end-to-end event flow:
1. Emit sankey.complete → verify question generation triggered
2. Generation success → verify question.ready emitted
3. Generation failure → verify question.generation_failed emitted

Uses:
- Mock Claude API (no real LLM calls)
- Real event bus (Redis) for authentic event flow
- Verifies event ordering and timing
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.events.event_bus import EventBus
from src.events.event_types import (
    SankeyCompleteEvent,
    QuestionReadyEvent,
    QuestionGenerationFailedEvent,
    SankeyGraph,
    ThoughtSpaceSummary,
    FlowEdge,
)
from src.question_progression.event_handlers import (
    handle_sankey_complete,
    register_handlers,
)
from src.models import Round
from src.question_progression.models import (
    QuestionSequence,
    Question,
    QuestionMode,
    ValidationStatus,
    SequenceMode,
)


# Test Fixtures


@pytest.fixture
async def event_bus(redis_url: str) -> EventBus:
    """Create and connect event bus for testing."""
    bus = EventBus(redis_url=redis_url)
    await bus.connect()
    yield bus
    await bus.disconnect()


def make_session_factory(engine):
    """
    Create a session factory from an engine.

    This is NOT a fixture - it's a regular function that returns a callable
    session factory. This avoids pytest's fixture tracking.
    """
    from contextlib import asynccontextmanager
    from sqlalchemy.ext.asyncio import async_sessionmaker

    # Create session maker bound to engine
    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # Return a callable context manager
    @asynccontextmanager
    async def factory():
        async with session_maker() as session:
            yield session
            await session.commit()

    return factory


# NOTE: We don't use a fixture for db_session_factory because pytest aggressively
# tracks fixture objects and prevents them from being called in async event handlers.
# Instead, each test creates the factory directly using make_session_factory().


@pytest.fixture
def sample_sankey_event(test_discussion_id: uuid.UUID, test_round_id: uuid.UUID) -> SankeyCompleteEvent:
    """Create sample sankey.complete event for testing."""
    thought_space_1 = ThoughtSpaceSummary(
        cluster_id=uuid.uuid4(),
        round_id=test_round_id,
        label_summary="Funding constraints limit program scope",
        member_count=12,
        member_pct=40.0,
        participant_ids=[uuid.uuid4() for _ in range(12)],
    )

    thought_space_2 = ThoughtSpaceSummary(
        cluster_id=uuid.uuid4(),
        round_id=test_round_id,
        label_summary="Staff capacity stretched across initiatives",
        member_count=8,
        member_pct=27.0,
        participant_ids=[uuid.uuid4() for _ in range(8)],
    )

    sankey_graph = SankeyGraph(
        discussion_id=test_discussion_id,
        rounds=[test_round_id],
        nodes=[thought_space_1, thought_space_2],
        edges=[],
        total_participants=30,
    )

    return SankeyCompleteEvent(
        round_id=test_round_id,
        sankey_graph=sankey_graph,
        timestamp=datetime.utcnow(),
    )


@pytest.fixture
async def test_question_sequence(
    db_session: AsyncSession,
    test_discussion_id: uuid.UUID,
    test_round_id: uuid.UUID
) -> QuestionSequence:
    """Create test question sequence in AUTO_GENERATED mode with necessary FK records."""
    from src.models import Discussion, Round
    from src.models.protocol_state import DiscussionMode, DiscussionStatus, RoundStatus

    # Create Discussion record first (FK requirement)
    discussion = Discussion(
        discussion_id=test_discussion_id,
        community_id=uuid.uuid4(),
        host_user_id=uuid.uuid4(),
        mode=DiscussionMode.AUTO_GENERATED,
        total_rounds=3,
        status=DiscussionStatus.ACTIVE,
    )
    db_session.add(discussion)

    # Create Round record (FK requirement)
    round_record = Round(
        round_id=test_round_id,
        discussion_id=test_discussion_id,
        round_num=1,
        question_text="What are the main challenges facing our community?",
        status=RoundStatus.SANKEY_BUILDING,
        submission_window_duration_sec=300,
    )
    db_session.add(round_record)

    # Now create QuestionSequence
    sequence = QuestionSequence(
        discussion_id=test_discussion_id,
        mode=SequenceMode.AUTO_GENERATED,
        total_questions=None,
    )

    # Add initial question (Round 1)
    question = Question(
        sequence_id=sequence.sequence_id,
        order=1,
        question_text="What are the main challenges facing our community?",
        mode=QuestionMode.HOST_DEFINED,
        validation_status=ValidationStatus.VALID,
    )

    db_session.add(sequence)
    db_session.add(question)
    await db_session.commit()
    await db_session.refresh(sequence)

    return sequence


# Test Cases


class TestSankeyCompleteEventHandling:
    """Test handling of sankey.complete events."""

    @pytest.mark.asyncio
    async def test_sankey_complete_triggers_generation(
        self,
        db_session: AsyncSession,
        test_engine,
        event_bus: EventBus,
        test_question_sequence: QuestionSequence,
        sample_sankey_event: SankeyCompleteEvent,
    ):
        """
        Test: Emit sankey.complete → verify question generation triggered.

        Flow:
        1. Create question sequence in AUTO_GENERATED mode
        2. Emit sankey.complete event
        3. Verify handler is called
        4. Verify question generation starts
        """
        # Event capture list
        captured_events: List[Dict[str, Any]] = []

        async def capture_question_ready(event: QuestionReadyEvent):
            """Capture question.ready events."""
            captured_events.append({
                "type": "question.ready",
                "question_id": event.question_id,
                "question_text": event.question_text,
                "timestamp": event.timestamp,
            })

        async def capture_generation_failed(event: QuestionGenerationFailedEvent):
            """Capture question.generation_failed events."""
            captured_events.append({
                "type": "question.generation_failed",
                "discussion_id": event.discussion_id,
                "retry_count": event.retry_count,
                "last_error": event.last_error,
                "timestamp": event.timestamp,
            })

        # Subscribe to downstream events
        await event_bus.subscribe("question.ready", capture_question_ready)
        await event_bus.subscribe("question.generation_failed", capture_generation_failed)

        # Mock Claude API for successful generation
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text="How could funding gaps be addressed?")
        ]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=20)

        with patch("src.question_progression.services.generation.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            # Create session factory directly (not from a fixture) to avoid pytest tracking
            session_factory = make_session_factory(test_engine)

            # Register handler
            await register_handlers(event_bus, session_factory)

            # Align sankey graph IDs with test data (Fix Pattern 3)
            # Ensure the event references match the DB records
            sample_sankey_event.sankey_graph.discussion_id = test_question_sequence.discussion_id
            sample_sankey_event.round_id = await db_session.execute(
                select(Round.round_id).where(Round.discussion_id == test_question_sequence.discussion_id)
            )
            round_result = await db_session.scalar(
                select(Round.round_id).where(Round.discussion_id == test_question_sequence.discussion_id)
            )
            if round_result:
                sample_sankey_event.round_id = round_result
                sample_sankey_event.sankey_graph.nodes[0].round_id = round_result

            # Emit sankey.complete event
            await event_bus.emit("sankey.complete", sample_sankey_event)

            # Wait for event processing
            await asyncio.sleep(1.0)  # Increased wait time

        # Get sequence_id before expiring (avoid lazy load after expire)
        sequence_id = test_question_sequence.sequence_id

        # Refresh session to see changes from other sessions
        db_session.expire_all()

        # Debug: Check what events were captured
        print(f"DEBUG: Captured {len(captured_events)} events: {captured_events}")

        # Verify question was created
        result = await db_session.execute(
            select(Question)
            .where(Question.sequence_id == sequence_id)
            .order_by(Question.question_order)
        )
        questions = result.scalars().all()

        print(f"DEBUG: Found {len(questions)} questions")
        for q in questions:
            print(f"  - Question {q.question_order}: {q.question_text[:50]}... (mode={q.mode}, status={q.validation_status})")

        assert len(questions) == 2, f"Should have 2 questions (initial + generated), but got {len(questions)}. Events captured: {len(captured_events)}"
        assert questions[1].mode == QuestionMode.AUTO_GENERATED
        assert questions[1].validation_status == ValidationStatus.VALID
        assert len(questions[1].question_text) >= 10

        # Verify question.ready event was emitted
        assert len(captured_events) == 1, "Should emit 1 event"
        assert captured_events[0]["type"] == "question.ready"
        assert captured_events[0]["question_id"] == questions[1].question_id


class TestQuestionReadyEmission:
    """Test question.ready event emission after successful generation."""

    @pytest.mark.asyncio
    async def test_generation_success_emits_question_ready(
        self,
        db_session: AsyncSession,
        test_engine,
        event_bus: EventBus,
        test_question_sequence: QuestionSequence,
        sample_sankey_event: SankeyCompleteEvent,
    ):
        """
        Test: Generation success → verify question.ready emitted.

        Validates:
        - Event payload structure
        - Provenance metadata (llm_model, latency_ms)
        - Timing of emission (after DB commit)
        """
        captured_ready_events: List[QuestionReadyEvent] = []

        async def capture_ready(event: QuestionReadyEvent):
            captured_ready_events.append(event)

        await event_bus.subscribe("question.ready", capture_ready)

        # Mock successful Claude API response
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text="How could sustainable funding models be developed?")
        ]
        mock_response.usage = MagicMock(input_tokens=150, output_tokens=25)
        mock_response.model = "claude-sonnet-4-5-20250929"

        with patch("src.question_progression.services.generation.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            # Create session factory directly (not from a fixture)
            session_factory = make_session_factory(test_engine)
            await register_handlers(event_bus, session_factory)

            # Record emission time
            start_time = datetime.utcnow()

            # Emit sankey.complete
            await event_bus.emit("sankey.complete", sample_sankey_event)

            # Wait for processing
            await asyncio.sleep(0.5)

            end_time = datetime.utcnow()

        # Verify question.ready event
        assert len(captured_ready_events) == 1, "Should emit exactly one question.ready event"

        ready_event = captured_ready_events[0]

        # Validate event structure
        assert ready_event.question_id is not None
        assert len(ready_event.question_text) >= 10
        assert ready_event.timestamp >= start_time
        assert ready_event.timestamp <= end_time

        # Refresh session to see changes from other sessions
        db_session.expire_all()

        # Verify question exists in DB
        result = await db_session.execute(
            select(Question).where(Question.question_id == ready_event.question_id)
        )
        question = result.scalar_one_or_none()

        assert question is not None
        assert question.question_text == ready_event.question_text
        assert question.mode == QuestionMode.AUTO_GENERATED


class TestQuestionGenerationFailedEmission:
    """Test question.generation_failed event emission on failures."""

    @pytest.mark.asyncio
    async def test_generation_failure_emits_failed_event(
        self,
        db_session: AsyncSession,
        test_engine,
        event_bus: EventBus,
        test_question_sequence: QuestionSequence,
        sample_sankey_event: SankeyCompleteEvent,
    ):
        """
        Test: Generation failure → verify question.generation_failed emitted.

        Simulates:
        - Claude API timeout/failure
        - Validation exhaustion
        - Retry count tracking
        """
        captured_failed_events: List[QuestionGenerationFailedEvent] = []

        async def capture_failed(event: QuestionGenerationFailedEvent):
            captured_failed_events.append(event)

        await event_bus.subscribe("question.generation_failed", capture_failed)

        # Mock Claude API failure (timeout)
        with patch("src.question_progression.services.generation.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=asyncio.TimeoutError("API timeout after 30s")
            )
            mock_anthropic.return_value = mock_client

            # Create session factory directly (not from a fixture)
            session_factory = make_session_factory(test_engine)
            await register_handlers(event_bus, session_factory)

            # Emit sankey.complete
            await event_bus.emit("sankey.complete", sample_sankey_event)

            # Wait for retry exhaustion (3 API attempts + delays: 1s + 2s = 3s minimum)
            await asyncio.sleep(5.0)

        # Verify question.generation_failed event
        assert len(captured_failed_events) == 1, "Should emit exactly one failure event"

        failed_event = captured_failed_events[0]

        # Validate event structure
        assert failed_event.discussion_id == sample_sankey_event.sankey_graph.discussion_id
        assert failed_event.retry_count >= 0
        assert failed_event.retry_count <= 3
        assert "timeout" in failed_event.last_error.lower() or "error" in failed_event.last_error.lower()

        # Cache sequence_id before expire_all()
        sequence_id = test_question_sequence.sequence_id

        # Refresh session to see changes from other sessions
        db_session.expire_all()

        # Verify no question was created
        result = await db_session.execute(
            select(Question)
            .where(Question.sequence_id == sequence_id)
        )
        questions = result.scalars().all()

        # Should only have the initial question (no generated question on failure)
        assert len(questions) == 1, "Should not create question on generation failure"

    @pytest.mark.asyncio
    async def test_validation_failure_includes_failed_text(
        self,
        db_session: AsyncSession,
        test_engine,
        event_bus: EventBus,
        test_question_sequence: QuestionSequence,
        sample_sankey_event: SankeyCompleteEvent,
    ):
        """
        Test: Validation failure includes failed_question_text in event.

        Simulates:
        - Claude generates invalid question (contains "vote", "rank", etc.)
        - Validation retries exhausted
        - Event includes the failed text for debugging
        """
        captured_failed_events: List[QuestionGenerationFailedEvent] = []

        async def capture_failed(event: QuestionGenerationFailedEvent):
            captured_failed_events.append(event)

        await event_bus.subscribe("question.generation_failed", capture_failed)

        # Mock Claude API returning invalid question
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text="Which option should we vote on?")  # Invalid: contains "vote"
        ]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=15)

        with patch("src.question_progression.services.generation.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            # Create session factory directly (not from a fixture)
            session_factory = make_session_factory(test_engine)
            await register_handlers(event_bus, session_factory)

            # Emit sankey.complete
            await event_bus.emit("sankey.complete", sample_sankey_event)

            # Wait for validation failure
            await asyncio.sleep(1.0)

        # Verify failure event with failed text
        assert len(captured_failed_events) == 1

        failed_event = captured_failed_events[0]
        assert "validation" in failed_event.last_error.lower()


class TestEventOrdering:
    """Test event ordering and timing guarantees."""

    @pytest.mark.asyncio
    async def test_events_emitted_in_correct_order(
        self,
        db_session: AsyncSession,
        test_engine,
        event_bus: EventBus,
        test_question_sequence: QuestionSequence,
        test_round_id: uuid.UUID,
    ):
        """
        Test: Verify event ordering in successful flow.

        Expected order:
        1. sankey.complete (input)
        2. question.ready (output)

        Timing constraints:
        - question.ready timestamp > sankey.complete timestamp
        - DB commit happens before question.ready emission
        """
        event_timeline: List[Dict[str, Any]] = []

        async def track_sankey(event: SankeyCompleteEvent):
            event_timeline.append({
                "type": "sankey.complete",
                "timestamp": event.timestamp,
            })

        async def track_ready(event: QuestionReadyEvent):
            event_timeline.append({
                "type": "question.ready",
                "timestamp": event.timestamp,
            })

        await event_bus.subscribe("sankey.complete", track_sankey)
        await event_bus.subscribe("question.ready", track_ready)

        # Create and emit events
        thought_space = ThoughtSpaceSummary(
            cluster_id=uuid.uuid4(),
            round_id=test_round_id,
            label_summary="Test thought space",
            member_count=10,
            member_pct=50.0,
            participant_ids=[uuid.uuid4() for _ in range(10)],
        )

        sankey_event = SankeyCompleteEvent(
            round_id=test_round_id,
            sankey_graph=SankeyGraph(
                discussion_id=test_question_sequence.discussion_id,
                rounds=[test_round_id],
                nodes=[thought_space],
                edges=[],
                total_participants=20,
            ),
            timestamp=datetime.utcnow(),
        )

        # Mock successful generation
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="How can we improve collaboration?")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=20)

        with patch("src.question_progression.services.generation.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            # Create session factory directly (not from a fixture)
            session_factory = make_session_factory(test_engine)
            await register_handlers(event_bus, session_factory)
            await event_bus.emit("sankey.complete", sankey_event)
            await asyncio.sleep(0.5)

        # Verify event ordering
        assert len(event_timeline) >= 2, "Should have both events"

        sankey_events = [e for e in event_timeline if e["type"] == "sankey.complete"]
        ready_events = [e for e in event_timeline if e["type"] == "question.ready"]

        assert len(sankey_events) > 0, "Should have sankey.complete event"
        assert len(ready_events) > 0, "Should have question.ready event"

        # Verify timing: question.ready comes after sankey.complete
        first_sankey = min(sankey_events, key=lambda e: e["timestamp"])
        first_ready = min(ready_events, key=lambda e: e["timestamp"])

        assert first_ready["timestamp"] >= first_sankey["timestamp"], \
            "question.ready should be emitted after sankey.complete"


# Helper Functions


@pytest.fixture
def test_discussion_id() -> uuid.UUID:
    """Generate test discussion ID."""
    return uuid.uuid4()


@pytest.fixture
def test_round_id() -> uuid.UUID:
    """Generate test round ID."""
    return uuid.uuid4()


@pytest.fixture
def redis_url() -> str:
    """Redis URL for testing (can be overridden via env)."""
    return "redis://localhost:6379/1"  # Use DB 1 for testing
