"""
LLM clients for summarization (Spec 003)
"""

from .openai_client import get_openai_client, generate_summary_llm

__all__ = [
    "get_openai_client",
    "generate_summary_llm",
]
