"""
Deterministic Cluster Label Extraction Service

Generates cluster labels using ONLY the semantic clustering output (no LLM).
Extracts labels from medoid summaries using deterministic NLP parsing.

Approach:
1. Use medoid (closest to centroid) - purely mathematical selection
2. Extract noun phrases using spaCy - deterministic parsing
3. Select first major noun phrase as label - rule-based
4. Fallback to simple truncation if parsing fails

This ensures the final aggregation step is bias-free and deterministic.
"""

import logging
import re
from typing import List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class ClusterLabelExtractorError(Exception):
    """Raised when cluster label extraction fails."""
    pass


def extract_noun_phrases(text: str) -> List[str]:
    """
    Extract noun phrases from text using spaCy.

    Args:
        text: Text to extract noun phrases from

    Returns:
        List of noun phrases, ordered by appearance

    Example:
        >>> extract_noun_phrases("Fairness and non-discrimination should be fundamental principles")
        ["Fairness and non-discrimination", "fundamental principles"]
    """
    try:
        import spacy

        # Try to load the model
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning(
                "spaCy model 'en_core_web_sm' not found. "
                "Install with: python -m spacy download en_core_web_sm"
            )
            return []

        doc = nlp(text)

        # Extract noun phrases (noun chunks)
        noun_phrases = []
        for chunk in doc.noun_chunks:
            # Clean up the phrase (remove trailing determiners, etc.)
            phrase = chunk.text.strip()

            # Skip very short phrases (single words, pronouns)
            if len(phrase.split()) < 2 and chunk.root.pos_ in ['PRON', 'DET']:
                continue

            # Skip phrases starting with pronouns
            if phrase.lower().startswith(('it ', 'this ', 'that ', 'these ', 'those ')):
                continue

            noun_phrases.append(phrase)

        return noun_phrases

    except ImportError:
        logger.warning("spaCy not installed. Cannot extract noun phrases.")
        return []
    except Exception as e:
        logger.error(f"Error extracting noun phrases: {e}")
        return []


def extract_first_clause(text: str) -> str:
    """
    Extract the first clause from a sentence.

    Splits on common clause boundaries (commas, 'that', 'which', etc.)
    and returns the first substantial clause.

    Args:
        text: Text to extract from

    Returns:
        First clause or full text if no clear boundary

    Example:
        >>> extract_first_clause("Fairness is crucial, especially in AI systems")
        "Fairness is crucial"
    """
    # Split on common clause boundaries
    # Order matters - check semicolon before comma
    for delimiter in [';', ' - ', ' that ', ' which ', ' where ', ' when ']:
        if delimiter in text:
            parts = text.split(delimiter)
            first_part = parts[0].strip()
            if len(first_part.split()) >= 3:  # At least 3 words
                return first_part

    # Try comma, but only if the first part is substantial
    if ',' in text:
        parts = text.split(',')
        first_part = parts[0].strip()
        if len(first_part.split()) >= 3:
            return first_part

    return text


def simple_truncate(text: str, max_words: int = 8) -> str:
    """
    Simple truncation fallback: take first N words.

    Args:
        text: Text to truncate
        max_words: Maximum number of words (default: 8)

    Returns:
        Truncated text

    Example:
        >>> simple_truncate("This is a very long sentence that needs truncation", max_words=5)
        "This is a very long..."
    """
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def extract_label_from_summary(summary_text: str) -> str:
    """
    Extract a concise label from a summary text using deterministic rules.

    Strategy:
    1. Try to extract first major noun phrase (most specific concept)
    2. If no good noun phrase, extract first clause
    3. If still too long, simple truncation

    Args:
        summary_text: The medoid summary text

    Returns:
        Extracted label (concise, meaningful)

    Examples:
        >>> extract_label_from_summary(
        ...     "Fairness and non-discrimination should be fundamental ethical principles"
        ... )
        "Fairness and non-discrimination"

        >>> extract_label_from_summary(
        ...     "The participant emphasizes transparency requirements for AI systems"
        ... )
        "Transparency requirements for AI systems"
    """
    # Clean up the text
    text = summary_text.strip()

    # Remove common prefixes that appear in summaries
    prefixes_to_remove = [
        "The participant ",
        "The response ",
        "The submission ",
        "Participant ",
        "It is ",
        "There is ",
        "There are ",
    ]
    for prefix in prefixes_to_remove:
        if text.startswith(prefix):
            text = text[len(prefix):]
            # Capitalize first letter
            text = text[0].upper() + text[1:] if text else text
            break

    # Strategy 1: Extract noun phrases using NLP
    noun_phrases = extract_noun_phrases(text)

    if noun_phrases:
        # Take the first substantial noun phrase
        for phrase in noun_phrases:
            word_count = len(phrase.split())
            # Good noun phrase: 2-8 words, contains meaningful content
            if 2 <= word_count <= 8:
                logger.debug(f"Extracted noun phrase label: '{phrase}'")
                return phrase

        # If all noun phrases are too long, take the first and truncate
        first_phrase = noun_phrases[0]
        if len(first_phrase.split()) > 8:
            truncated = simple_truncate(first_phrase, max_words=8)
            logger.debug(f"Truncated long noun phrase to: '{truncated}'")
            return truncated

        logger.debug(f"Using first noun phrase: '{first_phrase}'")
        return first_phrase

    # Strategy 2: Extract first clause
    first_clause = extract_first_clause(text)
    if first_clause != text and len(first_clause.split()) <= 10:
        logger.debug(f"Extracted first clause label: '{first_clause}'")
        return first_clause

    # Strategy 3: Simple truncation fallback
    truncated = simple_truncate(text, max_words=8)
    logger.debug(f"Using simple truncation: '{truncated}'")
    return truncated


def generate_cluster_label_from_medoid(
    medoid_summary_text: str,
    cluster_label: int,
) -> str:
    """
    Generate a cluster label from the medoid summary (deterministic).

    This is the main entry point for cluster label generation.

    Args:
        medoid_summary_text: Text of the medoid summary (closest to centroid)
        cluster_label: Cluster label number (for logging)

    Returns:
        Concise cluster label extracted from medoid

    Example:
        >>> generate_cluster_label_from_medoid(
        ...     "Fairness and non-discrimination should be fundamental principles in AI",
        ...     cluster_label=0
        ... )
        "Fairness and non-discrimination"
    """
    if not medoid_summary_text:
        raise ClusterLabelExtractorError(
            f"Empty medoid summary text for cluster {cluster_label}"
        )

    logger.info(f"Generating label for cluster {cluster_label} from medoid")

    try:
        label = extract_label_from_summary(medoid_summary_text)

        logger.info(
            f"Cluster {cluster_label}: Generated label '{label}' "
            f"from medoid summary (length: {len(medoid_summary_text)} → {len(label)} chars)"
        )

        return label

    except Exception as e:
        logger.error(
            f"Failed to extract label from medoid for cluster {cluster_label}: {e}",
            exc_info=True
        )
        # Fallback: simple truncation
        fallback = simple_truncate(medoid_summary_text, max_words=6)
        logger.warning(f"Using fallback label for cluster {cluster_label}: '{fallback}'")
        return fallback
