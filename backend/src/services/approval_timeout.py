"""
Approval timeout handler for marking unapproved summaries after deadline.

Scheduled via TimingService to enforce approval deadlines and mark participants
as dropouts when they fail to approve their summaries within the time window.
"""

import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.events.event_bus import get_event_bus
from src.models.approved_summary import ApprovedSummary
from src.models.participant import Participant
from src.models.protocol_state import DropoutReason
from src.models.round import Round
from src.models.submission import Submission, SummaryStatus

logger = logging.getLogger(__name__)


class ApprovalTimeoutService:
    """
    Service for handling approval deadline timeouts.

    Features (T087):
    - Mark unapproved submissions as APPROVAL_TIMEOUT after deadline
    - Mark participants as dropouts (dropout_reason=NO_APPROVAL)
    - Schedule via TimingService
    - Emit timeout events for monitoring
    - Idempotent operations (safe to retry)
    """

    def __init__(self) -> None:
        """Initialize approval timeout service."""
        self._session_factory = get_session_factory()

    async def schedule_approval_deadline(
        self,
        round_id: UUID,
        approval_deadline: datetime,
    ) -> None:
        """
        Schedule approval deadline timeout handler for a round.

        Args:
            round_id: UUID of the round
            approval_deadline: UTC datetime when approval deadline expires

        Raises:
            ConnectionError: If TimingService not available
            ValueError: If deadline is in the past
        """
        from src.services.timing_service import get_timing_service

        timing_service = await get_timing_service()

        # Schedule closure at approval deadline
        await timing_service.schedule_closure(
            round_id=round_id,
            close_at=approval_deadline,
        )

        logger.info(
            f"Scheduled approval deadline timeout for round {round_id} at {approval_deadline}"
        )

    async def handle_approval_timeout(self, round_id: UUID) -> None:
        """
        Handle approval deadline timeout for a round.

        Marks all unapproved submissions as APPROVAL_TIMEOUT and marks
        participants as dropouts with reason=NO_APPROVAL.

        This operation is idempotent - safe to call multiple times.

        Args:
            round_id: UUID of the round with expired approval deadline

        Constitutional Principle:
        - Synchronous Deliberation (Principle VI): Enforce strict timing to
          prevent gaming and maintain time-boxed execution.
        """
        async with self._session_factory() as session:
            try:
                # Fetch round
                round_result = await session.execute(
                    select(Round).where(Round.round_id == round_id)
                )
                round_obj = round_result.scalar_one_or_none()

                if not round_obj:
                    logger.warning(
                        f"Round {round_id} not found for approval timeout handling"
                    )
                    return

                # Check if deadline has actually passed (idempotency check)
                now = datetime.now(timezone.utc)
                if round_obj.approval_deadline and round_obj.approval_deadline > now:
                    logger.warning(
                        f"Approval deadline for round {round_id} has not yet passed "
                        f"(deadline: {round_obj.approval_deadline}, now: {now})"
                    )
                    return

                # Find all unapproved submissions for this round
                unapproved_result = await session.execute(
                    select(Submission)
                    .where(
                        Submission.round_id == round_id,
                        Submission.summary_status == SummaryStatus.PENDING,
                    )
                )
                unapproved_submissions = unapproved_result.scalars().all()

                if not unapproved_submissions:
                    logger.info(
                        f"No unapproved submissions found for round {round_id} - "
                        f"timeout handler is idempotent"
                    )
                    return

                # Mark submissions as APPROVAL_TIMEOUT
                participant_ids_to_dropout: List[UUID] = []
                for submission in unapproved_submissions:
                    submission.summary_status = SummaryStatus.APPROVAL_TIMEOUT
                    submission.mark_for_deletion()
                    participant_ids_to_dropout.append(submission.participant_id)

                    logger.info(
                        f"Marked submission {submission.submission_id} as APPROVAL_TIMEOUT "
                        f"for participant {submission.participant_id}"
                    )

                # Mark participants as dropouts
                dropout_count = await self._mark_participants_as_dropouts(
                    session=session,
                    participant_ids=participant_ids_to_dropout,
                    round_num=round_obj.round_num,
                )

                # Commit changes
                await session.commit()

                # Emit timeout event for monitoring
                await self._emit_timeout_event(
                    round_id=round_id,
                    timeout_count=len(unapproved_submissions),
                    dropout_count=dropout_count,
                )

                logger.info(
                    f"Approval timeout handled for round {round_id}: "
                    f"{len(unapproved_submissions)} submissions marked APPROVAL_TIMEOUT, "
                    f"{dropout_count} participants marked as dropouts"
                )

            except Exception as e:
                await session.rollback()
                logger.error(
                    f"Error handling approval timeout for round {round_id}: {e}",
                    exc_info=True,
                )
                raise

    async def _mark_participants_as_dropouts(
        self,
        session: AsyncSession,
        participant_ids: List[UUID],
        round_num: int,
    ) -> int:
        """
        Mark participants as dropouts with reason=NO_APPROVAL.

        Args:
            session: Database session
            participant_ids: List of participant UUIDs to mark as dropouts
            round_num: Round number where dropout occurred

        Returns:
            Number of participants marked as dropouts
        """
        dropout_count = 0

        for participant_id in participant_ids:
            result = await session.execute(
                select(Participant).where(Participant.participant_id == participant_id)
            )
            participant = result.scalar_one_or_none()

            if not participant:
                logger.warning(f"Participant {participant_id} not found")
                continue

            # Skip if already marked as dropout (idempotency)
            if not participant.is_active():
                logger.debug(
                    f"Participant {participant_id} already marked as dropout - skipping"
                )
                continue

            # Mark as dropout
            participant.mark_dropout(
                reason=DropoutReason.NO_APPROVAL,
                round_num=round_num,
            )
            dropout_count += 1

            logger.info(
                f"Marked participant {participant_id} as dropout "
                f"(reason=NO_APPROVAL, round={round_num})"
            )

        return dropout_count

    async def _emit_timeout_event(
        self,
        round_id: UUID,
        timeout_count: int,
        dropout_count: int,
    ) -> None:
        """
        Emit approval timeout event for monitoring.

        Args:
            round_id: Round where timeout occurred
            timeout_count: Number of submissions marked APPROVAL_TIMEOUT
            dropout_count: Number of participants marked as dropouts
        """
        try:
            event_bus = await get_event_bus()
            await event_bus.emit(
                "approval.timeout",
                {
                    "round_id": str(round_id),
                    "timeout_count": timeout_count,
                    "dropout_count": dropout_count,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            logger.debug(
                f"Emitted approval.timeout event for round {round_id}: "
                f"timeout_count={timeout_count}, dropout_count={dropout_count}"
            )

        except Exception as e:
            # Don't fail the entire operation if event emission fails
            logger.warning(
                f"Failed to emit approval.timeout event for round {round_id}: {e}"
            )


# Global service instance
_approval_timeout_service: ApprovalTimeoutService | None = None


async def get_approval_timeout_service() -> ApprovalTimeoutService:
    """
    Get or create the global approval timeout service instance.

    Returns:
        ApprovalTimeoutService: The global service instance
    """
    global _approval_timeout_service

    if _approval_timeout_service is None:
        _approval_timeout_service = ApprovalTimeoutService()

    return _approval_timeout_service
