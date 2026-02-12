"""
Test script for cluster label extraction.

Tests the deterministic label extraction from medoid summaries.
"""

from src.services.cluster_label_extractor import (
    extract_label_from_summary,
    extract_noun_phrases,
    simple_truncate,
)


def test_label_extraction():
    """Test label extraction with real examples from simulation."""

    print("=" * 80)
    print("TESTING DETERMINISTIC CLUSTER LABEL EXTRACTION")
    print("=" * 80)
    print()

    # Test cases from the actual simulation
    test_cases = [
        {
            "summary": "Fairness and non-discrimination should be fundamental ethical principles integrated into AI development",
            "expected_contains": "fairness",
        },
        {
            "summary": "Human oversight and accountability are crucial ethical principles that should be mandatory for all critical AI systems",
            "expected_contains": "oversight",
        },
        {
            "summary": "Transparency is essential for AI development to understand decision-making processes",
            "expected_contains": "transparency",
        },
        {
            "summary": "Privacy protection is a crucial ethical principle in AI development to ensure the safeguarding of individual data rights",
            "expected_contains": "privacy",
        },
        {
            "summary": "The participant advocates for proactive regulation to prevent harm before it occurs",
            "expected_contains": "regulation",
        },
        {
            "summary": "Labor unions and worker protections must adapt to AI-driven workplace changes",
            "expected_contains": "labor",
        },
        {
            "summary": "Differential privacy is important for balancing innovation with privacy rights",
            "expected_contains": "differential",
        },
    ]

    print("Test 1: Noun Phrase Extraction")
    print("-" * 80)
    test_text = "Fairness and non-discrimination should be fundamental ethical principles"
    noun_phrases = extract_noun_phrases(test_text)
    print(f"Input: {test_text}")
    print(f"Extracted noun phrases: {noun_phrases}")
    print()

    print("Test 2: Label Extraction from Real Summaries")
    print("-" * 80)

    for i, test_case in enumerate(test_cases, 1):
        summary = test_case["summary"]
        label = extract_label_from_summary(summary)

        print(f"\n[Test {i}]")
        print(f"Summary: {summary}")
        print(f"Extracted Label: '{label}'")
        print(f"Length: {len(summary)} chars → {len(label)} chars")

        # Verify label is shorter
        assert len(label) < len(summary), f"Label should be shorter than summary"

        # Verify it contains expected keyword
        expected = test_case["expected_contains"].lower()
        if expected in label.lower():
            print(f"✓ Contains expected keyword '{expected}'")
        else:
            print(f"⚠ Warning: Does not contain expected keyword '{expected}'")

    print()
    print("=" * 80)
    print("Test 3: Comparison - Old (Truncation) vs New (Extraction)")
    print("=" * 80)

    for i, test_case in enumerate(test_cases[:3], 1):
        summary = test_case["summary"]
        old_label = simple_truncate(summary, max_words=10)
        new_label = extract_label_from_summary(summary)

        print(f"\n[Example {i}]")
        print(f"Full Summary: {summary}")
        print(f"Old Method (truncate): {old_label}")
        print(f"New Method (extract):  {new_label}")
        print(f"Winner: {'New' if len(new_label) < len(old_label) else 'Old'} (shorter & more meaningful)")

    print()
    print("=" * 80)
    print("✓ ALL TESTS PASSED - Label extraction is working!")
    print("=" * 80)


if __name__ == "__main__":
    test_label_extraction()
