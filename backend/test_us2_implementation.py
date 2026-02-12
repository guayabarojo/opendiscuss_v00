#!/usr/bin/env python3
"""
Quick verification script for User Story 2 (T038-T042) implementation.

This script verifies:
- T038: min_cluster_size=2 validation exists
- T039: validate_cluster_count function exists and logs distribution
- T040: validate_no_forced_merging function exists
- T041: minority_cluster_count is included in event payload
- T042: Integration test exists

Does NOT require database or running services - just checks code structure.
"""

import sys
import os

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_t038_min_cluster_size_validation():
    """T038: Validate min_cluster_size=2 in clustering_algorithms.py"""
    print("\n[T038] Testing min_cluster_size validation...")

    try:
        from src.ml.clustering_algorithms import ClusteringConfig, create_clusterer

        # Check MIN_CLUSTER_SIZE is set to 2
        assert ClusteringConfig.MIN_CLUSTER_SIZE == 2, \
            f"Expected MIN_CLUSTER_SIZE=2, got {ClusteringConfig.MIN_CLUSTER_SIZE}"

        # Check validate_config exists and runs
        ClusteringConfig.validate_config()

        # Check create_clusterer validates min_cluster_size
        try:
            create_clusterer(min_cluster_size=3)
            assert False, "Should raise ValueError for min_cluster_size > 2"
        except ValueError as e:
            assert "FR-012" in str(e), f"Error should mention FR-012: {e}"

        print("   ✅ PASS: min_cluster_size=2 validation exists and enforces FR-012")
        return True

    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False


def test_t039_cluster_count_validation():
    """T039: Validate cluster count validation in clustering_service.py"""
    print("\n[T039] Testing cluster count validation...")

    try:
        from src.services.clustering_service import validate_cluster_count
        import numpy as np

        # Test with sample cluster labels
        cluster_labels = np.array([0, 0, 0, 1, 1, 2, -1, -1])

        result = validate_cluster_count(cluster_labels)

        # Check return structure
        assert 'n_clusters' in result, "Result should contain n_clusters"
        assert 'n_noise' in result, "Result should contain n_noise"
        assert 'cluster_sizes' in result, "Result should contain cluster_sizes"
        assert 'minority_cluster_count' in result, "Result should contain minority_cluster_count (T041)"

        # Check values
        assert result['n_clusters'] == 3, f"Expected 3 clusters, got {result['n_clusters']}"
        assert result['n_noise'] == 2, f"Expected 2 noise points, got {result['n_noise']}"

        print(f"   ✅ PASS: validate_cluster_count exists and returns minority_cluster_count")
        print(f"      Result: {result}")
        return True

    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_t040_no_forced_merging_validation():
    """T040: Validate no forced merging check in clustering_service.py"""
    print("\n[T040] Testing no forced merging validation...")

    try:
        from src.services.clustering_service import validate_no_forced_merging
        import numpy as np

        # Create test data: 2 distinct clusters
        cluster_stats = {
            0: (10, 0.67),  # 10 participants, 67%
            1: (5, 0.33)    # 5 participants, 33%
        }

        # Create orthogonal centroids (dissimilar)
        centroid_0 = np.zeros(384)
        centroid_0[0] = 1.0

        centroid_1 = np.zeros(384)
        centroid_1[1] = 1.0

        centroids = {
            0: centroid_0 / np.linalg.norm(centroid_0),
            1: centroid_1 / np.linalg.norm(centroid_1)
        }

        # This should NOT raise an error (clusters are distinct)
        validate_no_forced_merging(cluster_stats, centroids, similarity_threshold=0.7)

        print("   ✅ PASS: validate_no_forced_merging exists and checks FR-013")
        return True

    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_t041_minority_cluster_count_in_event():
    """T041: Check minority_cluster_count is added to event payload"""
    print("\n[T041] Testing minority_cluster_count in event payload...")

    try:
        import inspect
        from src.services.event_service import ClusteringEventService

        # Check publish_clustering_completed signature
        sig = inspect.signature(ClusteringEventService.publish_clustering_completed)
        params = list(sig.parameters.keys())

        assert 'minority_cluster_count' in params, \
            f"publish_clustering_completed should have minority_cluster_count parameter. Got: {params}"

        # Check it's optional (has default value)
        param = sig.parameters['minority_cluster_count']
        assert param.default is not inspect.Parameter.empty, \
            "minority_cluster_count should be optional"

        print("   ✅ PASS: minority_cluster_count parameter added to publish_clustering_completed")
        return True

    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_t042_integration_test_exists():
    """T042: Check integration test file exists"""
    print("\n[T042] Testing integration test file exists...")

    try:
        test_file = os.path.join(
            os.path.dirname(__file__),
            'tests', 'integration', 'test_minority_preservation.py'
        )

        assert os.path.exists(test_file), f"Test file not found: {test_file}"

        # Check test file has required test functions
        with open(test_file, 'r') as f:
            content = f.read()

        assert 'test_minority_preservation_18_plus_2' in content, \
            "Test should contain test_minority_preservation_18_plus_2"
        assert 'majority_count = 18' in content, "Test should use 18 majority participants"
        assert 'minority_count = 2' in content, "Test should use 2 minority participants"

        print(f"   ✅ PASS: Integration test exists at {test_file}")
        return True

    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False


def main():
    """Run all User Story 2 verification tests"""
    print("=" * 70)
    print("User Story 2 (T038-T042) Implementation Verification")
    print("Minority Cluster Preservation")
    print("=" * 70)

    tests = [
        ("T038", test_t038_min_cluster_size_validation),
        ("T039", test_t039_cluster_count_validation),
        ("T040", test_t040_no_forced_merging_validation),
        ("T041", test_t041_minority_cluster_count_in_event),
        ("T042", test_t042_integration_test_exists),
    ]

    results = {}
    for task_id, test_func in tests:
        try:
            results[task_id] = test_func()
        except Exception as e:
            print(f"\n[{task_id}] ❌ UNEXPECTED ERROR: {e}")
            import traceback
            traceback.print_exc()
            results[task_id] = False

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for task_id, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{task_id}: {status}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    print("\n" + "=" * 70)
    print(f"TOTAL: {passed}/{total} tasks verified")

    if passed == total:
        print("✅ All User Story 2 tasks (T038-T042) are implemented!")
        return 0
    else:
        print(f"❌ {total - passed} task(s) need attention")
        return 1


if __name__ == "__main__":
    sys.exit(main())
