"""
Ephemeral Data Cleanup Service

Deletes raw submissions after approval grace period (5 minutes after approval).
Implements TTL-based cleanup for approved summaries.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T092)
"""

import logging
from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import Submission
from ..models.summary import Summary, SummaryStatus

logger = logging.getLogger(__name__)


class CleanupService:
    """Service for cleaning up ephemeral submission data after approval."""

    def __init__(self, db: AsyncSession):
        """Initialize cleanup service with database session."""
        self.db = db
        self.ttl_minutes = settings.submission_ttl_minutes

    async def cleanup_approved_submissions(self) -> int:
        """
        Delete raw submissions for summaries that were approved more than TTL ago.

        Returns:
            Number of submissions deleted
        """
        try:
            # Calculate cutoff time (now - TTL)
            cutoff_time = datetime.utcnow() - timedelta(minutes=self.ttl_minutes)

            # Find approved summaries older than cutoff
            result = await self.db.execute(
                select(Summary.submission_id)
                .where(Summary.status == SummaryStatus.APPROVED)
                .where(Summary.approved_at < cutoff_time)
                .distinct()
            )
            submission_ids = [row[0] for row in result.fetchall()]

            if not submission_ids:
                logger.debug("No submissions to cleanup")
                return 0

            # Delete submissions (raw text data)
            delete_result = await self.db.execute(
                delete(Submission)
                .where(Submission.submission_id.in_(submission_ids))
            )

            deleted_count = delete_result.rowcount
            await self.db.commit()

            logger.info(
                f"Cleaned up {deleted_count} ephemeral submissions "
                f"(approved >{self.ttl_minutes} minutes ago)",
                extra={
                    "deleted_count": deleted_count,
                    "ttl_minutes": self.ttl_minutes,
                    "cutoff_time": cutoff_time.isoformat(),
                },
            )

            return deleted_count

        except Exception as e:
            logger.error(
                f"Error during submission cleanup: {e}",
                extra={"error": str(e)},
                exc_info=True,
            )
            await self.db.rollback()
            return 0

    async def cleanup_specific_submission(self, submission_id: UUID) -> bool:
        """
        Delete specific submission immediately (e.g., after REJECTED_FINAL).

        Args:
            submission_id: UUID of submission to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            result = await self.db.execute(
                delete(Submission)
                .where(Submission.submission_id == submission_id)
            )

            deleted = result.rowcount > 0
            await self.db.commit()

            if deleted:
                logger.info(
                    f"Cleaned up submission {submission_id}",
                    extra={"submission_id": str(submission_id)},
                )

            return deleted

        except Exception as e:
            logger.error(
                f"Error cleaning up submission {submission_id}: {e}",
                extra={"submission_id": str(submission_id), "error": str(e)},
                exc_info=True,
            )
            await self.db.rollback()
            return False

    async def get_cleanup_stats(self) -> dict:
        """
        Get statistics about ephemeral data eligible for cleanup.

        Returns:
            Dictionary with cleanup stats
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=self.ttl_minutes)

            # Count submissions eligible for cleanup
            result = await self.db.execute(
                select(Summary.submission_id)
                .where(Summary.status == SummaryStatus.APPROVED)
                .where(Summary.approved_at < cutoff_time)
                .distinct()
            )
            eligible_count = len(result.fetchall())

            # Count all approved summaries
            total_result = await self.db.execute(
                select(Summary.summary_id)
                .where(Summary.status == SummaryStatus.APPROVED)
            )
            total_approved = len(total_result.fetchall())

            return {
                "eligible_for_cleanup": eligible_count,
                "total_approved_summaries": total_approved,
                "ttl_minutes": self.ttl_minutes,
                "cutoff_time": cutoff_time.isoformat(),
            }

        except Exception as e:
            logger.error(
                f"Error retrieving cleanup stats: {e}",
                extra={"error": str(e)},
                exc_info=True,
            )
            return {
                "eligible_for_cleanup": 0,
                "total_approved_summaries": 0,
                "error": str(e),
            }
