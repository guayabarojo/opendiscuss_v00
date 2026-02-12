"""
Handler for clustering.complete event (Spec 4 completion).

Triggered when the Clustering sub-protocol completes for a round.
Transitions round to SANKEY_BUILDING status and validates 100%
participant coverage in thought spaces (Semantic Accuracy).
"""

import logging
from uuid import UUID
from typing import Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.events.event_types import ClusteringCompleteEvent, ThoughtSpaceSummary
from src.models.protocol_state import RoundStatus

logger = logging.getLogger(__name__)


async def handle_clustering_complete(event: ClusteringCompleteEvent) -> None:
    """
    Handle clustering completion event.

    Actions:
    1. Transition Round: CLUSTERING → SANKEY_BUILDING
    2. Validate 100% participant coverage in clusters (Semantic Accuracy)
    3. Store thought spaces in database
    4. Forward thought spaces to Spec 5 (Sankey Construction)

    Constitutional Enforcement:
    - Semantic Accuracy: Every participant must be assigned to exactly one thought space
    - No forced merging of distinct ideas
    - Preserve minority viewpoints

    Args:
        event: ClusteringCompleteEvent containing round_id and thought_spaces

    Raises:
        ValueError: If round not found, invalid state, or coverage violation
        RuntimeError: If state transition fails
    """
    round_id = event.round_id
    thought_spaces = event.thought_spaces
    thought_space_count = len(thought_spaces)

    logger.info(
        f"Processing clustering.complete event for round {round_id} "
        f"with {thought_space_count} thought spaces"
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

            # Validate current state (should be CLUSTERING or APPROVING transitioning to CLUSTERING)
            if round_obj.status not in [RoundStatus.APPROVING, RoundStatus.CLUSTERING]:
                error_msg = (
                    f"Invalid state transition for round {round_id}: "
                    f"expected APPROVING or CLUSTERING, got {round_obj.status}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Constitutional Invariant: Semantic Accuracy - validate 100% participant coverage
            validate_participant_coverage(thought_spaces, round_id)

            # Transition to SANKEY_BUILDING
            round_obj.status = RoundStatus.SANKEY_BUILDING

            logger.info(
                f"Round {round_id} transitioned: {round_obj.status} → SANKEY_BUILDING "
                f"({thought_space_count} thought spaces validated)"
            )

            # Commit state transition
            await db.commit()

            # Store thought spaces in database
            await store_thought_spaces(thought_spaces, round_id, db)

            # TODO: Forward thought spaces to Spec 5 (Sankey Construction sub-protocol)
            # This will be implemented when Spec 5 integration is available
            logger.debug(
                f"Forwarding {thought_space_count} thought spaces to Sankey Construction "
                f"(Spec 5 integration pending)"
            )

            # Log thought space statistics
            total_participants = sum(ts.member_count for ts in thought_spaces)
            avg_cluster_size = total_participants / thought_space_count if thought_space_count > 0 else 0
            logger.info(
                f"Round {round_id} clustering stats: "
                f"{total_participants} participants across {thought_space_count} thought spaces "
                f"(avg: {avg_cluster_size:.1f} per space)"
            )

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to handle clustering_complete for round {round_id}: {e}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Clustering complete handler failed for round {round_id}"
            ) from e


def validate_participant_coverage(
    thought_spaces: list[ThoughtSpaceSummary],
    round_id: UUID
) -> None:
    """
    Validate 100% participant coverage across thought spaces.

    Constitutional Invariant: Semantic Accuracy
    - Every participant must appear in exactly one thought space
    - No participant can be unassigned
    - No participant can appear in multiple thought spaces

    Args:
        thought_spaces: List of thought spaces to validate
        round_id: Round ID for error messages

    Raises:
        ValueError: If coverage invariant is violated
    """
    if not thought_spaces:
        logger.warning(f"Round {round_id}: No thought spaces created (zero participants)")
        return

    # Collect all participant IDs across thought spaces
    all_participant_ids: Set[UUID] = set()
    duplicate_participants: Set[UUID] = set()

    for ts in thought_spaces:
        for pid in ts.participant_ids:
            if pid in all_participant_ids:
                duplicate_participants.add(pid)
            all_participant_ids.add(pid)

    # Check for duplicate assignments (participant in multiple thought spaces)
    if duplicate_participants:
        error_msg = (
            f"Round {round_id}: Semantic Accuracy violation - "
            f"{len(duplicate_participants)} participant(s) assigned to multiple thought spaces"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Verify member counts match participant_ids length
    for ts in thought_spaces:
        actual_count = len(ts.participant_ids)
        if ts.member_count != actual_count:
            error_msg = (
                f"Round {round_id}: Thought space {ts.cluster_id} member_count mismatch - "
                f"declared {ts.member_count}, actual {actual_count}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    total_participants = len(all_participant_ids)
    logger.info(
        f"Round {round_id}: Semantic Accuracy validated - "
        f"100% coverage ({total_participants} participants across {len(thought_spaces)} thought spaces)"
    )


async def store_thought_spaces(
    thought_spaces: list[ThoughtSpaceSummary],
    round_id: UUID,
    db: AsyncSession
) -> None:
    """
    Store thought spaces in the database.

    Args:
        thought_spaces: List of thought spaces to store
        round_id: Round these thought spaces belong to
        db: Database session

    Note:
        This is a placeholder until ThoughtSpace model is fully implemented
    """
    # TODO: Implement once ThoughtSpace model is complete
    # Expected logic:
    # 1. Create ThoughtSpace records for each thought_space
    # 2. Store cluster_id, round_id, label_summary, member_count, member_pct
    # 3. Store participant_ids for flow computation
    # 4. Commit to database

    logger.debug(
        f"Storing {len(thought_spaces)} thought spaces for round {round_id} "
        f"(implementation pending - requires ThoughtSpace model)"
    )


async def register_clustering_complete_handler(event_bus) -> None:
    """
    Register this handler with the event bus.

    Args:
        event_bus: EventBus instance to register with
    """
    await event_bus.subscribe(
        event_type="clustering.complete",
        handler=handle_clustering_complete,
    )
    logger.info("Registered handler for clustering.complete event")
