"""
Contract tests for Spec 5 → Spec 6 event integration.

Validates event payloads against AsyncAPI schema.
"""

import pytest
from uuid import uuid4
from datetime import datetime

from src.events.event_types import (
    SankeyCompleteEvent,
    SankeyGraph,
    ThoughtSpaceSummary,
    FlowEdge,
    QuestionReadyEvent,
    QuestionGenerationFailedEvent
)


def test_valid_sankey_complete_payload():
    """Test valid sankey.complete event structure."""
    discussion_id = uuid4()
    round_id = uuid4()
    
    thought_space = ThoughtSpaceSummary(
        cluster_id=uuid4(),
        round_id=round_id,
        label_summary="Funding constraints",
        member_count=12,
        member_pct=40.0,
        participant_ids=[uuid4() for _ in range(12)]
    )
    
    sankey_graph = SankeyGraph(
        discussion_id=discussion_id,
        rounds=[round_id],
        nodes=[thought_space],
        edges=[],
        total_participants=30
    )
    
    event = SankeyCompleteEvent(
        round_id=round_id,
        sankey_graph=sankey_graph,
        timestamp=datetime.utcnow()
    )
    
    assert event.round_id == round_id
    assert event.sankey_graph.discussion_id == discussion_id


def test_valid_question_ready_payload():
    """Test valid question.ready event structure."""
    event = QuestionReadyEvent(
        round_id=uuid4(),
        question_id=uuid4(),
        question_text="What are the main challenges?",
        timestamp=datetime.utcnow()
    )
    
    assert event.question_text is not None


def test_valid_generation_failed_payload():
    """Test valid question.generation_failed event structure."""
    event = QuestionGenerationFailedEvent(
        round_id=uuid4(),
        discussion_id=uuid4(),
        retry_count=3,
        last_error="Validation failed",
        timestamp=datetime.utcnow()
    )
    
    assert event.retry_count == 3
