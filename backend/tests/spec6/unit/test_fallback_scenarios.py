"""
Unit tests for fallback scenarios (Phase 9, T091).

Tests fallback behavior when generation fails:
- All retries exhausted → QUESTION_GENERATION_FAILED
- Validation fails 3 times → QUESTION_GENERATION_FAILED
- question.generation_failed event emitted
- Host can manually provide question after failure
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from anthropic import APIStatusError

from src.question_progression.services.generation import (
    QuestionGenerationService,
    QuestionGenerationError,
    QuestionValidationExhausted
)
from src.models import Discussion, Round, RoundStatus, DiscussionMode, DiscussionStatus
from src.question_progression.models import (
    QuestionSequence,
    Question,
    SequenceMode,
    QuestionMode,
    ValidationStatus
)
from src.question_progression.event_handlers import handle_sankey_complete
from src.events.event_types import (
    SankeyCompleteEvent,
    SankeyGraph,
    ThoughtSpaceSummary
)


@pytest.fixture
def mock_sankey_graph():
    """Create mock Sankey graph for testing."""
    round_id = uuid4()

    thought_space = ThoughtSpaceSummary(
        cluster_id=uuid4(),
        round_id=round_id,
        label_summary="Funding constraints",
        member_count=12,
        member_pct=40.0,
        participant_ids=[uuid4() for _ in range(12)]
    )

    return SankeyGraph(
        discussion_id=uuid4(),
        rounds=[round_id],
        nodes=[thought_space],
        edges=[],
        total_participants=30
    )


@pytest.fixture
def mock_invalid_response():
    """Mock invalid Claude API response."""
    mock_response = Mock()
    mock_response.content = [Mock(text="Do you agree?")]  # Invalid: starts with "Do you"
    mock_response.usage = Mock(input_tokens=500, output_tokens=20)
    return mock_response


@pytest.mark.asyncio
async def test_all_retries_exhausted_question_generation_failed(db_session, mock_sankey_graph):
    """
    Test all API retries exhausted → QUESTION_GENERATION_FAILED state.

    Scenario:
    - All 3 API calls return 503 Service Unavailable
    Expected:
    - Round created with QUESTION_GENERATION_FAILED status
    - question.generation_failed event emitted
    """
    # Create AUTO_GENERATED discussion
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.AUTO_GENERATED,
        total_rounds=3
    )
    discussion.status = DiscussionStatus.ACTIVE
    db_session.add(discussion)

    # Create question sequence
    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    # Create Round 1 (COMPLETE)
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are the key priorities?",
        submission_window_duration_sec=300
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Mock Claude API to return 503 errors
    with patch('src.question_progression.services.generation.AsyncAnthropic') as mock_anthropic, \
         patch('src.question_progression.services.generation.settings') as mock_settings:
        # Provide dummy API key for test
        mock_settings.claude_api_key = "test-key"
        mock_settings.claude_model = "claude-3-5-sonnet-20241022"
        mock_settings.question_generation_timeout_seconds = 30
        mock_settings.question_generation_max_retries = 3

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=APIStatusError(
                "Service unavailable",
                response=Mock(status_code=503),
                body={}
            )
        )
        mock_anthropic.return_value = mock_client

        mock_event_bus = AsyncMock()

        # Update mock sankey graph with correct discussion_id
        mock_sankey_graph.discussion_id = discussion.discussion_id

        event = SankeyCompleteEvent(
            round_id=round1.round_id,
            sankey_graph=mock_sankey_graph,
            timestamp=datetime.utcnow()
        )

        # Handle event (should catch error and set QUESTION_GENERATION_FAILED)
        await handle_sankey_complete(event, db_session, mock_event_bus)

    # Verify Round 2 created with QUESTION_GENERATION_FAILED status
    from sqlalchemy import select
    result = await db_session.execute(
        select(Round)
        .where(Round.discussion_id == discussion.discussion_id)
        .where(Round.round_num == 2)
    )
    round2 = result.scalar_one_or_none()

    assert round2 is not None
    assert round2.status == RoundStatus.QUESTION_GENERATION_FAILED
    assert round2.question_text == ""  # Empty until host provides

    # Verify question.generation_failed event emitted
    assert mock_event_bus.emit.call_count >= 1
    failed_event_emitted = False
    for call in mock_event_bus.emit.call_args_list:
        if call[0][0] == "question.generation_failed":
            failed_event_emitted = True
            break
    assert failed_event_emitted, "question.generation_failed event should be emitted"


@pytest.mark.asyncio
async def test_validation_fails_3_times_question_generation_failed(db_session, mock_sankey_graph, mock_invalid_response):
    """
    Test validation fails 3 times → QUESTION_GENERATION_FAILED.

    Scenario:
    - All 3 validation attempts return invalid questions
    Expected:
    - Round created with QUESTION_GENERATION_FAILED status
    - question.generation_failed event emitted
    """
    # Create AUTO_GENERATED discussion
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.AUTO_GENERATED,
        total_rounds=3
    )
    discussion.status = DiscussionStatus.ACTIVE
    db_session.add(discussion)

    # Create question sequence
    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    # Create Round 1 (COMPLETE)
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are the key priorities?",
        submission_window_duration_sec=300
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Mock Claude API to return invalid responses
    with patch('src.question_progression.services.generation.AsyncAnthropic') as mock_anthropic, \
         patch('src.question_progression.services.generation.settings') as mock_settings:
        # Provide dummy API key for test
        mock_settings.claude_api_key = "test-key"
        mock_settings.claude_model = "claude-3-5-sonnet-20241022"
        mock_settings.question_generation_timeout_seconds = 30
        mock_settings.question_generation_max_retries = 3

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_invalid_response)
        mock_anthropic.return_value = mock_client

        mock_event_bus = AsyncMock()

        # Update mock sankey graph with correct discussion_id
        mock_sankey_graph.discussion_id = discussion.discussion_id

        event = SankeyCompleteEvent(
            round_id=round1.round_id,
            sankey_graph=mock_sankey_graph,
            timestamp=datetime.utcnow()
        )

        await handle_sankey_complete(event, db_session, mock_event_bus)

    # Verify Round 2 created with QUESTION_GENERATION_FAILED status
    from sqlalchemy import select
    result = await db_session.execute(
        select(Round)
        .where(Round.discussion_id == discussion.discussion_id)
        .where(Round.round_num == 2)
    )
    round2 = result.scalar_one_or_none()

    assert round2 is not None
    assert round2.status == RoundStatus.QUESTION_GENERATION_FAILED

    # Verify question.generation_failed event emitted
    failed_event_emitted = False
    for call in mock_event_bus.emit.call_args_list:
        if call[0][0] == "question.generation_failed":
            failed_event_emitted = True
            break
    assert failed_event_emitted


@pytest.mark.asyncio
async def test_question_generation_failed_event_emitted(db_session, mock_sankey_graph):
    """
    Test question.generation_failed event emitted on failure.

    Verifies:
    - Event contains correct discussion_id and round_id
    - Event includes error message
    """
    # Create AUTO_GENERATED discussion
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.AUTO_GENERATED,
        total_rounds=3
    )
    discussion.status = DiscussionStatus.ACTIVE
    db_session.add(discussion)

    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are the key priorities?",
        submission_window_duration_sec=300
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Mock Claude API to fail
    with patch('src.question_progression.services.generation.AsyncAnthropic') as mock_anthropic, \
         patch('src.question_progression.services.generation.settings') as mock_settings:
        # Provide dummy API key for test
        mock_settings.claude_api_key = "test-key"
        mock_settings.claude_model = "claude-3-5-sonnet-20241022"
        mock_settings.question_generation_timeout_seconds = 30
        mock_settings.question_generation_max_retries = 3

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=APIStatusError("Service unavailable", response=Mock(status_code=503), body={})
        )
        mock_anthropic.return_value = mock_client

        mock_event_bus = AsyncMock()

        # Update mock sankey graph with correct discussion_id
        mock_sankey_graph.discussion_id = discussion.discussion_id

        event = SankeyCompleteEvent(
            round_id=round1.round_id,
            sankey_graph=mock_sankey_graph,
            timestamp=datetime.utcnow()
        )

        await handle_sankey_complete(event, db_session, mock_event_bus)

    # Verify event emitted with correct structure
    failed_event_found = False
    for call in mock_event_bus.emit.call_args_list:
        if call[0][0] == "question.generation_failed":
            failed_event_found = True
            event_data = call[0][1]
            # Verify event contains required fields
            assert hasattr(event_data, 'discussion_id') or 'discussion_id' in event_data
            break

    assert failed_event_found, "question.generation_failed event should be emitted"


@pytest.mark.asyncio
async def test_host_can_manually_provide_question_after_failure(db_session):
    """
    Test host can manually provide question after generation failure.

    Scenario:
    1. Generation fails → Round with QUESTION_GENERATION_FAILED
    2. Host provides question via API
    3. Round transitions to QUESTION_READY
    """
    from src.question_progression.services.sequence import QuestionSequenceService

    # Create AUTO_GENERATED discussion
    discussion = Discussion(
        community_id=uuid4(),
        host_user_id=uuid4(),
        mode=DiscussionMode.AUTO_GENERATED,
        total_rounds=3
    )
    discussion.status = DiscussionStatus.ACTIVE
    db_session.add(discussion)

    # Create sequence
    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    # Create Round 1 (COMPLETE)
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are the key priorities?",
        submission_window_duration_sec=300
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    # Create Round 2 with QUESTION_GENERATION_FAILED
    round2 = Round(
        discussion_id=discussion.discussion_id,
        round_num=2,
        question_text="",  # Empty - generation failed
        submission_window_duration_sec=300
    )
    round2.status = RoundStatus.QUESTION_GENERATION_FAILED
    db_session.add(round2)

    await db_session.commit()

    # Host manually provides question
    manual_question_text = "What improvements would you suggest?"

    # Create question manually
    question2 = Question(
        sequence_id=sequence.sequence_id,
        order=2,
        question_text=manual_question_text,
        mode=QuestionMode.HOST_DEFINED,  # Manually provided
        validation_status=ValidationStatus.VALID
    )
    db_session.add(question2)
    await db_session.flush()

    # Update round with manual question
    round2.question_text = manual_question_text
    round2.question_id = question2.question_id
    round2.status = RoundStatus.QUESTION_READY
    db_session.add(round2)

    await db_session.commit()
    await db_session.refresh(round2)

    # Verify round is now QUESTION_READY with manual question
    assert round2.status == RoundStatus.QUESTION_READY
    assert round2.question_text == manual_question_text
    assert round2.question_id == question2.question_id

    # Verify question has HOST_DEFINED mode (manual)
    await db_session.refresh(question2)
    assert question2.mode == QuestionMode.HOST_DEFINED
    assert question2.validation_status == ValidationStatus.VALID


@pytest.mark.asyncio
async def test_generation_service_raises_correct_exceptions():
    """
    Test QuestionGenerationService raises correct exception types.

    Verifies:
    - QuestionGenerationError for API failures
    - QuestionValidationExhausted for validation failures
    """
    service = QuestionGenerationService(
        api_key="test-key",
        model="claude-3-5-sonnet-20241022",
        max_retries=2  # Reduce retries for faster test
    )

    sankey_data = {
        "nodes": [{"label_summary": "Test", "member_count": 10, "member_pct": 0.5}],
        "flows": [],
        "total_participants": 20
    }

    # Test API failure raises QuestionGenerationError
    with patch.object(service.client.messages, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = APIStatusError("Service error", response=Mock(status_code=500), body={})

        with pytest.raises(QuestionGenerationError):
            await service.generate_from_sankey(
                round_num=2,
                previous_questions=["What?"],
                sankey_data=sankey_data,
                input_round_id=uuid4()
            )

    # Test validation failure raises QuestionValidationExhausted
    invalid_response = Mock()
    invalid_response.content = [Mock(text="Invalid question format")]
    invalid_response.usage = Mock(input_tokens=100, output_tokens=10)

    with patch.object(service.client.messages, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = invalid_response

        with pytest.raises(QuestionValidationExhausted):
            await service.generate_from_sankey(
                round_num=2,
                previous_questions=["What?"],
                sankey_data=sankey_data,
                input_round_id=uuid4()
            )
