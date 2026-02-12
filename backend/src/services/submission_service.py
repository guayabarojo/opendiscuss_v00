"""
Submission Service - Handles multiple submissions per participant with rate limiting.

Implements T065: handle_multiple_submissions with:
- Track submission count per participant per round
- Enforce rate limit = 3 submissions per participant per round
- Store all submissions in database (don't delete old ones)
- Apply last-approved-wins rule during approval process
- Return submission with remaining_submissions count
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.submission import Submission, SummaryStatus
from ..models.participant import Participant
from ..models.round import Round
from ..api.error_handlers import RateLimitExceededException, TimingViolationException

logger = logging.getLogger(__name__)

# Rate limit constants
MAX_SUBMISSIONS_PER_ROUND = 3


class SubmissionService:
    """
    Service for handling participant submissions with rate limiting and multiple submission support.

    Constitutional Principles:
    - Intent Fidelity (Principle II): Only approved summaries enter clustering
    - Parallel-First (Principle I): Support concurrent submissions from multiple participants
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize submission service.

        Args:
            db: Database session
        """
        self.db = db

    async def handle_multiple_submissions(
        self,
        participant_id: UUID,
        round_id: UUID,
        submission_text: str,
        modality: str = "text"
    ) -> tuple[Submission, int]:
        """
        Handle a participant submission with rate limiting and last-approved-wins logic.

        Process:
        1. Validate submission window is open
        2. Check rate limit (max 3 submissions per participant per round)
        3. Create new submission in database
        4. Return submission with remaining_submissions count

        Args:
            participant_id: UUID of participant submitting
            round_id: UUID of target round
            submission_text: Submission content (max 2000 chars)
            modality: Submission type (text or voice)

        Returns:
            Tuple of (Submission entity, remaining_submissions count)

        Raises:
            RateLimitExceededException: If participant has already submitted 3 times
            TimingViolationException: If submission window is not open
            ValueError: If submission_text is invalid
        """
        logger.info(
            f"Processing submission for participant={participant_id}, round={round_id}"
        )

        # Validate submission text
        if not submission_text or not submission_text.strip():
            raise ValueError("Submission text cannot be empty")

        if len(submission_text) > 2000:
            raise ValueError(f"Submission text exceeds 2000 character limit: {len(submission_text)} chars")

        # Validate round exists and window is open
        round_entity = await self._validate_submission_window(round_id)

        # Check rate limit
        submission_count = await self._get_submission_count(participant_id, round_id)

        if submission_count >= MAX_SUBMISSIONS_PER_ROUND:
            logger.warning(
                f"Rate limit exceeded for participant={participant_id}, "
                f"round={round_id}, count={submission_count}"
            )
            raise RateLimitExceededException(
                resource=f"submissions for round {round_id}",
                limit=MAX_SUBMISSIONS_PER_ROUND,
                current=submission_count,
                reset_at=round_entity.submission_window_end
            )

        # Create new submission
        submission = Submission(
            participant_id=participant_id,
            round_id=round_id,
            submission_text=submission_text.strip(),
            modality=modality,
            submitted_at=datetime.utcnow(),
            summary_status=SummaryStatus.PENDING
        )

        self.db.add(submission)
        await self.db.flush()  # Get submission_id without committing

        remaining_submissions = MAX_SUBMISSIONS_PER_ROUND - (submission_count + 1)

        logger.info(
            f"Submission created: id={submission.submission_id}, "
            f"participant={participant_id}, round={round_id}, "
            f"remaining={remaining_submissions}"
        )

        return submission, remaining_submissions

    async def mark_previous_submissions_superseded(
        self,
        participant_id: UUID,
        round_id: UUID,
        approved_submission_id: UUID
    ) -> int:
        """
        Mark all previous submissions as SUPERSEDED when a new summary is approved.

        Implements last-approved-wins rule: When participant approves a new summary,
        all their previous submissions for this round are marked SUPERSEDED.

        Args:
            participant_id: UUID of participant
            round_id: UUID of round
            approved_submission_id: UUID of the newly approved submission

        Returns:
            Count of submissions marked as SUPERSEDED
        """
        logger.info(
            f"Marking previous submissions as SUPERSEDED for participant={participant_id}, "
            f"round={round_id}, approved_submission={approved_submission_id}"
        )

        # Find all other submissions by this participant in this round
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

        logger.info(
            f"Marked {superseded_count} submissions as SUPERSEDED for "
            f"participant={participant_id}, round={round_id}"
        )

        return superseded_count

    async def _validate_submission_window(self, round_id: UUID) -> Round:
        """
        Validate that submission window is open for the round.

        Args:
            round_id: UUID of round

        Returns:
            Round entity

        Raises:
            TimingViolationException: If window is not open or discussion is closed
        """
        from ..models.protocol_state import RoundStatus, DiscussionStatus
        from ..models.discussion import Discussion

        stmt = select(Round).where(Round.round_id == round_id)
        result = await self.db.execute(stmt)
        round_entity = result.scalar_one_or_none()

        if not round_entity:
            raise ValueError(f"Round not found: {round_id}")

        # T072: Check if discussion is completed or terminated
        discussion_stmt = select(Discussion).where(
            Discussion.discussion_id == round_entity.discussion_id
        )
        discussion_result = await self.db.execute(discussion_stmt)
        discussion = discussion_result.scalar_one_or_none()

        if discussion and discussion.status in (DiscussionStatus.COMPLETED, DiscussionStatus.TERMINATED):
            closure_reason = "COMPLETED" if discussion.status == DiscussionStatus.COMPLETED else "TERMINATED"
            raise TimingViolationException(
                operation="submit",
                reason=f"Discussion has ended. No further submissions accepted. (Closure reason: {closure_reason})",
                details={
                    "discussion_id": str(discussion.discussion_id),
                    "round_id": str(round_id),
                    "discussion_status": discussion.status.value,
                    "closure_reason": closure_reason,
                    "is_closed": True,
                }
            )

        if round_entity.status != RoundStatus.SUBMISSION_OPEN:
            raise TimingViolationException(
                operation="submit",
                reason=f"Submission window is not open (current status: {round_entity.status})",
                details={
                    "round_id": str(round_id),
                    "current_status": round_entity.status.value,
                    "window_start": round_entity.submission_window_start.isoformat() if round_entity.submission_window_start else None,
                    "window_end": round_entity.submission_window_end.isoformat() if round_entity.submission_window_end else None
                }
            )

        # Check if current time is within window
        now = datetime.utcnow()
        if round_entity.submission_window_end and now > round_entity.submission_window_end:
            raise TimingViolationException(
                operation="submit",
                reason="Submission window has closed",
                details={
                    "round_id": str(round_id),
                    "window_end": round_entity.submission_window_end.isoformat(),
                    "current_time": now.isoformat()
                }
            )

        return round_entity

    async def _get_submission_count(
        self,
        participant_id: UUID,
        round_id: UUID
    ) -> int:
        """
        Get count of submissions by participant in round.

        Counts all submissions regardless of summary_status (PENDING, APPROVED, SUPERSEDED, etc.)
        to enforce rate limit.

        Args:
            participant_id: UUID of participant
            round_id: UUID of round

        Returns:
            Count of submissions
        """
        stmt = (
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.participant_id == participant_id,
                Submission.round_id == round_id,
                Submission.deleted_at.is_(None)  # Don't count soft-deleted submissions
            )
        )

        result = await self.db.execute(stmt)
        count = result.scalar_one()

        logger.debug(
            f"Submission count for participant={participant_id}, "
            f"round={round_id}: {count}"
        )

        return count

    async def get_participant_submissions(
        self,
        participant_id: UUID,
        round_id: UUID
    ) -> list[Submission]:
        """
        Get all submissions by a participant in a round, ordered by submission time.

        Args:
            participant_id: UUID of participant
            round_id: UUID of round

        Returns:
            List of Submission entities ordered by submitted_at (newest first)
        """
        stmt = (
            select(Submission)
            .where(
                Submission.participant_id == participant_id,
                Submission.round_id == round_id,
                Submission.deleted_at.is_(None)
            )
            .order_by(Submission.submitted_at.desc())
        )

        result = await self.db.execute(stmt)
        submissions = result.scalars().all()

        logger.debug(
            f"Retrieved {len(submissions)} submissions for participant={participant_id}, "
            f"round={round_id}"
        )

        return list(submissions)

    async def get_remaining_submissions(
        self,
        participant_id: UUID,
        round_id: UUID
    ) -> int:
        """
        Get remaining submission count for participant in round.

        Args:
            participant_id: UUID of participant
            round_id: UUID of round

        Returns:
            Number of submissions remaining (0-3)
        """
        current_count = await self._get_submission_count(participant_id, round_id)
        return max(0, MAX_SUBMISSIONS_PER_ROUND - current_count)
