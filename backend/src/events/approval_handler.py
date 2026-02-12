"""
Event handler for summary approval (T049).
Implements "last approved wins" logic for multiple submissions.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID
from src.models.submission_metadata import SubmissionMetadata
from src.events.bus import Event
import logging

logger = logging.getLogger(__name__)


async def handle_summary_approved(event: Event, db_session: AsyncSession) -> None:
    """
    Handle summary.approved event (T049).

    Implements "last approved wins" logic:
    1. Set counted=False on all previous submissions for this participant in this round
    2. Set counted=True on the newly approved submission
    3. Use atomic UPDATE queries to ensure consistency

    CRITICAL LOGIC: Last-Approved-Wins Atomicity
    ----------------------------------------------
    This implements the "last approved wins" rule (FR-013):
    - Multiple submissions allowed per participant per round
    - Only ONE submission can be counted=True at any time
    - When participant approves a new summary, previous counted submission is unmarked

    Example Timeline:
    - T1: Participant submits "Option A" → counted=False
    - T2: Summary generated, participant approves → counted=True (flows to Spec 4)
    - T3: Participant submits "Option B" (refined thinking) → counted=False
    - T4: New summary generated, participant approves → "Option A" becomes counted=False,
          "Option B" becomes counted=True (Sankey flows updated)

    Atomicity Strategy:
    - Two UPDATE queries in single transaction
    - Query 1: Unmark ALL counted submissions for (participant_id, round_id)
    - Query 2: Mark the newly approved submission as counted
    - If either fails, transaction rolls back (maintains invariant)

    Race Condition Protection:
    - Database transaction isolation ensures atomicity
    - No SELECT-then-UPDATE pattern (avoids lost updates)
    - Direct UPDATE queries with WHERE clauses (set-based operations)

    Constitutional Compliance:
    - Intent Fidelity: Participant's most recent approved intent is preserved
    - Temporal Transparency: Submission history retained (only counted flag changes)
    - Parallel-First: Independent approval events don't conflict (per-participant isolation)

    Event payload:
    {
        "submission_id": UUID of the approved submission,
        "participant_id": UUID of the participant,
        "round_id": UUID of the round,
        "timestamp": ISO timestamp of approval
    }
    """
    try:
        submission_id = UUID(event.payload["submission_id"])
        participant_id = UUID(event.payload["participant_id"])
        round_id = UUID(event.payload["round_id"])

        logger.info(
            f"Processing summary approval for submission {submission_id}, "
            f"participant {participant_id}, round {round_id}"
        )

        # Step 1: Unmark all previous counted submissions for this participant in this round
        # This ensures only one submission is counted per (participant, round)
        # Note: This might unmark 0 or 1 previous submissions
        # - 0 if this is the first approval
        # - 1 if participant previously approved a different submission
        await db_session.execute(
            update(SubmissionMetadata)
            .where(
                SubmissionMetadata.participant_id == participant_id,
                SubmissionMetadata.round_id == round_id,
                SubmissionMetadata.counted == True
            )
            .values(counted=False)
        )

        # Step 2: Mark the newly approved submission as counted
        # This is the "wins" part of "last approved wins"
        # Only this submission will be forwarded to clustering (Spec 4)
        await db_session.execute(
            update(SubmissionMetadata)
            .where(SubmissionMetadata.submission_id == submission_id)
            .values(counted=True)
        )

        # Commit the transaction
        await db_session.commit()

        logger.info(
            f"Successfully marked submission {submission_id} as counted. "
            f"All previous submissions for participant {participant_id} in round {round_id} "
            f"have been unmarked."
        )

    except Exception as e:
        logger.error(
            f"Error handling summary approval: {e}",
            exc_info=True
        )
        await db_session.rollback()
        raise
