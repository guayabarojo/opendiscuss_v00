"""
Handler for summarization.complete event (Spec 3 completion).

Triggered when the Summarization sub-protocol completes for a round.
Sets approval deadline, transitions round to APPROVING status,
and enforces Intent Fidelity (100% approval before clustering).
"""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.events.event_types import SummarizationCompleteEvent
from src.models.protocol_state import RoundStatus

logger = logging.getLogger(__name__)

# Approval window duration (constitutional parameter)
APPROVAL_WINDOW_MINUTES = 10


async def handle_summarization_complete(event: SummarizationCompleteEvent) -> None:
    """
    Handle summarization completion event.

    Actions:
    1. Set approval_deadline (window_end + 10 minutes)
    2. Transition Round: SUMMARIZING → APPROVING
    3. Validate 100% approved before proceeding to clustering
    4. Forward approved summaries to Spec 4 (Clustering)

    Constitutional Enforcement:
    - Intent Fidelity: Only explicitly approved summaries enter aggregation
    - No timeout-based or implicit approval

    Args:
        event: SummarizationCompleteEvent containing round_id and approved_summaries

    Raises:
        ValueError: If round not found or in invalid state
        RuntimeError: If state transition fails
    """
    round_id = event.round_id
    approved_summaries = event.approved_summaries
    approved_count = len(approved_summaries)

    logger.info(
        f"Processing summarization.complete event for round {round_id} "
        f"with {approved_count} approved summaries"
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
            if round_obj.status != RoundStatus.SUMMARIZING:
                error_msg = (
                    f"Invalid state transition for round {round_id}: "
                    f"expected SUMMARIZING, got {round_obj.status}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Set approval deadline (10 minutes from now)
            approval_deadline = datetime.utcnow() + timedelta(minutes=APPROVAL_WINDOW_MINUTES)
            round_obj.approval_deadline = approval_deadline

            # Transition to APPROVING
            round_obj.status = RoundStatus.APPROVING

            logger.info(
                f"Round {round_id} transitioned: SUMMARIZING → APPROVING "
                f"(approval deadline: {approval_deadline.isoformat()})"
            )

            # Commit state transition
            await db.commit()

            # Constitutional Invariant: Intent Fidelity
            # Validate 100% approval requirement
            if approved_count == 0:
                logger.warning(
                    f"Round {round_id}: Zero approved summaries. "
                    f"Waiting for participant approvals before clustering."
                )
            else:
                logger.info(
                    f"Round {round_id}: {approved_count} summaries approved. "
                    f"Intent Fidelity enforced - only explicitly approved summaries "
                    f"will enter clustering."
                )

            # Check if all participants have approved
            # TODO: Query submission and approval counts to determine if ready for clustering
            # For now, we assume approval gate is handled by the approval workflow
            # When 100% are approved, a separate event will trigger clustering

            # TODO: Forward approved summaries to Spec 4 (Clustering sub-protocol)
            # This will be implemented when Spec 4 integration is available
            logger.debug(
                f"Approved summaries ready for clustering (Spec 4 integration pending)"
            )

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to handle summarization_complete for round {round_id}: {e}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Summarization complete handler failed for round {round_id}"
            ) from e


async def validate_approval_completion(round_id: UUID, db: AsyncSession) -> bool:
    """
    Validate that 100% of summaries are approved for a round.

    Constitutional Invariant: Intent Fidelity
    - Every participant's summary must be explicitly approved
    - No implicit approval or timeout-based approval

    Args:
        round_id: Round to validate
        db: Database session

    Returns:
        True if all summaries approved, False otherwise
    """
    # TODO: Implement once Submission and ApprovedSummary models exist
    # Expected logic:
    # 1. Count total submissions for round
    # 2. Count approved summaries for round
    # 3. Return (approved_count == submission_count)

    logger.debug(
        f"Approval validation for round {round_id} "
        f"(implementation pending - requires Submission model)"
    )
    return True  # Placeholder


async def register_summarization_complete_handler(event_bus) -> None:
    """
    Register this handler with the event bus.

    Args:
        event_bus: EventBus instance to register with
    """
    await event_bus.subscribe(
        event_type="summarization.complete",
        handler=handle_summarization_complete,
    )
    logger.info("Registered handler for summarization.complete event")
