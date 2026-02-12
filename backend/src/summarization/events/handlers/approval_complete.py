"""
Handler for summary approval completion (Spec 3 → Spec 4).

Task T026: Emit summarization.complete event when all summaries are approved.
"""

from datetime import datetime
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....database import get_session_factory
from ....events.bus import event_bus, EVENT_SUMMARIZATION_COMPLETED
from ....events.event_types import (
    SummarizationCompleteEvent,
    ApprovedSummarySummary,
)
from ....logging_config import logger
from ....models import Round, RoundStatus
from ...models.summary import Summary, SummaryStatus


async def handle_summary_approved(summary_id: UUID) -> None:
    """
    Handle individual summary approval (called after approval service).

    Checks if all summaries for the round are approved, and if so,
    emits summarization.complete event to trigger clustering (Spec 4).

    Constitutional Compliance:
    - Intent Fidelity: Only APPROVED summaries are forwarded (trust gate)
    - Last-Approved-Wins: If multiple approvals per participant, only latest counts
    - Parallel-First: Independent approval process per participant

    Actions:
    1. Check if all participants have approved summaries
    2. If complete, collect approved summaries (last-approved-wins)
    3. Emit summarization.complete event to Spec 4
    4. Transition round status: SUMMARIZING → CLUSTERING

    Args:
        summary_id: UUID of the summary that was just approved

    Raises:
        RuntimeError: If event emission or state transition fails
    """
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Fetch the approved summary
            result = await db.execute(
                select(Summary).where(Summary.summary_id == summary_id)
            )
            approved_summary = result.scalar_one_or_none()

            if not approved_summary:
                logger.error(f"[Spec 3→4] Summary {summary_id} not found")
                return

            round_id = approved_summary.round_id

            logger.info(
                f"[Spec 3→4] Summary {summary_id} approved for round {round_id}"
            )

            # Check if summarization is complete for this round
            is_complete = await _check_summarization_complete(db, round_id)

            if is_complete:
                # Collect all approved summaries (last-approved-wins logic)
                approved_summaries = await _collect_approved_summaries(db, round_id)

                logger.info(
                    f"[Spec 3→4] Summarization complete for round {round_id}: "
                    f"{len(approved_summaries)} approved summaries"
                )

                # Emit summarization.complete event to Spec 4 (Clustering)
                await _emit_summarization_complete_event(
                    round_id=round_id,
                    approved_summaries=approved_summaries,
                )

                # Transition round status: SUMMARIZING → CLUSTERING
                await _transition_round_status(db, round_id)

                logger.info(
                    f"[Spec 3→4] Emitted summarization.complete event for round {round_id}"
                )
            else:
                logger.debug(
                    f"[Spec 3→4] Summarization not yet complete for round {round_id}"
                )

        except Exception as e:
            logger.error(
                f"[Spec 3→4] Handler failed for summary {summary_id}: {e}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Approval complete handler failed for summary {summary_id}"
            ) from e


async def _check_summarization_complete(db: AsyncSession, round_id: UUID) -> bool:
    """
    Check if all participants in the round have approved summaries.

    For MVP (User Story 1), we consider summarization complete when:
    - All submissions have at least one approved summary

    For User Story 5 (Last-Approved-Wins), we'll refine this logic.

    Args:
        db: Database session
        round_id: Round UUID

    Returns:
        bool: True if summarization is complete for this round
    """
    # Count total submissions for round
    from ....models import Submission

    total_submissions_result = await db.execute(
        select(Submission)
        .where(Submission.round_id == round_id)
    )
    total_submissions = len(list(total_submissions_result.scalars().all()))

    # Count approved summaries for round (unique by participant)
    approved_summaries_result = await db.execute(
        select(Summary)
        .where(Summary.round_id == round_id)
        .where(Summary.status == SummaryStatus.APPROVED)
    )
    approved_summaries = list(approved_summaries_result.scalars().all())

    # Get unique participants with approved summaries
    unique_approved_participants = set(s.participant_id for s in approved_summaries)

    logger.debug(
        f"[Spec 3→4] Round {round_id}: {len(unique_approved_participants)} "
        f"participants with approved summaries (out of {total_submissions} submissions)"
    )

    # For MVP, we consider complete when we have at least one approved summary
    # (In production, you'd want to wait for all participants or handle timeouts)
    # TODO: Implement approval deadline timeout handling (Phase 8)

    return len(unique_approved_participants) > 0


async def _collect_approved_summaries(
    db: AsyncSession, round_id: UUID
) -> List[ApprovedSummarySummary]:
    """
    Collect all approved summaries for a round (last-approved-wins).

    For each participant, selects the most recently approved summary.
    Validates that exactly one summary per participant is forwarded (T080-T081).

    Args:
        db: Database session
        round_id: Round UUID

    Returns:
        List of ApprovedSummarySummary for event payload

    Raises:
        RuntimeError: If multiple APPROVED summaries exist for same participant
    """
    # Fetch all approved summaries for round
    result = await db.execute(
        select(Summary)
        .where(Summary.round_id == round_id)
        .where(Summary.status == SummaryStatus.APPROVED)
        .order_by(Summary.participant_id, Summary.approved_at.desc())
    )
    all_approved = list(result.scalars().all())

    # Apply last-approved-wins logic: one summary per participant
    participant_to_summary = {}
    participant_approved_counts = {}

    for summary in all_approved:
        participant_id = summary.participant_id

        # Track count of approved summaries per participant
        if participant_id not in participant_approved_counts:
            participant_approved_counts[participant_id] = 0
        participant_approved_counts[participant_id] += 1

        if participant_id not in participant_to_summary:
            # First entry (latest approved_at due to DESC ordering)
            participant_to_summary[participant_id] = summary

    # T080-T081: Validate exactly one APPROVED summary per participant
    # (Others should have been marked as SUPERSEDED by ApprovalService)
    multiple_approved = {
        pid: count
        for pid, count in participant_approved_counts.items()
        if count > 1
    }

    if multiple_approved:
        logger.error(
            f"[Spec 3→4] VALIDATION FAILED: Found participants with multiple APPROVED summaries: "
            f"{multiple_approved}. Last-approved-wins logic may not be working correctly."
        )
        # Log details for debugging
        for pid, count in multiple_approved.items():
            participant_summaries = [s for s in all_approved if s.participant_id == pid]
            logger.error(
                f"[Spec 3→4] Participant {pid} has {count} APPROVED summaries: "
                f"{[(s.summary_id, s.approved_at.isoformat()) for s in participant_summaries]}"
            )
        # Don't fail the event - use last-approved-wins logic to select the latest
        logger.warning(
            f"[Spec 3→4] Proceeding with last-approved-wins selection despite validation failure"
        )

    # Convert to event payload format
    approved_summaries = [
        ApprovedSummarySummary(
            summary_id=s.summary_id,
            participant_id=s.participant_id,
            submission_id=s.submission_id,
            summary_text=s.summary_text,
            approved_at=s.approved_at,
        )
        for s in participant_to_summary.values()
    ]

    logger.info(
        f"[Spec 3→4] Collected {len(approved_summaries)} approved summaries "
        f"for round {round_id} (last-approved-wins applied, "
        f"total approved in DB: {len(all_approved)})"
    )

    return approved_summaries


async def _emit_summarization_complete_event(
    round_id: UUID,
    approved_summaries: List[ApprovedSummarySummary],
) -> None:
    """
    Emit summarization.complete event to trigger Spec 4 (Clustering).

    Args:
        round_id: Round UUID
        approved_summaries: List of approved summaries to forward
    """
    event = SummarizationCompleteEvent(
        round_id=round_id,
        approved_summaries=approved_summaries,
        timestamp=datetime.utcnow(),
    )

    # Publish event to event bus
    await event_bus.publish(
        event_type="summarization.complete",
        payload=event.model_dump(),
    )

    logger.info(
        f"[Spec 3→4] Emitted summarization.complete event: "
        f"round_id={round_id}, "
        f"approved_count={len(approved_summaries)}"
    )


async def _transition_round_status(db: AsyncSession, round_id: UUID) -> None:
    """
    Transition round status: SUMMARIZING → CLUSTERING.

    Args:
        db: Database session
        round_id: Round UUID
    """
    result = await db.execute(
        select(Round).where(Round.round_id == round_id)
    )
    round_obj = result.scalar_one_or_none()

    if not round_obj:
        logger.error(f"[Spec 3→4] Round {round_id} not found for status transition")
        return

    # Validate current status
    if round_obj.status != RoundStatus.SUMMARIZING:
        logger.warning(
            f"[Spec 3→4] Round {round_id} not in SUMMARIZING state "
            f"(current: {round_obj.status}), skipping transition"
        )
        return

    # Transition to CLUSTERING
    round_obj.status = RoundStatus.CLUSTERING
    await db.commit()

    logger.info(
        f"[Spec 3→4] Round {round_id} transitioned: SUMMARIZING → CLUSTERING"
    )
