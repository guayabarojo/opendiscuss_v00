"""
Ephemeral data cleanup service for TTL-based submission deletion.

Deletes Submission records after approval + 5-minute grace period using soft
delete. Preserves ApprovedSummary records permanently for constitutional compliance.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_session_factory
from src.models.submission import Submission

logger = logging.getLogger(__name__)


class CleanupService:
    """
    Service for cleaning up ephemeral submission data.

    Features (T088):
    - Delete Submission records after approval + 5-minute grace period
    - Set deleted_at timestamp (soft delete)
    - Schedule via background worker (e.g., Celery, APScheduler)
    - Preserve ApprovedSummary records (permanent)
    - Idempotent operations (safe to retry)

    Constitutional Compliance:
    - Intent Fidelity: Only approved summaries are retained permanently
    - Data retention: Submissions deleted after grace period for privacy
    """

    def __init__(self) -> None:
        """Initialize cleanup service."""
        self._session_factory = get_session_factory()
        self._is_running = False
        self._worker_task: asyncio.Task | None = None
        self._cleanup_interval_seconds = 60  # Run every 60 seconds

    async def start_worker(self) -> None:
        """
        Start the background cleanup worker.

        The worker runs continuously, checking for eligible submissions
        every 60 seconds.
        """
        if self._is_running:
            logger.warning("CleanupService worker already running")
            return

        self._is_running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info(
            f"CleanupService worker started (interval: {self._cleanup_interval_seconds}s)"
        )

    async def stop_worker(self) -> None:
        """Stop the background cleanup worker."""
        if not self._is_running:
            return

        self._is_running = False

        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        logger.info("CleanupService worker stopped")

    async def _worker_loop(self) -> None:
        """
        Internal worker loop that runs cleanup every 60 seconds.

        Runs continuously until cancelled or an unrecoverable error occurs.
        """
        logger.info("CleanupService worker loop started")

        try:
            while self._is_running:
                try:
                    await self.cleanup_expired_submissions()
                except Exception as e:
                    logger.error(f"Error in cleanup worker loop: {e}", exc_info=True)
                    # Continue running - transient errors shouldn't kill the worker

                # Sleep for cleanup interval
                await asyncio.sleep(self._cleanup_interval_seconds)

        except asyncio.CancelledError:
            logger.info("CleanupService worker loop cancelled")
            raise

        except Exception as e:
            logger.error(f"Fatal error in cleanup worker loop: {e}", exc_info=True)
            self._is_running = False
            raise

    async def cleanup_expired_submissions(self) -> int:
        """
        Clean up submissions that are eligible for deletion.

        Deletes submissions where deleted_at + grace_period < now.
        Uses soft delete (deleted_at timestamp already set) to hard delete.

        Returns:
            Number of submissions deleted

        Constitutional Note:
        - ApprovedSummary records are NEVER deleted (permanent retention)
        - Only ephemeral Submission records are deleted after grace period
        """
        async with self._session_factory() as session:
            try:
                # Find submissions eligible for cleanup
                eligible_submissions = await self._find_eligible_submissions(session)

                if not eligible_submissions:
                    logger.debug("No eligible submissions found for cleanup")
                    return 0

                # Delete eligible submissions (hard delete)
                deleted_count = await self._delete_submissions(
                    session=session,
                    submission_ids=[s.submission_id for s in eligible_submissions],
                )

                # Commit changes
                await session.commit()

                logger.info(
                    f"Cleaned up {deleted_count} expired submissions "
                    f"(grace period: {settings.submission_ttl_minutes} minutes)"
                )

                return deleted_count

            except Exception as e:
                await session.rollback()
                logger.error(f"Error during submission cleanup: {e}", exc_info=True)
                raise

    async def _find_eligible_submissions(
        self,
        session: AsyncSession,
    ) -> List[Submission]:
        """
        Find submissions eligible for cleanup.

        A submission is eligible if:
        - deleted_at is not NULL (soft delete marker set)
        - deleted_at + grace_period < now

        Args:
            session: Database session

        Returns:
            List of eligible Submission entities
        """
        now = datetime.now(timezone.utc)
        grace_period = timedelta(minutes=settings.submission_ttl_minutes)
        cleanup_threshold = now - grace_period

        result = await session.execute(
            select(Submission).where(
                Submission.deleted_at.isnot(None),
                Submission.deleted_at < cleanup_threshold,
            )
        )

        eligible = result.scalars().all()

        if eligible:
            logger.debug(
                f"Found {len(eligible)} submissions eligible for cleanup "
                f"(threshold: {cleanup_threshold})"
            )

        return list(eligible)

    async def _delete_submissions(
        self,
        session: AsyncSession,
        submission_ids: List,
    ) -> int:
        """
        Hard delete submissions by ID.

        Args:
            session: Database session
            submission_ids: List of submission UUIDs to delete

        Returns:
            Number of submissions deleted
        """
        if not submission_ids:
            return 0

        result = await session.execute(
            delete(Submission).where(Submission.submission_id.in_(submission_ids))
        )

        deleted_count = result.rowcount

        logger.info(
            f"Hard deleted {deleted_count} submissions: {submission_ids[:5]}..."
            f"{'...' if len(submission_ids) > 5 else ''}"
        )

        return deleted_count

    async def mark_submissions_for_deletion(
        self,
        round_id,
        participant_ids: List | None = None,
    ) -> int:
        """
        Mark submissions for deletion by setting deleted_at timestamp.

        This is a soft delete marker. Actual deletion occurs later via
        cleanup_expired_submissions after grace period.

        Args:
            round_id: Round UUID to mark submissions for
            participant_ids: Optional list of participant UUIDs to filter by

        Returns:
            Number of submissions marked for deletion
        """
        async with self._session_factory() as session:
            try:
                # Build query
                query = select(Submission).where(Submission.round_id == round_id)

                if participant_ids:
                    query = query.where(Submission.participant_id.in_(participant_ids))

                # Find submissions
                result = await session.execute(query)
                submissions = result.scalars().all()

                if not submissions:
                    logger.debug(f"No submissions found to mark for deletion")
                    return 0

                # Mark for deletion
                marked_count = 0
                for submission in submissions:
                    if submission.deleted_at is None:
                        submission.mark_for_deletion()
                        marked_count += 1

                # Commit changes
                await session.commit()

                logger.info(
                    f"Marked {marked_count} submissions for deletion in round {round_id}"
                )

                return marked_count

            except Exception as e:
                await session.rollback()
                logger.error(
                    f"Error marking submissions for deletion: {e}", exc_info=True
                )
                raise

    def is_running(self) -> bool:
        """Check if the cleanup worker is running."""
        return self._is_running


# Global service instance
_cleanup_service: CleanupService | None = None


async def get_cleanup_service() -> CleanupService:
    """
    Get or create the global cleanup service instance.

    Returns:
        CleanupService: The global service instance
    """
    global _cleanup_service

    if _cleanup_service is None:
        _cleanup_service = CleanupService()

    return _cleanup_service


async def start_cleanup_worker() -> None:
    """Start the global cleanup service worker."""
    service = await get_cleanup_service()
    await service.start_worker()


async def stop_cleanup_worker() -> None:
    """Stop the global cleanup service worker."""
    global _cleanup_service

    if _cleanup_service is not None:
        await _cleanup_service.stop_worker()
