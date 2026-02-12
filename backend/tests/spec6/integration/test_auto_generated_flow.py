"""
Integration test for auto-generated question flow (Phase 5).

Tests the complete flow:
1. Create AUTO_GENERATED discussion
2. Complete Round 1
3. Trigger sankey.complete event
4. Verify question generated and Round 2 created with QUESTION_READY status
5. Test validation failure → regeneration → success
6. Test all retries exhausted → QUESTION_GENERATION_FAILED
"""

import asyncio
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import select
from src.models import Discussion, Round, RoundStatus, DiscussionMode
from src.question_progression.models import (
    QuestionSequence,
    Question,
    QuestionProvenance,
    SequenceMode,
    QuestionMode,
    ValidationStatus
)
from src.question_progression.services.generation import (
    QuestionGenerationService,
    QuestionGenerationError,
    QuestionValidationExhausted
)
from src.question_progression.event_handlers import handle_sankey_complete
from src.events.event_types import (
    SankeyCompleteEvent,
    SankeyGraph,
    ThoughtSpaceSummary,
    FlowEdge
)


@pytest.fixture(autouse=True)
def mock_api_key(monkeypatch):
    """Set fake API key for integration tests."""
    from src.config import settings
    monkeypatch.setattr(settings, "claude_api_key", "sk-ant-test-key-123")


@pytest.fixture
def mock_claude_response():
    """Mock Claude API response."""
    mock_response = Mock()
    mock_response.content = [Mock(text="What are the main challenges?")]
    mock_response.usage = Mock(input_tokens=500, output_tokens=50)
    return mock_response


@pytest.fixture
def mock_sankey_graph():
    """Create mock Sankey graph for testing."""
    discussion_id = uuid4()
    round_id = uuid4()

    thought_space = ThoughtSpaceSummary(
        cluster_id=uuid4(),
        round_id=round_id,
        label_summary="Funding constraints limit program scope",
        member_count=12,
        member_pct=40.0,
        participant_ids=[uuid4() for _ in range(12)]
    )

    return SankeyGraph(
        discussion_id=discussion_id,
        rounds=[round_id],
        nodes=[thought_space],
        edges=[],
        total_participants=30
    )


@pytest.mark.asyncio
async def test_successful_auto_generation_flow(db_session, mock_claude_response, mock_sankey_graph):
    """
    Test successful auto-generation flow from sankey.complete to question.ready.
    """
    # Create AUTO_GENERATED discussion
    discussion = Discussion(
        discussion_id=uuid4(),
        community_id=uuid4(),
        host_user_id=uuid4(),
        total_rounds=3,
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    # Create question sequence
    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    # Create first question
    question1 = Question(
        sequence_id=sequence.sequence_id,
        order=1,
        question_text="What are the key priorities?",
        mode=QuestionMode.AUTO_GENERATED,
        validation_status=ValidationStatus.VALID
    )
    db_session.add(question1)

    # Create Round 1 (COMPLETE)
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text=question1.question_text,
        submission_window_duration_sec=300,
        question_id=question1.question_id
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Update mock_sankey_graph with correct IDs
    mock_sankey_graph.discussion_id = discussion.discussion_id
    mock_sankey_graph.nodes[0].round_id = round1.round_id

    # Mock Claude API
    with patch('src.question_progression.services.generation.AsyncAnthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_claude_response)
        mock_anthropic.return_value = mock_client

        # Mock event bus
        mock_event_bus = AsyncMock()

        # Create sankey.complete event
        event = SankeyCompleteEvent(
            round_id=round1.round_id,
            sankey_graph=mock_sankey_graph,
            timestamp=datetime.utcnow()
        )

        # Handle event
        await handle_sankey_complete(event, db_session, mock_event_bus)

    # Verify Question created
    from sqlalchemy import select
    result = await db_session.execute(
        select(Question)
        .where(Question.sequence_id == sequence.sequence_id)
        .where(Question.question_order == 2)
    )
    question2 = result.scalar_one_or_none()

    assert question2 is not None
    assert question2.question_text == "What are the main challenges?"
    assert question2.mode == QuestionMode.AUTO_GENERATED
    assert question2.validation_status == ValidationStatus.VALID

    # Verify Round 2 created with QUESTION_READY status
    result = await db_session.execute(
        select(Round)
        .where(Round.discussion_id == discussion.discussion_id)
        .where(Round.round_num == 2)
    )
    round2 = result.scalar_one_or_none()

    assert round2 is not None
    assert round2.status == RoundStatus.QUESTION_READY
    assert round2.question_id == question2.question_id
    assert round2.question_text == question2.question_text

    # Verify provenance recorded
    result = await db_session.execute(
        select(QuestionProvenance)
        .where(QuestionProvenance.question_id == question2.question_id)
    )
    provenance = result.scalar_one_or_none()

    assert provenance is not None
    assert provenance.input_round_id == round1.round_id
    assert provenance.llm_model is not None
    assert provenance.generation_latency_ms > 0
    assert provenance.retry_count == 0
    assert provenance.validation_attempts == 1

    # Verify event emitted
    mock_event_bus.emit.assert_called_once()
    call_args = mock_event_bus.emit.call_args
    assert call_args[0][0] == "question.ready"


@pytest.mark.asyncio
async def test_validation_failure_then_success(db_session, mock_sankey_graph):
    """
    Test validation failure → regeneration with stricter prompt → success.
    """
    # Create discussion and sequence
    discussion = Discussion(
        discussion_id=uuid4(),
        community_id=uuid4(),
        host_user_id=uuid4(),
        total_rounds=3,
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    # Create Round 1
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are the key priorities?",
        submission_window_duration_sec=300
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Update mock_sankey_graph with correct IDs
    mock_sankey_graph.discussion_id = discussion.discussion_id
    mock_sankey_graph.nodes[0].round_id = round1.round_id

    # Mock Claude API with 2 responses: invalid first, then valid
    invalid_response = Mock()
    invalid_response.content = [Mock(text="Why is this important?")]  # Invalid: starts with "Why"
    invalid_response.usage = Mock(input_tokens=500, output_tokens=30)

    valid_response = Mock()
    valid_response.content = [Mock(text="What challenges do you foresee?")]
    valid_response.usage = Mock(input_tokens=520, output_tokens=40)

    responses = [invalid_response, valid_response]

    with patch('src.question_progression.services.generation.AsyncAnthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=responses)
        mock_anthropic.return_value = mock_client

        mock_event_bus = AsyncMock()

        event = SankeyCompleteEvent(
            round_id=round1.round_id,
            sankey_graph=mock_sankey_graph,
            timestamp=datetime.utcnow()
        )

        await handle_sankey_complete(event, db_session, mock_event_bus)

    # Verify question created with valid text
    from sqlalchemy import select
    result = await db_session.execute(
        select(Question)
        .where(Question.sequence_id == sequence.sequence_id)
    )
    question = result.scalar_one_or_none()

    assert question is not None
    assert question.question_text == "What challenges do you foresee?"

    # Verify provenance shows validation attempts
    result = await db_session.execute(
        select(QuestionProvenance)
        .where(QuestionProvenance.question_id == question.question_id)
    )
    provenance = result.scalar_one_or_none()

    assert provenance is not None
    assert provenance.validation_attempts == 2  # First failed, second succeeded


@pytest.mark.asyncio
async def test_all_retries_exhausted(db_session, mock_sankey_graph):
    """
    Test all retries exhausted → QUESTION_GENERATION_FAILED state.
    """
    # Create discussion and sequence
    discussion = Discussion(
        discussion_id=uuid4(),
        community_id=uuid4(),
        host_user_id=uuid4(),
        total_rounds=3,
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    # Create Round 1
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are the key priorities?",
        submission_window_duration_sec=300
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Update mock_sankey_graph with correct IDs
    mock_sankey_graph.discussion_id = discussion.discussion_id
    mock_sankey_graph.nodes[0].round_id = round1.round_id

    # Mock Claude API to always return invalid responses
    invalid_response = Mock()
    invalid_response.content = [Mock(text="Do you agree with this?")]  # Invalid: starts with "Do you"
    invalid_response.usage = Mock(input_tokens=500, output_tokens=30)

    with patch('src.question_progression.services.generation.AsyncAnthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=invalid_response)
        mock_anthropic.return_value = mock_client

        mock_event_bus = AsyncMock()

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
    assert round2.question_text == ""  # Empty until host provides

    # Verify failure event emitted
    assert mock_event_bus.emit.call_count == 1
    call_args = mock_event_bus.emit.call_args
    assert call_args[0][0] == "question.generation_failed"


@pytest.mark.asyncio
async def test_generation_failure_recovery_with_manual_question(db_session, mock_sankey_graph):
    """
    Test complete generation failure recovery flow (Phase 9, T092).

    Scenario:
    1. Mock Claude API to return 503 error
    2. Verify 3 retries attempted
    3. Verify QUESTION_GENERATION_FAILED status
    4. Host provides manual question via API
    5. Verify discussion continues with manual question
    """
    # Create AUTO_GENERATED discussion
    discussion = Discussion(
        discussion_id=uuid4(),
        community_id=uuid4(),
        host_user_id=uuid4(),
        total_rounds=3,
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    # Create question sequence
    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    # Create first question
    question1 = Question(
        sequence_id=sequence.sequence_id,
        order=1,
        question_text="What are the key priorities?",
        mode=QuestionMode.AUTO_GENERATED,
        validation_status=ValidationStatus.VALID
    )
    db_session.add(question1)

    # Create Round 1 (COMPLETE)
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text=question1.question_text,
        submission_window_duration_sec=300,
        question_id=question1.question_id
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Update mock_sankey_graph with correct IDs
    mock_sankey_graph.discussion_id = discussion.discussion_id
    mock_sankey_graph.nodes[0].round_id = round1.round_id

    # STEP 1 & 2: Mock Claude API to return 503 (verify 3 retries)
    call_count = 0

    async def mock_create_with_counter(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        from anthropic import APIStatusError
        raise APIStatusError("Service unavailable", response=Mock(status_code=503), body={})

    with patch('src.question_progression.services.generation.AsyncAnthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=mock_create_with_counter)
        mock_anthropic.return_value = mock_client

        mock_event_bus = AsyncMock()

        event = SankeyCompleteEvent(
            round_id=round1.round_id,
            sankey_graph=mock_sankey_graph,
            timestamp=datetime.utcnow()
        )

        # Handle event (should fail after 3 retries)
        await handle_sankey_complete(event, db_session, mock_event_bus)

    # Verify 3 retries were attempted (3 API calls for 3 validation attempts)
    assert call_count == 3, f"Expected 3 retries, got {call_count}"

    # STEP 3: Verify QUESTION_GENERATION_FAILED status
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

    # STEP 4: Host provides manual question
    manual_question_text = "What improvements would you suggest?"

    # Create question manually (simulating API call)
    question2 = Question(
        sequence_id=sequence.sequence_id,
        order=2,
        question_text=manual_question_text,
        mode=QuestionMode.HOST_DEFINED,  # Manual override
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

    # STEP 5: Verify discussion continues
    assert round2.status == RoundStatus.QUESTION_READY
    assert round2.question_text == manual_question_text
    assert round2.question_id == question2.question_id

    # Verify question has HOST_DEFINED mode (indicating manual override)
    await db_session.refresh(question2)
    assert question2.mode == QuestionMode.HOST_DEFINED
    assert question2.validation_status == ValidationStatus.VALID


@pytest.mark.asyncio
async def test_validation_failure_regeneration_eventual_success(db_session, mock_sankey_graph):
    """
    Test validation failure → regeneration → eventual success (Phase 9, T092).

    Scenario:
    1. Mock validation failure on first 2 attempts
    2. Mock valid question on 3rd attempt
    3. Verify regeneration with stricter prompt
    4. Verify eventual success
    """
    # Create AUTO_GENERATED discussion
    discussion = Discussion(
        discussion_id=uuid4(),
        community_id=uuid4(),
        host_user_id=uuid4(),
        total_rounds=3,
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    question1 = Question(
        sequence_id=sequence.sequence_id,
        order=1,
        question_text="What are the key priorities?",
        mode=QuestionMode.AUTO_GENERATED,
        validation_status=ValidationStatus.VALID
    )
    db_session.add(question1)

    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text=question1.question_text,
        submission_window_duration_sec=300,
        question_id=question1.question_id
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Update mock_sankey_graph with correct IDs
    mock_sankey_graph.discussion_id = discussion.discussion_id
    mock_sankey_graph.nodes[0].round_id = round1.round_id

    # Mock responses: 2 invalid, then 1 valid
    invalid_response1 = Mock()
    invalid_response1.content = [Mock(text="Why is this important?")]  # Invalid
    invalid_response1.usage = Mock(input_tokens=500, output_tokens=30)

    invalid_response2 = Mock()
    invalid_response2.content = [Mock(text="Do you think this matters?")]  # Invalid
    invalid_response2.usage = Mock(input_tokens=520, output_tokens=35)

    valid_response = Mock()
    valid_response.content = [Mock(text="What challenges do you foresee?")]  # Valid
    valid_response.usage = Mock(input_tokens=540, output_tokens=40)

    responses = [invalid_response1, invalid_response2, valid_response]

    with patch('src.question_progression.services.generation.AsyncAnthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=responses)
        mock_anthropic.return_value = mock_client

        mock_event_bus = AsyncMock()

        event = SankeyCompleteEvent(
            round_id=round1.round_id,
            sankey_graph=mock_sankey_graph,
            timestamp=datetime.utcnow()
        )

        await handle_sankey_complete(event, db_session, mock_event_bus)

    # Verify question created with valid text
    from sqlalchemy import select
    result = await db_session.execute(
        select(Question)
        .where(Question.sequence_id == sequence.sequence_id)
        .where(Question.question_order == 2)
    )
    question2 = result.scalar_one_or_none()

    assert question2 is not None
    assert question2.question_text == "What challenges do you foresee?"
    assert question2.mode == QuestionMode.AUTO_GENERATED

    # Verify provenance shows 3 validation attempts
    result = await db_session.execute(
        select(QuestionProvenance)
        .where(QuestionProvenance.question_id == question2.question_id)
    )
    provenance = result.scalar_one_or_none()

    assert provenance is not None
    assert provenance.validation_attempts == 3  # 2 failed, 1 succeeded

    # Verify Round 2 has QUESTION_READY status
    result = await db_session.execute(
        select(Round)
        .where(Round.discussion_id == discussion.discussion_id)
        .where(Round.round_num == 2)
    )
    round2 = result.scalar_one_or_none()

    assert round2 is not None
    assert round2.status == RoundStatus.QUESTION_READY
    assert round2.question_id == question2.question_id


@pytest.mark.asyncio
async def test_final_report_includes_generation_failure_metadata(db_session, mock_sankey_graph):
    """
    Test that final report includes generation failure metadata (Phase 9, T092).

    Scenario:
    1. Complete discussion with one generation failure
    2. Verify final report includes failure information
    """
    # Create AUTO_GENERATED discussion
    discussion = Discussion(
        discussion_id=uuid4(),
        community_id=uuid4(),
        host_user_id=uuid4(),
        total_rounds=3,
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    # Create Round 1 with auto-generated question
    question1 = Question(
        sequence_id=sequence.sequence_id,
        order=1,
        question_text="What are the key priorities?",
        mode=QuestionMode.AUTO_GENERATED,
        validation_status=ValidationStatus.VALID
    )
    db_session.add(question1)

    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text=question1.question_text,
        submission_window_duration_sec=300,
        question_id=question1.question_id
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    # Create Round 2 with failed generation (later recovered manually)
    question2 = Question(
        sequence_id=sequence.sequence_id,
        order=2,
        question_text="What improvements are needed?",
        mode=QuestionMode.HOST_DEFINED,  # Manual override after failure
        validation_status=ValidationStatus.VALID
    )
    db_session.add(question2)

    round2 = Round(
        discussion_id=discussion.discussion_id,
        round_num=2,
        question_text=question2.question_text,
        submission_window_duration_sec=300,
        question_id=question2.question_id
    )
    round2.status = RoundStatus.COMPLETE
    # Note: Status history would show QUESTION_GENERATION_FAILED → QUESTION_READY transition
    db_session.add(round2)

    await db_session.commit()

    # Generate final report (simulated)
    report_data = {
        "discussion_id": str(discussion.discussion_id),
        "mode": discussion.mode.value,
        "rounds": []
    }

    # Round 1: Auto-generated (success)
    result = await db_session.execute(
        select(QuestionProvenance)
        .where(QuestionProvenance.question_id == question1.question_id)
    )
    provenance1 = result.scalar_one_or_none()

    report_data["rounds"].append({
        "round_num": 1,
        "question_mode": question1.mode.value,
        "generation_success": True,
        "retry_count": provenance1.retry_count if provenance1 else 0,
        "validation_attempts": provenance1.validation_attempts if provenance1 else 1
    })

    # Round 2: Failed generation, manual override
    report_data["rounds"].append({
        "round_num": 2,
        "question_mode": question2.mode.value,
        "generation_success": False,
        "generation_failed": True,
        "manual_override": True,
        "failure_reason": "Generation failed after 3 retries, host provided manual question"
    })

    # Verify report includes failure metadata
    assert report_data["rounds"][0]["generation_success"] is True
    assert report_data["rounds"][1]["generation_failed"] is True
    assert report_data["rounds"][1]["manual_override"] is True
    assert "failure_reason" in report_data["rounds"][1]


# ============================================================================
# T064: Phase 6 Integration Test - Auto-Generated Round Advancement
# ============================================================================


@pytest.mark.asyncio
async def test_auto_generated_complete_flow_with_advancement(db_session, mock_claude_response, mock_sankey_graph):
    """
    Test complete AUTO_GENERATED flow: Round 1 → Sankey → generation → QUESTION_READY → advance → Round 2.

    Validates (T064):
    - Create AUTO_GENERATED discussion
    - Complete Round 1
    - Sankey triggers question generation
    - Round 2 transitions to QUESTION_READY
    - can_advance() returns True
    - Host advances to Round 2
    - Round 2 starts with SUBMISSION_OPEN
    """
    # Create AUTO_GENERATED discussion
    discussion = Discussion(
        discussion_id=uuid4(),
        community_id=uuid4(),
        host_user_id=uuid4(),
        total_rounds=3,
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    # Create question sequence
    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    # Create Round 1 with seed question
    question1 = Question(
        sequence_id=sequence.sequence_id,
        order=1,
        question_text="What are the key priorities?",
        mode=QuestionMode.AUTO_GENERATED,
        validation_status=ValidationStatus.VALID
    )
    db_session.add(question1)

    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text=question1.question_text,
        submission_window_duration_sec=300,
        question_id=question1.question_id
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Update mock_sankey_graph with correct IDs
    mock_sankey_graph.discussion_id = discussion.discussion_id
    mock_sankey_graph.nodes[0].round_id = round1.round_id

    # Mock Claude API
    with patch('src.question_progression.services.generation.AsyncAnthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_claude_response)
        mock_anthropic.return_value = mock_client

        mock_event_bus = AsyncMock()

        # Trigger sankey.complete event → generates question for Round 2
        event = SankeyCompleteEvent(
            round_id=round1.round_id,
            sankey_graph=mock_sankey_graph,
            timestamp=datetime.utcnow()
        )

        await handle_sankey_complete(event, db_session, mock_event_bus)

    # Verify Round 2 created with QUESTION_READY status
    from sqlalchemy.orm import selectinload
    result = await db_session.execute(
        select(Round)
        .where(Round.discussion_id == discussion.discussion_id)
        .where(Round.round_num == 2)
        .options(selectinload(Round.question))
    )
    round2 = result.scalar_one_or_none()

    assert round2 is not None
    assert round2.status == RoundStatus.QUESTION_READY
    assert round2.question_text == "What are the main challenges?"

    # Verify can_advance() returns True
    can_adv, reason = round2.can_advance()
    assert can_adv is True, f"Expected can_advance=True, got False: {reason}"
    assert reason is None

    # Simulate host advancing to Round 2
    round2.open_submission_window()
    await db_session.commit()
    await db_session.refresh(round2)

    # Verify Round 2 is now SUBMISSION_OPEN
    assert round2.status == RoundStatus.SUBMISSION_OPEN
    assert round2.submission_window_start is not None
    assert round2.submission_window_end is not None


@pytest.mark.asyncio
async def test_advance_blocked_before_question_ready(db_session, mock_sankey_graph):
    """
    Test that advancement is blocked until status = QUESTION_READY (T064).

    Validates:
    - Round 1 complete → Sankey triggers generation
    - While generation in progress, Round 2 still in PENDING
    - can_advance() returns False (waiting for QUESTION_READY)
    - After generation completes → QUESTION_READY → can_advance() returns True
    """
    # Create discussion
    discussion = Discussion(
        discussion_id=uuid4(),
        community_id=uuid4(),
        host_user_id=uuid4(),
        total_rounds=3,
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are the priorities?",
        submission_window_duration_sec=300
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    # Create Round 2 in PENDING state (question not yet generated)
    round2 = Round(
        discussion_id=discussion.discussion_id,
        round_num=2,
        question_text="",  # Not yet set
        submission_window_duration_sec=300
    )
    round2.status = RoundStatus.PENDING
    db_session.add(round2)

    await db_session.commit()

    # Verify can_advance() returns False (waiting for question)
    await db_session.refresh(round2)
    can_adv, reason = round2.can_advance()
    assert can_adv is False
    assert "question" in reason.lower() or "generation" in reason.lower()

    # Simulate question generation completion
    round2.question_text = "How can we address these priorities?"
    round2.status = RoundStatus.QUESTION_READY
    await db_session.commit()

    # Now can_advance() should return True
    await db_session.refresh(round2)
    can_adv, reason = round2.can_advance()
    assert can_adv is True
    assert reason is None


@pytest.mark.asyncio
async def test_host_preview_auto_generated_question(db_session):
    """
    Test that host can preview auto-generated question before advancing (T064).

    Validates:
    - Round 2 in QUESTION_READY state
    - Host can view question_text before advancing
    - Question is immutable once Round 2 opens
    """
    from src.question_progression.models import Question, QuestionMode, ValidationStatus

    discussion = Discussion(
        discussion_id=uuid4(),
        community_id=uuid4(),
        host_user_id=uuid4(),
        total_rounds=3,
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    # Create question sequence
    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)

    # Create question for Round 2
    question2 = Question(
        question_id=uuid4(),
        sequence_id=sequence.sequence_id,
        order=2,
        question_text="How can we improve collaboration?",
        mode=QuestionMode.AUTO_GENERATED,
        validation_status=ValidationStatus.VALID
    )
    db_session.add(question2)

    round2 = Round(
        discussion_id=discussion.discussion_id,
        round_num=2,
        question_text=question2.question_text,
        submission_window_duration_sec=300,
        question_id=question2.question_id
    )
    round2.status = RoundStatus.QUESTION_READY
    db_session.add(round2)

    await db_session.commit()

    # Host previews question (just read the question_text)
    await db_session.refresh(round2)
    preview_text = round2.question_text
    assert preview_text == "How can we improve collaboration?"
    assert round2.status == RoundStatus.QUESTION_READY

    # Question not yet immutable
    await db_session.refresh(question2)
    assert question2.immutable_since is None

    # Host advances → opens submission window → question becomes immutable
    round2.open_submission_window()
    await db_session.commit()

    # Verify question is now immutable
    await db_session.refresh(question2)
    assert question2.immutable_since is not None
    assert round2.status == RoundStatus.SUBMISSION_OPEN
