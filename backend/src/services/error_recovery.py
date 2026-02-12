"""
Error recovery mechanisms for handling round failures and discussion termination.

Implements rollback logic for transient failures and termination logic for
unrecoverable errors, with comprehensive logging and event notifications.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.events.event_bus import get_event_bus
from src.models.discussion import Discussion
from src.models.protocol_state import RoundStatus, DiscussionStatus
from src.models.round import Round

logger = logging.getLogger(__name__)


class ErrorRecoveryService:
    """
    Service for error recovery and failure handling.

    Features (T092):
    - Round state rollback on FAILED status
    - Discussion termination on unrecoverable errors
    - Retry logic for transient failures
    - Error notification events
    - Comprehensive error logging
    - Idempotent operations (safe to retry)

    Constitutional Principle:
    - Synchronous Deliberation (Principle VI): Maintain system integrity and
      prevent invalid states that could compromise protocol guarantees.
    """

    def __init__(self) -> None:
        """Initialize error recovery service."""
        self._session_factory = get_session_factory()
        self._max_retry_attempts = 3

    async def handle_round_failure(
        self,
        round_id: UUID,
        error: Exception,
        phase: str,
        retry_count: int = 0,
    ) -> bool:
        """
        Handle round failure with retry logic.

        Attempts to retry transient failures up to max_retry_attempts.
        On permanent failure, marks round as FAILED.

        Args:
            round_id: UUID of the failed round
            error: Exception that caused the failure
            phase: Protocol phase where failure occurred (e.g., "SUMMARIZING")
            retry_count: Current retry attempt number

        Returns:
            True if recovery succeeded (retry can proceed), False if permanent failure

        Constitutional Note:
        - Preserves Intent Fidelity by preventing partial state corruption
        - Maintains Temporal Transparency by tracking failure timing
        """
        async with self._session_factory() as session:
            try:
                # Fetch round
                round_result = await session.execute(
                    select(Round).where(Round.round_id == round_id)
                )
                round_obj = round_result.scalar_one_or_none()

                if not round_obj:
                    logger.error(f"Round {round_id} not found for failure handling")
                    return False

                # Check if this is a transient error
                is_transient = self._is_transient_error(error)

                # Log failure
                logger.error(
                    f"Round {round_id} failure in {phase}: {error} "
                    f"(transient={is_transient}, retry={retry_count}/{self._max_retry_attempts})",
                    exc_info=True,
                )

                # Attempt retry for transient errors
                if is_transient and retry_count < self._max_retry_attempts:
                    logger.info(
                        f"Attempting retry {retry_count + 1}/{self._max_retry_attempts} "
                        f"for round {round_id} in {phase}"
                    )

                    # Emit retry event for monitoring
                    await self._emit_error_event(
                        event_type="round.retry",
                        round_id=round_id,
                        phase=phase,
                        error=error,
                        retry_count=retry_count + 1,
                    )

                    return True  # Signal that retry can proceed

                # Permanent failure - mark round as FAILED
                await self._mark_round_failed(
                    session=session,
                    round_obj=round_obj,
                    phase=phase,
                    error=error,
                )

                # Emit failure event
                await self._emit_error_event(
                    event_type="round.failed",
                    round_id=round_id,
                    phase=phase,
                    error=error,
                    retry_count=retry_count,
                )

                # Commit changes
                await session.commit()

                logger.error(
                    f"Round {round_id} marked as FAILED after {retry_count} retry attempts"
                )

                return False  # Signal permanent failure

            except Exception as e:
                await session.rollback()
                logger.error(
                    f"Error during round failure handling: {e}", exc_info=True
                )
                raise

    async def _mark_round_failed(
        self,
        session: AsyncSession,
        round_obj: Round,
        phase: str,
        error: Exception,
    ) -> None:
        """
        Mark a round as FAILED.

        Args:
            session: Database session
            round_obj: Round entity to mark as failed
            phase: Phase where failure occurred
            error: Exception that caused the failure
        """
        # Transition to FAILED status
        round_obj.advance_status(RoundStatus.FAILED)

        logger.error(
            f"Round {round_obj.round_id} marked as FAILED "
            f"(phase={phase}, discussion={round_obj.discussion_id})"
        )

    async def rollback_round_state(
        self,
        round_id: UUID,
        target_status: RoundStatus,
    ) -> bool:
        """
        Rollback round to a previous valid state.

        This is used for transient failures where the round can be retried
        from a known good state.

        Args:
            round_id: UUID of the round to rollback
            target_status: Status to rollback to

        Returns:
            True if rollback succeeded, False otherwise
        """
        async with self._session_factory() as session:
            try:
                # Fetch round
                round_result = await session.execute(
                    select(Round).where(Round.round_id == round_id)
                )
                round_obj = round_result.scalar_one_or_none()

                if not round_obj:
                    logger.error(f"Round {round_id} not found for state rollback")
                    return False

                # Store current status for logging
                current_status = round_obj.status

                # Update status (bypass state machine for rollback)
                round_obj.status = target_status
                round_obj.updated_at = datetime.now(timezone.utc)

                # Commit changes
                await session.commit()

                logger.info(
                    f"Rolled back round {round_id} state: {current_status} → {target_status}"
                )

                # Emit rollback event
                await self._emit_error_event(
                    event_type="round.rollback",
                    round_id=round_id,
                    phase=str(current_status),
                    error=Exception(f"Rollback to {target_status}"),
                    retry_count=0,
                )

                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Error during round state rollback: {e}", exc_info=True)
                return False

    async def terminate_discussion(
        self,
        discussion_id: UUID,
        reason: str,
        error: Optional[Exception] = None,
    ) -> bool:
        """
        Terminate a discussion due to unrecoverable error.

        Sets discussion status to TERMINATED and logs comprehensive error details.

        Args:
            discussion_id: UUID of the discussion to terminate
            reason: Human-readable termination reason
            error: Optional exception that triggered termination

        Returns:
            True if termination succeeded, False otherwise

        Constitutional Note:
        - Preserves system integrity by gracefully handling unrecoverable failures
        - Maintains auditability through comprehensive logging
        """
        async with self._session_factory() as session:
            try:
                # Fetch discussion
                discussion_result = await session.execute(
                    select(Discussion).where(Discussion.discussion_id == discussion_id)
                )
                discussion_obj = discussion_result.scalar_one_or_none()

                if not discussion_obj:
                    logger.error(
                        f"Discussion {discussion_id} not found for termination"
                    )
                    return False

                # Check if already terminated (idempotency)
                if discussion_obj.status == DiscussionStatus.TERMINATED:
                    logger.info(
                        f"Discussion {discussion_id} already terminated - idempotent"
                    )
                    return True

                # Terminate discussion
                discussion_obj.terminate(reason=reason)

                # Commit changes
                await session.commit()

                # Log termination with full context
                error_msg = str(error) if error else "No exception provided"
                logger.error(
                    f"Discussion {discussion_id} TERMINATED: {reason} - {error_msg}",
                    exc_info=error if error else False,
                )

                # Emit termination event
                await self._emit_error_event(
                    event_type="discussion.terminated",
                    discussion_id=discussion_id,
                    phase="N/A",
                    error=error or Exception(reason),
                    retry_count=0,
                    reason=reason,
                )

                return True

            except Exception as e:
                await session.rollback()
                logger.error(
                    f"Error during discussion termination: {e}", exc_info=True
                )
                return False

    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if an error is transient and retryable.

        Transient errors include:
        - Connection errors (database, Redis)
        - Timeout errors
        - Temporary resource unavailability

        Args:
            error: Exception to classify

        Returns:
            True if error is transient, False if permanent
        """
        transient_error_types = (
            ConnectionError,
            TimeoutError,
            OSError,
        )

        # Check exception type
        if isinstance(error, transient_error_types):
            return True

        # Check error message for transient indicators
        error_msg = str(error).lower()
        transient_keywords = [
            "connection",
            "timeout",
            "temporary",
            "unavailable",
            "retry",
        ]

        for keyword in transient_keywords:
            if keyword in error_msg:
                return True

        # Default to non-transient (safer for data integrity)
        return False

    async def _emit_error_event(
        self,
        event_type: str,
        round_id: Optional[UUID] = None,
        discussion_id: Optional[UUID] = None,
        phase: str = "unknown",
        error: Optional[Exception] = None,
        retry_count: int = 0,
        reason: Optional[str] = None,
    ) -> None:
        """
        Emit error event for monitoring and alerting.

        Args:
            event_type: Type of error event (e.g., "round.failed")
            round_id: Optional round UUID
            discussion_id: Optional discussion UUID
            phase: Protocol phase where error occurred
            error: Optional exception
            retry_count: Number of retry attempts
            reason: Optional termination reason
        """
        try:
            event_bus = await get_event_bus()

            event_data = {
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "phase": phase,
                "retry_count": retry_count,
            }

            if round_id:
                event_data["round_id"] = str(round_id)

            if discussion_id:
                event_data["discussion_id"] = str(discussion_id)

            if error:
                event_data["error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }

            if reason:
                event_data["reason"] = reason

            await event_bus.emit(event_type, event_data)

            logger.debug(f"Emitted {event_type} event: {event_data}")

        except Exception as e:
            # Don't fail the entire operation if event emission fails
            logger.warning(f"Failed to emit {event_type} event: {e}")


# Global service instance
_error_recovery_service: ErrorRecoveryService | None = None


async def get_error_recovery_service() -> ErrorRecoveryService:
    """
    Get or create the global error recovery service instance.

    Returns:
        ErrorRecoveryService: The global service instance
    """
    global _error_recovery_service

    if _error_recovery_service is None:
        _error_recovery_service = ErrorRecoveryService()

    return _error_recovery_service
