"""
Event handlers for Spec 003 integration with Spec 2 and Spec 4.
"""

from .submission_collected import handle_submission_window_closed
from .approval_complete import handle_summary_approved

__all__ = [
    "handle_submission_window_closed",
    "handle_summary_approved",
]
