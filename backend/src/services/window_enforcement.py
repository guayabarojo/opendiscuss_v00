"""
Window enforcement service for Input Collection Protocol.
Enforces time-bounded submission windows (inclusive start, exclusive end).
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from src.models.protocol_state import DiscussionTimingMode


class WindowStatus(str, Enum):
    """Window status enumeration for detailed error responses."""
    BEFORE_WINDOW = "BEFORE_WINDOW"
    AFTER_WINDOW = "AFTER_WINDOW"
    WITHIN_WINDOW = "WITHIN_WINDOW"


def is_within_window(
    timestamp: datetime,
    window_start: datetime,
    window_end: datetime,
    timing_mode: DiscussionTimingMode = DiscussionTimingMode.SYNCHRONOUS
) -> bool:
    """
    Check if timestamp is within submission window.

    Rules:
    - Inclusive start: timestamp >= window_start
    - Exclusive end: timestamp < window_end

    Args:
        timestamp: Submission timestamp (UTC)
        window_start: Window start time (UTC)
        window_end: Window end time (UTC)
        timing_mode: Discussion timing mode (SYNCHRONOUS or ASYNCHRONOUS)

    Returns:
        True if within window, False otherwise

    Example (SYNCHRONOUS mode):
        window_start = 14:00:00, window_end = 14:05:00
        - 13:59:59 → False (before window)
        - 14:00:00 → True  (inclusive start boundary)
        - 14:02:30 → True  (within window)
        - 14:05:00 → False (exclusive end boundary)
        - 14:05:01 → False (after window)

    Example (ASYNCHRONOUS mode):
        window_start = 14:00:00, window_end = 14:05:00 (soft deadline)
        - 13:59:59 → False (before window)
        - 14:00:00 → True  (inclusive start boundary)
        - 14:02:30 → True  (within window)
        - 14:05:00 → True  (after soft deadline, still accepted)
        - 14:05:01 → True  (after soft deadline, still accepted)

    Constitutional Compliance:
    - SYNCHRONOUS: Strict time boundaries ensure fair participation
    - ASYNCHRONOUS: Only enforces start boundary, allows late submissions
    """
    if timing_mode == DiscussionTimingMode.ASYNCHRONOUS:
        # Async: only check if after start (no end enforcement)
        return timestamp >= window_start

    # CRITICAL LOGIC: Boundary semantics for SYNCHRONOUS mode
    # Use >= for inclusive start: participant CAN submit at window_start
    # Use < for exclusive end: participant CANNOT submit at window_end
    # This matches Python's range semantics: [start, end)
    # Rationale: Prevents race conditions where two systems see different states at exact boundary
    return window_start <= timestamp < window_end


def get_remaining_seconds(current_time: datetime, window_end: datetime) -> int:
    """
    Get remaining seconds in submission window.

    Args:
        current_time: Current time (UTC)
        window_end: Window end time (UTC)

    Returns:
        Remaining seconds (0 if window closed)
    """
    if current_time >= window_end:
        return 0

    delta = window_end - current_time
    return int(delta.total_seconds())


def get_window_status(timestamp: datetime, window_start: datetime, window_end: datetime) -> WindowStatus:
    """
    Determine window status for a given timestamp.

    Args:
        timestamp: Time to check (UTC)
        window_start: Window start time (UTC)
        window_end: Window end time (UTC)

    Returns:
        WindowStatus enum indicating relationship to window

    Example:
        window_start = 14:00, window_end = 14:05
        - 13:59 → BEFORE_WINDOW
        - 14:00 → WITHIN_WINDOW
        - 14:02 → WITHIN_WINDOW
        - 14:05 → AFTER_WINDOW
        - 14:06 → AFTER_WINDOW
    """
    if timestamp < window_start:
        return WindowStatus.BEFORE_WINDOW
    elif timestamp >= window_end:
        return WindowStatus.AFTER_WINDOW
    else:
        return WindowStatus.WITHIN_WINDOW


def get_wait_duration_seconds(current_time: datetime, window_start: datetime) -> int:
    """
    Calculate how long to wait until window opens.

    Args:
        current_time: Current time (UTC)
        window_start: Window start time (UTC)

    Returns:
        Seconds to wait (0 if window already started or passed)
    """
    if current_time >= window_start:
        return 0

    delta = window_start - current_time
    return int(delta.total_seconds())
