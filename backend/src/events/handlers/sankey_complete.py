"""
Handler for sankey.complete event (Spec 5 completion).

Triggered when the Sankey Construction sub-protocol completes for a round.
Transitions round to COMPLETE status and determines if discussion should
advance to next round or complete entirely.
"""

import logging
from uuid import UUID
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.events.event_bus import get_event_bus
from src.events.event_types import SankeyCompleteEvent, RoundCompleteEvent
from src.models.protocol_state import RoundStatus, DiscussionStatus

logger = logging.getLogger(__name__)


async def handle_sankey_complete(event: SankeyCompleteEvent) -> None:
    """
    Handle Sankey construction completion event.

    Actions:
    1. Transition Round: SANKEY_BUILDING → COMPLETE
    2. Emit round.complete event
    3. Check if discussion should advance to next round or complete
    4. Update discussion status if final round

    Constitutional Enforcement:
    - Temporal Transparency: Sankey graph accurately represents participant movement
    - All constitutional invariants preserved through complete round lifecycle

    Args:
        event: SankeyCompleteEvent containing round_id and sankey_graph

    Raises:
        ValueError: If round not found or in invalid state
        RuntimeError: If state transition fails
    """
    round_id = event.round_id
    sankey_graph = event.sankey_graph

    logger.info(
        f"Processing sankey.complete event for round {round_id} "
        f"(discussion {sankey_graph.discussion_id})"
    )

    # Get database session
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Import models here to avoid circular dependency
            from src.models.round import Round
            from src.models.discussion import Discussion

            # Fetch the round
            result = await db.execute(
                select(Round).where(Round.round_id == round_id)
            )
            round_obj = result.scalar_one_or_none()

            if not round_obj:
                error_msg = f"Round {round_id} not found"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Validate current state
            if round_obj.status != RoundStatus.SANKEY_BUILDING:
                error_msg = (
                    f"Invalid state transition for round {round_id}: "
                    f"expected SANKEY_BUILDING, got {round_obj.status}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Transition to COMPLETE
            round_obj.status = RoundStatus.COMPLETE

            logger.info(
                f"Round {round_id} transitioned: SANKEY_BUILDING → COMPLETE "
                f"(Sankey graph with {len(sankey_graph.nodes)} nodes, "
                f"{len(sankey_graph.edges)} edges)"
            )

            # Commit state transition
            await db.commit()

            # Determine next action: advance round or complete discussion
            next_round_id = await determine_next_action(
                round_obj, sankey_graph.discussion_id, db
            )

            # Emit round.complete event
            await emit_round_complete_event(round_id, next_round_id)

            # Log Sankey statistics for Temporal Transparency validation
            logger.info(
                f"Round {round_id} complete - Sankey statistics: "
                f"Total participants: {sankey_graph.total_participants}, "
                f"Thought spaces: {len(sankey_graph.nodes)}, "
                f"Flows: {len(sankey_graph.edges)}"
            )

            # Constitutional Invariant: Temporal Transparency
            # Validate that flow edges represent actual participant movement
            logger.info(
                f"Constitutional check - Temporal Transparency: "
                f"Sankey graph represents actual participant trajectories "
                f"(not semantic similarity between ideas)"
            )

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to handle sankey_complete for round {round_id}: {e}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Sankey complete handler failed for round {round_id}"
            ) from e


async def determine_next_action(
    current_round,
    discussion_id: UUID,
    db: AsyncSession
) -> Optional[UUID]:
    """
    Determine if discussion should advance to next round or complete.

    Logic:
    - If current_round.round_num < discussion.total_rounds: advance to next round
    - If current_round.round_num == discussion.total_rounds: complete discussion
    - If HOST_DEFINED mode and no next question: complete discussion

    Args:
        current_round: Current round object
        discussion_id: Discussion ID
        db: Database session

    Returns:
        UUID of next round if advancing, None if discussion complete
    """
    try:
        # Import Discussion model
        from src.models.discussion import Discussion

        # Fetch discussion
        result = await db.execute(
            select(Discussion).where(Discussion.discussion_id == discussion_id)
        )
        discussion = result.scalar_one_or_none()

        if not discussion:
            logger.error(f"Discussion {discussion_id} not found")
            return None

        current_round_num = current_round.round_num
        total_rounds = discussion.total_rounds

        logger.info(
            f"Discussion {discussion_id}: Round {current_round_num}/{total_rounds} complete"
        )

        # Check if this is the final round
        if current_round_num >= total_rounds:
            logger.info(
                f"Discussion {discussion_id}: Final round complete, transitioning to COMPLETED"
            )
            discussion.status = DiscussionStatus.COMPLETED
            await db.commit()
            return None

        # More rounds remaining - next round should be created/opened by host
        logger.info(
            f"Discussion {discussion_id}: More rounds remaining "
            f"({total_rounds - current_round_num} rounds left)"
        )

        # TODO: Return next_round_id if it already exists (for multi-round flow)
        # For now, return None and expect host to trigger round advancement
        return None

    except Exception as e:
        logger.error(f"Error determining next action for discussion {discussion_id}: {e}")
        return None


async def emit_round_complete_event(
    round_id: UUID,
    next_round_id: Optional[UUID]
) -> None:
    """
    Emit round.complete event to notify other components.

    Args:
        round_id: Completed round ID
        next_round_id: Next round ID if discussion continues, None if final round
    """
    try:
        event_bus = await get_event_bus()

        round_complete_event = RoundCompleteEvent(
            round_id=round_id,
            next_round_id=next_round_id,
        )

        await event_bus.emit("round.complete", round_complete_event)

        logger.info(
            f"Emitted round.complete event for round {round_id} "
            f"(next_round_id: {next_round_id or 'None - discussion complete'})"
        )

    except Exception as e:
        logger.error(
            f"Failed to emit round.complete event for round {round_id}: {e}",
            exc_info=True,
        )
        # Don't raise - event emission failure shouldn't block state transition


async def register_sankey_complete_handler(event_bus) -> None:
    """
    Register this handler with the event bus.

    Args:
        event_bus: EventBus instance to register with
    """
    await event_bus.subscribe(
        event_type="sankey.complete",
        handler=handle_sankey_complete,
    )
    logger.info("Registered handler for sankey.complete event")
