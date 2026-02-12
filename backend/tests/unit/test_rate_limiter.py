"""
Unit tests for rate limiter service (Spec 002 - T071).

Tests rate limiting functionality from ephemeral_storage:
- Concurrent submissions with threading.Lock
- Race condition prevention
- Rate limit enforcement
- Time window-based cleanup
"""

import pytest
import threading
import time
from datetime import datetime, timedelta
from uuid import uuid4
from src.services.ephemeral_storage import EphemeralStorageManager


@pytest.mark.unit
class TestRateLimiter:
    """Test rate limiting functionality in EphemeralStorageManager."""

    @pytest.fixture
    def storage(self):
        """Create fresh storage manager for each test."""
        return EphemeralStorageManager()

    def test_first_submission_allowed(self, storage):
        """Test that first submission is always allowed."""
        participant_id = uuid4()
        max_submissions = 3
        window_minutes = 5

        result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
        assert result is True

    def test_within_limit_allowed(self, storage):
        """Test that submissions within limit are allowed."""
        participant_id = uuid4()
        max_submissions = 3
        window_minutes = 5

        # Submit 3 times (max allowed)
        result1 = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
        result2 = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
        result3 = storage.check_rate_limit(participant_id, max_submissions, window_minutes)

        assert result1 is True
        assert result2 is True
        assert result3 is True

    def test_exceed_limit_rejected(self, storage):
        """Test that exceeding limit is rejected."""
        participant_id = uuid4()
        max_submissions = 3
        window_minutes = 5

        # Submit 3 times (should succeed)
        for _ in range(3):
            storage.check_rate_limit(participant_id, max_submissions, window_minutes)

        # 4th submission should fail
        result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
        assert result is False

    def test_different_participants_independent(self, storage):
        """Test that rate limits are independent per participant."""
        participant1 = uuid4()
        participant2 = uuid4()
        max_submissions = 2
        window_minutes = 5

        # Participant 1 reaches limit
        storage.check_rate_limit(participant1, max_submissions, window_minutes)
        storage.check_rate_limit(participant1, max_submissions, window_minutes)

        # Participant 2 should still be able to submit
        result = storage.check_rate_limit(participant2, max_submissions, window_minutes)
        assert result is True

    def test_rate_limit_cleanup_old_entries(self, storage):
        """Test that old entries outside window are cleaned up."""
        participant_id = uuid4()
        max_submissions = 2
        window_minutes = 5

        # Manually add old timestamp (6 minutes ago, outside 5-minute window)
        old_time = datetime.utcnow() - timedelta(minutes=6)
        storage.rate_limits[participant_id] = [old_time]

        # Should allow submission since old entry is cleaned
        result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
        assert result is True

        # Should have only 1 entry (the new one)
        assert len(storage.rate_limits[participant_id]) == 1

    def test_rate_limit_respects_window(self, storage):
        """Test that rate limit respects time window."""
        participant_id = uuid4()
        max_submissions = 2
        window_minutes = 5

        # Add timestamps just inside window (4.5 minutes ago)
        recent_time = datetime.utcnow() - timedelta(minutes=4, seconds=30)
        storage.rate_limits[participant_id] = [recent_time, recent_time]

        # Should be at limit
        result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
        assert result is False

    def test_rate_limit_single_submission_limit(self, storage):
        """Test rate limit with max_submissions=1."""
        participant_id = uuid4()
        max_submissions = 1
        window_minutes = 5

        # First submission allowed
        result1 = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
        assert result1 is True

        # Second submission rejected
        result2 = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
        assert result2 is False

    def test_rate_limit_zero_limit(self, storage):
        """Test rate limit with max_submissions=0 (no submissions allowed)."""
        participant_id = uuid4()
        max_submissions = 0
        window_minutes = 5

        # Even first submission should be rejected
        result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
        assert result is False

    def test_rate_limit_high_limit(self, storage):
        """Test rate limit with high max_submissions."""
        participant_id = uuid4()
        max_submissions = 100
        window_minutes = 5

        # Submit 50 times, all should succeed
        for _ in range(50):
            result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
            assert result is True

    def test_rate_limit_mixed_timestamps(self, storage):
        """Test rate limit with mix of old and recent timestamps."""
        participant_id = uuid4()
        max_submissions = 3
        window_minutes = 5

        # Add 2 old entries (outside window) and 1 recent (inside window)
        old_time1 = datetime.utcnow() - timedelta(minutes=10)
        old_time2 = datetime.utcnow() - timedelta(minutes=8)
        recent_time = datetime.utcnow() - timedelta(minutes=2)
        storage.rate_limits[participant_id] = [old_time1, old_time2, recent_time]

        # Should clean old entries, leaving only 1 recent entry
        # So should allow 2 more submissions
        result1 = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
        result2 = storage.check_rate_limit(participant_id, max_submissions, window_minutes)

        assert result1 is True
        assert result2 is True
        assert len(storage.rate_limits[participant_id]) == 3  # 1 old + 2 new

    def test_rate_limit_boundary_exact_window_edge(self, storage):
        """Test rate limit at exact boundary of time window."""
        participant_id = uuid4()
        max_submissions = 2
        window_minutes = 5

        # Add timestamp exactly 5 minutes ago (at boundary)
        boundary_time = datetime.utcnow() - timedelta(minutes=5, seconds=0)
        storage.rate_limits[participant_id] = [boundary_time]

        # Should be cleaned (> cutoff, not >= cutoff)
        result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)

        # After cleanup, should have only the new submission
        assert result is True
        assert len(storage.rate_limits[participant_id]) == 1

    def test_rate_limit_just_inside_window(self, storage):
        """Test rate limit just inside time window."""
        participant_id = uuid4()
        max_submissions = 2
        window_minutes = 5

        # Add timestamp 4 minutes 59 seconds ago (just inside window)
        inside_time = datetime.utcnow() - timedelta(minutes=4, seconds=59)
        storage.rate_limits[participant_id] = [inside_time]

        # Should NOT be cleaned
        result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)

        # Should have 2 entries (1 old + 1 new)
        assert result is True
        assert len(storage.rate_limits[participant_id]) == 2


@pytest.mark.unit
class TestRateLimiterConcurrency:
    """Test rate limiter under concurrent access."""

    @pytest.fixture
    def storage(self):
        """Create fresh storage manager for each test."""
        return EphemeralStorageManager()

    def test_concurrent_submissions_respects_limit(self, storage):
        """Test that concurrent submissions respect rate limit."""
        participant_id = uuid4()
        max_submissions = 3
        window_minutes = 5
        num_threads = 10

        results = []
        lock = threading.Lock()

        def submit():
            result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
            with lock:
                results.append(result)

        # Launch concurrent submissions
        threads = [threading.Thread(target=submit) for _ in range(num_threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have exactly max_submissions True results
        true_count = sum(1 for r in results if r is True)
        false_count = sum(1 for r in results if r is False)

        assert true_count == max_submissions
        assert false_count == num_threads - max_submissions

    def test_concurrent_different_participants(self, storage):
        """Test concurrent submissions from different participants."""
        participants = [uuid4() for _ in range(5)]
        max_submissions = 2
        window_minutes = 5

        results = {}
        lock = threading.Lock()

        def submit(participant_id):
            result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
            with lock:
                if participant_id not in results:
                    results[participant_id] = []
                results[participant_id].append(result)

        # Each participant submits 3 times concurrently
        threads = []
        for participant_id in participants:
            for _ in range(3):
                thread = threading.Thread(target=submit, args=(participant_id,))
                threads.append(thread)

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Each participant should have exactly 2 successful submissions
        for participant_id in participants:
            true_count = sum(1 for r in results[participant_id] if r is True)
            assert true_count == max_submissions

    def test_race_condition_prevention(self, storage):
        """Test that threading.Lock prevents race conditions."""
        participant_id = uuid4()
        max_submissions = 1
        window_minutes = 5

        success_count = 0
        lock = threading.Lock()

        def submit():
            nonlocal success_count
            result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
            if result:
                with lock:
                    success_count += 1

        # Try to submit 100 times concurrently
        threads = [threading.Thread(target=submit) for _ in range(100)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Despite 100 attempts, only 1 should succeed
        assert success_count == 1

    def test_concurrent_cleanup_operations(self, storage):
        """Test that cleanup operations are thread-safe."""
        participant_id = uuid4()
        max_submissions = 5
        window_minutes = 5

        # Pre-populate with old entries
        old_time = datetime.utcnow() - timedelta(minutes=10)
        storage.rate_limits[participant_id] = [old_time] * 20

        results = []
        lock = threading.Lock()

        def check_and_submit():
            result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
            with lock:
                results.append(result)

        # Multiple threads will trigger cleanup simultaneously
        threads = [threading.Thread(target=check_and_submit) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have exactly max_submissions successes
        true_count = sum(1 for r in results if r is True)
        assert true_count == max_submissions

    def test_high_concurrency_stress(self, storage):
        """Stress test with high number of concurrent requests."""
        participant_id = uuid4()
        max_submissions = 10
        window_minutes = 5
        num_threads = 100

        results = []
        lock = threading.Lock()

        def submit():
            result = storage.check_rate_limit(participant_id, max_submissions, window_minutes)
            with lock:
                results.append(result)
            # Small delay to increase contention
            time.sleep(0.001)

        threads = [threading.Thread(target=submit) for _ in range(num_threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify integrity: exactly max_submissions should succeed
        true_count = sum(1 for r in results if r is True)
        assert true_count == max_submissions
        assert len(results) == num_threads


@pytest.mark.unit
class TestRateLimiterDataStructures:
    """Test internal data structure handling."""

    @pytest.fixture
    def storage(self):
        """Create fresh storage manager for each test."""
        return EphemeralStorageManager()

    def test_rate_limit_dict_initialization(self, storage):
        """Test that rate_limits dict is initialized empty."""
        assert storage.rate_limits == {}

    def test_rate_limit_creates_entry_for_new_participant(self, storage):
        """Test that check_rate_limit creates entry for new participant."""
        participant_id = uuid4()
        storage.check_rate_limit(participant_id, max_submissions=3, window_minutes=5)

        assert participant_id in storage.rate_limits
        assert len(storage.rate_limits[participant_id]) == 1

    def test_rate_limit_timestamp_ordering(self, storage):
        """Test that timestamps are appended in order."""
        participant_id = uuid4()
        max_submissions = 5
        window_minutes = 5

        timestamps_before = []
        for _ in range(3):
            storage.check_rate_limit(participant_id, max_submissions, window_minutes)
            timestamps_before.append(datetime.utcnow())
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # Timestamps should be in chronological order (or very close)
        timestamps_in_storage = storage.rate_limits[participant_id]
        assert len(timestamps_in_storage) == 3

        for i in range(len(timestamps_in_storage) - 1):
            assert timestamps_in_storage[i] <= timestamps_in_storage[i + 1]

    def test_rate_limit_cleanup_preserves_recent(self, storage):
        """Test that cleanup preserves recent timestamps."""
        participant_id = uuid4()
        max_submissions = 10
        window_minutes = 5

        # Add mix of old and recent
        now = datetime.utcnow()
        old_times = [now - timedelta(minutes=i) for i in range(10, 15)]
        recent_times = [now - timedelta(minutes=i) for i in range(1, 4)]

        storage.rate_limits[participant_id] = old_times + recent_times

        # Trigger cleanup
        storage.check_rate_limit(participant_id, max_submissions, window_minutes)

        # Should have 3 recent + 1 new = 4 total
        assert len(storage.rate_limits[participant_id]) == 4

    def test_multiple_participants_isolated(self, storage):
        """Test that multiple participants have isolated rate limits."""
        participants = [uuid4() for _ in range(5)]
        max_submissions = 10  # High enough to not limit any participant
        window_minutes = 5

        # Each participant submits different number of times
        for i, participant_id in enumerate(participants):
            for _ in range(i + 1):
                storage.check_rate_limit(participant_id, max_submissions, window_minutes)

        # Verify each has correct count
        for i, participant_id in enumerate(participants):
            assert len(storage.rate_limits[participant_id]) == i + 1
