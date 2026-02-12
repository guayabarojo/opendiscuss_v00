"""
Text normalization service for Input Collection Protocol.
Normalizes raw text inputs while preserving semantic meaning.
"""

import re
import html


def normalize_text(text: str) -> str:
    """
    Normalize raw text input.

    Operations:
    - Strip leading/trailing whitespace
    - Remove HTML tags
    - Normalize whitespace (multiple spaces/newlines to single space)
    - Decode HTML entities
    - Preserve meaning (no stemming, no case conversion)

    Args:
        text: Raw text input

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    text = html.unescape(text)

    # Normalize whitespace (replace multiple spaces/newlines with single space)
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def is_valid_text(text: str) -> bool:
    """
    Check if text is valid (non-empty after normalization).

    Args:
        text: Text to validate

    Returns:
        True if valid, False otherwise
    """
    normalized = normalize_text(text)
    return len(normalized) > 0
