"""
Event handlers for Question Progression Protocol.

Subscribes to:
- sankey.complete (from Spec 5): Triggers autonomous question generation

Emits:
- question.ready: Question generated and validated, ready for use
- question.generation_failed: Generation failed after retries, fallback to manual
"""

import asyncio
import time
import uuid
from uuid import UUID
from typing import Dict, Any, Optional
from pydantic import ValidationError as PydanticValidationError

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.events.event_types import (
    SankeyCompleteEvent,
    QuestionReadyEvent,
    QuestionGenerationFailedEvent
)
from src.models import Discussion, Round, DiscussionMode, RoundStatus
from src.question_progression.models import (
    QuestionSequence,
    Question,
    QuestionMode,
    ValidationStatus,
    SequenceMode
)
from src.question_progression.services.generation import (
    QuestionGenerationService,
    QuestionGenerationError,
    QuestionValidationExhausted
)
from src.question_progression.services.provenance import ProvenanceTracker
from src.logging_config import get_logger

logger = get_logger(__name__)


# T079: Event Handler Retry Wrapper with Exponential Backoff


class EventHandlerWithRetry:
    """
    Wrapper for event handlers with exponential backoff retry logic.

    Features:
    - Configurable max retries (default 3)
    - Exponential backoff: 2s, 4s, 8s
    - Structured logging with trace IDs
    - Failure event emission after exhaustion
    """

    def __init__(self, max_retries: int = 3, base_delay_seconds: float = 2.0):
        """
        Initialize retry handler.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay_seconds: Base delay for exponential backoff
        """
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds

    async def execute_with_retry(
        self,
        handler_func,
        event: SankeyCompleteEvent,
        db_session: AsyncSession,
        event_bus,
        trace_id: str,
    ) -> None:
        """
        Execute handler with retry logic.

        Args:
            handler_func: Async handler function to execute
            event: SankeyCompleteEvent payload
            db_session: Database session
            event_bus: Event bus for emitting failure events
            trace_id: Correlation ID for logging
        """
        retry_count = 0
        last_error: Optional[Exception] = None

        while retry_count <= self.max_retries:
            try:
                logger.info(
                    f"[{trace_id}] Executing event handler (attempt {retry_count + 1}/{self.max_retries + 1})",
                    extra={
                        "trace_id": trace_id,
                        "attempt": retry_count + 1,
                        "max_attempts": self.max_retries + 1,
                    }
                )
                start_time = time.perf_counter()

                await handler_func(event, db_session, event_bus)

                execution_time_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    f"[{trace_id}] Handler execution successful",
                    extra={
                        "trace_id": trace_id,
                        "execution_time_ms": execution_time_ms,
                        "retry_count": retry_count,
                        "outcome": "success",
                    }
                )
                return

            except Exception as e:
                last_error = e
                retry_count += 1

                logger.warning(
                    f"[{trace_id}] Handler execution failed (attempt {retry_count}/{self.max_retries + 1}): {e}",
                    extra={
                        "trace_id": trace_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "retry_count": retry_count,
                    },
                    exc_info=True,
                )

                if retry_count <= self.max_retries:
                    delay = self.base_delay_seconds * (2 ** (retry_count - 1))
                    logger.info(
                        f"[{trace_id}] Retrying in {delay}s...",
                        extra={
                            "trace_id": trace_id,
                            "delay_seconds": delay,
                            "next_attempt": retry_count + 1,
                        }
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted - emit failure event
        logger.error(
            f"[{trace_id}] Handler execution failed after {self.max_retries + 1} attempts",
            extra={
                "trace_id": trace_id,
                "last_error": str(last_error),
                "retry_count": self.max_retries,
                "outcome": "failure",
            }
        )

        # Emit handler.failure event (question.generation_failed)
        try:
            discussion_id = event.sankey_graph.discussion_id
            round_id = event.round_id

            failure_event = QuestionGenerationFailedEvent(
                round_id=round_id,
                discussion_id=discussion_id,
                retry_count=self.max_retries,
                last_error=str(last_error),
            )

            await event_bus.emit("question.generation_failed", failure_event)
            logger.info(
                f"[{trace_id}] Emitted question.generation_failed event after retry exhaustion",
                extra={"trace_id": trace_id}
            )
        except Exception as emit_error:
            logger.error(
                f"[{trace_id}] Failed to emit failure event: {emit_error}",
                extra={"trace_id": trace_id},
                exc_info=True
            )


# T076: Payload Validation


def validate_sankey_complete_payload(event: SankeyCompleteEvent, trace_id: str) -> None:
    """
    Validate sankey.complete event payload structure.

    Required fields:
    - discussion_id
    - round_id
    - sankey_graph (with columns, nodes, flows)

    Args:
        event: SankeyCompleteEvent to validate
        trace_id: Correlation ID for logging

    Raises:
        ValueError: If payload is malformed
    """
    logger.debug(
        f"[{trace_id}] Validating sankey.complete payload",
        extra={
            "trace_id": trace_id,
            "event_type": "sankey.complete",
        }
    )

    # Validate required fields: discussion_id, round_id, sankey_graph
    if not event.sankey_graph.discussion_id:
        error_msg = "Missing required field: discussion_id"
        logger.error(
            f"[{trace_id}] Payload validation failed: {error_msg}",
            extra={
                "trace_id": trace_id,
                "validation_error": error_msg,
                "payload_summary": str(event)[:200],
            }
        )
        raise ValueError(error_msg)

    if not event.round_id:
        error_msg = "Missing required field: round_id"
        logger.error(
            f"[{trace_id}] Payload validation failed: {error_msg}",
            extra={
                "trace_id": trace_id,
                "validation_error": error_msg,
            }
        )
        raise ValueError(error_msg)

    # Validate sankey_graph structure: columns, nodes, flows
    if not hasattr(event.sankey_graph, 'nodes') or not event.sankey_graph.nodes:
        error_msg = "sankey_graph must contain at least one node"
        logger.error(
            f"[{trace_id}] Payload validation failed: {error_msg}",
            extra={
                "trace_id": trace_id,
                "validation_error": error_msg,
                "node_count": 0,
            }
        )
        raise ValueError(error_msg)

    if not hasattr(event.sankey_graph, 'edges'):
        error_msg = "sankey_graph must contain edges list (can be empty)"
        logger.error(
            f"[{trace_id}] Payload validation failed: {error_msg}",
            extra={
                "trace_id": trace_id,
                "validation_error": error_msg,
            }
        )
        raise ValueError(error_msg)

    # Validate each node has required fields
    for idx, node in enumerate(event.sankey_graph.nodes):
        if not hasattr(node, 'cluster_id') or not node.cluster_id:
            error_msg = f"Node {idx} missing required field: cluster_id"
            logger.error(
                f"[{trace_id}] Payload validation failed: {error_msg}",
                extra={
                    "trace_id": trace_id,
                    "validation_error": error_msg,
                    "node_index": idx,
                }
            )
            raise ValueError(error_msg)

        if not hasattr(node, 'label_summary'):
            error_msg = f"Node {idx} missing required field: label_summary"
            logger.error(
                f"[{trace_id}] Payload validation failed: {error_msg}",
                extra={
                    "trace_id": trace_id,
                    "validation_error": error_msg,
                    "node_index": idx,
                }
            )
            raise ValueError(error_msg)

        if not hasattr(node, 'member_count'):
            error_msg = f"Node {idx} missing required field: member_count"
            logger.error(
                f"[{trace_id}] Payload validation failed: {error_msg}",
                extra={
                    "trace_id": trace_id,
                    "validation_error": error_msg,
                    "node_index": idx,
                }
            )
            raise ValueError(error_msg)

    # Validate flows structure
    for idx, flow in enumerate(event.sankey_graph.edges):
        if not hasattr(flow, 'source_cluster_id') or not flow.source_cluster_id:
            error_msg = f"Flow {idx} missing required field: source_cluster_id"
            logger.error(
                f"[{trace_id}] Payload validation failed: {error_msg}",
                extra={
                    "trace_id": trace_id,
                    "validation_error": error_msg,
                    "flow_index": idx,
                }
            )
            raise ValueError(error_msg)

        if not hasattr(flow, 'target_cluster_id') or not flow.target_cluster_id:
            error_msg = f"Flow {idx} missing required field: target_cluster_id"
            logger.error(
                f"[{trace_id}] Payload validation failed: {error_msg}",
                extra={
                    "trace_id": trace_id,
                    "validation_error": error_msg,
                    "flow_index": idx,
                }
            )
            raise ValueError(error_msg)

        if not hasattr(flow, 'participant_count'):
            error_msg = f"Flow {idx} missing required field: participant_count"
            logger.error(
                f"[{trace_id}] Payload validation failed: {error_msg}",
                extra={
                    "trace_id": trace_id,
                    "validation_error": error_msg,
                    "flow_index": idx,
                }
            )
            raise ValueError(error_msg)

    logger.info(
        f"[{trace_id}] Payload validation successful",
        extra={
            "trace_id": trace_id,
            "node_count": len(event.sankey_graph.nodes),
            "flow_count": len(event.sankey_graph.edges),
            "total_participants": event.sankey_graph.total_participants,
        }
    )


async def handle_sankey_complete(
    event: SankeyCompleteEvent,
    db_session: AsyncSession,
    event_bus
) -> None:
    """
    Handle sankey.complete event by generating next question (AUTO mode only).

    Flow:
    1. Validate event payload (T076)
    2. Check discussion mode (only AUTO_GENERATED)
    3. Get previous questions for context
    4. Call QuestionGenerationService
    5. Create Question entity with provenance
    6. Create next Round with QUESTION_READY status
    7. Emit question.ready or question.generation_failed event (T077/T078)

    Args:
        event: SankeyCompleteEvent payload
        db_session: Database session
        event_bus: Event bus for emitting events

    Raises:
        Exception: Logs and emits failure event, does not propagate
    """
    # T080: Generate trace ID for correlation
    trace_id = str(uuid.uuid4())[:8]

    round_id = event.round_id
    sankey_graph = event.sankey_graph
    discussion_id = sankey_graph.discussion_id

    # T080: Log event receipt with trace_id
    logger.info(
        f"[{trace_id}] Event received: sankey.complete",
        extra={
            "trace_id": trace_id,
            "event_type": "sankey.complete",
            "discussion_id": str(discussion_id),
            "round_id": str(round_id),
            "event_timestamp": event.timestamp.isoformat(),
        }
    )

    # T080: Track handler execution time
    start_time = time.perf_counter()

    try:
        # T076: Validate event payload
        validate_sankey_complete_payload(event, trace_id)

        # Fetch discussion with question sequence
        result = await db_session.execute(
            select(Discussion)
            .where(Discussion.discussion_id == discussion_id)
            .options(selectinload(Discussion.question_sequence))
        )
        discussion = result.scalar_one_or_none()

        if not discussion:
            logger.error(
                "Discussion not found for sankey.complete event",
                extra={"discussion_id": str(discussion_id)}
            )
            return

        # Only process AUTO_GENERATED discussions
        if discussion.mode != DiscussionMode.AUTO_GENERATED:
            logger.debug(
                "Skipping sankey.complete: discussion is HOST_DEFINED",
                extra={"discussion_id": str(discussion_id), "mode": discussion.mode.value}
            )
            return

        # Get current round
        result = await db_session.execute(
            select(Round).where(Round.round_id == round_id)
        )
        current_round = result.scalar_one_or_none()

        if not current_round:
            logger.error(
                "Round not found for sankey.complete event",
                extra={"round_id": str(round_id)}
            )
            return

        # Get question sequence
        if not discussion.question_sequence:
            logger.error(
                "Question sequence not found for AUTO_GENERATED discussion",
                extra={"discussion_id": str(discussion_id)}
            )
            return

        sequence = discussion.question_sequence

        # Get previous questions for context
        previous_questions = [q.question_text for q in sorted(sequence.questions, key=lambda x: x.question_order)]

        logger.info(
            "Starting auto-question generation",
            extra={
                "discussion_id": str(discussion_id),
                "current_round_num": current_round.round_num,
                "previous_questions_count": len(previous_questions)
            }
        )

        # Prepare Sankey data for generation
        sankey_data = _prepare_sankey_data(sankey_graph, current_round.round_num)

        # Generate question
        generation_service = QuestionGenerationService()
        result = await generation_service.generate_from_sankey(
            round_num=current_round.round_num,
            previous_questions=previous_questions,
            sankey_data=sankey_data,
            input_round_id=round_id
        )

        question_text = result["question_text"]
        provenance_data = result["provenance"]

        # Create Question entity
        next_order = len(sequence.questions) + 1
        question = Question(
            sequence_id=sequence.sequence_id,
            order=next_order,
            question_text=question_text,
            mode=QuestionMode.AUTO_GENERATED,
            validation_status=ValidationStatus.VALID
        )

        db_session.add(question)
        await db_session.flush()  # Get question_id

        # Create provenance record
        provenance_tracker = ProvenanceTracker(db_session)
        await provenance_tracker.record(
            question_id=question.question_id,
            provenance_data=provenance_data
        )

        # Create next round with QUESTION_READY status
        next_round_num = current_round.round_num + 1
        next_round = Round(
            discussion_id=discussion_id,
            round_num=next_round_num,
            question_text=question_text,
            submission_window_duration_sec=current_round.submission_window_duration_sec,
            question_id=question.question_id
        )
        next_round.status = RoundStatus.QUESTION_READY
        db_session.add(next_round)

        await db_session.commit()
        await db_session.refresh(question)
        await db_session.refresh(next_round)

        # T080: Calculate execution time
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"[{trace_id}] Auto-generated question ready",
            extra={
                "trace_id": trace_id,
                "discussion_id": str(discussion_id),
                "question_id": str(question.question_id),
                "next_round_id": str(next_round.round_id),
                "next_round_num": next_round_num,
                "question_text": question_text,
                "execution_time_ms": execution_time_ms,
                "outcome": "success",
            }
        )

        # T077: Emit question.ready event
        await event_bus.emit(
            "question.ready",
            QuestionReadyEvent(
                round_id=next_round.round_id,
                question_id=question.question_id,
                question_text=question_text
            )
        )

        logger.info(
            f"[{trace_id}] Emitted question.ready event",
            extra={
                "trace_id": trace_id,
                "question_id": str(question.question_id),
                "round_id": str(next_round.round_id),
            }
        )

    except (QuestionGenerationError, QuestionValidationExhausted) as e:
        # T080: Calculate execution time on failure
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Generation failed after retries
        logger.error(
            f"[{trace_id}] Question generation failed",
            extra={
                "trace_id": trace_id,
                "discussion_id": str(discussion_id),
                "round_id": str(round_id),
                "error_type": type(e).__name__,
                "error": str(e),
                "execution_time_ms": execution_time_ms,
                "outcome": "failure",
            },
            exc_info=True
        )

        try:
            # Create next round with QUESTION_GENERATION_FAILED status
            next_round_num = current_round.round_num + 1
            next_round = Round(
                discussion_id=discussion_id,
                round_num=next_round_num,
                question_text="",  # Empty until host provides manual question
                submission_window_duration_sec=current_round.submission_window_duration_sec
            )
            next_round.status = RoundStatus.QUESTION_GENERATION_FAILED
            db_session.add(next_round)
            await db_session.commit()
            await db_session.refresh(next_round)

            # T078: Emit question.generation_failed event with detailed metadata
            await event_bus.emit(
                "question.generation_failed",
                QuestionGenerationFailedEvent(
                    round_id=next_round.round_id,
                    discussion_id=discussion_id,
                    retry_count=3,  # Max retries from QuestionGenerationService
                    last_error=str(e)
                )
            )

            logger.info(
                f"[{trace_id}] Emitted question.generation_failed event",
                extra={
                    "trace_id": trace_id,
                    "discussion_id": str(discussion_id),
                    "round_id": str(next_round.round_id),
                    "round_num": next_round_num,
                    "error_type": type(e).__name__,
                }
            )

        except Exception as inner_e:
            logger.error(
                "Failed to create QUESTION_GENERATION_FAILED round",
                extra={
                    "discussion_id": str(discussion_id),
                    "error": str(inner_e)
                },
                exc_info=True
            )

    except Exception as e:
        # T080: Calculate execution time on unexpected error
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Unexpected error
        logger.error(
            f"[{trace_id}] Unexpected error handling sankey.complete event",
            extra={
                "trace_id": trace_id,
                "discussion_id": str(discussion_id),
                "round_id": str(round_id),
                "error_type": type(e).__name__,
                "error": str(e),
                "execution_time_ms": execution_time_ms,
                "outcome": "failure",
            },
            exc_info=True
        )
        raise  # Re-raise for retry logic


def _prepare_sankey_data(sankey_graph, current_round_num: int) -> Dict[str, Any]:
    """
    Convert SankeyGraph event payload to generation service format.

    Args:
        sankey_graph: SankeyGraph from event payload
        current_round_num: Current round number

    Returns:
        Dictionary with nodes, flows, dropout data
    """
    # Extract nodes (thought spaces)
    nodes = [
        {
            "label_summary": node.label_summary,
            "member_count": node.member_count,
            "member_pct": node.member_pct
        }
        for node in sankey_graph.nodes
    ]

    # Extract flows (edges)
    flows = [
        {
            "source_label": _get_node_label(sankey_graph.nodes, edge.source_cluster_id),
            "target_label": _get_node_label(sankey_graph.nodes, edge.target_cluster_id),
            "participant_count": edge.participant_count
        }
        for edge in sankey_graph.edges
    ]

    # Compute dropout (participants who didn't continue)
    # For Round 1, there's no previous round, so no dropout
    if current_round_num == 1:
        dropout_count = 0
    else:
        # Calculate dropout from edges (participants who moved vs total in previous round)
        # This is a simplification - actual implementation depends on data structure
        dropout_count = 0  # TODO: Calculate from actual data

    return {
        "nodes": nodes,
        "flows": flows,
        "dropout_count": dropout_count,
        "total_participants": sankey_graph.total_participants
    }


def _get_node_label(nodes, cluster_id: UUID) -> str:
    """Get label for a cluster by ID."""
    for node in nodes:
        if node.cluster_id == cluster_id:
            return node.label_summary
    return "Unknown"


async def register_handlers(event_bus, db_session_factory) -> None:
    """
    Register all question progression event handlers with retry logic (T079).

    Args:
        event_bus: EventBus instance
        db_session_factory: Factory function for creating DB sessions
    """
    # T079: Create retry handler with exponential backoff
    retry_handler = EventHandlerWithRetry(
        max_retries=3,
        base_delay_seconds=2.0,
    )

    async def wrapped_sankey_handler(event: SankeyCompleteEvent) -> None:
        """
        Wrapper to inject DB session and add retry logic (T079).

        Features:
        - Exponential backoff: 2s, 4s, 8s
        - Structured logging with trace IDs
        - Failure event emission after exhaustion
        """
        # Generate trace ID for this event
        trace_id = str(uuid.uuid4())[:8]

        # T080: Log event receipt
        logger.info(
            f"[{trace_id}] Received event: sankey.complete",
            extra={
                "trace_id": trace_id,
                "event_type": "sankey.complete",
                "discussion_id": str(event.sankey_graph.discussion_id),
                "round_id": str(event.round_id),
                "timestamp": event.timestamp.isoformat(),
            }
        )

        async with db_session_factory() as session:
            # T079: Execute with retry logic
            await retry_handler.execute_with_retry(
                handler_func=handle_sankey_complete,
                event=event,
                db_session=session,
                event_bus=event_bus,
                trace_id=trace_id,
            )

    await event_bus.subscribe("sankey.complete", wrapped_sankey_handler)
    logger.info("Registered question progression event handlers with retry logic")
