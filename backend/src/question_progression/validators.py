"""
Question validation pipeline for Question Progression Protocol (Spec 006).

Implements 5-check validation pipeline enforcing constitutional constraints:
1. Length check (10-200 characters)
2. Opening word check (What/How only)
3. Prohibited word check (no Why, Do you, Should we, Would you)
4. Ranking/voting keyword check (no vote, rank, best, worst, etc.)
5. Binary choice pattern check (no yes/no questions)

Validation is fail-fast: stops at first failure and returns specific error code.
Includes metrics tracking for monitoring validation rejection rates (T103).
"""

import re
import time
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class ValidationErrorCode(str, Enum):
    """Error codes for question validation failures."""
    INVALID_LENGTH = "INVALID_LENGTH"
    INVALID_START = "INVALID_START"
    CONTAINS_PROHIBITED_WORD = "CONTAINS_PROHIBITED_WORD"
    CONTAINS_RANKING_KEYWORD = "CONTAINS_RANKING_KEYWORD"
    BINARY_CHOICE = "BINARY_CHOICE"


class ValidationResult(BaseModel):
    """Result of question validation."""
    valid: bool = Field(description="Whether question passed validation")
    validated_text: Optional[str] = Field(
        default=None,
        description="Validated and trimmed question text (only if valid)"
    )
    error_code: Optional[ValidationErrorCode] = Field(
        default=None,
        description="Error code if validation failed"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Human-readable error message if validation failed"
    )


# Monitoring metrics for validation (T103)
class ValidationMetrics:
    """
    Metrics collector for question validation monitoring.

    Tracks:
    - validation_success_count: Successful validation counter
    - validation_failure_count: Failed validation counter by error_code
    - validation_duration_seconds: Histogram of validation duration

    Usage:
        metrics.record_success(duration_seconds=0.001)
        metrics.record_failure(error_code="INVALID_START", duration_seconds=0.002)
    """

    def __init__(self):
        self.success_count = 0
        self.failure_by_code = {}  # error_code -> count
        self.duration_histogram = {}  # duration_bucket -> occurrences
        self.total_duration_ms = 0.0
        self.total_validations = 0

    def record_success(self, duration_seconds: float):
        """Record successful validation."""
        self.success_count += 1
        self._update_duration(duration_seconds)

    def record_failure(self, error_code: str, duration_seconds: float):
        """Record failed validation."""
        self.failure_by_code[error_code] = self.failure_by_code.get(error_code, 0) + 1
        self._update_duration(duration_seconds)

    def _update_duration(self, duration_seconds: float):
        """Update duration metrics."""
        self.total_validations += 1
        self.total_duration_ms += duration_seconds * 1000

        # Update duration histogram (buckets: <1ms, <5ms, <10ms, <50ms, >50ms)
        duration_ms = duration_seconds * 1000
        if duration_ms < 1.0:
            bucket = "0-1ms"
        elif duration_ms < 5.0:
            bucket = "1-5ms"
        elif duration_ms < 10.0:
            bucket = "5-10ms"
        elif duration_ms < 50.0:
            bucket = "10-50ms"
        else:
            bucket = "50ms+"
        self.duration_histogram[bucket] = self.duration_histogram.get(bucket, 0) + 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current metrics statistics."""
        total_failures = sum(self.failure_by_code.values())
        total = self.success_count + total_failures

        return {
            "total_validations": total,
            "success_count": self.success_count,
            "failure_count": total_failures,
            "success_rate": self.success_count / max(1, total),
            "failure_rate": total_failures / max(1, total),
            "failures_by_code": self.failure_by_code,
            "duration_histogram": self.duration_histogram,
            "avg_duration_ms": self.total_duration_ms / max(1, self.total_validations),
            "most_common_failure": max(self.failure_by_code.items(), key=lambda x: x[1])[0]
            if self.failure_by_code else None
        }


# Global metrics instance
validation_metrics = ValidationMetrics()


class QuestionValidator:
    """
    Validator for question text enforcing constitutional constraints.

    Constitutional Guarantee (Representation Not Adjudication - Principle VII):
    - All questions must be exploratory (What/How)
    - No ranking, voting, or adjudication keywords allowed
    - No binary choice questions (yes/no, agree/disagree)
    """

    # Opening words (allowed)
    ALLOWED_OPENINGS = ["what", "how"]

    # Prohibited opening words/phrases
    PROHIBITED_OPENINGS = [
        "why",
        "do you",
        "should we",
        "would you",
        "would we",
        "could you",
        "could we",
        "will you",
        "will we",
    ]

    # Ranking/voting keywords (comprehensive list)
    RANKING_KEYWORDS = [
        "vote",
        "rank",
        "order",
        "best",
        "worst",
        "choose",
        "select",
        "pick",
        "prefer",
        "favorite",
        "top",
        "bottom",
        "first",
        "last",
        "winner",
        "loser",
        "better",
        "worse",
        "superior",
        "inferior",
    ]

    # Binary choice pattern regex
    BINARY_CHOICE_PATTERN = re.compile(
        r"\b(yes|no|agree|disagree|true|false)\s*(or|/|vs\.?)\s*(yes|no|agree|disagree|true|false)\b",
        re.IGNORECASE
    )

    def __init__(self):
        """Initialize QuestionValidator."""
        pass

    def validate(self, text: str) -> ValidationResult:
        """
        Validate question text through 5-check pipeline.

        Pipeline is fail-fast: stops at first failure.

        Args:
            text: Question text to validate

        Returns:
            ValidationResult with valid=True/False and error details
        """
        # Start timing for metrics (T103)
        start_time = time.perf_counter()

        # Trim whitespace
        text = text.strip()

        # Check 1: Length (10-200 characters)
        if not (10 <= len(text) <= 200):
            duration = time.perf_counter() - start_time
            validation_metrics.record_failure(
                error_code=ValidationErrorCode.INVALID_LENGTH.value,
                duration_seconds=duration
            )

            if len(text) < 10:
                return ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.INVALID_LENGTH,
                    error_message=(
                        f"Question must be 10-200 characters. "
                        f"Your question is too short: {len(text)} characters (minimum: 10). "
                        f"Add more context to make your question clearer. "
                        f"Example: Instead of 'What now?', try 'What steps should we take next?'"
                    )
                )
            else:
                return ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.INVALID_LENGTH,
                    error_message=(
                        f"Question must be 10-200 characters. "
                        f"Your question is too long: {len(text)} characters (maximum: 200). "
                        f"Try to make your question more concise while keeping it clear. "
                        f"Break complex questions into multiple rounds if needed."
                    )
                )

        # Check 2: Prohibited opening words (must come before allowed opening check)
        text_lower = text.lower()
        for prohibited in self.PROHIBITED_OPENINGS:
            if text_lower.startswith(prohibited):
                # Provide specific guidance based on prohibited word
                suggestions = {
                    "why": "Replace 'Why...' with 'What factors...' or 'What reasons...'",
                    "do you": "Replace 'Do you...' with 'What are your thoughts on...' or 'How do you view...'",
                    "should we": "Replace 'Should we...' with 'What are the options for...' or 'How could we...'",
                    "would you": "Replace 'Would you...' with 'What would you think about...' or 'How might you approach...'",
                }
                suggestion = suggestions.get(prohibited, f"Replace '{prohibited}' with 'What' or 'How'")

                duration = time.perf_counter() - start_time
                validation_metrics.record_failure(
                    error_code=ValidationErrorCode.CONTAINS_PROHIBITED_WORD.value,
                    duration_seconds=duration
                )

                return ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.CONTAINS_PROHIBITED_WORD,
                    error_message=(
                        f"Question cannot start with '{prohibited}' as it implies justification or binary choice. "
                        f"Suggestion: {suggestion}. "
                        f"We encourage exploratory questions that gather perspectives, not closed-ended queries."
                    )
                )

        # Check 3: Opening word (What or How)
        if not any(text_lower.startswith(opening + " ") for opening in self.ALLOWED_OPENINGS):
            # Detect what the user started with
            first_word = text.split()[0] if text.split() else text

            duration = time.perf_counter() - start_time
            validation_metrics.record_failure(
                error_code=ValidationErrorCode.INVALID_START.value,
                duration_seconds=duration
            )

            return ValidationResult(
                valid=False,
                error_code=ValidationErrorCode.INVALID_START,
                error_message=(
                    f"Question must start with 'What' or 'How'. Your question starts with '{first_word}'. "
                    f"Try rephrasing as an exploratory question. "
                    f"Examples: 'What factors contribute to...?', 'How could we address...?', "
                    f"'What approaches might work for...?', 'How do participants view...?'"
                )
            )

        # Check 4: Ranking/voting keywords (case-insensitive with word boundaries)
        for keyword in self.RANKING_KEYWORDS:
            # Use word boundaries to avoid false positives (e.g., "top" in "topic")
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                # Provide specific guidance based on keyword
                suggestions = {
                    "vote": "Instead of asking people to vote, ask 'What options should be considered?'",
                    "rank": "Instead of ranking, ask 'What factors are most important?' or 'What priorities emerge?'",
                    "best": "Instead of 'best', ask 'What approaches might be effective?' or 'What qualities matter?'",
                    "worst": "Instead of 'worst', ask 'What challenges exist?' or 'What concerns arise?'",
                    "choose": "Instead of asking people to choose, ask 'What options resonate?' or 'What paths exist?'",
                    "prefer": "Instead of preferences, ask 'What appeals to you about different approaches?'",
                }
                suggestion = suggestions.get(keyword, f"Remove '{keyword}' and focus on gathering perspectives")

                duration = time.perf_counter() - start_time
                validation_metrics.record_failure(
                    error_code=ValidationErrorCode.CONTAINS_RANKING_KEYWORD.value,
                    duration_seconds=duration
                )

                return ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.CONTAINS_RANKING_KEYWORD,
                    error_message=(
                        f"Question contains ranking/voting keyword: '{keyword}'. "
                        f"This platform is for gathering diverse perspectives, not voting or ranking. "
                        f"Suggestion: {suggestion}. "
                        f"Focus on understanding the landscape of opinions rather than finding 'winners'."
                    )
                )

        # Check 5: Binary choice patterns
        if self.BINARY_CHOICE_PATTERN.search(text):
            duration = time.perf_counter() - start_time
            validation_metrics.record_failure(
                error_code=ValidationErrorCode.BINARY_CHOICE.value,
                duration_seconds=duration
            )

            return ValidationResult(
                valid=False,
                error_code=ValidationErrorCode.BINARY_CHOICE,
                error_message=(
                    "Question appears to be a binary choice (yes/no, agree/disagree). "
                    "These limit the range of responses and discourage nuanced thinking. "
                    "Instead, ask open-ended questions that invite diverse perspectives. "
                    "Examples: 'What aspects of this proposal resonate with you?', "
                    "'How might this approach work in practice?', "
                    "'What concerns or opportunities do you see?'"
                )
            )

        # All checks passed - record success
        duration = time.perf_counter() - start_time
        validation_metrics.record_success(duration_seconds=duration)

        return ValidationResult(
            valid=True,
            validated_text=text
        )

    @staticmethod
    def get_validation_rules_summary() -> str:
        """
        Get human-readable summary of validation rules.

        Returns:
            Multi-line string describing all validation rules
        """
        return """
Question Validation Rules:
1. Length: 10-200 characters
2. Opening: Must start with 'What' or 'How'
3. Prohibited: Cannot start with 'Why', 'Do you', 'Should we', 'Would you', etc.
4. No Ranking: Cannot contain vote, rank, best, worst, choose, select, pick, prefer, etc.
5. No Binary Choice: Cannot be yes/no or agree/disagree questions

Examples of VALID questions:
- "What are the main challenges facing our community?"
- "How can we improve access to education?"

Examples of INVALID questions:
- "Why is this important?" (starts with Why)
- "Do you agree with this proposal?" (starts with Do you, binary choice)
- "Which option is best?" (contains ranking keyword 'best')
- "Should we vote on this?" (contains 'vote', starts with Should)
""".strip()


# Singleton instance for easy import
validator = QuestionValidator()


def validate_question(text: str) -> ValidationResult:
    """
    Convenience function to validate a question.

    Args:
        text: Question text to validate

    Returns:
        ValidationResult with valid=True/False and error details
    """
    return validator.validate(text)
