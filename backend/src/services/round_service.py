"""
Round management service for the OpenDiscuss Discussion Protocol.

Coordinates submission window timing and integrates with TimingService
for precise window enforcement (±100ms precision).
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.round import Round, RoundStatus
from src.models.submission import Submission
from src.events.event_bus import EventBus
from src.events.event_types import SubmissionWindowClosedEvent, SubmissionSummary
from src.services.timing_service import TimingService
from src.api.error_handlers import RoundNotFoundException, InvalidStateTransitionException

logger = logging.getLogger(__name__)


class RoundService:
    """
    Service for managing round lifecycle and submission window timing.

    Features:
    - Opens submission windows with precise timing
    - Schedules window closures via TimingService (±100ms precision)
    - Closes submission windows and emits events with submission data
    - Validates round status transitions
    """

    def __init__(
        self,
        db_session: AsyncSession,
        event_bus: EventBus,
        timing_service: TimingService,
    ) -> None:
        """
        Initialize RoundService with required dependencies.

        Args:
            db_session: Database session for persistence operations
            event_bus: Event bus for emitting protocol events
            timing_service: Timing service for scheduling window closures
        """
        self.db_session = db_session
        self.event_bus = event_bus
        self.timing_service = timing_service

    async def open_submission_window(self, round_id: UUID) -> Round:
        """
        Open the submission window for a round.

        Transitions the round from PENDING or QUESTION_READY to SUBMISSION_OPEN,
        computes the window_end timestamp. For SYNCHRONOUS mode, schedules closure
        via TimingService. For ASYNCHRONOUS mode, logs soft deadline.

        Args:
            round_id: Unique identifier for the round

        Returns:
            Updated Round entity with SUBMISSION_OPEN status

        Raises:
            RoundNotFoundException: If round not found
            InvalidStateTransitionException: If round not in PENDING or QUESTION_READY
            ConnectionError: If TimingService scheduling fails (sync mode only)
        """
        # Fetch round from database
        result = await self.db_session.execute(
            select(Round).where(Round.round_id == round_id)
        )
        round_entity = result.scalar_one_or_none()

        if not round_entity:
            raise RoundNotFoundException(str(round_id))

        # Validate status transition using Round's state machine
        try:
            round_entity.open_submission_window()
        except ValueError as e:
            raise InvalidStateTransitionException(
                entity_type="Round",
                entity_id=str(round_id),
                from_state=str(round_entity.status),
                to_state=str(RoundStatus.SUBMISSION_OPEN),
                reason=str(e),
            ) from e

        # Get discussion to check timing mode
        from src.models.discussion import Discussion
        from src.models.protocol_state import DiscussionTimingMode

        discussion_result = await self.db_session.execute(
            select(Discussion).where(Discussion.discussion_id == round_entity.discussion_id)
        )
        discussion = discussion_result.scalar_one_or_none()

        # Conditional timing enforcement based on mode
        if discussion and discussion.timing_mode == DiscussionTimingMode.SYNCHRONOUS:
            # Schedule window closure via TimingService for synchronous mode
            try:
                await self.timing_service.schedule_closure(
                    round_id=round_id,
                    close_at=round_entity.submission_window_end,
                )
            except Exception as e:
                logger.error(
                    f"Failed to schedule closure for round {round_id}: {e}",
                    exc_info=True,
                )
                # Rollback the status change if scheduling fails
                await self.db_session.rollback()
                raise ConnectionError(
                    f"Failed to schedule window closure for round {round_id}: {e}"
                ) from e

            logger.info(
                f"Opened SYNCHRONOUS submission window for round {round_id}. "
                f"Window closes at {round_entity.submission_window_end} "
                f"(duration: {round_entity.submission_window_duration_sec}s)"
            )
        else:
            # Async mode: no timer, just log soft deadline
            logger.info(
                f"Opened ASYNCHRONOUS submission window for round {round_id}. "
                f"Soft deadline: {round_entity.submission_window_end}"
            )

        # Commit the changes to the database
        self.db_session.add(round_entity)
        await self.db_session.commit()
        await self.db_session.refresh(round_entity)

        return round_entity

    async def manual_close_submission_window(self, round_id: UUID, user_id: UUID) -> Round:
        """
        Host manually closes async round submission window.

        Args:
            round_id: Unique identifier for the round
            user_id: User attempting to close the round

        Returns:
            Updated Round entity with SUBMISSION_CLOSED status

        Raises:
            RoundNotFoundException: If round not found
            PermissionError: If user is not the discussion host
            ValueError: If discussion is not in ASYNCHRONOUS mode
        """
        # Fetch round from database
        result = await self.db_session.execute(
            select(Round).where(Round.round_id == round_id)
        )
        round_entity = result.scalar_one_or_none()

        if not round_entity:
            raise RoundNotFoundException(str(round_id))

        # Get discussion to validate permissions and mode
        from src.models.discussion import Discussion
        from src.models.protocol_state import DiscussionTimingMode

        discussion_result = await self.db_session.execute(
            select(Discussion).where(Discussion.discussion_id == round_entity.discussion_id)
        )
        discussion = discussion_result.scalar_one_or_none()

        if not discussion:
            raise RoundNotFoundException(f"Discussion not found for round {round_id}")

        # Validate host permission
        if discussion.host_user_id != user_id:
            raise PermissionError("Only discussion host can manually close rounds")

        # Validate async mode
        if discussion.timing_mode != DiscussionTimingMode.ASYNCHRONOUS:
            raise ValueError("Manual close only available for ASYNCHRONOUS discussions")

        # Close the submission window
        return await self.close_submission_window(round_id)

    async def close_submission_window(self, round_id: UUID) -> Round:
        """
        Close the submission window for a round.

        Transitions the round from SUBMISSION_OPEN to SUBMISSION_CLOSED,
        fetches all submissions for the round, and emits a
        submission_window.closed event with submission data.

        Args:
            round_id: Unique identifier for the round

        Returns:
            Updated Round entity with SUBMISSION_CLOSED status

        Raises:
            RoundNotFoundException: If round not found
            InvalidStateTransitionException: If round not in SUBMISSION_OPEN
        """
        # Fetch round from database
        result = await self.db_session.execute(
            select(Round).where(Round.round_id == round_id)
        )
        round_entity = result.scalar_one_or_none()

        if not round_entity:
            raise RoundNotFoundException(str(round_id))

        # Validate status transition using Round's state machine
        try:
            round_entity.close_submission_window()
        except ValueError as e:
            raise InvalidStateTransitionException(
                entity_type="Round",
                entity_id=str(round_id),
                from_state=str(round_entity.status),
                to_state=str(RoundStatus.SUBMISSION_CLOSED),
                reason=str(e),
            ) from e

        # Fetch all submissions for this round
        submissions_result = await self.db_session.execute(
            select(Submission).where(Submission.round_id == round_id)
        )
        submissions = submissions_result.scalars().all()

        # Convert submissions to event payload format
        submission_summaries: List[SubmissionSummary] = [
            SubmissionSummary(
                submission_id=sub.submission_id,
                participant_id=sub.participant_id,
                submission_text=sub.submission_text,
                modality=sub.modality.value,
                submitted_at=sub.submitted_at,
            )
            for sub in submissions
        ]

        # Commit the status change to the database
        self.db_session.add(round_entity)
        await self.db_session.commit()
        await self.db_session.refresh(round_entity)

        # Emit submission_window.closed event
        try:
            await self.event_bus.emit(
                "submission_window.closed",
                SubmissionWindowClosedEvent(
                    round_id=round_id,
                    submissions=submission_summaries,
                    timestamp=datetime.now(timezone.utc),
                ),
            )

            logger.info(
                f"Closed submission window for round {round_id}. "
                f"Total submissions: {len(submission_summaries)}"
            )

        except Exception as e:
            logger.error(
                f"Failed to emit submission_window.closed event for round {round_id}: {e}",
                exc_info=True,
            )
            # Don't raise - event emission failure shouldn't prevent window closure

        return round_entity

    async def get_round(self, round_id: UUID) -> Round:
        """
        Fetch a round by ID.

        Args:
            round_id: Unique identifier for the round

        Returns:
            Round entity

        Raises:
            RoundNotFoundException: If round not found
        """
        result = await self.db_session.execute(
            select(Round).where(Round.round_id == round_id)
        )
        round_entity = result.scalar_one_or_none()

        if not round_entity:
            raise RoundNotFoundException(str(round_id))

        return round_entity

    async def get_rounds_by_discussion(self, discussion_id: UUID) -> List[Round]:
        """
        Fetch all rounds for a discussion.

        Args:
            discussion_id: Unique identifier for the discussion

        Returns:
            List of Round entities ordered by round_num
        """
        result = await self.db_session.execute(
            select(Round)
            .where(Round.discussion_id == discussion_id)
            .order_by(Round.round_num)
        )
        return list(result.scalars().all())

    async def check_advancement_blockers(self, round_id: UUID) -> List[str]:
        """
        Check for blockers preventing round advancement (T059).

        Checks:
        1. Round exists
        2. Round is ready for advancement (Sankey complete, question ready)
        3. Previous round (if exists) is COMPLETE
        4. Current round hasn't already started

        Args:
            round_id: UUID of the round to check

        Returns:
            List of blocking reasons (empty list if ready to advance)

        Raises:
            RoundNotFoundException: If round not found
        """
        blockers = []

        # Fetch round
        result = await self.db_session.execute(
            select(Round).where(Round.round_id == round_id)
        )
        round_entity = result.scalar_one_or_none()

        if not round_entity:
            raise RoundNotFoundException(str(round_id))

        # Check if round can advance using Round's can_advance method
        can_advance, reason = round_entity.can_advance()
        if not can_advance:
            blockers.append(reason)

        # Check if already started
        if round_entity.status not in (RoundStatus.PENDING, RoundStatus.QUESTION_READY):
            blockers.append(
                f"Round already in {round_entity.status.value} state - cannot advance"
            )

        # Check previous round is complete (if not round 1)
        if round_entity.round_num > 1:
            result = await self.db_session.execute(
                select(Round)
                .where(Round.discussion_id == round_entity.discussion_id)
                .where(Round.round_num == round_entity.round_num - 1)
            )
            prev_round = result.scalar_one_or_none()

            if prev_round is None:
                blockers.append(f"Previous round {round_entity.round_num - 1} not found")
            elif prev_round.status != RoundStatus.COMPLETE:
                blockers.append(
                    f"Previous round {prev_round.round_num} must be COMPLETE "
                    f"(current: {prev_round.status.value})"
                )

        return blockers

    async def validate_host_can_advance(self, discussion_id: UUID, user_id: UUID) -> bool:
        """
        Validate that a user is authorized to advance a discussion (T061).

        Only the discussion host can advance to the next round.

        Args:
            discussion_id: UUID of the discussion
            user_id: UUID of the user attempting to advance

        Returns:
            bool: True if user is the host

        Raises:
            RoundNotFoundException: If discussion not found (reusing exception for simplicity)
        """
        from src.models.discussion import Discussion

        # Fetch discussion
        result = await self.db_session.execute(
            select(Discussion).where(Discussion.discussion_id == discussion_id)
        )
        discussion = result.scalar_one_or_none()

        if not discussion:
            # Reuse RoundNotFoundException for consistency (or could create DiscussionNotFoundException)
            raise RoundNotFoundException(f"Discussion {discussion_id} not found")

        return discussion.host_user_id == user_id
