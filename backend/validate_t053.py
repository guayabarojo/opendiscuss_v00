#!/usr/bin/env python3
"""
Quick validation script for T053 implementation.

Validates the correction signal endpoint implementation without running full tests.
Checks:
1. Route exists and is properly registered
2. Request/response models are correct
3. Validation logic is in place
4. Service method exists
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def validate_imports():
    """Validate all required imports work."""
    print("Validating imports...")
    try:
        from summarization.api.correction_routes import router, CorrectionSignalRequest, CorrectionSignalResponse
        from summarization.models.correction_signal import CorrectionSignal, ReasonTag
        from summarization.services.summarization_service import SummarizationService
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def validate_route():
    """Validate the route is registered."""
    print("\nValidating route registration...")
    try:
        from summarization.api.correction_routes import router

        # Check route exists
        routes = [route for route in router.routes if hasattr(route, 'path')]
        correction_routes = [r for r in routes if '/correction' in r.path]

        if not correction_routes:
            print("✗ Correction route not found")
            return False

        route = correction_routes[0]
        print(f"✓ Route found: {route.path}")
        print(f"  Methods: {route.methods}")
        print(f"  Name: {route.name}")
        return True
    except Exception as e:
        print(f"✗ Route validation error: {e}")
        return False


def validate_request_model():
    """Validate request model has correct fields and validators."""
    print("\nValidating request model...")
    try:
        from summarization.api.correction_routes import CorrectionSignalRequest

        # Check fields
        fields = CorrectionSignalRequest.model_fields

        if 'reason_tag' not in fields:
            print("✗ reason_tag field missing")
            return False
        print("✓ reason_tag field exists")

        if 'feedback_text' not in fields:
            print("✗ feedback_text field missing")
            return False
        print("✓ feedback_text field exists")

        # Test validation
        try:
            # Should fail - invalid reason tag
            CorrectionSignalRequest(reason_tag="invalid_tag")
            print("✗ reason_tag validation not working")
            return False
        except Exception:
            print("✓ reason_tag validation works")

        try:
            # Should fail - feedback too long
            CorrectionSignalRequest(
                reason_tag="wrong_crux",
                feedback_text="a" * 241
            )
            print("✗ feedback_text length validation not working")
            return False
        except Exception:
            print("✓ feedback_text length validation works")

        # Should succeed
        valid_request = CorrectionSignalRequest(
            reason_tag="wrong_crux",
            feedback_text="Test feedback"
        )
        print("✓ Valid request accepted")

        return True
    except Exception as e:
        print(f"✗ Request model validation error: {e}")
        return False


def validate_reason_tags():
    """Validate all reason tags are defined."""
    print("\nValidating reason tags...")
    try:
        from summarization.models.correction_signal import ReasonTag

        expected_tags = [
            'WRONG_CRUX',
            'TOO_VAGUE',
            'MISREPRESENTS_ME',
            'MISSED_CONSTRAINT',
            'MISSED_SOLUTION',
            'OTHER'
        ]

        actual_tags = [tag.name for tag in ReasonTag]

        for tag in expected_tags:
            if tag in actual_tags:
                print(f"✓ {tag} defined")
            else:
                print(f"✗ {tag} missing")
                return False

        return True
    except Exception as e:
        print(f"✗ Reason tags validation error: {e}")
        return False


def validate_service_method():
    """Validate service method exists."""
    print("\nValidating service method...")
    try:
        from summarization.services.summarization_service import SummarizationService

        if not hasattr(SummarizationService, 'regenerate_with_correction'):
            print("✗ regenerate_with_correction method not found")
            return False

        print("✓ regenerate_with_correction method exists")

        # Check method signature
        import inspect
        sig = inspect.signature(SummarizationService.regenerate_with_correction)
        params = list(sig.parameters.keys())

        if 'previous_summary_id' in params:
            print("✓ previous_summary_id parameter exists")
        else:
            print("✗ previous_summary_id parameter missing")
            return False

        return True
    except Exception as e:
        print(f"✗ Service method validation error: {e}")
        return False


def validate_main_app_registration():
    """Validate route is registered in main app."""
    print("\nValidating main app registration...")
    try:
        from main import app
        from summarization.api import summary_router

        # Check if summary_router is in app routes
        router_found = False
        for route in app.routes:
            if hasattr(route, 'path') and '/summaries' in route.path:
                router_found = True
                break

        if router_found:
            print("✓ Summary router registered in main app")
            return True
        else:
            print("✗ Summary router not found in main app")
            return False
    except Exception as e:
        print(f"✗ Main app registration validation error: {e}")
        return False


def main():
    """Run all validations."""
    print("=" * 60)
    print("T053 Implementation Validation")
    print("=" * 60)

    validations = [
        ("Imports", validate_imports),
        ("Route", validate_route),
        ("Request Model", validate_request_model),
        ("Reason Tags", validate_reason_tags),
        ("Service Method", validate_service_method),
        ("Main App Registration", validate_main_app_registration),
    ]

    results = []
    for name, func in validations:
        try:
            result = func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Validation '{name}' failed with exception: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(result for _, result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL VALIDATIONS PASSED - T053 IMPLEMENTATION COMPLETE")
    else:
        print("✗ SOME VALIDATIONS FAILED - CHECK ERRORS ABOVE")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
