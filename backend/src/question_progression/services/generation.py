"""
QuestionGenerationService for LLM-powered autonomous question generation.

Uses Anthropic Claude API to generate questions from Sankey patterns with:
- Retry logic with exponential backoff
- Validation retry loop
- Provenance tracking
- Error handling and fallbacks
- Prometheus metrics for monitoring
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

import httpx
from anthropic import (
    AsyncAnthropic,
    APIError,
    APITimeoutError,
    RateLimitError,
    APIStatusError,
    AuthenticationError
)

from src.config import settings
from src.question_progression.prompts import build_generation_prompt
from src.question_progression.validators import QuestionValidator, ValidationResult
from src.question_progression.models import Question, QuestionProvenance, QuestionMode, ValidationStatus
from src.logging_config import get_logger

logger = get_logger(__name__)


# Monitoring metrics (Prometheus/OpenTelemetry compatible) - T102
class GenerationMetrics:
    """
    Metrics collector for question generation monitoring.

    Tracks:
    - generation_success_count: Successful generation counter
    - generation_failure_count: Failed generation counter
    - generation_retry_count: Histogram of retry counts
    - generation_latency_seconds: Histogram of latency in seconds

    Usage:
        metrics.record_success(latency_seconds=2.5, retry_count=0)
        metrics.record_failure(error_type="timeout", retry_count=3)
    """

    def __init__(self):
        self.success_count = 0
        self.failure_count = 0
        self.retry_histogram = {}  # retry_count -> occurrences
        self.latency_histogram = {}  # latency_bucket -> occurrences
        self.failure_by_type = {}  # error_type -> count

    def record_success(self, latency_seconds: float, retry_count: int, validation_attempts: int):
        """Record successful generation."""
        self.success_count += 1

        # Update retry histogram
        self.retry_histogram[retry_count] = self.retry_histogram.get(retry_count, 0) + 1

        # Update latency histogram (buckets: <1s, <2s, <5s, <10s, >10s)
        if latency_seconds < 1.0:
            bucket = "0-1s"
        elif latency_seconds < 2.0:
            bucket = "1-2s"
        elif latency_seconds < 5.0:
            bucket = "2-5s"
        elif latency_seconds < 10.0:
            bucket = "5-10s"
        else:
            bucket = "10s+"
        self.latency_histogram[bucket] = self.latency_histogram.get(bucket, 0) + 1

        logger.info(
            "Generation metrics: success",
            extra={
                "metric_type": "generation_success",
                "latency_seconds": latency_seconds,
                "retry_count": retry_count,
                "validation_attempts": validation_attempts,
                "total_successes": self.success_count
            }
        )

    def record_failure(self, error_type: str, retry_count: int, validation_attempts: int):
        """Record failed generation."""
        self.failure_count += 1
        self.failure_by_type[error_type] = self.failure_by_type.get(error_type, 0) + 1

        # Update retry histogram
        self.retry_histogram[retry_count] = self.retry_histogram.get(retry_count, 0) + 1

        logger.error(
            "Generation metrics: failure",
            extra={
                "metric_type": "generation_failure",
                "error_type": error_type,
                "retry_count": retry_count,
                "validation_attempts": validation_attempts,
                "total_failures": self.failure_count,
                "failure_rate": self.failure_count / max(1, self.success_count + self.failure_count)
            }
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get current metrics statistics."""
        total = self.success_count + self.failure_count
        return {
            "total_generations": total,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_count / max(1, total),
            "failure_rate": self.failure_count / max(1, total),
            "retry_histogram": self.retry_histogram,
            "latency_histogram": self.latency_histogram,
            "failures_by_type": self.failure_by_type
        }


# Global metrics instance
generation_metrics = GenerationMetrics()


class QuestionGenerationError(Exception):
    """Base exception for question generation failures."""
    pass


class QuestionGenerationTimeout(QuestionGenerationError):
    """Raised when generation times out."""
    pass


class QuestionValidationExhausted(QuestionGenerationError):
    """Raised when all validation retry attempts are exhausted."""
    pass


class QuestionGenerationService:
    """
    Service for generating questions from Sankey patterns using Claude LLM.

    Implements:
    - Exponential backoff retry (3 attempts)
    - Validation retry loop (3 attempts)
    - Provenance metadata tracking
    - Error handling with fallback states
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None
    ):
        """
        Initialize QuestionGenerationService.

        Args:
            api_key: Anthropic API key (defaults to settings.claude_api_key)
            model: Claude model identifier (defaults to settings.claude_model)
            timeout: Timeout in seconds (defaults to settings.question_generation_timeout_seconds)
            max_retries: Max retry attempts (defaults to settings.question_generation_max_retries)
        """
        self.api_key = api_key or settings.claude_api_key
        self.model = model or settings.claude_model
        self.timeout = timeout or settings.question_generation_timeout_seconds
        self.max_retries = max_retries or settings.question_generation_max_retries

        if not self.api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable.")

        self.client = AsyncAnthropic(
            api_key=self.api_key,
            timeout=httpx.Timeout(self.timeout, connect=5.0)
        )
        self.validator = QuestionValidator()

    async def generate_from_sankey(
        self,
        round_num: int,
        previous_questions: List[str],
        sankey_data: Dict[str, Any],
        input_round_id: UUID
    ) -> Dict[str, Any]:
        """
        Generate next question from Sankey patterns with retry and validation.

        Args:
            round_num: Current round number
            previous_questions: List of previous question texts
            sankey_data: Sankey graph data dictionary
            input_round_id: Round ID that triggered generation

        Returns:
            Dictionary containing:
                - question_text: Generated and validated question
                - provenance: Provenance metadata dict
                - sankey_hash: SHA-256 hash of Sankey data

        Raises:
            QuestionGenerationError: If all retries exhausted
            QuestionValidationExhausted: If validation fails after max attempts
        """
        start_time = time.time()

        # Compute Sankey hash for provenance
        sankey_json = json.dumps(sankey_data, sort_keys=True)
        sankey_hash = hashlib.sha256(sankey_json.encode()).hexdigest()

        logger.info(
            "Starting question generation",
            extra={
                "round_num": round_num,
                "sankey_hash": sankey_hash[:16],
                "previous_questions_count": len(previous_questions),
                "input_round_id": str(input_round_id)
            }
        )

        retry_count = 0
        validation_attempts = 0
        last_error = None
        failed_question = None
        rejection_reason = None

        # Validation retry loop (outer)
        for validation_attempt in range(self.max_retries):
            validation_attempts = validation_attempt + 1

            # API retry loop (inner) with exponential backoff
            for api_attempt in range(self.max_retries):
                try:
                    # Build prompt (stricter if retrying after validation failure)
                    prompt = build_generation_prompt(
                        round_num=round_num,
                        previous_questions=previous_questions,
                        sankey_data=sankey_data,
                        failed_question=failed_question,
                        rejection_reason=rejection_reason
                    )

                    logger.debug(
                        "Calling Claude API",
                        extra={
                            "attempt": api_attempt + 1,
                            "validation_attempt": validation_attempt + 1,
                            "model": self.model,
                            "prompt_length": len(prompt)
                        }
                    )

                    # Call Claude API
                    response = await self.client.messages.create(
                        model=self.model,
                        max_tokens=150,
                        messages=[{"role": "user", "content": prompt}]
                    )

                    # Extract question text from response
                    question_text = self._extract_question(response)

                    # Validate question
                    validation_result = self.validator.validate(question_text)

                    if validation_result.valid:
                        # Success!
                        generation_latency_ms = (time.time() - start_time) * 1000

                        logger.info(
                            "Question generation successful",
                            extra={
                                "question_text": question_text,
                                "latency_ms": generation_latency_ms,
                                "retry_count": retry_count,
                                "validation_attempts": validation_attempts,
                                "sankey_hash": sankey_hash[:16]
                            }
                        )

                        # Record success metrics (T102)
                        generation_metrics.record_success(
                            latency_seconds=generation_latency_ms / 1000.0,
                            retry_count=retry_count,
                            validation_attempts=validation_attempts
                        )

                        # Build provenance metadata
                        provenance = {
                            "input_round_id": input_round_id,
                            "generation_timestamp": datetime.utcnow(),
                            "generation_latency_ms": generation_latency_ms,
                            "input_sankey_hash": sankey_hash,
                            "llm_model": self.model,
                            "prompt_tokens": response.usage.input_tokens,
                            "completion_tokens": response.usage.output_tokens,
                            "retry_count": retry_count,
                            "validation_attempts": validation_attempts,
                            "previous_questions_count": len(previous_questions)
                        }

                        return {
                            "question_text": validation_result.validated_text,
                            "provenance": provenance,
                            "sankey_hash": sankey_hash
                        }
                    else:
                        # Validation failed - break inner loop and retry with stricter prompt
                        failed_question = question_text
                        rejection_reason = validation_result.error_message

                        logger.warning(
                            "Question validation failed, will regenerate",
                            extra={
                                "question_text": question_text,
                                "error_code": validation_result.error_code.value,
                                "error_message": validation_result.error_message,
                                "validation_attempt": validation_attempt + 1
                            }
                        )
                        break  # Break inner API retry loop, continue outer validation loop

                except APITimeoutError as e:
                    # Handle: TimeoutError (30s exceeded)
                    retry_count += 1
                    last_error = e

                    logger.warning(
                        "Claude API timeout",
                        extra={
                            "attempt": api_attempt + 1,
                            "timeout_seconds": self.timeout,
                            "error": str(e)
                        }
                    )

                    if api_attempt < self.max_retries - 1:
                        # Exponential backoff: 1s, 2s, 4s
                        delay = 2 ** api_attempt
                        logger.info(f"Retrying in {delay} seconds after timeout...")
                        await asyncio.sleep(delay)
                    else:
                        # All API retries exhausted for this validation attempt
                        break

                except AuthenticationError as e:
                    # Handle: AuthenticationError (invalid API key) - do not retry
                    retry_count += 1
                    last_error = e

                    logger.error(
                        "Claude API authentication error - invalid API key",
                        extra={
                            "attempt": api_attempt + 1,
                            "error_type": type(e).__name__,
                            "error": str(e)
                        },
                        exc_info=True
                    )

                    # AuthenticationError is not retryable - fail immediately
                    raise QuestionGenerationError(f"Authentication failed: {str(e)}")

                except RateLimitError as e:
                    # Handle: RateLimitError (429 from Claude API)
                    retry_count += 1
                    last_error = e

                    logger.warning(
                        "Claude API rate limit exceeded",
                        extra={
                            "attempt": api_attempt + 1,
                            "error_type": type(e).__name__,
                            "error": str(e)
                        }
                    )

                    if api_attempt < self.max_retries - 1:
                        # Longer exponential backoff for rate limits: 2s, 4s, 8s
                        delay = 2 ** (api_attempt + 1)
                        logger.info(f"Rate limited, retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                    else:
                        break

                except APIStatusError as e:
                    # Handle: ServiceUnavailableError (500, 503 from Claude API)
                    retry_count += 1
                    last_error = e

                    logger.error(
                        "Claude API service error",
                        extra={
                            "attempt": api_attempt + 1,
                            "status_code": e.status_code if hasattr(e, 'status_code') else None,
                            "error_type": type(e).__name__,
                            "error": str(e)
                        },
                        exc_info=True
                    )

                    if api_attempt < self.max_retries - 1:
                        delay = 2 ** api_attempt
                        logger.info(f"Service unavailable, retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                    else:
                        break

                except APIError as e:
                    # Handle: Generic APIError (catch-all for other Anthropic errors)
                    retry_count += 1
                    last_error = e

                    logger.error(
                        "Claude API error",
                        extra={
                            "attempt": api_attempt + 1,
                            "error_type": type(e).__name__,
                            "error": str(e)
                        },
                        exc_info=True
                    )

                    if api_attempt < self.max_retries - 1:
                        delay = 2 ** api_attempt
                        await asyncio.sleep(delay)
                    else:
                        break

                except Exception as e:
                    # Handle: Unexpected errors
                    retry_count += 1
                    last_error = e

                    logger.error(
                        "Unexpected error during question generation",
                        extra={
                            "attempt": api_attempt + 1,
                            "error_type": type(e).__name__,
                            "error": str(e)
                        },
                        exc_info=True
                    )

                    if api_attempt < self.max_retries - 1:
                        delay = 2 ** api_attempt
                        await asyncio.sleep(delay)
                    else:
                        break

            # If we have a failed question, continue to next validation attempt
            if failed_question and validation_attempt < self.max_retries - 1:
                continue

            # If last API call succeeded but validation failed, and we're out of validation attempts
            if failed_question:
                break

            # If last error was API-related and we're out of attempts
            if last_error:
                break

        # All retries exhausted
        if failed_question:
            error_msg = f"Question validation failed after {validation_attempts} attempts. Last rejection: {rejection_reason}"
            logger.error(
                "Question generation failed: validation exhausted",
                extra={
                    "validation_attempts": validation_attempts,
                    "last_failed_question": failed_question,
                    "rejection_reason": rejection_reason
                }
            )

            # Record failure metrics (T102)
            generation_metrics.record_failure(
                error_type="validation_exhausted",
                retry_count=retry_count,
                validation_attempts=validation_attempts
            )

            raise QuestionValidationExhausted(error_msg)
        else:
            error_msg = f"Question generation failed after {retry_count} retries. Last error: {last_error}"
            logger.error(
                "Question generation failed: API retries exhausted",
                extra={
                    "retry_count": retry_count,
                    "last_error": str(last_error)
                }
            )

            # Record failure metrics (T102)
            error_type = "timeout" if isinstance(last_error, APITimeoutError) else "api_error"
            generation_metrics.record_failure(
                error_type=error_type,
                retry_count=retry_count,
                validation_attempts=validation_attempts
            )

            raise QuestionGenerationError(error_msg)

    def _extract_question(self, response) -> str:
        """
        Extract question text from Claude API response.

        Args:
            response: Anthropic API response object

        Returns:
            Extracted question text (trimmed)

        Raises:
            QuestionGenerationError: If response format is invalid
        """
        try:
            # Extract text from first content block
            if not response.content or len(response.content) == 0:
                raise QuestionGenerationError("Empty response from Claude API")

            text_block = response.content[0]
            if not hasattr(text_block, 'text'):
                raise QuestionGenerationError("Invalid response format: no text attribute")

            question_text = text_block.text.strip()

            # Remove any markdown formatting or quotes
            question_text = question_text.strip('"').strip("'").strip()

            return question_text

        except (AttributeError, IndexError, TypeError) as e:
            logger.error(
                "Failed to extract question from response",
                extra={"error": str(e)},
                exc_info=True
            )
            raise QuestionGenerationError(f"Failed to parse Claude response: {e}")
