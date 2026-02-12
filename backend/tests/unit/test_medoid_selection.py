"""
Unit tests for medoid selection and determinism.

Tests:
- T067: Unit test for medoid determinism (run 10 times, assert same result)

Requirements:
- SC-006: Deterministic medoid selection across multiple runs
- FR-025: Same cluster produces same medoid
- FR-044: Deterministic tie-breaking with lexicographic order
"""

import pytest
import numpy as np
from uuid import UUID, uuid4

from src.services.medoid_labeling import (
    compute_medoid,
    deterministic_tiebreaker,
    assign_medoid_labels,
    validate_medoid_is_member,
    MedoidLabelingError
)


class TestComputeMedoid:
    """Tests for compute_medoid function."""

    def test_single_member_cluster(self):
        """Test medoid selection for singleton cluster."""
        cluster_id = uuid4()
        summary_id = uuid4()

        # Centroid and single member (same vector)
        centroid = np.random.randn(384)
        centroid = centroid / np.linalg.norm(centroid)

        members = [(summary_id, centroid)]

        medoid_id = compute_medoid(cluster_id, centroid, members)

        assert medoid_id == summary_id

    def test_multiple_members_distinct_distances(self):
        """Test medoid selection when distances are distinct."""
        cluster_id = uuid4()

        # Create centroid at origin
        centroid = np.zeros(384)
        centroid[0] = 1.0  # Unit vector along first dimension

        # Create three members at different distances
        # Member 1: Close to centroid (small angle)
        member1_id = uuid4()
        member1_vec = np.zeros(384)
        member1_vec[0] = 0.9
        member1_vec[1] = 0.1
        member1_vec = member1_vec / np.linalg.norm(member1_vec)

        # Member 2: Closest to centroid (smallest angle)
        member2_id = uuid4()
        member2_vec = np.zeros(384)
        member2_vec[0] = 0.99
        member2_vec[1] = 0.01
        member2_vec = member2_vec / np.linalg.norm(member2_vec)

        # Member 3: Far from centroid (larger angle)
        member3_id = uuid4()
        member3_vec = np.zeros(384)
        member3_vec[0] = 0.5
        member3_vec[1] = 0.5
        member3_vec = member3_vec / np.linalg.norm(member3_vec)

        members = [
            (member1_id, member1_vec),
            (member2_id, member2_vec),
            (member3_id, member3_vec)
        ]

        medoid_id = compute_medoid(cluster_id, centroid, members)

        # Member 2 should be selected (closest to centroid)
        assert medoid_id == member2_id

    def test_equidistant_members_tiebreaker(self):
        """Test deterministic tie-breaking when multiple members are equidistant."""
        cluster_id = uuid4()

        # Create centroid
        centroid = np.random.randn(384)
        centroid = centroid / np.linalg.norm(centroid)

        # Create three members with identical embeddings (equidistant from centroid)
        member_vec = np.random.randn(384)
        member_vec = member_vec / np.linalg.norm(member_vec)

        # Use UUIDs with predictable lexicographic order
        member_ids = [
            UUID('aaaaaaaa-0000-0000-0000-000000000001'),
            UUID('cccccccc-0000-0000-0000-000000000003'),
            UUID('bbbbbbbb-0000-0000-0000-000000000002')
        ]

        members = [(mid, member_vec.copy()) for mid in member_ids]

        medoid_id = compute_medoid(cluster_id, centroid, members)

        # Should select lexicographically first UUID
        expected_id = UUID('aaaaaaaa-0000-0000-0000-000000000001')
        assert medoid_id == expected_id

    def test_empty_members_raises_error(self):
        """Test that empty member list raises error."""
        cluster_id = uuid4()
        centroid = np.random.randn(384)

        with pytest.raises(MedoidLabelingError, match="no members provided"):
            compute_medoid(cluster_id, centroid, [])

    def test_invalid_centroid_raises_error(self):
        """Test that invalid centroid raises error."""
        cluster_id = uuid4()
        invalid_centroid = np.array([1, 2, 3])  # Wrong dimension

        members = [(uuid4(), np.random.randn(384))]

        with pytest.raises(MedoidLabelingError, match="Invalid centroid vector"):
            compute_medoid(cluster_id, invalid_centroid, members)


class TestDeterministicTiebreaker:
    """Tests for deterministic_tiebreaker function."""

    def test_single_candidate(self):
        """Test tie-breaker with single candidate."""
        candidate = uuid4()
        result = deterministic_tiebreaker([candidate])
        assert result == candidate

    def test_multiple_candidates_lexicographic_order(self):
        """Test tie-breaker selects lexicographically first UUID."""
        candidates = [
            UUID('ffffffff-0000-0000-0000-000000000001'),
            UUID('aaaaaaaa-0000-0000-0000-000000000001'),
            UUID('cccccccc-0000-0000-0000-000000000001')
        ]

        result = deterministic_tiebreaker(candidates)

        # Should select 'aaaaaaaa...' (lexicographically first)
        assert result == UUID('aaaaaaaa-0000-0000-0000-000000000001')

    def test_empty_candidates_raises_error(self):
        """Test that empty candidate list raises error."""
        with pytest.raises(MedoidLabelingError, match="no candidates provided"):
            deterministic_tiebreaker([])

    def test_determinism_multiple_calls(self):
        """Test that tie-breaker is deterministic across multiple calls."""
        candidates = [uuid4() for _ in range(10)]

        # Call tie-breaker multiple times
        results = [deterministic_tiebreaker(candidates.copy()) for _ in range(5)]

        # All results should be identical
        assert len(set(results)) == 1


class TestAssignMedoidLabels:
    """Tests for assign_medoid_labels function."""

    def test_single_cluster(self):
        """Test label assignment for single cluster."""
        cluster_id = uuid4()
        member1_id = uuid4()
        member2_id = uuid4()

        centroid = np.random.randn(384)
        centroid = centroid / np.linalg.norm(centroid)

        # Member 1 is closer to centroid
        member1_vec = centroid + np.random.randn(384) * 0.01
        member1_vec = member1_vec / np.linalg.norm(member1_vec)

        member2_vec = centroid + np.random.randn(384) * 0.1
        member2_vec = member2_vec / np.linalg.norm(member2_vec)

        clusters = [
            {
                'cluster_id': cluster_id,
                'centroid_vector': centroid,
                'members': [
                    (member1_id, member1_vec),
                    (member2_id, member2_vec)
                ]
            }
        ]

        labels = assign_medoid_labels(clusters)

        assert len(labels) == 1
        assert labels[0][0] == cluster_id
        # Member 1 should be selected (closer to centroid)
        assert labels[0][1] == member1_id

    def test_multiple_clusters(self):
        """Test label assignment for multiple clusters."""
        clusters = []
        expected_medoids = []

        for _ in range(3):
            cluster_id = uuid4()
            centroid = np.random.randn(384)
            centroid = centroid / np.linalg.norm(centroid)

            # First member is closest to centroid
            member_ids = [uuid4() for _ in range(3)]
            members = []

            for i, mid in enumerate(member_ids):
                # First member has smallest perturbation
                vec = centroid + np.random.randn(384) * (0.01 * (i + 1))
                vec = vec / np.linalg.norm(vec)
                members.append((mid, vec))

            clusters.append({
                'cluster_id': cluster_id,
                'centroid_vector': centroid,
                'members': members
            })

            expected_medoids.append((cluster_id, member_ids[0]))

        labels = assign_medoid_labels(clusters)

        assert len(labels) == 3
        # Check all expected medoids are assigned
        for cluster_id, medoid_id in expected_medoids:
            assert (cluster_id, medoid_id) in labels

    def test_empty_clusters_list(self):
        """Test that empty cluster list returns empty labels."""
        labels = assign_medoid_labels([])
        assert labels == []


class TestMedoidDeterminism:
    """
    T067: Test medoid selection determinism.

    Requirement: SC-006 - Same cluster produces same medoid across multiple runs
    """

    def test_determinism_single_cluster_10_runs(self):
        """
        Test that medoid selection is deterministic across 10 runs.

        This is the core test for SC-006: run medoid selection 10 times
        with the same input and assert the same result every time.
        """
        cluster_id = uuid4()

        # Create fixed centroid
        np.random.seed(42)  # Fixed seed for test reproducibility
        centroid = np.random.randn(384)
        centroid = centroid / np.linalg.norm(centroid)

        # Create 5 members with known embeddings
        member_ids = [uuid4() for _ in range(5)]
        members = []
        for mid in member_ids:
            vec = np.random.randn(384)
            vec = vec / np.linalg.norm(vec)
            members.append((mid, vec))

        # Run medoid selection 10 times
        results = []
        for run in range(10):
            medoid_id = compute_medoid(cluster_id, centroid, members)
            results.append(medoid_id)

        # Assert all results are identical
        unique_results = set(results)
        assert len(unique_results) == 1, (
            f"Medoid selection not deterministic: got {len(unique_results)} "
            f"different results across 10 runs: {unique_results}"
        )

        print(f"✓ SC-006 validated: Medoid selection is deterministic "
              f"(same result across 10 runs: {results[0]})")

    def test_determinism_with_equidistant_members_10_runs(self):
        """
        Test determinism when tie-breaking is required (equidistant members).

        This tests FR-044: deterministic tie-breaking with lexicographic order.
        """
        cluster_id = uuid4()

        # Create centroid
        np.random.seed(99)
        centroid = np.random.randn(384)
        centroid = centroid / np.linalg.norm(centroid)

        # Create 3 members with identical embeddings (equidistant)
        member_vec = np.random.randn(384)
        member_vec = member_vec / np.linalg.norm(member_vec)

        member_ids = [
            UUID('dddddddd-0000-0000-0000-000000000001'),
            UUID('aaaaaaaa-0000-0000-0000-000000000001'),
            UUID('cccccccc-0000-0000-0000-000000000001')
        ]

        members = [(mid, member_vec.copy()) for mid in member_ids]

        # Run medoid selection 10 times
        results = []
        for run in range(10):
            medoid_id = compute_medoid(cluster_id, centroid, members)
            results.append(medoid_id)

        # Assert all results are identical
        unique_results = set(results)
        assert len(unique_results) == 1, (
            f"Tie-breaking not deterministic: got {len(unique_results)} "
            f"different results across 10 runs: {unique_results}"
        )

        # Assert lexicographically first UUID was selected
        expected_id = UUID('aaaaaaaa-0000-0000-0000-000000000001')
        assert results[0] == expected_id, (
            f"Tie-breaking did not select lexicographically first UUID: "
            f"expected {expected_id}, got {results[0]}"
        )

        print(f"✓ FR-044 validated: Tie-breaking is deterministic "
              f"(lexicographic order: {results[0]})")

    def test_determinism_multiple_clusters_10_runs(self):
        """
        Test determinism for multiple clusters simultaneously.

        Ensures that assign_medoid_labels produces identical results
        across multiple runs for a set of clusters.
        """
        np.random.seed(123)

        # Create 3 clusters with fixed data
        clusters_data = []
        for i in range(3):
            cluster_id = uuid4()
            centroid = np.random.randn(384)
            centroid = centroid / np.linalg.norm(centroid)

            members = []
            for j in range(4):
                mid = uuid4()
                vec = np.random.randn(384)
                vec = vec / np.linalg.norm(vec)
                members.append((mid, vec))

            clusters_data.append({
                'cluster_id': cluster_id,
                'centroid_vector': centroid,
                'members': members
            })

        # Run label assignment 10 times
        all_results = []
        for run in range(10):
            labels = assign_medoid_labels(clusters_data)
            # Sort by cluster_id for consistent comparison
            labels_sorted = sorted(labels, key=lambda x: str(x[0]))
            all_results.append(labels_sorted)

        # Assert all runs produced identical results
        first_result = all_results[0]
        for run_idx, result in enumerate(all_results[1:], start=2):
            assert result == first_result, (
                f"Run {run_idx} produced different results:\n"
                f"Expected: {first_result}\n"
                f"Got: {result}"
            )

        print(f"✓ SC-006 validated: Multiple cluster labeling is deterministic "
              f"({len(clusters_data)} clusters, 10 runs)")


class TestValidateMedoidIsMember:
    """Tests for validate_medoid_is_member function."""

    def test_valid_medoid_is_member(self):
        """Test validation passes when medoid is a member."""
        cluster_id = uuid4()
        medoid_id = uuid4()
        member_ids = [uuid4(), medoid_id, uuid4()]

        result = validate_medoid_is_member(cluster_id, medoid_id, member_ids)
        assert result is True

    def test_invalid_medoid_not_member(self):
        """Test validation fails when medoid is not a member."""
        cluster_id = uuid4()
        medoid_id = uuid4()
        member_ids = [uuid4(), uuid4(), uuid4()]

        with pytest.raises(MedoidLabelingError, match="not a cluster member"):
            validate_medoid_is_member(cluster_id, medoid_id, member_ids)


if __name__ == "__main__":
    # Run determinism tests directly for quick validation
    print("Running medoid determinism tests (T067)...\n")

    test_suite = TestMedoidDeterminism()

    print("Test 1: Single cluster determinism (10 runs)")
    test_suite.test_determinism_single_cluster_10_runs()

    print("\nTest 2: Tie-breaking determinism (10 runs)")
    test_suite.test_determinism_with_equidistant_members_10_runs()

    print("\nTest 3: Multiple clusters determinism (10 runs)")
    test_suite.test_determinism_multiple_clusters_10_runs()

    print("\n✓ All determinism tests passed (T067 complete)")
