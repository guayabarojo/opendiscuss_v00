"""
Analytics Service for Summarization & Approval

Tracks approval rates, rejection rates, and correction signal usage.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T103)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.summary import Summary, SummaryStatus
from ..models.correction_signal import CorrectionSignal

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for tracking approval analytics."""

    def __init__(self, db: AsyncSession):
        """Initialize analytics service with database session."""
        self.db = db

    async def get_approval_rates(self, round_id: Optional[UUID] = None) -> Dict:
        """
        Calculate approval rates for summaries.

        Args:
            round_id: Optional round ID to filter by

        Returns:
            Dictionary with approval statistics
        """
        try:
            # Build query
            query = select(Summary.status, func.count(Summary.summary_id))

            if round_id:
                query = query.where(Summary.round_id == round_id)

            query = query.group_by(Summary.status)

            # Execute query
            result = await self.db.execute(query)
            status_counts = dict(result.fetchall())

            # Calculate rates
            total = sum(status_counts.values())
            approved_count = status_counts.get(SummaryStatus.APPROVED, 0)
            rejected_count = status_counts.get(SummaryStatus.REJECTED, 0)
            rejected_final_count = status_counts.get(SummaryStatus.REJECTED_FINAL, 0)
            pending_count = status_counts.get(SummaryStatus.PENDING_REVIEW, 0)
            disallowed_count = status_counts.get(SummaryStatus.DISALLOWED_CONTENT, 0)
            timeout_count = status_counts.get(SummaryStatus.APPROVAL_TIMEOUT, 0)

            approval_rate = (approved_count / total * 100) if total > 0 else 0.0
            rejection_rate = ((rejected_count + rejected_final_count) / total * 100) if total > 0 else 0.0

            return {
                "total_summaries": total,
                "approved": approved_count,
                "rejected": rejected_count,
                "rejected_final": rejected_final_count,
                "pending_review": pending_count,
                "disallowed_content": disallowed_count,
                "approval_timeout": timeout_count,
                "approval_rate_percent": round(approval_rate, 2),
                "rejection_rate_percent": round(rejection_rate, 2),
                "round_id": str(round_id) if round_id else "all",
            }

        except Exception as e:
            logger.error(f"Error calculating approval rates: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_first_attempt_approval_rate(self, round_id: Optional[UUID] = None) -> float:
        """
        Calculate approval rate on first attempt (regen_count=0).

        Target: 80% approval on first attempt (intent fidelity metric).

        Args:
            round_id: Optional round ID to filter by

        Returns:
            First-attempt approval rate percentage
        """
        try:
            # Count summaries with regen_count=0
            query_total = select(func.count(Summary.summary_id)).where(
                Summary.regen_count == 0
            )

            if round_id:
                query_total = query_total.where(Summary.round_id == round_id)

            result_total = await self.db.execute(query_total)
            total_first_attempts = result_total.scalar()

            # Count approved with regen_count=0
            query_approved = select(func.count(Summary.summary_id)).where(
                Summary.regen_count == 0,
                Summary.status == SummaryStatus.APPROVED,
            )

            if round_id:
                query_approved = query_approved.where(Summary.round_id == round_id)

            result_approved = await self.db.execute(query_approved)
            approved_first_attempts = result_approved.scalar()

            rate = (
                (approved_first_attempts / total_first_attempts * 100)
                if total_first_attempts > 0
                else 0.0
            )

            return round(rate, 2)

        except Exception as e:
            logger.error(f"Error calculating first-attempt approval rate: {e}", exc_info=True)
            return 0.0

    async def get_regeneration_statistics(self, round_id: Optional[UUID] = None) -> Dict:
        """
        Get regeneration statistics.

        Args:
            round_id: Optional round ID to filter by

        Returns:
            Dictionary with regeneration stats
        """
        try:
            # Count summaries by regen_count
            query = select(Summary.regen_count, func.count(Summary.summary_id))

            if round_id:
                query = query.where(Summary.round_id == round_id)

            query = query.group_by(Summary.regen_count)

            result = await self.db.execute(query)
            regen_counts = dict(result.fetchall())

            total = sum(regen_counts.values())

            return {
                "total_summaries": total,
                "initial_generation": regen_counts.get(0, 0),
                "first_regeneration": regen_counts.get(1, 0),
                "second_regeneration": regen_counts.get(2, 0),
                "correction_based_regeneration": regen_counts.get(3, 0),
                "average_regenerations": sum(k * v for k, v in regen_counts.items()) / total if total > 0 else 0.0,
                "round_id": str(round_id) if round_id else "all",
            }

        except Exception as e:
            logger.error(f"Error calculating regeneration statistics: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_correction_signal_usage(self, round_id: Optional[UUID] = None) -> Dict:
        """
        Get correction signal usage statistics.

        Args:
            round_id: Optional round ID to filter by

        Returns:
            Dictionary with correction signal stats
        """
        try:
            # Count correction signals
            query_total = select(func.count(CorrectionSignal.signal_id))

            if round_id:
                query_total = query_total.join(Summary).where(Summary.round_id == round_id)

            result_total = await self.db.execute(query_total)
            total_signals = result_total.scalar()

            # Count by reason tag
            query_reasons = select(
                CorrectionSignal.reason_tag,
                func.count(CorrectionSignal.signal_id),
            )

            if round_id:
                query_reasons = query_reasons.join(Summary).where(Summary.round_id == round_id)

            query_reasons = query_reasons.group_by(CorrectionSignal.reason_tag)

            result_reasons = await self.db.execute(query_reasons)
            reason_counts = dict(result_reasons.fetchall())

            return {
                "total_correction_signals": total_signals,
                "by_reason": {
                    reason.value: count for reason, count in reason_counts.items()
                },
                "round_id": str(round_id) if round_id else "all",
            }

        except Exception as e:
            logger.error(f"Error calculating correction signal usage: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_safety_filtering_statistics(self, round_id: Optional[UUID] = None) -> Dict:
        """
        Get safety filtering statistics.

        Args:
            round_id: Optional round ID to filter by

        Returns:
            Dictionary with safety filtering stats
        """
        try:
            # Count disallowed content
            query_disallowed = select(func.count(Summary.summary_id)).where(
                Summary.status == SummaryStatus.DISALLOWED_CONTENT
            )

            if round_id:
                query_disallowed = query_disallowed.where(Summary.round_id == round_id)

            result_disallowed = await self.db.execute(query_disallowed)
            disallowed_count = result_disallowed.scalar()

            # Count summaries with safety flags
            query_flagged = select(func.count(Summary.summary_id)).where(
                Summary.safety_flags.isnot(None),
                func.array_length(Summary.safety_flags, 1) > 0,
            )

            if round_id:
                query_flagged = query_flagged.where(Summary.round_id == round_id)

            result_flagged = await self.db.execute(query_flagged)
            flagged_count = result_flagged.scalar()

            return {
                "disallowed_content_count": disallowed_count,
                "summaries_with_safety_flags": flagged_count,
                "round_id": str(round_id) if round_id else "all",
            }

        except Exception as e:
            logger.error(f"Error calculating safety filtering statistics: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_comprehensive_report(self, round_id: Optional[UUID] = None) -> Dict:
        """
        Get comprehensive analytics report.

        Args:
            round_id: Optional round ID to filter by

        Returns:
            Dictionary with all analytics
        """
        return {
            "approval_rates": await self.get_approval_rates(round_id),
            "first_attempt_approval_rate": await self.get_first_attempt_approval_rate(round_id),
            "regeneration_statistics": await self.get_regeneration_statistics(round_id),
            "correction_signal_usage": await self.get_correction_signal_usage(round_id),
            "safety_filtering": await self.get_safety_filtering_statistics(round_id),
            "generated_at": datetime.utcnow().isoformat(),
        }
