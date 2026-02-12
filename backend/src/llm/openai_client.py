"""
OpenAI SDK client for summarization (Spec 003).

Provides LLM generation with model selection (GPT-4-turbo vs GPT-3.5).
"""

from typing import Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from ..config import settings
from ..logging_config import logger


# Global OpenAI client instance
_openai_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    """
    Get or create OpenAI async client.

    Configured with API key and organization ID from settings.

    Returns:
        AsyncOpenAI: Async OpenAI client instance

    Raises:
        ValueError: If OPENAI_API_KEY is not configured
    """
    global _openai_client

    if _openai_client is None:
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY not configured. "
                "Set OPENAI_API_KEY environment variable."
            )

        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            organization=settings.openai_org_id,
            timeout=30.0,  # Request timeout (seconds)
            max_retries=3,  # Retry failed requests
        )
        logger.info("OpenAI client initialized successfully")

    return _openai_client


async def generate_summary_llm(
    prompt: str,
    model: str = "gpt-4-turbo",
    temperature: float = 0.7,
    max_tokens: int = 150,
) -> str:
    """
    Generate summary using OpenAI LLM.

    Model Selection (T020):
    - GPT-4-turbo: Default for high-quality summaries
    - GPT-3.5-turbo: Fallback for cost optimization or retry

    Args:
        prompt: Full prompt including instructions and user input
        model: Model identifier (default: "gpt-4-turbo")
        temperature: Sampling temperature (0.0-2.0, default: 0.7)
        max_tokens: Maximum response tokens (default: 150)

    Returns:
        str: Generated summary text

    Raises:
        openai.OpenAIError: If API call fails after retries
        ValueError: If response is empty or invalid
    """
    # MOCK MODE: If no API key configured, generate deterministic summaries for testing
    if not settings.openai_api_key or settings.openai_api_key == "your-openai-api-key-here":
        import hashlib
        import re

        # Extract the submission text from prompt (after "Text to summarize:")
        submission_match = re.search(r'Text to summarize:\s*(.+)', prompt, re.DOTALL)
        if submission_match:
            submission_text = submission_match.group(1).strip()
        else:
            submission_text = prompt

        # Generate deterministic summary based on content hash
        content_hash = hashlib.md5(submission_text.encode()).hexdigest()[:6]

        # Create a short summary (first 80 chars + hash for uniqueness)
        words = submission_text.split()[:15]  # First 15 words
        mock_summary = ' '.join(words)
        if len(submission_text.split()) > 15:
            mock_summary += "..."

        mock_summary = f"{mock_summary} [mock-{content_hash}]"

        logger.warning(
            f"MOCK MODE: Generated deterministic summary (no OpenAI API key configured). "
            f"Length: {len(mock_summary)} chars"
        )
        return mock_summary

    try:
        client = get_openai_client()

        # Call OpenAI API
        response: ChatCompletion = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a neutral summarization assistant. "
                        "Generate concise, factual summaries that preserve participant intent."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            n=1,  # Single completion
            stop=None,
        )

        # Extract summary text
        if not response.choices or not response.choices[0].message.content:
            raise ValueError("Empty response from OpenAI API")

        summary_text = response.choices[0].message.content.strip()

        logger.info(
            f"Generated summary with {model}: "
            f"{len(summary_text)} chars, "
            f"tokens used: {response.usage.total_tokens if response.usage else 'unknown'}"
        )

        return summary_text

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise
