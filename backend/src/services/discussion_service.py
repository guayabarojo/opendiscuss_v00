"""
Discussion management service for the OpenDiscuss Discussion Protocol.

Provides business logic for creating and managing discussions, including
question validation, round creation, and lifecycle state transitions.
"""

import re
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.discussion import Discussion, DiscussionMode, DiscussionStatus
from src.models.round import Round, RoundStatus
from src.events.event_bus import EventBus
from src.events.event_types import DiscussionStartedEvent, RoundStartedEvent
from src.services.timing_service import TimingService
from src.services.round_service import RoundService
from src.api.error_handlers import (
    DiscussionNotFoundException,
    InvalidStateTransitionException,
)
from src.logging_config import get_logger, set_discussion_id, set_round_id

logger = get_logger(__name__)


class DiscussionService:
    """
    Service for managing discussion lifecycle and coordination.

    Features:
    - Creates discussions in HOST_DEFINED mode with validated questions
    - Creates Round entities for each question
    - Transitions discussions from CREATED to ACTIVE
    - Opens first round submission window
    - Emits discussion.started event
    """

    # Question validation constants
    QUESTION_MIN_LENGTH = 10
    QUESTION_MAX_LENGTH = 200
    FORBIDDEN_KEYWORDS = ["vote", "rank", "best", "worst"]
    VALID_QUESTION_STARTERS = ["What", "How"]

    def __init__(
        self,
        db_session: AsyncSession,
        event_bus: EventBus,
        timing_service: TimingService,
    ) -> None:
        """
        Initialize DiscussionService with required dependencies.

        Args:
            db_session: Database session for persistence operations
            event_bus: Event bus for emitting protocol events
            timing_service: Timing service for scheduling window closures
        """
        self.db_session = db_session
        self.event_bus = event_bus
        self.timing_service = timing_service

    def _validate_question(self, question: str) -> None:
        """
        Validate a question against protocol requirements.

        Requirements per spec:
        - 10-200 characters
        - Starts with "What" or "How" (case-insensitive)
        - No voting/ranking keywords (vote, rank, best, worst)

        Args:
            question: Question text to validate

        Raises:
            ValueError: If validation fails with descriptive message
        """
        if not question:
            raise ValueError("Question cannot be empty")

        question_len = len(question)
        if not (self.QUESTION_MIN_LENGTH <= question_len <= self.QUESTION_MAX_LENGTH):
            raise ValueError(
                f"Question must be {self.QUESTION_MIN_LENGTH}-{self.QUESTION_MAX_LENGTH} "
                f"characters, got {question_len}"
            )

        # Check if starts with valid starter
        question_lower = question.lower()
        if not any(question_lower.startswith(starter.lower()) for starter in self.VALID_QUESTION_STARTERS):
            starters_str = " or ".join([f"'{s}'" for s in self.VALID_QUESTION_STARTERS])
            raise ValueError(
                f"Question must start with {starters_str}, got: '{question[:20]}...'"
            )

        # Check for forbidden keywords
        for keyword in self.FORBIDDEN_KEYWORDS:
            if keyword in question_lower:
                raise ValueError(
                    f"Question cannot contain voting/ranking keyword: '{keyword}'"
                )

    async def create_discussion(
        self,
        community_id: UUID,
        host_user_id: UUID,
        questions: List[str],
        submission_window_duration_sec: int = 300,  # Default 5 minutes
    ) -> Discussion:
        """
        Create a new discussion in HOST_DEFINED mode with validated questions.

        Creates:
        - Discussion entity in CREATED status
        - Round entities for each question in PENDING status

        Args:
            community_id: UUID of the owning community
            host_user_id: UUID of the user creating the discussion
            questions: List of question texts (1-10 questions)
            submission_window_duration_sec: Duration for submission windows (180-360 seconds)

        Returns:
            Discussion entity with associated Round entities

        Raises:
            ValueError: If validation fails (question format, count, window duration)
        """
        # Validate question count
        if not questions:
            raise ValueError("Must provide at least one question")

        total_rounds = len(questions)
        if not (1 <= total_rounds <= 10):
            raise ValueError(
                f"Discussion must have 1-10 rounds, got {total_rounds}"
            )

        # Validate submission window duration
        if not (180 <= submission_window_duration_sec <= 360):
            raise ValueError(
                f"Submission window duration must be 180-360 seconds, "
                f"got {submission_window_duration_sec}"
            )

        # Validate each question
        for i, question in enumerate(questions, start=1):
            try:
                self._validate_question(question)
            except ValueError as e:
                raise ValueError(f"Question {i} validation failed: {e}") from e

        # Create Discussion entity
        discussion = Discussion(
            community_id=community_id,
            host_user_id=host_user_id,
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=total_rounds,
        )

        self.db_session.add(discussion)
        await self.db_session.flush()  # Get discussion_id before creating rounds

        # Set discussion_id in logging context for correlation
        set_discussion_id(str(discussion.discussion_id))

        logger.info(
            "Creating discussion with rounds",
            extra={
                "community_id": str(community_id),
                "total_rounds": total_rounds,
                "host_user_id": str(host_user_id),
                "mode": discussion.mode.value,
            },
        )

        # Create Round entities for each question
        rounds = []
        for round_num, question_text in enumerate(questions, start=1):
            round_entity = Round(
                discussion_id=discussion.discussion_id,
                round_num=round_num,
                question_text=question_text,
                submission_window_duration_sec=submission_window_duration_sec,
            )
            self.db_session.add(round_entity)
            rounds.append(round_entity)

            logger.debug(
                "Created round for discussion",
                extra={
                    "round_num": round_num,
                    "question_preview": question_text[:50],
                },
            )

        # Commit all entities
        await self.db_session.commit()
        await self.db_session.refresh(discussion)

        logger.info(
            "Successfully created discussion",
            extra={
                "rounds_created": len(rounds),
            },
        )

        return discussion

    async def start_discussion(self, discussion_id: UUID) -> Discussion:
        """
        Start a discussion by transitioning to ACTIVE status and opening Round 1.

        Performs:
        1. Transitions Discussion from CREATED to ACTIVE
        2. Increments current_round_num to 1
        3. Opens Round 1 submission window via RoundService
        4. Schedules window closure via TimingService
        5. Emits discussion.started event

        Args:
            discussion_id: Unique identifier for the discussion

        Returns:
            Updated Discussion entity with ACTIVE status

        Raises:
            DiscussionNotFoundException: If discussion not found
            InvalidStateTransitionException: If discussion not in CREATED status
            ValueError: If Round 1 not found
            ConnectionError: If TimingService scheduling fails
        """
        # Fetch discussion from database
        result = await self.db_session.execute(
            select(Discussion).where(Discussion.discussion_id == discussion_id)
        )
        discussion = result.scalar_one_or_none()

        if not discussion:
            raise DiscussionNotFoundException(str(discussion_id))

        # Set discussion_id in logging context
        set_discussion_id(str(discussion_id))

        # Validate status transition using Discussion's state machine
        try:
            discussion.start()
        except ValueError as e:
            logger.error(
                "Failed to start discussion - invalid state transition",
                extra={
                    "current_status": discussion.status.value,
                    "error": str(e),
                },
            )
            raise InvalidStateTransitionException(
                entity_type="Discussion",
                entity_id=str(discussion_id),
                from_state=str(discussion.status),
                to_state=str(DiscussionStatus.ACTIVE),
                reason=str(e),
            ) from e

        # Update current_round_num to 1
        discussion.current_round_num = 1

        # Commit discussion status change
        self.db_session.add(discussion)
        await self.db_session.commit()
        await self.db_session.refresh(discussion)

        logger.info(
            "Transitioned discussion to ACTIVE status",
            extra={
                "started_at": discussion.started_at.isoformat() if discussion.started_at else None,
                "current_round_num": discussion.current_round_num,
            },
        )

        # Fetch Round 1
        rounds_result = await self.db_session.execute(
            select(Round)
            .where(Round.discussion_id == discussion_id)
            .where(Round.round_num == 1)
        )
        round_1 = rounds_result.scalar_one_or_none()

        if not round_1:
            raise ValueError(
                f"Round 1 not found for discussion {discussion_id}. "
                f"Discussion may be in invalid state."
            )

        # Open Round 1 submission window via RoundService
        round_service = RoundService(
            db_session=self.db_session,
            event_bus=self.event_bus,
            timing_service=self.timing_service,
        )

        # Set round_id in logging context
        set_round_id(str(round_1.round_id))

        try:
            await round_service.open_submission_window(round_1.round_id)
            logger.info(
                "Opened submission window for Round 1",
                extra={
                    "round_num": 1,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to open submission window for Round 1",
                extra={
                    "error": str(e),
                },
                exc_info=True,
            )
            # Rollback discussion status if round opening fails
            discussion.status = DiscussionStatus.CREATED
            discussion.started_at = None
            discussion.current_round_num = 0
            self.db_session.add(discussion)
            await self.db_session.commit()
            raise

        # Emit discussion.started event
        try:
            await self.event_bus.emit(
                "discussion.started",
                DiscussionStartedEvent(
                    discussion_id=discussion_id,
                    round_id=round_1.round_id,
                    timestamp=datetime.now(timezone.utc),
                ),
            )

            logger.info(
                "Emitted discussion.started event",
                extra={
                    "event_type": "discussion.started",
                },
            )

        except Exception as e:
            logger.error(
                "Failed to emit discussion.started event",
                extra={
                    "error": str(e),
                },
                exc_info=True,
            )
            # Don't raise - event emission failure shouldn't prevent discussion start

        return discussion

    async def advance_round(self, discussion_id: UUID) -> Discussion:
        """
        Advance discussion to the next round.

        Performs:
        1. Validates discussion is ACTIVE
        2. Validates current_round_num < total_rounds
        3. Validates current round status is COMPLETE or QUESTION_READY
        4. Increments Discussion.current_round_num
        5. Fetches next Round entity
        6. Opens next round submission window via RoundService
        7. Emits round.started event
        8. Returns updated Discussion

        Args:
            discussion_id: Unique identifier for the discussion

        Returns:
            Updated Discussion entity with incremented current_round_num

        Raises:
            DiscussionNotFoundException: If discussion not found
            InvalidStateTransitionException: If discussion not ACTIVE,
                current round not COMPLETE/QUESTION_READY, or already at final round
            ValueError: If next round not found
            ConnectionError: If TimingService scheduling fails
        """
        # Fetch discussion from database
        result = await self.db_session.execute(
            select(Discussion).where(Discussion.discussion_id == discussion_id)
        )
        discussion = result.scalar_one_or_none()

        if not discussion:
            raise DiscussionNotFoundException(str(discussion_id))

        # Validate discussion is ACTIVE
        if discussion.status != DiscussionStatus.ACTIVE:
            raise InvalidStateTransitionException(
                entity_type="Discussion",
                entity_id=str(discussion_id),
                from_state=str(discussion.status),
                to_state="NEXT_ROUND",
                reason="Cannot advance round: discussion must be in ACTIVE status",
            )

        # Validate not at final round
        if discussion.current_round_num >= discussion.total_rounds:
            raise InvalidStateTransitionException(
                entity_type="Discussion",
                entity_id=str(discussion_id),
                from_state=f"Round {discussion.current_round_num}/{discussion.total_rounds}",
                to_state=f"Round {discussion.current_round_num + 1}",
                reason=f"Cannot advance: already at final round ({discussion.total_rounds})",
            )

        # Fetch current round to validate its status
        current_round_result = await self.db_session.execute(
            select(Round)
            .where(Round.discussion_id == discussion_id)
            .where(Round.round_num == discussion.current_round_num)
        )
        current_round = current_round_result.scalar_one_or_none()

        if current_round:
            # Validate current round is COMPLETE or QUESTION_READY
            if current_round.status not in (RoundStatus.COMPLETE, RoundStatus.QUESTION_READY):
                raise InvalidStateTransitionException(
                    entity_type="Round",
                    entity_id=str(current_round.round_id),
                    from_state=str(current_round.status),
                    to_state="ADVANCE_TO_NEXT",
                    reason=f"Cannot advance: current round must be COMPLETE or QUESTION_READY, got {current_round.status}",
                )

        # Increment current_round_num
        next_round_num = discussion.current_round_num + 1
        discussion.current_round_num = next_round_num
        discussion.updated_at = datetime.now(timezone.utc)

        # Commit discussion update
        self.db_session.add(discussion)
        await self.db_session.commit()
        await self.db_session.refresh(discussion)

        logger.info(
            f"Advanced discussion {discussion_id} to round {next_round_num}/{discussion.total_rounds}"
        )

        # Fetch next Round entity
        next_round_result = await self.db_session.execute(
            select(Round)
            .where(Round.discussion_id == discussion_id)
            .where(Round.round_num == next_round_num)
        )
        next_round = next_round_result.scalar_one_or_none()

        if not next_round:
            raise ValueError(
                f"Round {next_round_num} not found for discussion {discussion_id}. "
                f"Discussion may be in invalid state."
            )

        # Open next round submission window via RoundService
        round_service = RoundService(
            db_session=self.db_session,
            event_bus=self.event_bus,
            timing_service=self.timing_service,
        )

        try:
            await round_service.open_submission_window(next_round.round_id)
            logger.info(
                f"Opened submission window for Round {next_round_num} ({next_round.round_id}) "
                f"of discussion {discussion_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to open submission window for Round {next_round_num} of discussion {discussion_id}: {e}",
                exc_info=True,
            )
            # Rollback round number increment if window opening fails
            discussion.current_round_num = next_round_num - 1
            discussion.updated_at = datetime.now(timezone.utc)
            self.db_session.add(discussion)
            await self.db_session.commit()
            raise

        # Emit round.started event
        try:
            await self.event_bus.emit(
                "round.started",
                RoundStartedEvent(
                    discussion_id=discussion_id,
                    round_id=next_round.round_id,
                    timestamp=datetime.now(timezone.utc),
                ),
            )

            logger.info(
                f"Emitted round.started event for discussion {discussion_id}, "
                f"round {next_round.round_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to emit round.started event for discussion {discussion_id}: {e}",
                exc_info=True,
            )
            # Don't raise - event emission failure shouldn't prevent round advancement

        return discussion

    async def get_discussion(self, discussion_id: UUID) -> Discussion:
        """
        Fetch a discussion by ID.

        Args:
            discussion_id: Unique identifier for the discussion

        Returns:
            Discussion entity with relationships loaded

        Raises:
            DiscussionNotFoundException: If discussion not found
        """
        result = await self.db_session.execute(
            select(Discussion).where(Discussion.discussion_id == discussion_id)
        )
        discussion = result.scalar_one_or_none()

        if not discussion:
            raise DiscussionNotFoundException(str(discussion_id))

        return discussion

    async def get_discussions_by_community(
        self,
        community_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Discussion]:
        """
        Fetch discussions for a community.

        Args:
            community_id: UUID of the community
            limit: Maximum number of discussions to return
            offset: Number of discussions to skip (for pagination)

        Returns:
            List of Discussion entities ordered by created_at DESC
        """
        result = await self.db_session.execute(
            select(Discussion)
            .where(Discussion.community_id == community_id)
            .order_by(Discussion.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def check_and_complete_if_exhausted(
        self, discussion_id: UUID
    ) -> bool:
        """
        Check if discussion has exhausted all questions and mark as COMPLETED if so.

        For HOST_DEFINED mode, checks if current_index >= total_questions in QuestionSequence.
        Only transitions ACTIVE discussions to COMPLETED status.

        Args:
            discussion_id: UUID of the discussion

        Returns:
            True if discussion was completed, False otherwise

        Raises:
            DiscussionNotFoundException: If discussion not found
        """
        # Fetch discussion
        result = await self.db_session.execute(
            select(Discussion).where(Discussion.discussion_id == discussion_id)
        )
        discussion = result.scalar_one_or_none()

        if not discussion:
            raise DiscussionNotFoundException(str(discussion_id))

        # Only check if discussion is ACTIVE
        if discussion.status != DiscussionStatus.ACTIVE:
            return False

        # Check if in HOST_DEFINED mode
        if discussion.mode != DiscussionMode.HOST_DEFINED:
            return False

        # Check if all rounds are complete
        if discussion.current_round_num < discussion.total_rounds:
            return False

        # Check if current round (the last one) is complete
        current_round_result = await self.db_session.execute(
            select(Round)
            .where(Round.discussion_id == discussion_id)
            .where(Round.round_num == discussion.current_round_num)
        )
        current_round = current_round_result.scalar_one_or_none()

        if not current_round or current_round.status != RoundStatus.COMPLETE:
            return False

        # All conditions met, mark discussion as complete
        try:
            discussion.complete()
            self.db_session.add(discussion)
            await self.db_session.commit()
            await self.db_session.refresh(discussion)

            logger.info(
                "Discussion automatically completed (all questions exhausted)",
                extra={
                    "discussion_id": str(discussion_id),
                    "total_rounds": discussion.total_rounds,
                    "completed_at": discussion.completed_at.isoformat() if discussion.completed_at else None,
                },
            )

            return True
        except ValueError as e:
            logger.error(
                "Failed to complete discussion",
                extra={
                    "discussion_id": str(discussion_id),
                    "error": str(e),
                },
            )
            return False

    async def detect_stalled_discussions(self) -> List[Discussion]:
        """
        Detect discussions that have been inactive for more than 7 days.

        Marks discussions as stalled (is_stalled=True) if:
        - Last activity timestamp > 7 days ago
        - Discussion status is ACTIVE

        Returns:
            List of Discussion entities that were marked as stalled

        Note:
            This method should be run by a daily cron job.
        """
        from datetime import timedelta

        stall_threshold = datetime.now(timezone.utc) - timedelta(days=7)

        logger.info(
            "Running stall detection",
            extra={"stall_threshold": stall_threshold.isoformat()}
        )

        # Find ACTIVE discussions with no recent activity
        result = await self.db_session.execute(
            select(Discussion)
            .where(Discussion.status == DiscussionStatus.ACTIVE)
            .where(Discussion.updated_at < stall_threshold)
        )
        stalled_discussions = list(result.scalars().all())

        # Mark as stalled
        for discussion in stalled_discussions:
            # Add is_stalled field if it doesn't exist yet
            if not hasattr(discussion, 'is_stalled'):
                logger.warning(
                    "Discussion model missing is_stalled field - skipping stall detection",
                    extra={"discussion_id": str(discussion.discussion_id)}
                )
                continue

            discussion.is_stalled = True
            discussion.updated_at = datetime.now(timezone.utc)
            self.db_session.add(discussion)

            logger.warning(
                "Discussion marked as stalled",
                extra={
                    "discussion_id": str(discussion.discussion_id),
                    "last_activity": discussion.updated_at.isoformat(),
                    "days_inactive": (datetime.now(timezone.utc) - discussion.updated_at).days
                }
            )

        if stalled_discussions:
            await self.db_session.commit()

            logger.info(
                "Stall detection complete",
                extra={"stalled_count": len(stalled_discussions)}
            )

        return stalled_discussions
