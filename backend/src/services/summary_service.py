"""
Summary Supersession Service - Handles last-approved-wins logic for approved summaries.

Implements T066: SummarySupersessionService with:
- Mark previous ApprovedSummary as SUPERSEDED when new approval occurs
- Ensure exactly one APPROVED summary per participant per round
- Update previous summary's summary_status to SUPERSEDED
- Log all supersession events for audit trail
- Handle edge cases (no previous summary, concurrent approvals)
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from ..models.approved_summary import ApprovedSummary
from ..models.submission import Submission, SummaryStatus
from ..models.participant import Participant

logger = logging.getLogger(__name__)


class SummarySupersessionService:
    """
    Service for managing approved summary supersession with last-approved-wins logic.

    Constitutional Principles:
    - Intent Fidelity (Principle II): Only the last approved summary enters clustering
    - Temporal Transparency (Principle IV): Audit trail of all approval actions

    Implementation Strategy:
    Since ApprovedSummary has a unique constraint on (round_id, participant_id),
    we implement last-approved-wins by:
    1. Deleting the previous ApprovedSummary (if exists)
    2. Creating the new ApprovedSummary
    3. Marking the previous Submission as SUPERSEDED
    4. Logging all actions for audit trail
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize summary supersession service.

        Args:
            db: Database session
        """
        self.db = db

    async def apply_last_approved_wins(
        self,
        participant_id: UUID,
        round_id: UUID,
        new_submission_id: UUID,
        summary_text: str
    ) -> ApprovedSummary:
        """
        Apply last-approved-wins rule when participant approves a new summary.

        Process:
        1. Check for existing ApprovedSummary for this participant/round
        2. If exists, mark it as superseded and delete it
        3. Mark previous submissions as SUPERSEDED
        4. Create new ApprovedSummary
        5. Mark new submission as APPROVED

        Args:
            participant_id: UUID of participant
            round_id: UUID of round
            new_submission_id: UUID of the submission being approved
            summary_text: The approved summary text

        Returns:
            Newly created ApprovedSummary entity

        Raises:
            ValueError: If participant or round not found
            IntegrityError: If concurrent approval creates conflict
        """
        logger.info(
            f"Applying last-approved-wins for participant={participant_id}, "
            f"round={round_id}, new_submission={new_submission_id}"
        )

        # Step 1: Check for existing ApprovedSummary
        previous_summary = await self._get_existing_approved_summary(
            participant_id,
            round_id
        )

        # Step 2: If previous summary exists, supersede it
        if previous_summary:
            await self._supersede_previous_summary(
                previous_summary,
                new_submission_id
            )

        # Step 3: Mark previous submissions as SUPERSEDED
        await self._mark_previous_submissions_superseded(
            participant_id,
            round_id,
            new_submission_id
        )

        # Step 4: Create new ApprovedSummary
        new_summary = await self._create_approved_summary(
            participant_id,
            round_id,
            new_submission_id,
            summary_text
        )

        # Step 5: Mark new submission as APPROVED
        await self._mark_submission_approved(new_submission_id)

        logger.info(
            f"Successfully applied last-approved-wins: new_summary={new_summary.summary_id}, "
            f"participant={participant_id}, round={round_id}, "
            f"superseded_previous={previous_summary is not None}"
        )

        return new_summary

    async def _get_existing_approved_summary(
        self,
        participant_id: UUID,
        round_id: UUID
    ) -> Optional[ApprovedSummary]:
        """
        Get existing ApprovedSummary for participant in round.

        Args:
            participant_id: UUID of participant
            round_id: UUID of round

        Returns:
            ApprovedSummary if exists, None otherwise
        """
        stmt = (
            select(ApprovedSummary)
            .where(
                ApprovedSummary.participant_id == participant_id,
                ApprovedSummary.round_id == round_id
            )
        )

        result = await self.db.execute(stmt)
        summary = result.scalar_one_or_none()

        if summary:
            logger.debug(
                f"Found existing ApprovedSummary: id={summary.summary_id}, "
                f"participant={participant_id}, round={round_id}"
            )
        else:
            logger.debug(
                f"No existing ApprovedSummary found for participant={participant_id}, "
                f"round={round_id}"
            )

        return summary

    async def _supersede_previous_summary(
        self,
        previous_summary: ApprovedSummary,
        new_submission_id: UUID
    ) -> None:
        """
        Supersede previous ApprovedSummary by deleting it and logging the event.

        Since ApprovedSummary has unique constraint on (round_id, participant_id),
        we delete the old one before creating the new one.

        Args:
            previous_summary: The ApprovedSummary to supersede
            new_submission_id: UUID of the new submission being approved
        """
        previous_summary_id = previous_summary.summary_id
        previous_submission_id = previous_summary.submission_id
        participant_id = previous_summary.participant_id
        round_id = previous_summary.round_id

        logger.info(
            f"Superseding ApprovedSummary: id={previous_summary_id}, "
            f"participant={participant_id}, round={round_id}, "
            f"old_submission={previous_submission_id}, "
            f"new_submission={new_submission_id}"
        )

        # Delete the previous ApprovedSummary
        await self.db.delete(previous_summary)
        await self.db.flush()

        # Mark the previous submission as SUPERSEDED (if it still exists)
        if previous_submission_id:
            await self._mark_submission_superseded(previous_submission_id)

        logger.info(
            f"Successfully superseded ApprovedSummary: id={previous_summary_id}"
        )

    async def _mark_previous_submissions_superseded(
        self,
        participant_id: UUID,
        round_id: UUID,
        approved_submission_id: UUID
    ) -> int:
        """
        Mark all previous submissions (except the approved one) as SUPERSEDED.

        Args:
            participant_id: UUID of participant
            round_id: UUID of round
            approved_submission_id: UUID of the newly approved submission

        Returns:
            Count of submissions marked as SUPERSEDED
        """
        stmt = (
            select(Submission)
            .where(
                Submission.participant_id == participant_id,
                Submission.round_id == round_id,
                Submission.submission_id != approved_submission_id,
                Submission.summary_status.in_([
                    SummaryStatus.PENDING,
                    SummaryStatus.APPROVED
                ])
            )
        )

        result = await self.db.execute(stmt)
        previous_submissions = result.scalars().all()

        superseded_count = 0
        for submission in previous_submissions:
            old_status = submission.summary_status
            submission.summary_status = SummaryStatus.SUPERSEDED
            superseded_count += 1

            logger.debug(
                f"Marked submission {submission.submission_id} as SUPERSEDED "
                f"(was {old_status})"
            )

        await self.db.flush()

        logger.debug(
            f"Marked {superseded_count} submissions as SUPERSEDED for "
            f"participant={participant_id}, round={round_id}"
        )

        return superseded_count

    async def _mark_submission_superseded(self, submission_id: UUID) -> None:
        """
        Mark a specific submission as SUPERSEDED.

        Args:
            submission_id: UUID of submission
        """
        stmt = select(Submission).where(Submission.submission_id == submission_id)
        result = await self.db.execute(stmt)
        submission = result.scalar_one_or_none()

        if submission:
            old_status = submission.summary_status
            submission.summary_status = SummaryStatus.SUPERSEDED
            await self.db.flush()

            logger.debug(
                f"Marked submission {submission_id} as SUPERSEDED (was {old_status})"
            )

    async def _create_approved_summary(
        self,
        participant_id: UUID,
        round_id: UUID,
        submission_id: UUID,
        summary_text: str
    ) -> ApprovedSummary:
        """
        Create a new ApprovedSummary entity.

        Args:
            participant_id: UUID of participant
            round_id: UUID of round
            submission_id: UUID of source submission
            summary_text: Approved summary text

        Returns:
            Newly created ApprovedSummary

        Raises:
            ValueError: If summary_text is invalid
        """
        # Validate summary text
        if not summary_text or not summary_text.strip():
            raise ValueError("Summary text cannot be empty")

        if len(summary_text) > 500:
            raise ValueError(
                f"Summary text exceeds 500 character limit: {len(summary_text)} chars"
            )

        new_summary = ApprovedSummary(
            participant_id=participant_id,
            round_id=round_id,
            submission_id=submission_id,
            summary_text=summary_text.strip(),
            approved_at=datetime.utcnow(),
            cluster_id=None  # Set by clustering service later
        )

        self.db.add(new_summary)
        await self.db.flush()

        logger.debug(
            f"Created ApprovedSummary: id={new_summary.summary_id}, "
            f"participant={participant_id}, round={round_id}, "
            f"submission={submission_id}"
        )

        return new_summary

    async def _mark_submission_approved(self, submission_id: UUID) -> None:
        """
        Mark a submission as APPROVED.

        Args:
            submission_id: UUID of submission
        """
        stmt = select(Submission).where(Submission.submission_id == submission_id)
        result = await self.db.execute(stmt)
        submission = result.scalar_one_or_none()

        if not submission:
            raise ValueError(f"Submission not found: {submission_id}")

        old_status = submission.summary_status
        submission.summary_status = SummaryStatus.APPROVED
        await self.db.flush()

        logger.debug(
            f"Marked submission {submission_id} as APPROVED (was {old_status})"
        )

    async def ensure_single_approved_summary(
        self,
        participant_id: UUID,
        round_id: UUID
    ) -> Optional[ApprovedSummary]:
        """
        Ensure exactly one approved summary exists for participant in round.

        Validates the last-approved-wins invariant. This should be called
        during round state transitions to verify data integrity.

        Args:
            participant_id: UUID of participant
            round_id: UUID of round

        Returns:
            The single ApprovedSummary if exists, None if no approved summary

        Raises:
            RuntimeError: If multiple approved summaries found (data integrity violation)
        """
        stmt = (
            select(ApprovedSummary)
            .where(
                ApprovedSummary.participant_id == participant_id,
                ApprovedSummary.round_id == round_id
            )
        )

        result = await self.db.execute(stmt)
        summaries = result.scalars().all()

        if len(summaries) == 0:
            logger.debug(
                f"No approved summary for participant={participant_id}, "
                f"round={round_id}"
            )
            return None

        if len(summaries) == 1:
            logger.debug(
                f"Single approved summary confirmed for participant={participant_id}, "
                f"round={round_id}: {summaries[0].summary_id}"
            )
            return summaries[0]

        # This should never happen due to unique constraint
        logger.error(
            f"CRITICAL: Multiple approved summaries found for participant={participant_id}, "
            f"round={round_id}: {[s.summary_id for s in summaries]}"
        )
        raise RuntimeError(
            f"Data integrity violation: Multiple approved summaries found for "
            f"participant={participant_id}, round={round_id}"
        )

    async def get_approved_summary_count(self, round_id: UUID) -> int:
        """
        Get count of approved summaries for a round.

        Args:
            round_id: UUID of round

        Returns:
            Count of approved summaries
        """
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(ApprovedSummary)
            .where(ApprovedSummary.round_id == round_id)
        )

        result = await self.db.execute(stmt)
        count = result.scalar_one()

        logger.debug(f"Approved summary count for round={round_id}: {count}")

        return count
