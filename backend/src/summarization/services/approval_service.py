"""
Approval service for Spec 003.

Handles summary approval/rejection with FSM state transitions.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...logging_config import logger
from ..models.summary import Summary, SummaryStatus


class ApprovalService:
    """
    Service for managing summary approval lifecycle.

    Constitutional Compliance:
    - Intent Fidelity: 100% explicit approval required (no auto-approval)
    - Temporal Transparency: Tracks approved_at timestamps
    """

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db

    async def approve_summary(self, summary_id: UUID) -> Summary:
        """
        Approve a summary (Task T021).

        FSM Transition: PENDING_REVIEW → APPROVED

        Sets:
        - status = APPROVED
        - approved_at = current timestamp

        Implements last-approved-wins logic (T078-T079):
        - If participant has other approved summaries for this round, mark them as SUPERSEDED

        Idempotent: If summary is already approved, returns it without error.

        Args:
            summary_id: Summary UUID to approve

        Returns:
            Summary: Updated summary with status=APPROVED

        Raises:
            ValueError: If summary not found or invalid state (except already approved)
        """
        # Fetch summary
        result = await self.db.execute(
            select(Summary).where(Summary.summary_id == summary_id)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            raise ValueError(f"Summary {summary_id} not found")

        # Idempotent: If already approved, return it
        if summary.status == SummaryStatus.APPROVED:
            logger.info(
                f"Summary {summary_id} already approved at {summary.approved_at.isoformat()}. "
                f"Returning existing approval (idempotent operation)."
            )
            return summary

        # Validate state transition for other states
        if summary.status != SummaryStatus.PENDING_REVIEW:
            raise ValueError(
                f"Cannot approve summary with status {summary.status.value}. "
                f"Must be in PENDING_REVIEW state."
            )

        # Update status and timestamp
        summary.status = SummaryStatus.APPROVED
        summary.approved_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(summary)

        # Logging (T033)
        logger.info(
            f"Approved summary {summary_id}: "
            f"participant_id={summary.participant_id}, "
            f"round_id={summary.round_id}, "
            f"approved_at={summary.approved_at.isoformat()}"
        )

        # Apply last-approved-wins logic: mark older approved summaries as SUPERSEDED (T078-T079)
        await self._apply_last_approved_wins(
            participant_id=summary.participant_id,
            round_id=summary.round_id,
            latest_summary_id=summary_id
        )

        # Trigger event handler to check if summarization is complete (T026)
        try:
            from ..events.handlers.approval_complete import handle_summary_approved
            await handle_summary_approved(summary_id)
        except Exception as e:
            logger.error(
                f"Failed to trigger approval complete handler for {summary_id}: {e}"
            )
            # Don't fail the approval if event handler fails

        return summary

    async def reject_summary(self, summary_id: UUID) -> Summary:
        """
        Reject a summary (User Story 2).

        FSM Transition: PENDING_REVIEW → REJECTED

        Does NOT trigger regeneration (that's handled by the API layer).

        Args:
            summary_id: Summary UUID to reject

        Returns:
            Summary: Updated summary with status=REJECTED

        Raises:
            ValueError: If summary not found or invalid state
        """
        # Fetch summary
        result = await self.db.execute(
            select(Summary).where(Summary.summary_id == summary_id)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            raise ValueError(f"Summary {summary_id} not found")

        # Validate state transition
        if summary.status != SummaryStatus.PENDING_REVIEW:
            raise ValueError(
                f"Cannot reject summary in state {summary.status.value}. "
                f"Must be in PENDING_REVIEW state."
            )

        # Update status
        summary.status = SummaryStatus.REJECTED

        await self.db.commit()
        await self.db.refresh(summary)

        # Logging
        logger.info(
            f"Rejected summary {summary_id}: "
            f"participant_id={summary.participant_id}, "
            f"round_id={summary.round_id}, "
            f"regen_count={summary.regen_count}"
        )

        return summary

    async def mark_rejected_final(self, summary_id: UUID) -> Summary:
        """
        Mark summary as REJECTED_FINAL (User Story 3).

        FSM Transition: PENDING_REVIEW → REJECTED_FINAL

        Used after max regenerations (regen_count=3) and final rejection.

        Args:
            summary_id: Summary UUID to mark as final rejection

        Returns:
            Summary: Updated summary with status=REJECTED_FINAL

        Raises:
            ValueError: If summary not found or invalid state
        """
        # Fetch summary
        result = await self.db.execute(
            select(Summary).where(Summary.summary_id == summary_id)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            raise ValueError(f"Summary {summary_id} not found")

        # Validate state transition
        if summary.status != SummaryStatus.PENDING_REVIEW:
            raise ValueError(
                f"Cannot mark summary as REJECTED_FINAL in state {summary.status.value}. "
                f"Must be in PENDING_REVIEW state."
            )

        # Update status
        summary.status = SummaryStatus.REJECTED_FINAL

        await self.db.commit()
        await self.db.refresh(summary)

        # Logging
        logger.info(
            f"Marked summary {summary_id} as REJECTED_FINAL: "
            f"participant_id={summary.participant_id}, "
            f"round_id={summary.round_id}, "
            f"regen_count={summary.regen_count}"
        )

        return summary

    async def mark_superseded(
        self,
        participant_id: UUID,
        round_id: UUID,
        except_summary_id: UUID
    ) -> int:
        """
        Mark summaries as SUPERSEDED (User Story 5).

        FSM Transition: APPROVED → SUPERSEDED

        Marks all approved summaries for (participant, round) as SUPERSEDED,
        except for the specified summary ID.

        Args:
            participant_id: Participant UUID
            round_id: Round UUID
            except_summary_id: Summary ID to keep as APPROVED

        Returns:
            int: Number of summaries marked as SUPERSEDED

        Raises:
            ValueError: If summaries not found or invalid state
        """
        # Get all approved summaries for this participant in this round,
        # excluding the specified summary
        result = await self.db.execute(
            select(Summary)
            .where(Summary.participant_id == participant_id)
            .where(Summary.round_id == round_id)
            .where(Summary.status == SummaryStatus.APPROVED)
            .where(Summary.summary_id != except_summary_id)
        )
        summaries_to_supersede = list(result.scalars().all())

        if not summaries_to_supersede:
            logger.debug(
                f"No approved summaries to supersede for "
                f"participant_id={participant_id}, round_id={round_id}, "
                f"except_summary_id={except_summary_id}"
            )
            return 0

        # Mark all as SUPERSEDED
        superseded_count = 0
        for summary in summaries_to_supersede:
            # Validate state transition
            if summary.status != SummaryStatus.APPROVED:
                logger.warning(
                    f"Cannot mark summary {summary.summary_id} as SUPERSEDED "
                    f"in state {summary.status.value}. Skipping."
                )
                continue

            summary.status = SummaryStatus.SUPERSEDED
            superseded_count += 1

            # Logging
            logger.info(
                f"Marked summary {summary.summary_id} as SUPERSEDED: "
                f"participant_id={summary.participant_id}, "
                f"round_id={summary.round_id}"
            )

        await self.db.commit()

        logger.info(
            f"Superseded {superseded_count} summaries for "
            f"participant_id={participant_id}, round_id={round_id}"
        )

        return superseded_count

    async def get_approved_summaries_for_round(
        self, round_id: UUID
    ) -> list[Summary]:
        """
        Get all approved summaries for a round.

        Args:
            round_id: Round UUID

        Returns:
            List of summaries with status=APPROVED
        """
        result = await self.db.execute(
            select(Summary)
            .where(Summary.round_id == round_id)
            .where(Summary.status == SummaryStatus.APPROVED)
            .order_by(Summary.approved_at)
        )
        return list(result.scalars().all())

    async def get_last_approved_summary_for_participant(
        self, participant_id: UUID, round_id: UUID
    ) -> Optional[Summary]:
        """
        Get last approved summary for participant in round (User Story 5).

        Used for last-approved-wins logic.

        Args:
            participant_id: Participant UUID
            round_id: Round UUID

        Returns:
            Latest approved Summary or None
        """
        result = await self.db.execute(
            select(Summary)
            .where(Summary.participant_id == participant_id)
            .where(Summary.round_id == round_id)
            .where(Summary.status == SummaryStatus.APPROVED)
            .order_by(Summary.approved_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _apply_last_approved_wins(
        self, participant_id: UUID, round_id: UUID, latest_summary_id: UUID
    ) -> int:
        """
        Apply last-approved-wins logic (T078-T079).

        Marks all previously approved summaries for (participant, round) as SUPERSEDED,
        except for the latest approved summary.

        Args:
            participant_id: Participant UUID
            round_id: Round UUID
            latest_summary_id: The newly approved summary ID to keep as APPROVED

        Returns:
            int: Number of summaries marked as SUPERSEDED

        Logs:
            T085: Logs last-approved-wins selection
        """
        # Get all approved summaries for this participant in this round
        result = await self.db.execute(
            select(Summary)
            .where(Summary.participant_id == participant_id)
            .where(Summary.round_id == round_id)
            .where(Summary.status == SummaryStatus.APPROVED)
            .where(Summary.summary_id != latest_summary_id)
            .order_by(Summary.approved_at.desc())
        )
        older_summaries = list(result.scalars().all())

        if not older_summaries:
            logger.debug(
                f"[Last-Approved-Wins] No older approved summaries to supersede for "
                f"participant_id={participant_id}, round_id={round_id}"
            )
            return 0

        # Mark all older approved summaries as SUPERSEDED
        superseded_count = 0
        for old_summary in older_summaries:
            old_summary.status = SummaryStatus.SUPERSEDED
            superseded_count += 1

            # T085: Log supersession
            logger.info(
                f"[Last-Approved-Wins] Superseded summary {old_summary.summary_id}: "
                f"participant_id={participant_id}, "
                f"round_id={round_id}, "
                f"old_approved_at={old_summary.approved_at.isoformat()}, "
                f"superseded_by={latest_summary_id}"
            )

        await self.db.commit()

        logger.info(
            f"[Last-Approved-Wins] Selected latest summary {latest_summary_id} "
            f"for participant_id={participant_id}, round_id={round_id}. "
            f"Superseded {superseded_count} older summaries."
        )

        return superseded_count
