"""
Summarization service for Spec 003.

Generates LLM-based summaries with model selection and validation.
"""

import time
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...logging_config import logger
from ...llm.openai_client import generate_summary_llm
from ...models import Submission, Round
from ..models.summary import Summary, SummaryStatus
from ..prompts.base_summary_prompt import build_base_summary_prompt, build_regeneration_prompt
from ..prompts.correction_prompts import build_correction_prompt
from ..models.correction_signal import CorrectionSignal
from .llm_cache_service import LLMCacheService
from .safety_filter_service import SafetyFilterService


class SummarizationService:
    """
    Service for generating and managing summaries.

    Constitutional Compliance:
    - Intent Fidelity: Preserves participant intent through careful prompting
    - Parallel-First: Independent summary generation per participant
    - Temporal Transparency: Tracks creation timestamps
    """

    def __init__(self, db: AsyncSession, cache_service: Optional[LLMCacheService] = None):
        """Initialize service with database session and optional cache."""
        self.db = db
        self.cache_service = cache_service or LLMCacheService()
        self.safety_filter = SafetyFilterService()  # Task T069: Safety filtering integration
        self.prompt_version = "v1.0"  # Update when prompt templates change

    async def generate_summary(
        self,
        submission_id: UUID,
        use_fallback_model: bool = False,
    ) -> Summary:
        """
        Generate initial summary from submission.

        Task T019: Core summary generation logic
        Task T020: Model selection (GPT-4-turbo vs GPT-3.5)
        Task T031: Validation for max 500 chars
        Task T033: Logging for generation events

        Args:
            submission_id: ID of submission to summarize
            use_fallback_model: If True, use GPT-3.5 instead of GPT-4-turbo

        Returns:
            Summary: Created summary entity with status=PENDING_REVIEW

        Raises:
            ValueError: If submission not found or invalid
            Exception: If LLM call fails
        """
        # Fetch submission with relationships
        result = await self.db.execute(
            select(Submission)
            .where(Submission.submission_id == submission_id)
        )
        submission = result.scalar_one_or_none()

        if not submission:
            raise ValueError(f"Submission {submission_id} not found")

        if not submission.submission_text:
            raise ValueError(f"Submission {submission_id} has no text content")

        # Task T069: Safety filtering BEFORE LLM call
        filtered_text, safety_flags, is_blocked = await self.safety_filter.filter_submission(
            submission.submission_text
        )

        # Task T070: Block approval if DISALLOWED_CONTENT detected
        if is_blocked:
            # Create summary with DISALLOWED_CONTENT status
            blocked_summary = Summary(
                summary_id=uuid4(),
                submission_id=submission.submission_id,
                participant_id=submission.participant_id,
                round_id=submission.round_id,
                summary_text="[Content blocked due to safety violations]",
                status=SummaryStatus.DISALLOWED_CONTENT,
                regen_count=0,
                safety_flags=safety_flags,
            )

            self.db.add(blocked_summary)
            await self.db.commit()
            await self.db.refresh(blocked_summary)

            # Logging (T075)
            logger.error(
                f"Submission {submission_id} blocked due to safety violations: "
                f"safety_flags={safety_flags}, "
                f"status=DISALLOWED_CONTENT"
            )

            return blocked_summary

        # Use filtered text (with profanity neutralized if applicable)
        submission_text_for_summary = filtered_text

        # Fetch round for context (optional)
        round_context = ""
        if submission.round_id:
            round_result = await self.db.execute(
                select(Round).where(Round.round_id == submission.round_id)
            )
            round_obj = round_result.scalar_one_or_none()
            if round_obj and hasattr(round_obj, 'question_text'):
                round_context = round_obj.question_text

        # Build prompt (use filtered text with profanity neutralized)
        prompt = build_base_summary_prompt(
            submission_text=submission_text_for_summary,
            round_context=round_context,
        )

        # Model selection (T020)
        if use_fallback_model:
            model = settings.openai_fallback_model  # GPT-3.5-turbo
            logger.info(f"Using fallback model {model} for submission {submission_id}")
        else:
            model = settings.openai_default_model  # GPT-4-turbo
            logger.info(f"Using default model {model} for submission {submission_id}")

        # Check cache first (T087) - use filtered text for cache key
        cached_response = await self.cache_service.get_cached_summary(
            input_text=submission_text_for_summary,
            prompt_version=self.prompt_version,
            model_name=model,
        )

        if cached_response:
            summary_text = cached_response.summary_text
            logger.info(f"Using cached summary for submission {submission_id}")
        else:
            # Generate summary via LLM
            try:
                summary_text = await generate_summary_llm(
                    prompt=prompt,
                    model=model,
                    temperature=0.7,
                    max_tokens=150,
                )

                # Cache the response (T086) - use filtered text
                await self.cache_service.cache_summary(
                    input_text=submission_text_for_summary,
                    prompt_version=self.prompt_version,
                    model_name=model,
                    summary_text=summary_text,
                    cached_at=time.time(),
                )
            except Exception as e:
                logger.error(f"LLM generation failed for submission {submission_id}: {e}")
                raise

        # Validation: max 500 chars (T031)
        if len(summary_text) > 500:
            logger.warning(
                f"Summary exceeded 500 chars ({len(summary_text)}), truncating"
            )
            summary_text = summary_text[:497] + "..."

        # Create Summary entity (Task T069: Include safety_flags)
        summary = Summary(
            summary_id=uuid4(),
            submission_id=submission.submission_id,
            participant_id=submission.participant_id,
            round_id=submission.round_id,
            summary_text=summary_text,
            status=SummaryStatus.PENDING_REVIEW,
            regen_count=0,
            safety_flags=safety_flags,  # Set flags if profanity was neutralized
        )

        self.db.add(summary)
        await self.db.commit()
        await self.db.refresh(summary)

        # Logging (T033, T075)
        logger.info(
            f"Generated summary {summary.summary_id} for submission {submission_id}: "
            f"status={summary.status.value}, "
            f"length={len(summary_text)} chars, "
            f"model={model}, "
            f"safety_flags={safety_flags}"
        )

        return summary

    async def regenerate_summary(
        self,
        previous_summary_id: UUID,
        use_fallback_model: bool = False,
    ) -> Summary:
        """
        Regenerate summary after rejection (User Story 2).

        Creates new summary with incremented regen_count.
        Uses regeneration prompt strategy based on attempt number.

        Args:
            previous_summary_id: ID of rejected summary
            use_fallback_model: If True, use GPT-3.5 instead of GPT-4-turbo

        Returns:
            Summary: New summary entity with status=PENDING_REVIEW

        Raises:
            ValueError: If previous summary not found or invalid
            Exception: If LLM call fails
        """
        # Fetch previous summary
        result = await self.db.execute(
            select(Summary)
            .where(Summary.summary_id == previous_summary_id)
        )
        previous_summary = result.scalar_one_or_none()

        if not previous_summary:
            raise ValueError(f"Summary {previous_summary_id} not found")

        # Fetch original submission
        submission_result = await self.db.execute(
            select(Submission)
            .where(Submission.submission_id == previous_summary.submission_id)
        )
        submission = submission_result.scalar_one_or_none()

        if not submission:
            raise ValueError(
                f"Submission {previous_summary.submission_id} not found"
            )

        # Fetch round for context
        round_context = ""
        if submission.round_id:
            round_result = await self.db.execute(
                select(Round).where(Round.round_id == submission.round_id)
            )
            round_obj = round_result.scalar_one_or_none()
            if round_obj and hasattr(round_obj, 'question_text'):
                round_context = round_obj.question_text

        # Build regeneration prompt
        new_regen_count = previous_summary.regen_count + 1
        prompt = build_regeneration_prompt(
            submission_text=submission.submission_text,
            previous_summary=previous_summary.summary_text,
            regen_count=new_regen_count,
            round_context=round_context,
        )

        # Model selection
        model = (
            settings.openai_fallback_model
            if use_fallback_model
            else settings.openai_default_model
        )

        # Generate new summary via LLM
        try:
            summary_text = await generate_summary_llm(
                prompt=prompt,
                model=model,
                temperature=0.7,
                max_tokens=150,
            )
        except Exception as e:
            logger.error(
                f"LLM regeneration failed for summary {previous_summary_id}: {e}"
            )
            raise

        # Validation: max 500 chars
        if len(summary_text) > 500:
            logger.warning(
                f"Regenerated summary exceeded 500 chars ({len(summary_text)}), truncating"
            )
            summary_text = summary_text[:497] + "..."

        # Create new Summary entity with incremented regen_count
        new_summary = Summary(
            summary_id=uuid4(),
            submission_id=submission.submission_id,
            participant_id=submission.participant_id,
            round_id=submission.round_id,
            summary_text=summary_text,
            status=SummaryStatus.PENDING_REVIEW,
            regen_count=new_regen_count,
            safety_flags=[],
        )

        self.db.add(new_summary)
        await self.db.commit()
        await self.db.refresh(new_summary)

        # Logging
        logger.info(
            f"Regenerated summary {new_summary.summary_id} "
            f"(attempt {new_regen_count}) for submission {submission.submission_id}: "
            f"status={new_summary.status.value}, "
            f"length={len(summary_text)} chars, "
            f"model={model}"
        )

        return new_summary

    async def regenerate_with_correction(
        self,
        previous_summary_id: UUID,
        use_fallback_model: bool = False,
    ) -> Summary:
        """
        Regenerate summary with correction signal (User Story 3, Task T052).

        Final regeneration attempt (regen_count=3) after participant provides
        correction signal (reason tag + optional feedback).

        Args:
            previous_summary_id: ID of rejected summary (should have regen_count=2)
            use_fallback_model: If True, use GPT-3.5 instead of GPT-4-turbo

        Returns:
            Summary: New summary entity with status=PENDING_REVIEW and regen_count=3

        Raises:
            ValueError: If previous summary not found, no correction signal, or invalid state
            Exception: If LLM call fails
        """
        # Fetch previous summary
        result = await self.db.execute(
            select(Summary)
            .where(Summary.summary_id == previous_summary_id)
        )
        previous_summary = result.scalar_one_or_none()

        if not previous_summary:
            raise ValueError(f"Summary {previous_summary_id} not found")

        # Fetch correction signal
        correction_result = await self.db.execute(
            select(CorrectionSignal)
            .where(CorrectionSignal.summary_id == previous_summary_id)
            .order_by(CorrectionSignal.created_at.desc())
            .limit(1)
        )
        correction_signal = correction_result.scalar_one_or_none()

        if not correction_signal:
            raise ValueError(
                f"No correction signal found for summary {previous_summary_id}"
            )

        # Fetch original submission
        submission_result = await self.db.execute(
            select(Submission)
            .where(Submission.submission_id == previous_summary.submission_id)
        )
        submission = submission_result.scalar_one_or_none()

        if not submission:
            raise ValueError(
                f"Submission {previous_summary.submission_id} not found"
            )

        # Fetch round for context
        round_context = ""
        if submission.round_id:
            round_result = await self.db.execute(
                select(Round).where(Round.round_id == submission.round_id)
            )
            round_obj = round_result.scalar_one_or_none()
            if round_obj and hasattr(round_obj, 'question_text'):
                round_context = round_obj.question_text

        # Build correction-enhanced prompt (T051)
        prompt = build_correction_prompt(
            submission_text=submission.submission_text,
            previous_summary=previous_summary.summary_text,
            reason_tag=correction_signal.reason_tag,
            feedback_text=correction_signal.feedback_text or "",
            round_context=round_context,
        )

        # Model selection
        model = (
            settings.openai_fallback_model
            if use_fallback_model
            else settings.openai_default_model
        )

        # Generate new summary via LLM
        new_regen_count = previous_summary.regen_count + 1
        try:
            summary_text = await generate_summary_llm(
                prompt=prompt,
                model=model,
                temperature=0.7,
                max_tokens=150,
            )
        except Exception as e:
            logger.error(
                f"LLM correction-based regeneration failed for summary {previous_summary_id}: {e}"
            )
            raise

        # Validation: max 500 chars
        if len(summary_text) > 500:
            logger.warning(
                f"Correction-based summary exceeded 500 chars ({len(summary_text)}), truncating"
            )
            summary_text = summary_text[:497] + "..."

        # Create new Summary entity with regen_count=3
        new_summary = Summary(
            summary_id=uuid4(),
            submission_id=submission.submission_id,
            participant_id=submission.participant_id,
            round_id=submission.round_id,
            summary_text=summary_text,
            status=SummaryStatus.PENDING_REVIEW,
            regen_count=new_regen_count,
            safety_flags=[],
        )

        self.db.add(new_summary)
        await self.db.commit()
        await self.db.refresh(new_summary)

        # Logging (T061)
        logger.info(
            f"Regenerated summary {new_summary.summary_id} with correction signal "
            f"(attempt {new_regen_count}, FINAL): "
            f"reason_tag={correction_signal.reason_tag.value}, "
            f"submission_id={submission.submission_id}, "
            f"status={new_summary.status.value}, "
            f"length={len(summary_text)} chars, "
            f"model={model}"
        )

        return new_summary

    async def get_summary(self, summary_id: UUID) -> Optional[Summary]:
        """
        Get summary by ID.

        Args:
            summary_id: Summary UUID

        Returns:
            Summary or None if not found
        """
        result = await self.db.execute(
            select(Summary).where(Summary.summary_id == summary_id)
        )
        return result.scalar_one_or_none()

    async def get_summaries_for_submission(
        self, submission_id: UUID
    ) -> list[Summary]:
        """
        Get all summaries for a submission (including regenerations).

        Args:
            submission_id: Submission UUID

        Returns:
            List of summaries ordered by created_at
        """
        result = await self.db.execute(
            select(Summary)
            .where(Summary.submission_id == submission_id)
            .order_by(Summary.created_at)
        )
        return list(result.scalars().all())

    async def get_latest_summary_for_submission(
        self, submission_id: UUID
    ) -> Optional[Summary]:
        """
        Get latest summary for a submission.

        Args:
            submission_id: Submission UUID

        Returns:
            Latest Summary or None
        """
        result = await self.db.execute(
            select(Summary)
            .where(Summary.submission_id == submission_id)
            .order_by(Summary.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
