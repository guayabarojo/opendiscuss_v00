"""
Event handlers for Discussion Protocol state transitions.

These handlers orchestrate sub-protocol integration and enforce
constitutional invariants during round lifecycle transitions.
"""

from .submission_complete import handle_submission_complete
from .summarization_complete import handle_summarization_complete
from .clustering_complete import handle_clustering_complete
from .sankey_complete import handle_sankey_complete
from .registry import register_all_handlers

__all__ = [
    "handle_submission_complete",
    "handle_summarization_complete",
    "handle_clustering_complete",
    "handle_sankey_complete",
    "register_all_handlers",
]
