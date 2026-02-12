#!/usr/bin/env python3
"""
Manual test for medoid determinism (T067).
Tests that medoid selection produces the same result across 10 runs.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
from uuid import UUID, uuid4

# Import medoid functions
try:
    from services.medoid_labeling import compute_medoid, deterministic_tiebreaker
except ImportError:
    print("✗ Failed to import medoid_labeling module")
    print("  Make sure you're in the backend directory")
    sys.exit(1)


def test_determinism_single_cluster_10_runs():
    """
    Test that medoid selection is deterministic across 10 runs.
    This validates SC-006 and T067.
    """
    print("\n" + "="*70)
    print("TEST 1: Single Cluster Determinism (10 runs)")
    print("="*70)

    cluster_id = uuid4()

    # Create fixed centroid
    np.random.seed(42)  # Fixed seed for reproducibility
    centroid = np.random.randn(384)
    centroid = centroid / np.linalg.norm(centroid)

    # Create 5 members with known embeddings
    member_ids = [uuid4() for _ in range(5)]
    members = []
    for mid in member_ids:
        vec = np.random.randn(384)
        vec = vec / np.linalg.norm(vec)
        members.append((mid, vec))

    print(f"Cluster: {cluster_id}")
    print(f"Members: {len(members)}")

    # Run medoid selection 10 times
    results = []
    for run in range(10):
        medoid_id = compute_medoid(cluster_id, centroid, members)
        results.append(medoid_id)
        if run == 0:
            print(f"Run {run+1}: Selected medoid {medoid_id}")

    # Assert all results are identical
    unique_results = set(results)

    if len(unique_results) == 1:
        print(f"\n✓ PASS: Medoid selection is deterministic")
        print(f"  All 10 runs selected: {results[0]}")
        return True
    else:
        print(f"\n✗ FAIL: Medoid selection is NOT deterministic")
        print(f"  Got {len(unique_results)} different results: {unique_results}")
        return False


def test_determinism_with_equidistant_members_10_runs():
    """
    Test determinism when tie-breaking is required (equidistant members).
    This validates FR-044 (deterministic tie-breaking).
    """
    print("\n" + "="*70)
    print("TEST 2: Tie-Breaking Determinism (10 runs with equidistant members)")
    print("="*70)

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

    print(f"Cluster: {cluster_id}")
    print(f"Members (all equidistant): {len(members)}")
    print(f"Member IDs:")
    for mid in member_ids:
        print(f"  - {mid}")

    # Run medoid selection 10 times
    results = []
    for run in range(10):
        medoid_id = compute_medoid(cluster_id, centroid, members)
        results.append(medoid_id)
        if run == 0:
            print(f"Run {run+1}: Selected medoid {medoid_id}")

    # Assert all results are identical
    unique_results = set(results)

    # Assert lexicographically first UUID was selected
    expected_id = UUID('aaaaaaaa-0000-0000-0000-000000000001')

    if len(unique_results) == 1 and results[0] == expected_id:
        print(f"\n✓ PASS: Tie-breaking is deterministic")
        print(f"  All 10 runs selected lexicographically first: {results[0]}")
        return True
    elif len(unique_results) == 1:
        print(f"\n✗ FAIL: Tie-breaking selected wrong UUID")
        print(f"  Expected: {expected_id}")
        print(f"  Got: {results[0]}")
        return False
    else:
        print(f"\n✗ FAIL: Tie-breaking is NOT deterministic")
        print(f"  Got {len(unique_results)} different results: {unique_results}")
        return False


def test_determinism_multiple_clusters_10_runs():
    """
    Test determinism for multiple clusters simultaneously.
    Ensures that label assignment produces identical results across multiple runs.
    """
    print("\n" + "="*70)
    print("TEST 3: Multiple Clusters Determinism (3 clusters, 10 runs)")
    print("="*70)

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
            'centroid': centroid,
            'members': members
        })

    print(f"Testing {len(clusters_data)} clusters with 4 members each")

    # Run label assignment 10 times
    all_results = []
    for run in range(10):
        labels = []
        for cluster_data in clusters_data:
            medoid_id = compute_medoid(
                cluster_id=cluster_data['cluster_id'],
                centroid_vector=cluster_data['centroid'],
                member_embeddings=cluster_data['members']
            )
            labels.append((cluster_data['cluster_id'], medoid_id))

        # Sort by cluster_id for consistent comparison
        labels_sorted = sorted(labels, key=lambda x: str(x[0]))
        all_results.append(labels_sorted)

        if run == 0:
            print(f"Run {run+1}: Selected {len(labels)} medoids")

    # Assert all runs produced identical results
    first_result = all_results[0]
    all_match = all(result == first_result for result in all_results[1:])

    if all_match:
        print(f"\n✓ PASS: Multiple cluster labeling is deterministic")
        print(f"  All 10 runs produced identical results for {len(clusters_data)} clusters")
        return True
    else:
        print(f"\n✗ FAIL: Multiple cluster labeling is NOT deterministic")
        for run_idx, result in enumerate(all_results):
            if result != first_result:
                print(f"  Run {run_idx+1} differs from Run 1")
        return False


def main():
    """Run all determinism tests."""
    print("\n" + "="*70)
    print("MEDOID DETERMINISM TESTS (T067)")
    print("Testing SC-006: Same cluster produces same medoid across multiple runs")
    print("="*70)

    results = []

    # Run all tests
    results.append(test_determinism_single_cluster_10_runs())
    results.append(test_determinism_with_equidistant_members_10_runs())
    results.append(test_determinism_multiple_clusters_10_runs())

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if all(results):
        print("\n✓ ALL TESTS PASSED - T067 COMPLETE")
        print("  Medoid selection is deterministic across all scenarios")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
