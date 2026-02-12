"""
Input validation service for Input Collection Protocol.
Validates text inputs before acceptance.
"""

from typing import Tuple


def validate_text_input(text: str) -> Tuple[bool, str]:
    """
    Validate text input.

    Rules:
    - Must be non-empty
    - Max 5000 characters
    - Not whitespace-only

    Args:
        text: Input text to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not text:
        return False, "Text input cannot be empty"

    if text.strip() == "":
        return False, "Text input cannot be whitespace-only"

    if len(text) > 5000:
        return False, f"Text input exceeds maximum length of 5000 characters (got {len(text)})"

    return True, ""


def validate_participant_can_submit(
    participant_id: str,
    round_id: str,
    submission_count: int,
    max_submissions: int
) -> Tuple[bool, str]:
    """
    Validate participant can submit to round.

    Args:
        participant_id: Participant UUID
        round_id: Round UUID
        submission_count: Current submission count for participant in round
        max_submissions: Maximum allowed submissions

    Returns:
        Tuple of (can_submit, error_message)
    """
    if submission_count >= max_submissions:
        return False, f"Maximum submissions ({max_submissions}) reached for this round"

    return True, ""
