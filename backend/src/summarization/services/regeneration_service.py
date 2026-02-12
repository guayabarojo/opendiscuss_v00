"""
Regeneration service for Spec 003 - User Story 2.

Handles summary regeneration with bounded retry logic (max 2 automatic attempts).
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...logging_config import logger
from ..models.summary import Summary, SummaryStatus
from .summarization_service import SummarizationService


class RegenerationService:
    """
    Service for managing summary regeneration with bounded retries.

    Constitutional Compliance:
    - Intent Fidelity: Gives participants multiple chances to get accurate representation
    - Bounded Retry: Max 2 automatic regenerations to prevent infinite loops

    User Story 2 Implementation:
    - T038: Implement regenerate_summary() with bounded retry logic
    - T039: Integrate rejection workflow (check regen_count before triggering regen)
    - T045: Validation for max 2 automatic regenerations
    """

    MAX_AUTO_REGENERATIONS = 2  # After this, require correction signal (User Story 3)

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.summarization_service = SummarizationService(db)

    async def can_auto_regenerate(self, summary_id: UUID) -> bool:
        """
        Check if summary is eligible for automatic regeneration.

        Validation (T045): Returns True only if regen_count < MAX_AUTO_REGENERATIONS.

        Args:
            summary_id: Summary UUID to check

        Returns:
            bool: True if automatic regeneration is allowed, False otherwise

        Raises:
            ValueError: If summary not found
        """
        result = await self.db.execute(
            select(Summary).where(Summary.summary_id == summary_id)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            raise ValueError(f"Summary {summary_id} not found")

        can_regen = summary.regen_count < self.MAX_AUTO_REGENERATIONS

        # Logging (T046)
        logger.info(
            f"Auto-regeneration check for summary {summary_id}: "
            f"regen_count={summary.regen_count}, "
            f"can_auto_regenerate={can_regen}, "
            f"max_allowed={self.MAX_AUTO_REGENERATIONS}"
        )

        return can_regen

    async def regenerate_with_bounded_retry(
        self,
        rejected_summary_id: UUID,
        use_fallback_model: bool = False,
    ) -> Optional[Summary]:
        """
        Regenerate summary with bounded retry logic (T038, T039).

        Core regeneration workflow for User Story 2:
        1. Check if automatic regeneration is allowed (regen_count < 2)
        2. If allowed, call SummarizationService.regenerate_summary()
        3. If not allowed, return None (caller should prompt for correction signal)

        FSM Transitions:
        - If regen_count < 2: Generate new summary with PENDING_REVIEW status
        - If regen_count >= 2: Return None, require correction signal (User Story 3)

        Args:
            rejected_summary_id: ID of summary that was rejected
            use_fallback_model: If True, use GPT-3.5 instead of GPT-4-turbo

        Returns:
            Summary: New summary with incremented regen_count, or None if max retries reached

        Raises:
            ValueError: If summary not found or invalid
            Exception: If LLM call fails
        """
        # Fetch rejected summary
        result = await self.db.execute(
            select(Summary).where(Summary.summary_id == rejected_summary_id)
        )
        rejected_summary = result.scalar_one_or_none()

        if not rejected_summary:
            raise ValueError(f"Summary {rejected_summary_id} not found")

        # Validation: Check bounded retry limit (T045)
        if rejected_summary.regen_count >= self.MAX_AUTO_REGENERATIONS:
            logger.info(
                f"Max automatic regenerations reached for summary {rejected_summary_id}: "
                f"regen_count={rejected_summary.regen_count}, "
                f"max_allowed={self.MAX_AUTO_REGENERATIONS}. "
                f"Correction signal required (User Story 3)."
            )
            return None

        # Logging: Starting regeneration (T046)
        logger.info(
            f"Starting automatic regeneration for summary {rejected_summary_id}: "
            f"submission_id={rejected_summary.submission_id}, "
            f"participant_id={rejected_summary.participant_id}, "
            f"round_id={rejected_summary.round_id}, "
            f"current_regen_count={rejected_summary.regen_count}, "
            f"new_regen_count={rejected_summary.regen_count + 1}"
        )

        # Generate new summary using SummarizationService
        try:
            new_summary = await self.summarization_service.regenerate_summary(
                previous_summary_id=rejected_summary_id,
                use_fallback_model=use_fallback_model,
            )

            # Logging: Regeneration successful (T046)
            logger.info(
                f"Regeneration successful: "
                f"new_summary_id={new_summary.summary_id}, "
                f"regen_count={new_summary.regen_count}, "
                f"status={new_summary.status.value}, "
                f"length={len(new_summary.summary_text)} chars"
            )

            return new_summary

        except Exception as e:
            # Logging: Regeneration failed (T046)
            logger.error(
                f"Regeneration failed for summary {rejected_summary_id}: {e}",
                exc_info=True
            )
            raise

    async def get_regeneration_status(self, summary_id: UUID) -> dict:
        """
        Get regeneration status for a summary.

        Useful for frontend to display "Attempt X/3" counter.

        Args:
            summary_id: Summary UUID

        Returns:
            dict: {
                "current_attempt": int,  # regen_count + 1 (1-indexed)
                "max_attempts": int,     # 3 (initial + 2 auto-regen)
                "can_auto_regenerate": bool,
                "needs_correction_signal": bool,  # True if regen_count >= 2
            }

        Raises:
            ValueError: If summary not found
        """
        result = await self.db.execute(
            select(Summary).where(Summary.summary_id == summary_id)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            raise ValueError(f"Summary {summary_id} not found")

        current_attempt = summary.regen_count + 1  # 1-indexed for UI
        max_attempts = self.MAX_AUTO_REGENERATIONS + 1  # 3 total (initial + 2 regen)
        can_auto_regenerate = summary.regen_count < self.MAX_AUTO_REGENERATIONS
        needs_correction_signal = summary.regen_count >= self.MAX_AUTO_REGENERATIONS

        return {
            "current_attempt": current_attempt,
            "max_attempts": max_attempts,
            "can_auto_regenerate": can_auto_regenerate,
            "needs_correction_signal": needs_correction_signal,
        }
