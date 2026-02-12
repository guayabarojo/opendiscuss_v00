"""
End-to-End tests with real Claude API (Phase 10 - Spec 006).

Tests real LLM integration and performance validation with actual Claude API.
Requires ANTHROPIC_API_KEY environment variable and --e2e flag.

Tasks: T093-T096
"""

import asyncio
import os
import time
import statistics
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.models import Discussion, Round, RoundStatus, DiscussionMode
from src.question_progression.models import (
    QuestionSequence,
    Question,
    QuestionProvenance,
    SequenceMode,
    QuestionMode,
    ValidationStatus,
)
from src.question_progression.services.generation import QuestionGenerationService
from src.question_progression.services.sequence import QuestionSequenceService
from src.question_progression.validators import QuestionValidator
from src.events.event_types import (
    SankeyCompleteEvent,
    SankeyGraph,
    ThoughtSpaceSummary,
)


# Skip all tests in this file unless --e2e flag is provided
pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def skip_if_no_api_key():
    """Skip tests if ANTHROPIC_API_KEY is not set."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY environment variable not set")


@pytest.fixture
def mock_sankey_graph():
    """Create realistic Sankey graph for testing."""
    discussion_id = uuid4()
    round_id = uuid4()

    thought_spaces = [
        ThoughtSpaceSummary(
            cluster_id=uuid4(),
            round_id=round_id,
            label_summary="Funding constraints limit program scope and reach",
            member_count=15,
            member_pct=42.0,
            participant_ids=[uuid4() for _ in range(15)]
        ),
        ThoughtSpaceSummary(
            cluster_id=uuid4(),
            round_id=round_id,
            label_summary="Need for better communication and transparency",
            member_count=12,
            member_pct=35.0,
            participant_ids=[uuid4() for _ in range(12)]
        ),
        ThoughtSpaceSummary(
            cluster_id=uuid4(),
            round_id=round_id,
            label_summary="Community engagement requires more volunteers",
            member_count=8,
            member_pct=23.0,
            participant_ids=[uuid4() for _ in range(8)]
        ),
    ]

    return SankeyGraph(
        discussion_id=discussion_id,
        rounds=[round_id],
        nodes=thought_spaces,
        edges=[],
        total_participants=35
    )


# ============================================================================
# T093: Real Claude API Integration Test
# ============================================================================


@pytest.mark.asyncio
async def test_real_claude_api_question_generation(
    db_session,
    skip_if_no_api_key,
    mock_sankey_graph
):
    """
    T093: Test real Claude API call for question generation.

    Verifies:
    - Real Claude API call succeeds
    - Generated question passes validation
    - Provenance recorded correctly
    - Response within 30 seconds
    """
    # Create discussion and round
    discussion = Discussion(
        discussion_id=uuid4(),
        title="Test E2E Discussion",
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are the key priorities for our community?",
        submission_window_duration_sec=300
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Initialize real generation service
    generation_service = QuestionGenerationService()

    # Track latency
    start_time = time.time()

    # Generate question with real Claude API
    result = await generation_service.generate_from_sankey(
        round_num=2,
        previous_questions=["What are the key priorities for our community?"],
        sankey_data=mock_sankey_graph.dict(),
        input_round_id=round1.round_id
    )

    latency_seconds = time.time() - start_time

    # Verify: Response within 30 seconds
    assert latency_seconds < 30, f"Generation took {latency_seconds:.2f}s (expected < 30s)"

    # Verify: Question text generated
    assert "question_text" in result
    assert result["question_text"]
    question_text = result["question_text"]

    print(f"\n✓ Generated question: {question_text}")
    print(f"✓ Latency: {latency_seconds:.2f}s")

    # Verify: Generated question passes validation
    validator = QuestionValidator()
    validation_result = validator.validate(question_text)
    assert validation_result.valid, f"Generated question failed validation: {validation_result.error_message}"

    # Verify: Provenance recorded correctly
    assert "provenance" in result
    provenance = result["provenance"]
    assert provenance["input_round_id"] == round1.round_id
    assert provenance["llm_model"] is not None
    assert provenance["generation_latency_ms"] > 0
    assert provenance["prompt_tokens"] > 0
    assert provenance["completion_tokens"] > 0
    assert provenance["retry_count"] >= 0
    assert provenance["validation_attempts"] >= 1

    print(f"✓ Provenance: model={provenance['llm_model']}, "
          f"tokens={provenance['prompt_tokens']}+{provenance['completion_tokens']}, "
          f"retries={provenance['retry_count']}, "
          f"validation_attempts={provenance['validation_attempts']}")

    # Verify: Sankey hash recorded
    assert "sankey_hash" in result
    assert len(result["sankey_hash"]) == 64  # SHA-256 hex digest


# ============================================================================
# T094: Complete HOST_DEFINED Discussion E2E Test
# ============================================================================


@pytest.mark.asyncio
async def test_complete_host_defined_discussion_e2e(
    db_session,
    skip_if_no_api_key
):
    """
    T094: Test complete HOST_DEFINED discussion flow.

    Flow:
    1. Create discussion with 3 questions
    2. Advance through all rounds
    3. Verify completion

    Time limit: Complete in < 5 minutes
    """
    start_time = time.time()

    # Step 1: Create HOST_DEFINED discussion with 3 questions
    discussion = Discussion(
        discussion_id=uuid4(),
        title="Host-Defined E2E Test",
        mode=DiscussionMode.HOST_DEFINED,
        status="ACTIVE",
        total_rounds=3
    )
    db_session.add(discussion)
    await db_session.commit()

    questions_text = [
        "What are the main challenges facing our community?",
        "How can we improve communication and transparency?",
        "What resources are needed to achieve our goals?"
    ]

    sequence_service = QuestionSequenceService(db_session)
    sequence = await sequence_service.create_host_sequence(
        discussion_id=discussion.discussion_id,
        questions=questions_text
    )

    print(f"\n✓ Created sequence with {len(sequence.questions)} questions")

    # Step 2: Advance through all rounds
    for round_num in range(1, 4):
        # Get next question
        question = await sequence_service.get_next_question(discussion.discussion_id)
        assert question is not None
        assert question.question_text == questions_text[round_num - 1]

        print(f"✓ Round {round_num}: {question.question_text}")

        # Create round (simulating round advancement)
        round_obj = Round(
            discussion_id=discussion.discussion_id,
            round_num=round_num,
            question_text=question.question_text,
            question_id=question.question_id,
            submission_window_duration_sec=300
        )
        round_obj.status = RoundStatus.COMPLETE
        db_session.add(round_obj)

        # Mark question immutable
        await sequence_service.mark_question_immutable(question.question_id)

        # Advance sequence
        await sequence_service.advance_sequence(discussion.discussion_id)

        await db_session.commit()

    # Step 3: Verify completion
    result = await db_session.execute(
        select(QuestionSequence).where(
            QuestionSequence.discussion_id == discussion.discussion_id
        )
    )
    final_sequence = result.scalar_one()

    assert final_sequence.current_index == 3
    assert final_sequence.completion_status.value == "COMPLETED"

    # Verify all questions used
    result = await db_session.execute(
        select(Question).where(Question.sequence_id == final_sequence.sequence_id)
    )
    all_questions = result.scalars().all()
    assert len(all_questions) == 3
    assert all([q.is_immutable() for q in all_questions])

    elapsed_time = time.time() - start_time
    assert elapsed_time < 300, f"Test took {elapsed_time:.2f}s (expected < 300s)"

    print(f"✓ Discussion completed in {elapsed_time:.2f}s")
    print(f"✓ All {len(all_questions)} questions used in sequence")


# ============================================================================
# T095: Complete AUTO_GENERATED Discussion E2E Test
# ============================================================================


@pytest.mark.asyncio
async def test_complete_auto_generated_discussion_e2e(
    db_session,
    skip_if_no_api_key,
    mock_sankey_graph
):
    """
    T095: Test complete AUTO_GENERATED discussion flow.

    Flow:
    1. Create discussion with 1 initial question
    2. Complete Round 1
    3. Trigger real question generation
    4. Advance to Round 2 with auto-generated question

    Verifies:
    - Question generated from Sankey patterns
    - Constitutional constraints enforced
    - Provenance complete

    Time limit: Complete in < 10 minutes (includes LLM calls)
    """
    start_time = time.time()

    # Step 1: Create AUTO_GENERATED discussion with 1 initial question
    discussion = Discussion(
        discussion_id=uuid4(),
        title="Auto-Generated E2E Test",
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE",
        total_rounds=2
    )
    db_session.add(discussion)
    await db_session.commit()

    # Create initial question sequence
    sequence = QuestionSequence(
        discussion_id=discussion.discussion_id,
        mode=SequenceMode.AUTO_GENERATED
    )
    db_session.add(sequence)
    await db_session.commit()

    question1 = Question(
        sequence_id=sequence.sequence_id,
        order=1,
        question_text="What are the biggest challenges facing our community?",
        mode=QuestionMode.HOST_DEFINED,
        validation_status=ValidationStatus.VALID
    )
    db_session.add(question1)
    await db_session.commit()

    print(f"\n✓ Created AUTO_GENERATED discussion with initial question")

    # Step 2: Complete Round 1
    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text=question1.question_text,
        question_id=question1.question_id,
        submission_window_duration_sec=300
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)
    await db_session.commit()

    print(f"✓ Round 1 complete")

    # Step 3: Trigger real question generation from Sankey
    generation_service = QuestionGenerationService()

    generation_start = time.time()

    result = await generation_service.generate_from_sankey(
        round_num=2,
        previous_questions=[question1.question_text],
        sankey_data=mock_sankey_graph.dict(),
        input_round_id=round1.round_id
    )

    generation_latency = time.time() - generation_start

    print(f"✓ Question generated in {generation_latency:.2f}s")
    print(f"  Generated: {result['question_text']}")

    # Verify: Question generated from Sankey patterns
    assert result["question_text"]
    question2_text = result["question_text"]

    # Verify: Constitutional constraints enforced
    validator = QuestionValidator()
    validation_result = validator.validate(question2_text)
    assert validation_result.valid, f"Generated question violated constraints: {validation_result.error_message}"

    print(f"✓ Constitutional constraints enforced")

    # Create Question entity
    question2 = Question(
        sequence_id=sequence.sequence_id,
        order=2,
        question_text=question2_text,
        mode=QuestionMode.AUTO_GENERATED,
        validation_status=ValidationStatus.VALID
    )
    db_session.add(question2)
    await db_session.commit()

    # Create QuestionProvenance
    provenance_data = result["provenance"]
    provenance = QuestionProvenance(
        question_id=question2.question_id,
        input_round_id=provenance_data["input_round_id"],
        generation_timestamp=provenance_data["generation_timestamp"],
        generation_latency_ms=provenance_data["generation_latency_ms"],
        input_sankey_hash=provenance_data["input_sankey_hash"],
        llm_model=provenance_data["llm_model"],
        prompt_tokens=provenance_data["prompt_tokens"],
        completion_tokens=provenance_data["completion_tokens"],
        retry_count=provenance_data["retry_count"],
        validation_attempts=provenance_data["validation_attempts"],
        previous_questions_count=provenance_data["previous_questions_count"]
    )
    db_session.add(provenance)
    await db_session.commit()

    # Verify: Provenance complete
    result_prov = await db_session.execute(
        select(QuestionProvenance).where(
            QuestionProvenance.question_id == question2.question_id
        )
    )
    saved_provenance = result_prov.scalar_one()
    assert saved_provenance.input_round_id == round1.round_id
    assert saved_provenance.llm_model is not None
    assert saved_provenance.generation_latency_ms > 0
    assert saved_provenance.input_sankey_hash == result["sankey_hash"]

    print(f"✓ Provenance recorded: {saved_provenance.llm_model}")

    # Step 4: Advance to Round 2
    round2 = Round(
        discussion_id=discussion.discussion_id,
        round_num=2,
        question_text=question2_text,
        question_id=question2.question_id,
        submission_window_duration_sec=300
    )
    round2.status = RoundStatus.QUESTION_READY
    db_session.add(round2)
    await db_session.commit()

    print(f"✓ Round 2 ready with auto-generated question")

    # Verify final state
    result = await db_session.execute(
        select(Question).where(Question.sequence_id == sequence.sequence_id)
    )
    all_questions = result.scalars().all()
    assert len(all_questions) == 2
    assert all_questions[0].mode == QuestionMode.HOST_DEFINED
    assert all_questions[1].mode == QuestionMode.AUTO_GENERATED

    elapsed_time = time.time() - start_time
    assert elapsed_time < 600, f"Test took {elapsed_time:.2f}s (expected < 600s)"

    print(f"✓ AUTO_GENERATED discussion flow complete in {elapsed_time:.2f}s")


# ============================================================================
# T096: Performance Test - Auto-Generation Latency
# ============================================================================


@pytest.mark.asyncio
async def test_auto_generation_latency_performance(
    db_session,
    skip_if_no_api_key,
    mock_sankey_graph
):
    """
    T096: Test auto-generation latency performance metrics.

    Metrics:
    - p95 latency < 10 seconds (from Sankey complete to question ready)
    - p99 latency < 30 seconds

    Test: Generate 10 questions, measure each latency
    Report: Distribution of latencies
    """
    print("\n" + "="*80)
    print("Performance Test: Auto-Generation Latency")
    print("="*80)

    # Create discussion and round
    discussion = Discussion(
        discussion_id=uuid4(),
        title="Performance Test Discussion",
        mode=DiscussionMode.AUTO_GENERATED,
        status="ACTIVE"
    )
    db_session.add(discussion)

    round1 = Round(
        discussion_id=discussion.discussion_id,
        round_num=1,
        question_text="What are the key priorities?",
        submission_window_duration_sec=300
    )
    round1.status = RoundStatus.COMPLETE
    db_session.add(round1)

    await db_session.commit()

    # Initialize generation service
    generation_service = QuestionGenerationService()

    # Track latencies
    latencies = []
    successful_generations = 0

    print(f"\nGenerating 10 questions to measure latency...\n")

    for i in range(10):
        try:
            start_time = time.time()

            result = await generation_service.generate_from_sankey(
                round_num=i + 2,
                previous_questions=[f"What are question {j}?" for j in range(1, i + 2)],
                sankey_data=mock_sankey_graph.dict(),
                input_round_id=round1.round_id
            )

            latency_seconds = time.time() - start_time
            latencies.append(latency_seconds)
            successful_generations += 1

            print(f"  Generation {i+1}/10: {latency_seconds:.2f}s - {result['question_text'][:60]}...")

        except Exception as e:
            print(f"  Generation {i+1}/10: FAILED - {str(e)}")

    # Calculate statistics
    if latencies:
        mean_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        # Calculate percentiles
        sorted_latencies = sorted(latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        p99_index = int(len(sorted_latencies) * 0.99)
        p95_latency = sorted_latencies[p95_index] if p95_index < len(sorted_latencies) else sorted_latencies[-1]
        p99_latency = sorted_latencies[p99_index] if p99_index < len(sorted_latencies) else sorted_latencies[-1]

        # Report distribution
        print("\n" + "-"*80)
        print("Latency Distribution:")
        print("-"*80)
        print(f"  Successful generations: {successful_generations}/10")
        print(f"  Mean:    {mean_latency:.2f}s")
        print(f"  Median:  {median_latency:.2f}s")
        print(f"  Min:     {min_latency:.2f}s")
        print(f"  Max:     {max_latency:.2f}s")
        print(f"  p95:     {p95_latency:.2f}s")
        print(f"  p99:     {p99_latency:.2f}s")
        print("-"*80)

        # Verify: p95 < 10 seconds
        assert p95_latency < 10.0, f"p95 latency {p95_latency:.2f}s exceeds 10s threshold"
        print(f"✓ p95 latency {p95_latency:.2f}s < 10s threshold")

        # Verify: p99 < 30 seconds
        assert p99_latency < 30.0, f"p99 latency {p99_latency:.2f}s exceeds 30s threshold"
        print(f"✓ p99 latency {p99_latency:.2f}s < 30s threshold")

    else:
        pytest.fail("No successful generations to measure latency")

    print("="*80 + "\n")
