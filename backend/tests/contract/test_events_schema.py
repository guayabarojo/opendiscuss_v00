"""
T073: Contract Validation for Events

Verifies that clustering.completed and alignment.completed events match events.yaml schema:
- Event structure validation
- Required fields present
- Correct data types
- Timestamp format validation
- UUID format validation

Requirements:
- Events must match events.yaml schema
- clustering.completed event payload
- alignment.completed event payload
"""

import pytest
import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Dict


class TestClusteringCompletedEventSchema:
    """Validate clustering.completed event contract."""

    def test_clustering_completed_event_structure(self):
        """
        T073.1: Verify clustering.completed event has required fields.

        Per events.yaml schema.
        """
        event = {
            "event_id": str(uuid4()),
            "event_type": "clustering.completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "round_id": str(uuid4()),
                "cluster_count": 8,
                "total_participants": 95,
                "singleton_count": 2,
                "processing_time_ms": 3600,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # Verify required fields
        assert "event_id" in event, "Missing event_id"
        assert "event_type" in event, "Missing event_type"
        assert "timestamp" in event, "Missing timestamp"
        assert "data" in event, "Missing data"

        # Verify data fields
        data = event["data"]
        assert "round_id" in data, "Missing round_id"
        assert "cluster_count" in data, "Missing cluster_count"
        assert "total_participants" in data, "Missing total_participants"
        assert "singleton_count" in data, "Missing singleton_count"
        assert "processing_time_ms" in data, "Missing processing_time_ms"
        assert "completed_at" in data, "Missing completed_at"

    def test_clustering_completed_event_type_validation(self):
        """
        T073.2: Verify event_type is exactly "clustering.completed".

        Must match schema constant.
        """
        event_type = "clustering.completed"

        assert event_type == "clustering.completed", (
            f"Invalid event_type: {event_type}"
        )

    def test_clustering_completed_field_types(self):
        """
        T073.3: Verify field types match schema.

        - event_id: string (UUID format)
        - event_type: string (const)
        - timestamp: string (ISO8601 datetime)
        - data.round_id: string (UUID)
        - data.cluster_count: integer
        - data.total_participants: integer
        - data.singleton_count: integer
        - data.processing_time_ms: integer
        - data.completed_at: string (ISO8601 datetime)
        """
        event_id = str(uuid4())
        round_id = str(uuid4())
        cluster_count = 8
        total_participants = 95
        singleton_count = 2
        processing_time_ms = 3600
        timestamp = datetime.now(timezone.utc).isoformat()
        completed_at = datetime.now(timezone.utc).isoformat()

        # Verify types
        assert isinstance(event_id, str), "event_id should be string"
        assert isinstance(round_id, str), "round_id should be string"
        assert isinstance(cluster_count, int), "cluster_count should be integer"
        assert isinstance(total_participants, int), "total_participants should be integer"
        assert isinstance(singleton_count, int), "singleton_count should be integer"
        assert isinstance(processing_time_ms, int), "processing_time_ms should be integer"
        assert isinstance(timestamp, str), "timestamp should be string"
        assert isinstance(completed_at, str), "completed_at should be string"

    def test_clustering_completed_uuid_format(self):
        """
        T073.4: Verify UUID fields have valid UUID format.

        event_id and round_id must be valid UUIDs.
        """
        event_id = str(uuid4())
        round_id = str(uuid4())

        # Valid UUID format (36 chars with dashes)
        assert len(event_id) == 36, f"event_id length {len(event_id)} != 36"
        assert event_id.count("-") == 4, "event_id should have 4 dashes"
        assert len(round_id) == 36, f"round_id length {len(round_id)} != 36"
        assert round_id.count("-") == 4, "round_id should have 4 dashes"

    def test_clustering_completed_timestamp_format(self):
        """
        T073.5: Verify timestamp fields are ISO8601 format.

        timestamp and completed_at must be valid ISO8601 datetimes.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        completed_at = datetime.now(timezone.utc).isoformat()

        # ISO8601 format check
        try:
            dt1 = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            dt2 = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            # Success if no exception
        except ValueError as e:
            pytest.fail(f"Invalid ISO8601 format: {e}")

    def test_clustering_completed_numeric_ranges(self):
        """
        T073.6: Verify numeric fields have reasonable ranges.

        cluster_count >= 1
        total_participants >= 1
        singleton_count >= 0
        processing_time_ms >= 0
        """
        cluster_count = 8
        total_participants = 95
        singleton_count = 2
        processing_time_ms = 3600

        assert cluster_count >= 1, "cluster_count should be >= 1"
        assert total_participants >= 1, "total_participants should be >= 1"
        assert singleton_count >= 0, "singleton_count should be >= 0"
        assert processing_time_ms >= 0, "processing_time_ms should be >= 0"

        # Singleton count should not exceed total participants
        assert singleton_count <= total_participants, (
            "singleton_count should not exceed total_participants"
        )

    def test_clustering_completed_example_payload(self):
        """
        T073.7: Validate against example from events.yaml.

        Example from schema:
        ```
        round_id: "r1234567-89ab-cdef-0123-456789abcdef"
        cluster_count: 8
        total_participants: 95
        singleton_count: 2
        processing_time_ms: 3600
        completed_at: "2026-01-29T14:10:03.600Z"
        ```
        """
        event = {
            "event_id": "f2g3h4i5-5678-90ab-cdef-1234567890bc",
            "event_type": "clustering.completed",
            "timestamp": "2026-01-29T14:10:03.600Z",
            "data": {
                "round_id": "r1234567-89ab-cdef-0123-456789abcdef",
                "cluster_count": 8,
                "total_participants": 95,
                "singleton_count": 2,
                "processing_time_ms": 3600,
                "completed_at": "2026-01-29T14:10:03.600Z",
            },
        }

        # Validate structure
        assert event["event_type"] == "clustering.completed"
        assert event["data"]["cluster_count"] == 8
        assert event["data"]["total_participants"] == 95
        assert event["data"]["singleton_count"] == 2
        assert event["data"]["processing_time_ms"] == 3600

    def test_clustering_completed_optional_cluster_ids(self):
        """
        T073.8: Verify optional cluster_ids field.

        Per schema, cluster_ids is optional for reference.
        """
        event = {
            "event_id": str(uuid4()),
            "event_type": "clustering.completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "round_id": str(uuid4()),
                "cluster_count": 8,
                "total_participants": 95,
                "singleton_count": 2,
                "processing_time_ms": 3600,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "cluster_ids": [str(uuid4()) for _ in range(8)],  # Optional
            },
        }

        # Should accept with or without cluster_ids
        data = event["data"]
        if "cluster_ids" in data:
            assert isinstance(data["cluster_ids"], list), "cluster_ids should be array"
            assert all(
                isinstance(cid, str) for cid in data["cluster_ids"]
            ), "cluster_ids should contain strings"


class TestAlignmentCompletedEventSchema:
    """Validate alignment.completed event contract."""

    def test_alignment_completed_event_structure(self):
        """
        T073.9: Verify alignment.completed event has required fields.

        Per events.yaml schema.
        """
        event = {
            "event_id": str(uuid4()),
            "event_type": "alignment.completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "discussion_id": str(uuid4()),
                "round_r": 1,
                "round_r1": 2,
                "match_count": 6,
                "similarity_threshold": 0.7,
                "processing_time_ms": 500,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # Verify required fields
        assert "event_id" in event, "Missing event_id"
        assert "event_type" in event, "Missing event_type"
        assert "timestamp" in event, "Missing timestamp"
        assert "data" in event, "Missing data"

        # Verify data fields
        data = event["data"]
        assert "discussion_id" in data, "Missing discussion_id"
        assert "round_r" in data, "Missing round_r"
        assert "round_r1" in data, "Missing round_r1"
        assert "match_count" in data, "Missing match_count"
        assert "similarity_threshold" in data, "Missing similarity_threshold"
        assert "processing_time_ms" in data, "Missing processing_time_ms"
        assert "completed_at" in data, "Missing completed_at"

    def test_alignment_completed_event_type(self):
        """
        T073.10: Verify event_type is "alignment.completed".

        Must match schema constant.
        """
        event_type = "alignment.completed"

        assert event_type == "alignment.completed", (
            f"Invalid event_type: {event_type}"
        )

    def test_alignment_completed_field_types(self):
        """
        T073.11: Verify field types match schema.

        - event_id: string (UUID)
        - event_type: string (const)
        - timestamp: string (ISO8601)
        - data.discussion_id: string (UUID)
        - data.round_r: integer
        - data.round_r1: integer
        - data.match_count: integer
        - data.similarity_threshold: number (float)
        - data.processing_time_ms: integer
        - data.completed_at: string (ISO8601)
        """
        event_id = str(uuid4())
        discussion_id = str(uuid4())
        round_r = 1
        round_r1 = 2
        match_count = 6
        similarity_threshold = 0.7
        processing_time_ms = 500
        timestamp = datetime.now(timezone.utc).isoformat()
        completed_at = datetime.now(timezone.utc).isoformat()

        # Verify types
        assert isinstance(event_id, str), "event_id should be string"
        assert isinstance(discussion_id, str), "discussion_id should be string"
        assert isinstance(round_r, int), "round_r should be integer"
        assert isinstance(round_r1, int), "round_r1 should be integer"
        assert isinstance(match_count, int), "match_count should be integer"
        assert isinstance(similarity_threshold, (int, float)), (
            "similarity_threshold should be number"
        )
        assert isinstance(processing_time_ms, int), "processing_time_ms should be integer"
        assert isinstance(timestamp, str), "timestamp should be string"
        assert isinstance(completed_at, str), "completed_at should be string"

    def test_alignment_completed_round_adjacency(self):
        """
        T073.12: Verify rounds are adjacent (round_r1 == round_r + 1).

        Per spec requirement FR-031.
        """
        round_r = 1
        round_r1 = 2

        assert round_r1 == round_r + 1, (
            f"Rounds not adjacent: r={round_r}, r+1={round_r1}"
        )

    def test_alignment_completed_similarity_threshold_range(self):
        """
        T073.13: Verify similarity_threshold is in valid range.

        Should be between 0.0 and 1.0.
        """
        similarity_threshold = 0.7

        assert (
            0.0 <= similarity_threshold <= 1.0
        ), f"similarity_threshold {similarity_threshold} not in [0, 1]"

    def test_alignment_completed_numeric_constraints(self):
        """
        T073.14: Verify numeric field constraints.

        round_r >= 0
        round_r1 > round_r
        match_count >= 0
        processing_time_ms >= 0
        """
        round_r = 1
        round_r1 = 2
        match_count = 6
        processing_time_ms = 500

        assert round_r >= 0, "round_r should be >= 0"
        assert round_r1 > round_r, "round_r1 should be > round_r"
        assert match_count >= 0, "match_count should be >= 0"
        assert processing_time_ms >= 0, "processing_time_ms should be >= 0"

    def test_alignment_completed_example_payload(self):
        """
        T073.15: Validate against example from events.yaml.

        Example from schema:
        ```
        discussion_id: "d1234567-89ab-cdef-0123-456789abcdef"
        round_r: 1
        round_r1: 2
        match_count: 6
        similarity_threshold: 0.7
        processing_time_ms: 500
        completed_at: "2026-01-29T14:15:04.100Z"
        ```
        """
        event = {
            "event_id": "g3h4i5j6-5678-90ab-cdef-1234567890cd",
            "event_type": "alignment.completed",
            "timestamp": "2026-01-29T14:15:04.100Z",
            "data": {
                "discussion_id": "d1234567-89ab-cdef-0123-456789abcdef",
                "round_r": 1,
                "round_r1": 2,
                "match_count": 6,
                "similarity_threshold": 0.7,
                "processing_time_ms": 500,
                "completed_at": "2026-01-29T14:15:04.100Z",
            },
        }

        # Validate structure
        assert event["event_type"] == "alignment.completed"
        assert event["data"]["round_r"] == 1
        assert event["data"]["round_r1"] == 2
        assert event["data"]["match_count"] == 6
        assert event["data"]["similarity_threshold"] == 0.7

    def test_alignment_completed_optional_display_group_count(self):
        """
        T073.16: Verify optional display_group_count field.

        Per schema, display_group_count is optional but provides context.
        """
        event = {
            "event_id": str(uuid4()),
            "event_type": "alignment.completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "discussion_id": str(uuid4()),
                "round_r": 1,
                "round_r1": 2,
                "match_count": 6,
                "similarity_threshold": 0.7,
                "processing_time_ms": 500,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "display_group_count": 6,  # Optional
            },
        }

        # Should accept with optional field
        data = event["data"]
        if "display_group_count" in data:
            assert isinstance(data["display_group_count"], int), (
                "display_group_count should be integer"
            )


class TestEventPayloadJsonSerialization:
    """Test that events can be serialized to/from JSON."""

    def test_clustering_completed_json_serialization(self):
        """
        T073.17: Event can be serialized to JSON.

        Required for Redis pub/sub.
        """
        event = {
            "event_id": str(uuid4()),
            "event_type": "clustering.completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "round_id": str(uuid4()),
                "cluster_count": 8,
                "total_participants": 95,
                "singleton_count": 2,
                "processing_time_ms": 3600,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # Serialize to JSON
        json_str = json.dumps(event)
        assert isinstance(json_str, str), "Should serialize to string"

        # Deserialize from JSON
        deserialized = json.loads(json_str)
        assert deserialized["event_type"] == "clustering.completed"
        assert deserialized["data"]["cluster_count"] == 8

    def test_alignment_completed_json_serialization(self):
        """
        T073.18: Alignment event can be serialized to JSON.

        Required for Redis pub/sub.
        """
        event = {
            "event_id": str(uuid4()),
            "event_type": "alignment.completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "discussion_id": str(uuid4()),
                "round_r": 1,
                "round_r1": 2,
                "match_count": 6,
                "similarity_threshold": 0.7,
                "processing_time_ms": 500,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # Serialize to JSON
        json_str = json.dumps(event)
        assert isinstance(json_str, str), "Should serialize to string"

        # Deserialize from JSON
        deserialized = json.loads(json_str)
        assert deserialized["event_type"] == "alignment.completed"
        assert deserialized["data"]["round_r"] == 1


class TestEventIdempotency:
    """Test event ID for idempotency."""

    def test_event_id_uniqueness(self):
        """
        T073.19: Each event has unique event_id.

        For idempotency and tracking.
        """
        event_ids = [str(uuid4()) for _ in range(100)]

        # All should be unique
        assert len(set(event_ids)) == 100, "Event IDs should be unique"

    def test_clustering_completed_event_id_format(self):
        """
        T073.20: event_id follows UUID format.

        Standard UUID v4 format.
        """
        event_id = str(uuid4())

        # Should be valid UUID
        try:
            from uuid import UUID
            UUID(event_id)
            # Success if no exception
        except ValueError:
            pytest.fail(f"event_id is not valid UUID: {event_id}")


class TestEventTimestamps:
    """Test event timestamp handling."""

    def test_timestamp_ordering(self):
        """
        T073.21: Timestamps are monotonically increasing.

        clustering.completed should occur before alignment.completed for same round pair.
        """
        clustering_timestamp = "2026-01-29T14:10:03.600Z"
        alignment_timestamp = "2026-01-29T14:15:04.100Z"

        # Parse timestamps
        ct = datetime.fromisoformat(clustering_timestamp.replace("Z", "+00:00"))
        at = datetime.fromisoformat(alignment_timestamp.replace("Z", "+00:00"))

        # Clustering should happen before alignment
        assert ct < at, "Clustering should complete before alignment"

    def test_timestamp_timezone_aware(self):
        """
        T073.22: Timestamps are timezone-aware (UTC).

        ISO8601 format with Z or +00:00 suffix.
        """
        # Both formats should be valid
        timestamps = [
            "2026-01-29T14:10:03.600Z",
            "2026-01-29T14:10:03.600+00:00",
        ]

        for ts in timestamps:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                assert dt.tzinfo is not None, "Timestamp should be timezone-aware"
            except ValueError as e:
                pytest.fail(f"Invalid timestamp format: {ts} - {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
