"""
Approval Deadline Timeout Handler

Marks summaries as APPROVAL_TIMEOUT when approval deadline expires.
Participants who don't approve within deadline are marked as dropouts.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T091)
Event Trigger: approval_deadline.expired (from Spec 0 timing service)
"""

import logging
from datetime import datetime
from typing import List, Dict
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ..models.summary import Summary, SummaryStatus

logger = logging.getLogger(__name__)


class ApprovalDeadlineHandler:
    """Handler for approval deadline timeout events."""

    def __init__(self, db: AsyncSession):
        """Initialize handler with database session."""
        self.db = db

    async def handle_deadline_expired(
        self,
        round_id: UUID,
        deadline_timestamp: datetime,
    ) -> Dict[str, any]:
        """
        Handle approval deadline expiration for a round.

        Marks all PENDING_REVIEW summaries as APPROVAL_TIMEOUT.
        Returns statistics about timed-out summaries.

        Args:
            round_id: UUID of round with expired deadline
            deadline_timestamp: Deadline datetime that was exceeded

        Returns:
            Dictionary with timeout statistics
        """
        try:
            logger.info(
                f"Processing approval deadline timeout for round {round_id}",
                extra={
                    "round_id": str(round_id),
                    "deadline": deadline_timestamp.isoformat(),
                },
            )

            # Find all PENDING_REVIEW summaries for this round
            result = await self.db.execute(
                select(Summary)
                .where(Summary.round_id == round_id)
                .where(Summary.status == SummaryStatus.PENDING_REVIEW)
            )
            pending_summaries = list(result.scalars().all())

            if not pending_summaries:
                logger.info(
                    f"No pending summaries to timeout for round {round_id}",
                    extra={"round_id": str(round_id)},
                )
                return {
                    "round_id": str(round_id),
                    "timed_out_count": 0,
                    "dropout_participants": [],
                }

            # Mark summaries as APPROVAL_TIMEOUT
            timed_out_count = 0
            dropout_participants = []

            for summary in pending_summaries:
                summary.status = SummaryStatus.APPROVAL_TIMEOUT
                timed_out_count += 1
                if summary.participant_id not in dropout_participants:
                    dropout_participants.append(summary.participant_id)

            await self.db.commit()

            logger.info(
                f"Marked {timed_out_count} summaries as APPROVAL_TIMEOUT for round {round_id}",
                extra={
                    "round_id": str(round_id),
                    "timed_out_count": timed_out_count,
                    "dropout_count": len(dropout_participants),
                },
            )

            return {
                "round_id": str(round_id),
                "timed_out_count": timed_out_count,
                "dropout_participants": [str(p) for p in dropout_participants],
                "deadline": deadline_timestamp.isoformat(),
            }

        except Exception as e:
            logger.error(
                f"Error processing approval deadline timeout for round {round_id}: {e}",
                extra={"round_id": str(round_id), "error": str(e)},
                exc_info=True,
            )
            await self.db.rollback()
            raise

    async def get_timed_out_summaries(self, round_id: UUID) -> List[Summary]:
        """
        Get all timed-out summaries for a round.

        Args:
            round_id: UUID of round

        Returns:
            List of Summary objects with APPROVAL_TIMEOUT status
        """
        result = await self.db.execute(
            select(Summary)
            .where(Summary.round_id == round_id)
            .where(Summary.status == SummaryStatus.APPROVAL_TIMEOUT)
            .order_by(Summary.created_at)
        )
        return list(result.scalars().all())

    async def check_and_timeout_expired(self, round_id: UUID, deadline: datetime) -> int:
        """
        Check if deadline has passed and timeout summaries if needed.

        Args:
            round_id: UUID of round
            deadline: Approval deadline datetime

        Returns:
            Number of summaries timed out
        """
        now = datetime.utcnow()

        if now < deadline:
            logger.debug(
                f"Approval deadline not yet reached for round {round_id}",
                extra={
                    "round_id": str(round_id),
                    "deadline": deadline.isoformat(),
                    "now": now.isoformat(),
                },
            )
            return 0

        # Deadline has passed - timeout pending summaries
        result = await self.handle_deadline_expired(round_id, deadline)
        return result["timed_out_count"]
