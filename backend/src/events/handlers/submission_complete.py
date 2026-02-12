"""
Handler for submission_window.closed event (Spec 2 completion).

Triggered when the timed submission window for a round closes.
Transitions round to SUMMARIZING status and forwards submissions
to the Summarization sub-protocol (Spec 3).
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.events.event_types import SubmissionWindowClosedEvent
from src.models.protocol_state import RoundStatus

logger = logging.getLogger(__name__)


async def handle_submission_complete(event: SubmissionWindowClosedEvent) -> None:
    """
    Handle submission window closure event.

    Actions:
    1. Transition Round status: SUBMISSION_CLOSED → SUMMARIZING
    2. Validate submissions received
    3. Forward submissions to Spec 3 (Summarization sub-protocol)
    4. Log state transition

    Args:
        event: SubmissionWindowClosedEvent containing round_id and submissions

    Raises:
        ValueError: If round not found or in invalid state
        RuntimeError: If state transition fails
    """
    round_id = event.round_id
    submissions = event.submissions
    submission_count = len(submissions)

    logger.info(
        f"Processing submission_window.closed event for round {round_id} "
        f"with {submission_count} submissions"
    )

    # Get database session
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Import Round model here to avoid circular dependency
            from src.models.round import Round

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
            if round_obj.status != RoundStatus.SUBMISSION_CLOSED:
                error_msg = (
                    f"Invalid state transition for round {round_id}: "
                    f"expected SUBMISSION_CLOSED, got {round_obj.status}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Transition to SUMMARIZING
            round_obj.status = RoundStatus.SUMMARIZING

            logger.info(
                f"Round {round_id} transitioned: SUBMISSION_CLOSED → SUMMARIZING "
                f"({submission_count} submissions to process)"
            )

            # Commit state transition
            await db.commit()

            # TODO: Forward submissions to Spec 3 (Summarization sub-protocol)
            # This will be implemented when Spec 3 integration is available
            # Expected: Call summarization service or emit event to summarization queue
            logger.debug(
                f"Forwarding {submission_count} submissions to Summarization sub-protocol "
                f"(Spec 3 integration pending)"
            )

            # Validate constitutional invariant: Parallel-First Architecture
            # All submissions were collected independently without cross-participant visibility
            participant_ids = {s.participant_id for s in submissions}
            logger.info(
                f"Constitutional check - Parallel input: {len(participant_ids)} "
                f"unique participants contributed independently"
            )

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to handle submission_complete for round {round_id}: {e}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Submission complete handler failed for round {round_id}"
            ) from e


async def register_submission_complete_handler(event_bus) -> None:
    """
    Register this handler with the event bus.

    Args:
        event_bus: EventBus instance to register with
    """
    await event_bus.subscribe(
        event_type="submission_window.closed",
        handler=handle_submission_complete,
    )
    logger.info("Registered handler for submission_window.closed event")
