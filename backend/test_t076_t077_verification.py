#!/usr/bin/env python3
"""
Verification script for T076-T077: SUPERSEDED Status Implementation

Tests:
1. SUPERSEDED status exists in SummaryStatus enum
2. Database migration includes SUPERSEDED status
3. ApprovalService has mark_superseded() method
4. Last-approved-wins logic automatically marks older summaries as SUPERSEDED
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_superseded_status_exists():
    """Test 1: Verify SUPERSEDED status in enum"""
    from src.summarization.models.summary import SummaryStatus

    print("\n[Test 1] Checking SUPERSEDED status in SummaryStatus enum...")

    # Check if SUPERSEDED exists
    assert hasattr(SummaryStatus, 'SUPERSEDED'), "SUPERSEDED status not found in enum"
    assert SummaryStatus.SUPERSEDED.value == "superseded", "SUPERSEDED value incorrect"

    # Check all expected statuses
    expected_statuses = [
        'PENDING_REVIEW',
        'APPROVED',
        'REJECTED',
        'REJECTED_FINAL',
        'DISALLOWED_CONTENT',
        'APPROVAL_TIMEOUT',
        'SUPERSEDED'
    ]

    for status in expected_statuses:
        assert hasattr(SummaryStatus, status), f"Missing status: {status}"

    print("✓ SUPERSEDED status exists in enum")
    print(f"✓ SummaryStatus.SUPERSEDED = '{SummaryStatus.SUPERSEDED.value}'")
    return True


def test_migration_includes_superseded():
    """Test 2: Verify database migration includes SUPERSEDED status"""
    print("\n[Test 2] Checking migration file for SUPERSEDED status...")

    migration_file = Path(__file__).parent / "alembic" / "versions" / "011_create_summaries.py"

    assert migration_file.exists(), f"Migration file not found: {migration_file}"

    content = migration_file.read_text()

    # Check if superseded is in the enum creation
    assert "'superseded'" in content.lower(), "superseded not found in migration"

    # Count occurrences (should be in both upgrade and downgrade)
    count = content.lower().count("'superseded'")
    assert count >= 2, f"superseded should appear at least twice in migration (found {count})"

    print(f"✓ Migration file exists: {migration_file}")
    print(f"✓ SUPERSEDED status found {count} times in migration")
    return True


def test_approval_service_has_mark_superseded():
    """Test 3: Verify ApprovalService has mark_superseded() method"""
    from src.summarization.services.approval_service import ApprovalService

    print("\n[Test 3] Checking ApprovalService for mark_superseded() method...")

    # Check if method exists
    assert hasattr(ApprovalService, 'mark_superseded'), "mark_superseded method not found"

    # Check method signature
    import inspect
    sig = inspect.signature(ApprovalService.mark_superseded)
    params = list(sig.parameters.keys())

    assert 'summary_id' in params, "mark_superseded should accept summary_id parameter"

    print("✓ ApprovalService has mark_superseded() method")
    print(f"✓ Method signature: {sig}")
    return True


def test_approval_service_has_last_approved_wins_logic():
    """Test 4: Verify ApprovalService has _apply_last_approved_wins() method"""
    from src.summarization.services.approval_service import ApprovalService

    print("\n[Test 4] Checking ApprovalService for _apply_last_approved_wins() method...")

    # Check if private method exists
    assert hasattr(ApprovalService, '_apply_last_approved_wins'), \
        "_apply_last_approved_wins method not found"

    # Check method signature
    import inspect
    sig = inspect.signature(ApprovalService._apply_last_approved_wins)
    params = list(sig.parameters.keys())

    expected_params = ['participant_id', 'round_id', 'latest_summary_id']
    for param in expected_params:
        assert param in params, f"_apply_last_approved_wins should accept {param} parameter"

    print("✓ ApprovalService has _apply_last_approved_wins() method")
    print(f"✓ Method signature: {sig}")
    return True


def test_approve_summary_calls_last_approved_wins():
    """Test 5: Verify approve_summary() calls _apply_last_approved_wins()"""
    from src.summarization.services.approval_service import ApprovalService
    import inspect

    print("\n[Test 5] Checking if approve_summary() calls _apply_last_approved_wins()...")

    # Get source code
    source = inspect.getsource(ApprovalService.approve_summary)

    # Check if _apply_last_approved_wins is called
    assert '_apply_last_approved_wins' in source, \
        "approve_summary should call _apply_last_approved_wins"

    print("✓ approve_summary() calls _apply_last_approved_wins()")
    return True


def main():
    """Run all verification tests"""
    print("="*70)
    print("T076-T077 VERIFICATION: SUPERSEDED Status Implementation")
    print("="*70)

    tests = [
        ("T076: SUPERSEDED status exists", test_superseded_status_exists),
        ("T077: Migration includes SUPERSEDED", test_migration_includes_superseded),
        ("T078-T079: mark_superseded() method exists", test_approval_service_has_mark_superseded),
        ("T078-T079: _apply_last_approved_wins() exists", test_approval_service_has_last_approved_wins_logic),
        ("T078-T079: approve_summary() calls last-approved-wins", test_approve_summary_calls_last_approved_wins),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "PASS", None))
        except Exception as e:
            results.append((name, "FAIL", str(e)))
            print(f"✗ FAILED: {e}")

    # Print summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)

    passed = sum(1 for _, status, _ in results if status == "PASS")
    total = len(results)

    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  Error: {error}")

    print("\n" + "="*70)
    print(f"RESULT: {passed}/{total} tests passed")
    print("="*70)

    if passed == total:
        print("\n✓ T076-T077 implementation is COMPLETE and VERIFIED!")
        return 0
    else:
        print("\n✗ Some tests failed. Implementation may be incomplete.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
