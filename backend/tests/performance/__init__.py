"""
Performance benchmarks for OpenDiscuss Discussion Protocol.

This package contains performance tests validating constitutional requirements:
- SC-004: Sankey construction <2s per round
- SC-004: 100 concurrent submissions with zero failures
- SC-006: Total discussion time <60 minutes
- SC-007: Round completion time <10 minutes
- SC-008: Timing precision ±100ms (99th percentile)

These tests use pytest with @pytest.mark.performance and @pytest.mark.benchmark markers.
"""
