"""
Verification script for User Story 2 & 3 implementation.
Checks that all required functions and classes exist without running tests.
"""

import ast
import sys
from pathlib import Path


def check_file_functions(filepath: str, required_functions: list[str]) -> tuple[bool, list[str]]:
    """Check if a file contains all required functions (including async)."""
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())
        
        # Check both regular and async functions
        found_functions = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        
        missing = [func for func in required_functions if func not in found_functions]
        return len(missing) == 0, missing
    except Exception as e:
        return False, [f"Error: {e}"]


def check_file_classes(filepath: str, required_classes: list[str]) -> tuple[bool, list[str]]:
    """Check if a file contains all required classes."""
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())
        
        found_classes = {
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }
        
        missing = [cls for cls in required_classes if cls not in found_classes]
        return len(missing) == 0, missing
    except Exception as e:
        return False, [f"Error: {e}"]


def main():
    print("=" * 70)
    print("Verification: User Story 2 & 3 Implementation")
    print("=" * 70)
    print()
    
    all_passed = True
    
    # Check clustering_algorithms.py
    print("✓ Checking /backend/src/ml/clustering_algorithms.py")
    success, missing = check_file_classes(
        "src/ml/clustering_algorithms.py",
        ["ClusteringConfig"]
    )
    if success:
        print("  ✓ ClusteringConfig class exists (T038)")
    else:
        print(f"  ✗ Missing: {missing}")
        all_passed = False
    
    success, missing = check_file_functions(
        "src/ml/clustering_algorithms.py",
        ["create_clusterer", "cluster_embeddings", "cluster_with_hdbscan"]
    )
    if success:
        print("  ✓ All required functions exist")
    else:
        print(f"  ✗ Missing functions: {missing}")
        all_passed = False
    
    print()
    
    # Check clustering_service.py
    print("✓ Checking /backend/src/services/clustering_service.py")
    success, missing = check_file_functions(
        "src/services/clustering_service.py",
        [
            "validate_cluster_count",  # T039
            "validate_no_forced_merging",  # T040
            "validate_100_percent_coverage",  # T045
            "calculate_cluster_stats",  # T046 (async)
        ]
    )
    if success:
        print("  ✓ validate_cluster_count (T039)")
        print("  ✓ validate_no_forced_merging (T040)")
        print("  ✓ validate_100_percent_coverage (T045)")
        print("  ✓ calculate_cluster_stats (T046)")
    else:
        print(f"  ✗ Missing functions: {missing}")
        all_passed = False
    
    print()
    
    # Check outlier_handler.py
    print("✓ Checking /backend/src/services/outlier_handler.py")
    success, missing = check_file_functions(
        "src/services/outlier_handler.py",
        [
            "identify_outliers",  # T043
            "assign_singleton_cluster_ids",  # T044
            "convert_outliers_to_singletons",
            "calculate_singleton_metrics",  # T047
        ]
    )
    if success:
        print("  ✓ identify_outliers (T043)")
        print("  ✓ assign_singleton_cluster_ids (T044)")
        print("  ✓ calculate_singleton_metrics (T047)")
    else:
        print(f"  ✗ Missing functions: {missing}")
        all_passed = False
    
    print()
    
    # Check test files exist
    print("✓ Checking test files")
    test_files = [
        ("tests/integration/test_minority_preservation.py", "T042"),
        ("tests/integration/test_outlier_handling.py", "T048"),
    ]
    
    for test_file, task in test_files:
        if Path(test_file).exists():
            print(f"  ✓ {test_file} ({task})")
        else:
            print(f"  ✗ {test_file} ({task}) missing")
            all_passed = False
    
    print()
    print("=" * 70)
    
    if all_passed:
        print("✅ VERIFICATION PASSED")
        print()
        print("Implementation Summary:")
        print("  • User Story 2 (Minority Preservation): T038-T042 ✓")
        print("  • User Story 3 (Outlier Handling): T043-T048 ✓")
        print()
        print("All required functions, classes, and test files are present.")
        print()
        print("Next Steps:")
        print("  1. Install dependencies: poetry install")
        print("  2. Run minority tests: poetry run pytest tests/integration/test_minority_preservation.py -v")
        print("  3. Run outlier tests: poetry run pytest tests/integration/test_outlier_handling.py -v")
        return 0
    else:
        print("❌ VERIFICATION FAILED")
        print()
        print("Some required components are missing. Review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
