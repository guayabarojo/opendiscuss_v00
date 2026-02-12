"""
Question Progression Protocol (Spec 006).

Manages question sequencing for discussions with dual-mode support:
- Host-defined: Questions provided upfront at discussion creation
- Auto-generated: Questions generated autonomously after each Sankey analysis

All questions follow constitutional constraints (What/How only, no voting/ranking).
"""

__version__ = "0.1.0"
