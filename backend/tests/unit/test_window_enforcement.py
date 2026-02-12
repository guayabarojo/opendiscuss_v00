"""
Unit tests for window enforcement service (Spec 002 - T070).

Tests boundary conditions for submission window enforcement:
- Inclusive start: timestamp >= window_start
- Exclusive end: timestamp < window_end
- Before window (rejected)
- After window (rejected)
"""

import pytest
from datetime import datetime, timedelta
from src.services.window_enforcement import (
    is_within_window,
    get_remaining_seconds,
    get_window_status,
    get_wait_duration_seconds,
    WindowStatus
)


@pytest.mark.unit
class TestIsWithinWindow:
    """Test is_within_window function with boundary conditions."""

    def test_at_window_start_inclusive(self):
        """Test that submission exactly at window start is accepted (inclusive)."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)  # 2:00 PM
        window_end = datetime(2026, 1, 29, 14, 5, 0)    # 2:05 PM
        timestamp = datetime(2026, 1, 29, 14, 0, 0)     # Exactly at start

        assert is_within_window(timestamp, window_start, window_end) is True

    def test_at_window_end_exclusive(self):
        """Test that submission exactly at window end is rejected (exclusive)."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)  # 2:00 PM
        window_end = datetime(2026, 1, 29, 14, 5, 0)    # 2:05 PM
        timestamp = datetime(2026, 1, 29, 14, 5, 0)     # Exactly at end

        assert is_within_window(timestamp, window_start, window_end) is False

    def test_before_window_start(self):
        """Test that submission before window start is rejected."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)  # 2:00 PM
        window_end = datetime(2026, 1, 29, 14, 5, 0)    # 2:05 PM
        timestamp = datetime(2026, 1, 29, 13, 59, 59)   # 1:59:59 PM

        assert is_within_window(timestamp, window_start, window_end) is False

    def test_after_window_end(self):
        """Test that submission after window end is rejected."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)  # 2:00 PM
        window_end = datetime(2026, 1, 29, 14, 5, 0)    # 2:05 PM
        timestamp = datetime(2026, 1, 29, 14, 5, 1)     # 2:05:01 PM

        assert is_within_window(timestamp, window_start, window_end) is False

    def test_within_window_middle(self):
        """Test that submission in middle of window is accepted."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)  # 2:00 PM
        window_end = datetime(2026, 1, 29, 14, 5, 0)    # 2:05 PM
        timestamp = datetime(2026, 1, 29, 14, 2, 30)    # 2:02:30 PM

        assert is_within_window(timestamp, window_start, window_end) is True

    def test_one_second_after_start(self):
        """Test that submission one second after start is accepted."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 0, 1)     # 2:00:01 PM

        assert is_within_window(timestamp, window_start, window_end) is True

    def test_one_second_before_end(self):
        """Test that submission one second before end is accepted."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 4, 59)    # 2:04:59 PM

        assert is_within_window(timestamp, window_start, window_end) is True

    def test_microseconds_before_end(self):
        """Test that submission microseconds before end is accepted."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 4, 59, 999999)

        assert is_within_window(timestamp, window_start, window_end) is True

    def test_microseconds_at_end(self):
        """Test that submission with microseconds exactly at end is rejected."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 5, 0, 0)

        assert is_within_window(timestamp, window_start, window_end) is False

    def test_long_window(self):
        """Test with a long window (1 hour)."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 15, 0, 0)    # 1 hour later
        timestamp = datetime(2026, 1, 29, 14, 30, 0)    # 30 minutes in

        assert is_within_window(timestamp, window_start, window_end) is True

    def test_short_window(self):
        """Test with a very short window (1 minute)."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 1, 0)    # 1 minute window
        timestamp = datetime(2026, 1, 29, 14, 0, 30)    # 30 seconds in

        assert is_within_window(timestamp, window_start, window_end) is True

    def test_cross_day_boundary(self):
        """Test window that crosses midnight boundary."""
        window_start = datetime(2026, 1, 29, 23, 55, 0)  # 11:55 PM
        window_end = datetime(2026, 1, 30, 0, 5, 0)      # 12:05 AM next day
        timestamp = datetime(2026, 1, 30, 0, 0, 0)       # Midnight

        assert is_within_window(timestamp, window_start, window_end) is True

    def test_far_before_window(self):
        """Test submission hours before window start."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 10, 0, 0)     # 4 hours before

        assert is_within_window(timestamp, window_start, window_end) is False

    def test_far_after_window(self):
        """Test submission hours after window end."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 18, 0, 0)     # 4 hours after

        assert is_within_window(timestamp, window_start, window_end) is False


@pytest.mark.unit
class TestGetRemainingSeconds:
    """Test get_remaining_seconds function."""

    def test_remaining_seconds_full_window(self):
        """Test remaining seconds at window start."""
        current_time = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)    # 5 minutes = 300 seconds

        remaining = get_remaining_seconds(current_time, window_end)
        assert remaining == 300

    def test_remaining_seconds_halfway(self):
        """Test remaining seconds at halfway point."""
        current_time = datetime(2026, 1, 29, 14, 2, 30)  # 2.5 minutes in
        window_end = datetime(2026, 1, 29, 14, 5, 0)

        remaining = get_remaining_seconds(current_time, window_end)
        assert remaining == 150  # 2.5 minutes remaining

    def test_remaining_seconds_near_end(self):
        """Test remaining seconds near end of window."""
        current_time = datetime(2026, 1, 29, 14, 4, 50)  # 10 seconds left
        window_end = datetime(2026, 1, 29, 14, 5, 0)

        remaining = get_remaining_seconds(current_time, window_end)
        assert remaining == 10

    def test_remaining_seconds_one_second(self):
        """Test with exactly one second remaining."""
        current_time = datetime(2026, 1, 29, 14, 4, 59)
        window_end = datetime(2026, 1, 29, 14, 5, 0)

        remaining = get_remaining_seconds(current_time, window_end)
        assert remaining == 1

    def test_remaining_seconds_at_end(self):
        """Test remaining seconds at window end returns 0."""
        current_time = datetime(2026, 1, 29, 14, 5, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)

        remaining = get_remaining_seconds(current_time, window_end)
        assert remaining == 0

    def test_remaining_seconds_after_end(self):
        """Test remaining seconds after window end returns 0."""
        current_time = datetime(2026, 1, 29, 14, 6, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)

        remaining = get_remaining_seconds(current_time, window_end)
        assert remaining == 0

    def test_remaining_seconds_with_microseconds(self):
        """Test that microseconds are handled correctly (truncated)."""
        current_time = datetime(2026, 1, 29, 14, 4, 59, 500000)  # 0.5 seconds before end
        window_end = datetime(2026, 1, 29, 14, 5, 0)

        remaining = get_remaining_seconds(current_time, window_end)
        assert remaining == 0  # Truncated to 0 seconds

    def test_remaining_seconds_long_duration(self):
        """Test with a long remaining duration (1 hour)."""
        current_time = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 15, 0, 0)

        remaining = get_remaining_seconds(current_time, window_end)
        assert remaining == 3600  # 60 minutes

    def test_remaining_seconds_cross_day_boundary(self):
        """Test remaining seconds calculation across midnight."""
        current_time = datetime(2026, 1, 29, 23, 58, 0)
        window_end = datetime(2026, 1, 30, 0, 3, 0)      # 5 minutes later

        remaining = get_remaining_seconds(current_time, window_end)
        assert remaining == 300

    def test_remaining_seconds_negative_case(self):
        """Test that function returns 0 for negative time difference."""
        current_time = datetime(2026, 1, 29, 14, 10, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)    # End is in the past

        remaining = get_remaining_seconds(current_time, window_end)
        assert remaining == 0


@pytest.mark.unit
class TestWindowEnforcementEdgeCases:
    """Test edge cases and special scenarios."""

    def test_same_start_and_end_time(self):
        """Test with zero-duration window (start equals end)."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 0, 0)
        timestamp = datetime(2026, 1, 29, 14, 0, 0)

        # Even at the exact time, exclusive end means no valid window
        assert is_within_window(timestamp, window_start, window_end) is False

    def test_backwards_window(self):
        """Test with end time before start time (invalid configuration)."""
        window_start = datetime(2026, 1, 29, 14, 5, 0)
        window_end = datetime(2026, 1, 29, 14, 0, 0)    # End before start
        timestamp = datetime(2026, 1, 29, 14, 2, 0)

        # Should always be False for invalid window
        assert is_within_window(timestamp, window_start, window_end) is False

    def test_utc_timestamps(self):
        """Test that function works with UTC timestamps."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)  # Assumed UTC
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 2, 0)

        assert is_within_window(timestamp, window_start, window_end) is True

    def test_very_long_window(self):
        """Test with multi-day window."""
        window_start = datetime(2026, 1, 29, 0, 0, 0)
        window_end = datetime(2026, 2, 1, 0, 0, 0)       # 3 days later
        timestamp = datetime(2026, 1, 30, 12, 0, 0)      # Day 2, noon

        assert is_within_window(timestamp, window_start, window_end) is True

    def test_window_enforcement_consistency(self):
        """Test that multiple checks with same timestamp are consistent."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 2, 30)

        # Multiple calls should return same result
        result1 = is_within_window(timestamp, window_start, window_end)
        result2 = is_within_window(timestamp, window_start, window_end)
        result3 = is_within_window(timestamp, window_start, window_end)

        assert result1 == result2 == result3 == True


@pytest.mark.unit
class TestGetWindowStatus:
    """Test T063: get_window_status function for enhanced error responses."""

    def test_status_before_window(self):
        """Test status is BEFORE_WINDOW when timestamp is before start."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 13, 59, 59)

        status = get_window_status(timestamp, window_start, window_end)
        assert status == WindowStatus.BEFORE_WINDOW

    def test_status_at_start_is_within(self):
        """Test status is WITHIN_WINDOW at exact start (inclusive)."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 0, 0)

        status = get_window_status(timestamp, window_start, window_end)
        assert status == WindowStatus.WITHIN_WINDOW

    def test_status_within_window(self):
        """Test status is WITHIN_WINDOW when inside window."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 2, 30)

        status = get_window_status(timestamp, window_start, window_end)
        assert status == WindowStatus.WITHIN_WINDOW

    def test_status_at_end_is_after(self):
        """Test status is AFTER_WINDOW at exact end (exclusive)."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 5, 0)

        status = get_window_status(timestamp, window_start, window_end)
        assert status == WindowStatus.AFTER_WINDOW

    def test_status_after_window(self):
        """Test status is AFTER_WINDOW when timestamp is after end."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 5, 1)

        status = get_window_status(timestamp, window_start, window_end)
        assert status == WindowStatus.AFTER_WINDOW

    def test_status_one_second_before_start(self):
        """Test status exactly 1 second before start."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 13, 59, 59)

        status = get_window_status(timestamp, window_start, window_end)
        assert status == WindowStatus.BEFORE_WINDOW

    def test_status_one_second_before_end(self):
        """Test status exactly 1 second before end."""
        window_start = datetime(2026, 1, 29, 14, 0, 0)
        window_end = datetime(2026, 1, 29, 14, 5, 0)
        timestamp = datetime(2026, 1, 29, 14, 4, 59)

        status = get_window_status(timestamp, window_start, window_end)
        assert status == WindowStatus.WITHIN_WINDOW


@pytest.mark.unit
class TestGetWaitDurationSeconds:
    """Test T063: get_wait_duration_seconds function for BEFORE_WINDOW errors."""

    def test_wait_duration_one_minute(self):
        """Test wait duration with 1 minute until start."""
        current_time = datetime(2026, 1, 29, 13, 59, 0)
        window_start = datetime(2026, 1, 29, 14, 0, 0)

        wait_duration = get_wait_duration_seconds(current_time, window_start)
        assert wait_duration == 60

    def test_wait_duration_five_minutes(self):
        """Test wait duration with 5 minutes until start."""
        current_time = datetime(2026, 1, 29, 13, 55, 0)
        window_start = datetime(2026, 1, 29, 14, 0, 0)

        wait_duration = get_wait_duration_seconds(current_time, window_start)
        assert wait_duration == 300

    def test_wait_duration_one_second(self):
        """Test wait duration with 1 second until start."""
        current_time = datetime(2026, 1, 29, 13, 59, 59)
        window_start = datetime(2026, 1, 29, 14, 0, 0)

        wait_duration = get_wait_duration_seconds(current_time, window_start)
        assert wait_duration == 1

    def test_wait_duration_at_start(self):
        """Test wait duration returns 0 at window start."""
        current_time = datetime(2026, 1, 29, 14, 0, 0)
        window_start = datetime(2026, 1, 29, 14, 0, 0)

        wait_duration = get_wait_duration_seconds(current_time, window_start)
        assert wait_duration == 0

    def test_wait_duration_after_start(self):
        """Test wait duration returns 0 after window start."""
        current_time = datetime(2026, 1, 29, 14, 2, 0)
        window_start = datetime(2026, 1, 29, 14, 0, 0)

        wait_duration = get_wait_duration_seconds(current_time, window_start)
        assert wait_duration == 0

    def test_wait_duration_one_hour(self):
        """Test wait duration with 1 hour until start."""
        current_time = datetime(2026, 1, 29, 13, 0, 0)
        window_start = datetime(2026, 1, 29, 14, 0, 0)

        wait_duration = get_wait_duration_seconds(current_time, window_start)
        assert wait_duration == 3600

    def test_wait_duration_cross_day_boundary(self):
        """Test wait duration calculation across midnight."""
        current_time = datetime(2026, 1, 29, 23, 58, 0)
        window_start = datetime(2026, 1, 30, 0, 3, 0)

        wait_duration = get_wait_duration_seconds(current_time, window_start)
        assert wait_duration == 300  # 5 minutes

    def test_wait_duration_with_microseconds(self):
        """Test that microseconds are truncated correctly."""
        current_time = datetime(2026, 1, 29, 13, 59, 59, 500000)
        window_start = datetime(2026, 1, 29, 14, 0, 0)

        wait_duration = get_wait_duration_seconds(current_time, window_start)
        assert wait_duration == 0  # Truncated to 0 seconds
