"""
Safety filtering service for Spec 003 User Story 4.

Detects and neutralizes profanity, slurs, and illegal threats during summarization.
Implements two-layer safety filtering:
1. Profanity Neutralization: Detect profanity → strip/replace → allow approval
2. Threat Blocking: Detect illegal threats → prevent approval → notify participant

Constitutional Compliance:
- Community-Bounded Context: Safety standards align with community norms
- Intent Fidelity: Preserves participant intent while ensuring safety
- Representation Not Adjudication: Filters harmful content without judging ideas
"""

from typing import Dict, List, Optional, Tuple
import re
from better_profanity import profanity
from ...logging_config import logger
from ...config import settings


# Threat detection keywords (violence, illegal activity, harm)
THREAT_KEYWORDS = [
    # Violence keywords
    "kill", "murder", "shoot", "bomb", "attack", "assault",
    "hurt", "harm", "injure", "destroy", "eliminate",
    # Illegal activity keywords
    "illegal", "crime", "fraud", "steal", "hack",
    # Explicit threats
    "i will", "i'll", "going to", "threat", "threaten",
]

# Profanity replacement character
PROFANITY_REPLACEMENT = "*"


class SafetyFilterService:
    """
    Service for safety filtering of participant submissions.

    Provides two-layer filtering:
    1. Profanity detection/neutralization (allows submission with flag)
    2. Threat detection (blocks submission entirely)

    Tasks T066-T068:
    - T066: filter_submission() - Main entry point
    - T067: detect_profanity() + neutralize_profanity() - Profanity handling
    - T068: detect_threats() - Threat detection with keywords + OpenAI Moderation
    """

    def __init__(self):
        """Initialize safety filter service with better-profanity."""
        # Load better-profanity dictionary
        profanity.load_censor_words()

    async def filter_submission(
        self, submission_text: str
    ) -> Tuple[str, List[str], bool]:
        """
        Main entry point for safety filtering (T066).

        Applies profanity neutralization and threat detection.
        Returns filtered text, safety flags, and approval block status.

        Args:
            submission_text: Raw participant submission text

        Returns:
            Tuple of (filtered_text, safety_flags, is_blocked):
            - filtered_text: Text with profanity neutralized (if any)
            - safety_flags: List of flags (e.g., ["profanity_neutralized"])
            - is_blocked: True if content should be blocked (threats detected)

        Example:
            >>> text, flags, blocked = await filter_submission("some text")
            >>> if blocked:
            >>>     # Set status=DISALLOWED_CONTENT
            >>> elif flags:
            >>>     # Set safety_flags and proceed
        """
        safety_flags: List[str] = []
        filtered_text = submission_text

        # Layer 1: Profanity detection and neutralization
        has_profanity = self.detect_profanity(submission_text)
        if has_profanity:
            filtered_text = self.neutralize_profanity(submission_text)
            safety_flags.append("profanity_neutralized")
            logger.warning(
                f"Profanity detected and neutralized in submission. "
                f"Original length: {len(submission_text)}, "
                f"Filtered length: {len(filtered_text)}"
            )

        # Layer 2: Threat detection (blocking)
        is_threat, threat_details = await self.detect_threats(submission_text)
        if is_threat:
            safety_flags.append("threat_detected")
            logger.error(
                f"Threat detected in submission: {threat_details}. "
                f"Content will be blocked (DISALLOWED_CONTENT)."
            )
            return filtered_text, safety_flags, True  # Block approval

        # Layer 3: OpenAI Moderation API (if enabled)
        if settings.openai_moderation_enabled:
            is_flagged, moderation_details = await self._check_openai_moderation(
                submission_text
            )
            if is_flagged:
                safety_flags.append("ai_moderation_flagged")
                logger.warning(
                    f"OpenAI Moderation flagged submission: {moderation_details}. "
                    f"Treating as potential threat."
                )
                return filtered_text, safety_flags, True  # Block approval

        # All checks passed
        if safety_flags:
            logger.info(f"Submission passed safety filters with flags: {safety_flags}")
        else:
            logger.debug("Submission passed all safety filters without flags")

        return filtered_text, safety_flags, False

    def detect_profanity(self, text: str) -> bool:
        """
        Detect profanity using better-profanity library (T067).

        Args:
            text: Text to check for profanity

        Returns:
            True if profanity detected, False otherwise
        """
        return profanity.contains_profanity(text)

    def neutralize_profanity(self, text: str) -> str:
        """
        Neutralize profanity by replacing with asterisks (T067).

        Uses better-profanity's censoring to replace profane words.

        Args:
            text: Text containing profanity

        Returns:
            Text with profanity replaced by asterisks

        Example:
            >>> neutralize_profanity("This is bad word")
            "This is *** ****"
        """
        return profanity.censor(text, PROFANITY_REPLACEMENT)

    async def detect_threats(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Detect illegal threats using keyword matching (T068).

        Checks for violence keywords, illegal activity mentions, and explicit threats.
        Uses case-insensitive matching with word boundaries.

        Args:
            text: Text to check for threats

        Returns:
            Tuple of (is_threat, details):
            - is_threat: True if threat detected
            - details: Description of detected threat pattern (if any)

        Threat Categories:
        1. Violence: "kill", "murder", "shoot", "bomb", "attack", "destroy"
        2. Illegal Activity: "illegal", "crime", "fraud", "steal", "hack"
        3. Explicit Threats: "I will", "I'll", "going to" + violence keywords
        """
        text_lower = text.lower()

        # Check for explicit threat patterns (e.g., "I will kill")
        explicit_threat_patterns = [
            r"\b(i will|i'll|i am going to|im going to)\s+(kill|murder|hurt|harm|attack|destroy)",
            r"\b(threat|threaten)\b",
        ]

        for pattern in explicit_threat_patterns:
            if re.search(pattern, text_lower):
                return (
                    True,
                    f"Explicit threat pattern detected: {pattern}",
                )

        # Check for violence keywords in threatening context
        violence_keywords = ["kill", "murder", "shoot", "bomb", "attack", "assault", "destroy"]
        found_violence_keywords = [
            kw for kw in violence_keywords if re.search(rf"\b{kw}\b", text_lower)
        ]

        # If multiple violence keywords present, likely a threat
        if len(found_violence_keywords) >= 2:
            return (
                True,
                f"Multiple violence keywords detected: {', '.join(found_violence_keywords)}",
            )

        # Check for illegal activity keywords combined with personal pronouns
        # Pattern: personal pronoun + optional words + illegal keyword
        # Examples: "I plan to hack", "I hack", "we steal", "you will steal"
        illegal_keywords = ["illegal", "crime", "fraud", "steal", "hack"]
        for kw in illegal_keywords:
            # More flexible pattern to catch "I plan to hack" and similar constructions
            if re.search(rf"\b(i|we|you|they)(\s+\w+){0,4}\s+{kw}", text_lower):
                return (
                    True,
                    f"Illegal activity with personal involvement: {kw}",
                )

        # No threats detected
        return False, None

    async def _check_openai_moderation(
        self, text: str
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check text using OpenAI Moderation API (T068).

        Uses OpenAI's moderation endpoint to detect:
        - Hate speech
        - Harassment
        - Violence
        - Self-harm
        - Sexual content (non-consensual)

        Args:
            text: Text to moderate

        Returns:
            Tuple of (is_flagged, details):
            - is_flagged: True if flagged by moderation API
            - details: Moderation categories that were flagged (if any)
        """
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)

            response = await client.moderations.create(input=text)

            # Check if any category was flagged
            moderation_result = response.results[0]
            if moderation_result.flagged:
                # Extract flagged categories
                flagged_categories = [
                    category
                    for category, flagged in moderation_result.categories.model_dump().items()
                    if flagged
                ]

                details = {
                    "flagged_categories": flagged_categories,
                    "category_scores": moderation_result.category_scores.model_dump(),
                }

                return True, details

            return False, None

        except Exception as e:
            logger.error(f"OpenAI Moderation API call failed: {e}")
            # Fail open: Don't block submission if moderation API fails
            return False, None

    def get_safety_notice_message(self, safety_flags: List[str]) -> str:
        """
        Generate user-facing safety notice message based on flags.

        Args:
            safety_flags: List of safety flags from filter_submission()

        Returns:
            Human-readable safety notice message

        Example:
            >>> get_safety_notice_message(["profanity_neutralized"])
            "We detected and removed inappropriate language from your submission..."
        """
        if not safety_flags:
            return ""

        messages = []

        if "profanity_neutralized" in safety_flags:
            messages.append(
                "We detected and removed inappropriate language from your submission. "
                "The summary reflects your core idea without the profanity."
            )

        if "threat_detected" in safety_flags or "ai_moderation_flagged" in safety_flags:
            messages.append(
                "Your submission contains content that violates community safety guidelines. "
                "Please resubmit with appropriate content that focuses on the discussion topic."
            )

        return " ".join(messages)
