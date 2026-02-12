#!/usr/bin/env python3
"""
Simple verification script for User Story 2 (T038-T042) implementation.

This script verifies code exists without importing modules that need dependencies.
"""

import os
import re


def check_file_contains(filepath, patterns, task_name):
    """Check if file contains all required patterns."""
    print(f"\n[{task_name}] Checking {os.path.basename(filepath)}...")

    if not os.path.exists(filepath):
        print(f"   ❌ FAIL: File not found: {filepath}")
        return False

    with open(filepath, 'r') as f:
        content = f.read()

    all_found = True
    for pattern_name, pattern in patterns.items():
        if re.search(pattern, content, re.MULTILINE | re.DOTALL):
            print(f"   ✅ Found: {pattern_name}")
        else:
            print(f"   ❌ Missing: {pattern_name}")
            all_found = False

    return all_found


def test_t038():
    """T038: Validate min_cluster_size=2 in clustering_algorithms.py"""
    filepath = "src/ml/clustering_algorithms.py"

    patterns = {
        "MIN_CLUSTER_SIZE = 2": r"MIN_CLUSTER_SIZE\s*=\s*2",
        "validate_config method": r"def\s+validate_config",
        "FR-012 validation": r"FR-012.*min_cluster_size",
        "ValueError for min_cluster_size > 2": r"if\s+min_cluster_size\s*>\s*2.*raise\s+ValueError",
    }

    return check_file_contains(filepath, patterns, "T038")


def test_t039():
    """T039: Validate cluster count validation in clustering_service.py"""
    filepath = "src/services/clustering_service.py"

    patterns = {
        "validate_cluster_count function": r"def\s+validate_cluster_count",
        "FR-009 comment": r"FR-009.*variable cluster count",
        "minority_cluster_count calculation": r"minority_cluster_count\s*=",
        "minority_cluster_count in return": r"['\"]minority_cluster_count['\"]:\s*minority_cluster_count",
        "log cluster distribution": r"logger\.info.*cluster.*distribution",
    }

    return check_file_contains(filepath, patterns, "T039")


def test_t040():
    """T040: Validate no forced merging in clustering_service.py"""
    filepath = "src/services/clustering_service.py"

    patterns = {
        "validate_no_forced_merging function": r"def\s+validate_no_forced_merging",
        "FR-013 comment": r"FR-013.*forced merging",
        "similarity_threshold parameter": r"similarity_threshold.*float.*=.*0\.7",
        "cosine similarity check": r"cosine",
    }

    return check_file_contains(filepath, patterns, "T040")


def test_t041():
    """T041: minority_cluster_count in event payload"""
    filepath = "src/services/event_service.py"

    patterns = {
        "minority_cluster_count parameter": r"minority_cluster_count.*Optional\[int\]",
        "T041 in docstring": r"T041.*minority_cluster_count",
        "minority_cluster_count validation": r"if\s+minority_cluster_count.*<\s*0",
        "minority_cluster_count in payload": r"payload\[['\"]minority_cluster_count['\"]",
    }

    result = check_file_contains(filepath, patterns, "T041")

    # Also check clustering.py routes
    route_filepath = "src/api/routes/clustering.py"
    route_patterns = {
        "Calculate minority_cluster_count": r"minority_cluster_count\s*=\s*sum",
        "Pass to event publisher": r"minority_cluster_count=minority_cluster_count",
        "T041 comment": r"T041",
    }

    print(f"\n   Also checking {os.path.basename(route_filepath)}...")
    route_result = check_file_contains(route_filepath, route_patterns, "T041 (routes)")

    return result and route_result


def test_t042():
    """T042: Integration test exists"""
    filepath = "tests/integration/test_minority_preservation.py"

    patterns = {
        "test_minority_preservation_18_plus_2": r"def\s+test_minority_preservation_18_plus_2",
        "majority_count = 18": r"majority_count\s*=\s*18",
        "minority_count = 2": r"minority_count\s*=\s*2",
        "FR-012 assertion": r"FR-012",
        "FR-013 check": r"validate_no_forced_merging",
    }

    return check_file_contains(filepath, patterns, "T042")


def main():
    """Run all verification checks"""
    print("=" * 70)
    print("User Story 2 (T038-T042) Code Verification")
    print("Minority Cluster Preservation")
    print("=" * 70)

    # Change to backend directory
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)

    tests = [
        ("T038", test_t038),
        ("T039", test_t039),
        ("T040", test_t040),
        ("T041", test_t041),
        ("T042", test_t042),
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
    print(f"TOTAL: {passed}/{total} tasks implemented")

    if passed == total:
        print("✅ All User Story 2 tasks (T038-T042) are implemented!")
        return 0
    else:
        print(f"⚠️  {total - passed} task(s) may need attention")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
