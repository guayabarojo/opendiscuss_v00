"""
LLM Generation Retry Service

Implements retry logic with exponential backoff and automatic fallback to GPT-3.5.
Handles transient LLM API failures gracefully.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T093)
"""

import asyncio
import logging
from typing import Optional, Callable, Any
from uuid import UUID

from ...config import settings
from .summarization_service import SummarizationService

logger = logging.getLogger(__name__)


class GenerationRetryService:
    """Service for retrying LLM generation with fallback strategy."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
    ):
        """
        Initialize retry service.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries (seconds)
            backoff_factor: Multiplier for exponential backoff
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor

    async def generate_with_retry(
        self,
        summarization_service: SummarizationService,
        submission_id: UUID,
        use_fallback_on_retry: bool = True,
    ):
        """
        Generate summary with automatic retry and fallback.

        Retry strategy:
        1. First attempt: Use default model (GPT-4-turbo)
        2. Retry 1: Use default model with delay
        3. Retry 2+: Fallback to GPT-3.5-turbo

        Args:
            summarization_service: SummarizationService instance
            submission_id: ID of submission to summarize
            use_fallback_on_retry: If True, fallback to GPT-3.5 after first failure

        Returns:
            Summary object

        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None
        delay = self.initial_delay

        for attempt in range(self.max_retries + 1):
            try:
                # Determine whether to use fallback model
                use_fallback = use_fallback_on_retry and attempt >= 2

                if attempt > 0:
                    logger.info(
                        f"Retry attempt {attempt}/{self.max_retries} for submission {submission_id}",
                        extra={
                            "submission_id": str(submission_id),
                            "attempt": attempt,
                            "use_fallback": use_fallback,
                            "delay": delay,
                        },
                    )

                # Attempt generation
                summary = await summarization_service.generate_summary(
                    submission_id=submission_id,
                    use_fallback_model=use_fallback,
                )

                if attempt > 0:
                    logger.info(
                        f"Retry successful for submission {submission_id} on attempt {attempt}",
                        extra={
                            "submission_id": str(submission_id),
                            "attempt": attempt,
                            "summary_id": str(summary.summary_id),
                        },
                    )

                return summary

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"LLM generation attempt {attempt + 1} failed for submission {submission_id}: {e}",
                    extra={
                        "submission_id": str(submission_id),
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )

                # If not last attempt, wait before retrying
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    delay *= self.backoff_factor

        # All retries exhausted
        logger.error(
            f"All retry attempts exhausted for submission {submission_id}",
            extra={
                "submission_id": str(submission_id),
                "max_retries": self.max_retries,
                "last_error": str(last_exception),
            },
            exc_info=True,
        )
        raise last_exception

    async def regenerate_with_retry(
        self,
        summarization_service: SummarizationService,
        previous_summary_id: UUID,
        use_fallback_on_retry: bool = True,
    ):
        """
        Regenerate summary with automatic retry and fallback.

        Args:
            summarization_service: SummarizationService instance
            previous_summary_id: ID of rejected summary
            use_fallback_on_retry: If True, fallback to GPT-3.5 after first failure

        Returns:
            Summary object

        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None
        delay = self.initial_delay

        for attempt in range(self.max_retries + 1):
            try:
                use_fallback = use_fallback_on_retry and attempt >= 2

                if attempt > 0:
                    logger.info(
                        f"Retry attempt {attempt}/{self.max_retries} for regeneration of {previous_summary_id}",
                        extra={
                            "previous_summary_id": str(previous_summary_id),
                            "attempt": attempt,
                            "use_fallback": use_fallback,
                        },
                    )

                summary = await summarization_service.regenerate_summary(
                    previous_summary_id=previous_summary_id,
                    use_fallback_model=use_fallback,
                )

                if attempt > 0:
                    logger.info(
                        f"Regeneration retry successful on attempt {attempt}",
                        extra={
                            "previous_summary_id": str(previous_summary_id),
                            "new_summary_id": str(summary.summary_id),
                            "attempt": attempt,
                        },
                    )

                return summary

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Regeneration attempt {attempt + 1} failed: {e}",
                    extra={
                        "previous_summary_id": str(previous_summary_id),
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )

                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    delay *= self.backoff_factor

        logger.error(
            f"All regeneration retry attempts exhausted for summary {previous_summary_id}",
            extra={
                "previous_summary_id": str(previous_summary_id),
                "max_retries": self.max_retries,
                "last_error": str(last_exception),
            },
            exc_info=True,
        )
        raise last_exception

    async def execute_with_retry(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:
        """
        Generic retry wrapper for any async function.

        Args:
            func: Async function to execute with retry
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None
        delay = self.initial_delay

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    logger.debug(f"Generic retry attempt {attempt}/{self.max_retries}")

                result = await func(*args, **kwargs)
                return result

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Function {func.__name__} attempt {attempt + 1} failed: {e}",
                    extra={"function": func.__name__, "attempt": attempt + 1},
                )

                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    delay *= self.backoff_factor

        logger.error(
            f"All retry attempts exhausted for {func.__name__}",
            extra={"function": func.__name__, "max_retries": self.max_retries},
            exc_info=True,
        )
        raise last_exception
