"""
Unit tests for Question Validation Pipeline (Spec 006 - Phase 4).

Tests all 5 validation checks independently and the complete validation pipeline.
Validates constitutional constraints enforcement (Principle VII: Representation Not Adjudication).

Tasks: T036, T037
"""

import pytest

from src.question_progression.validators import (
    QuestionValidator,
    ValidationResult,
    ValidationErrorCode,
    validate_question,
)


# ============================================================================
# Test Fixture: Validator Instance
# ============================================================================


@pytest.fixture
def validator() -> QuestionValidator:
    """Provide a QuestionValidator instance for tests."""
    return QuestionValidator()


# ============================================================================
# T036: Unit Tests for Individual Validation Checks
# ============================================================================


@pytest.mark.unit
class TestLengthValidation:
    """Test length_bounds check (10-200 characters)."""

    def test_valid_length_minimum(self, validator):
        """Test question with exactly 10 characters passes."""
        result = validator.validate("What is x?")
        # Should fail on other checks, but not length
        assert result.error_code != ValidationErrorCode.INVALID_LENGTH

    def test_valid_length_maximum(self, validator):
        """Test question with exactly 200 characters passes length check."""
        # Create a 200-char question starting with "What"
        question = "What " + "x" * 195
        result = validator.validate(question)
        # Should not fail on length
        assert result.error_code != ValidationErrorCode.INVALID_LENGTH

    def test_invalid_length_too_short(self, validator):
        """Test question with < 10 characters fails."""
        result = validator.validate("What?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_LENGTH
        assert "10-200 characters" in result.error_message

    def test_invalid_length_too_long(self, validator):
        """Test question with > 200 characters fails."""
        question = "What " + "x" * 196  # 201 characters total
        result = validator.validate(question)
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_LENGTH
        assert "10-200 characters" in result.error_message

    def test_empty_string(self, validator):
        """Test empty string fails length validation."""
        result = validator.validate("")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_LENGTH

    def test_whitespace_trimming(self, validator):
        """Test that whitespace is trimmed before length check."""
        # "What is x?" = 10 chars, with surrounding whitespace
        result = validator.validate("  What is x?  ")
        # Should not fail on length (trimmed to 10 chars)
        assert result.error_code != ValidationErrorCode.INVALID_LENGTH


@pytest.mark.unit
class TestOpeningWordValidation:
    """Test starts_with_what_how check."""

    def test_valid_opening_what(self, validator):
        """Test question starting with 'What' passes opening check."""
        result = validator.validate("What are your thoughts on this topic?")
        assert result.valid is True
        assert result.validated_text is not None

    def test_valid_opening_how(self, validator):
        """Test question starting with 'How' passes opening check."""
        result = validator.validate("How can we improve our community?")
        assert result.valid is True
        assert result.validated_text is not None

    def test_valid_opening_case_insensitive(self, validator):
        """Test opening word check is case-insensitive."""
        result1 = validator.validate("what are your thoughts on this topic?")
        assert result1.valid is True

        result2 = validator.validate("WHAT ARE YOUR THOUGHTS ON THIS TOPIC?")
        assert result2.valid is True

        result3 = validator.validate("how can we improve our community?")
        assert result3.valid is True

        result4 = validator.validate("HOW CAN WE IMPROVE OUR COMMUNITY?")
        assert result4.valid is True

    def test_invalid_opening_why(self, validator):
        """Test question starting with 'Why' fails (T030)."""
        result = validator.validate("Why is this important?")
        assert result.valid is False
        # Should fail on prohibited word check, not opening word check
        assert result.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD
        assert "why" in result.error_message.lower()

    def test_invalid_opening_who(self, validator):
        """Test question starting with 'Who' fails opening check."""
        result = validator.validate("Who is responsible for this?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_START
        assert "What" in result.error_message or "How" in result.error_message

    def test_invalid_opening_when(self, validator):
        """Test question starting with 'When' fails opening check."""
        result = validator.validate("When should we meet?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_START

    def test_invalid_opening_where(self, validator):
        """Test question starting with 'Where' fails opening check."""
        result = validator.validate("Where are the documents?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_START

    def test_invalid_opening_which(self, validator):
        """Test question starting with 'Which' fails opening check."""
        result = validator.validate("Which option is better?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_START

    def test_opening_word_requires_space(self, validator):
        """Test that opening word must be followed by space."""
        # "Whatsapp" starts with "What" but isn't a valid question
        result = validator.validate("Whatsapp is a messaging app?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_START


@pytest.mark.unit
class TestProhibitedWordValidation:
    """Test no_why_questions check (T030)."""

    def test_prohibited_why(self, validator):
        """Test question starting with 'Why' is prohibited."""
        result = validator.validate("Why is this important for our community?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD
        assert "why" in result.error_message.lower()

    def test_prohibited_do_you(self, validator):
        """Test question starting with 'Do you' is prohibited."""
        result = validator.validate("Do you agree with this proposal?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD
        assert "do you" in result.error_message.lower()

    def test_prohibited_should_we(self, validator):
        """Test question starting with 'Should we' is prohibited."""
        result = validator.validate("Should we implement this feature?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD
        assert "should we" in result.error_message.lower()

    def test_prohibited_would_you(self, validator):
        """Test question starting with 'Would you' is prohibited."""
        result = validator.validate("Would you support this initiative?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD
        assert "would you" in result.error_message.lower()

    def test_prohibited_would_we(self, validator):
        """Test question starting with 'Would we' is prohibited."""
        result = validator.validate("Would we benefit from this change?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD
        assert "would we" in result.error_message.lower()

    def test_prohibited_case_insensitive(self, validator):
        """Test prohibited words are case-insensitive."""
        result1 = validator.validate("WHY IS THIS IMPORTANT?")
        assert result1.valid is False
        assert result1.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD

        result2 = validator.validate("Do You agree with this?")
        assert result2.valid is False
        assert result2.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD


@pytest.mark.unit
class TestRankingKeywordValidation:
    """Test no_ranking check (T031, T037)."""

    @pytest.mark.parametrize("keyword", [
        "vote", "rank", "order", "best", "worst", "choose", "select",
        "pick", "prefer", "favorite", "top", "bottom", "first", "last",
        "winner", "loser", "better", "worse", "superior", "inferior"
    ])
    def test_ranking_keyword_rejected(self, validator, keyword):
        """Test all ranking keywords are rejected individually (T037)."""
        question = f"What is the {keyword} approach to this problem?"
        result = validator.validate(question)
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD
        assert keyword.lower() in result.error_message.lower()

    def test_ranking_keyword_case_insensitive(self, validator):
        """Test ranking keywords are case-insensitive."""
        result1 = validator.validate("What is the BEST approach?")
        assert result1.valid is False
        assert result1.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD

        result2 = validator.validate("What is the BeSt approach?")
        assert result2.valid is False
        assert result2.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD

    def test_ranking_keyword_in_middle(self, validator):
        """Test ranking keywords are caught anywhere in question."""
        # Keyword at end
        result1 = validator.validate("What approach is the best?")
        assert result1.valid is False
        assert result1.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD

        # Keyword in middle
        result2 = validator.validate("What best practices should we follow?")
        assert result2.valid is False
        assert result2.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD

    def test_valid_question_no_ranking(self, validator):
        """Test valid question without ranking keywords passes."""
        result = validator.validate("What are your thoughts on this topic?")
        assert result.valid is True
        assert result.error_code is None


@pytest.mark.unit
class TestBinaryChoiceValidation:
    """Test no_yes_no check (T032)."""

    def test_yes_or_no_pattern(self, validator):
        """Test 'yes or no' pattern is rejected."""
        result = validator.validate("What is your answer, yes or no?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.BINARY_CHOICE
        assert "binary choice" in result.error_message.lower()

    def test_agree_or_disagree_pattern(self, validator):
        """Test 'agree or disagree' pattern is rejected."""
        result = validator.validate("What do you think, agree or disagree?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.BINARY_CHOICE

    def test_true_or_false_pattern(self, validator):
        """Test 'true or false' pattern is rejected."""
        result = validator.validate("What is your stance, true or false?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.BINARY_CHOICE

    def test_binary_with_slash(self, validator):
        """Test binary choice with slash separator is rejected."""
        result = validator.validate("What is your position: yes/no?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.BINARY_CHOICE

    def test_binary_case_insensitive(self, validator):
        """Test binary choice detection is case-insensitive."""
        result1 = validator.validate("What do you think, YES OR NO?")
        assert result1.valid is False
        assert result1.error_code == ValidationErrorCode.BINARY_CHOICE

        result2 = validator.validate("What is your view, Agree OR Disagree?")
        assert result2.valid is False
        assert result2.error_code == ValidationErrorCode.BINARY_CHOICE

    def test_valid_question_with_yes_no_separately(self, validator):
        """Test question containing 'yes' or 'no' separately is valid."""
        # "yes" and "no" appear but not as binary choice pattern
        result = validator.validate("What can we say yes to and what should we avoid saying no to?")
        # This should pass binary choice check (but may fail ranking check due to "best")
        # For this test, we just verify it doesn't fail on BINARY_CHOICE
        if not result.valid:
            assert result.error_code != ValidationErrorCode.BINARY_CHOICE


# ============================================================================
# T036: Complete Validation Pipeline Tests
# ============================================================================


@pytest.mark.unit
class TestValidationPipeline:
    """Test complete validation pipeline with fail-fast behavior."""

    def test_valid_question_what(self, validator):
        """Test valid question starting with 'What' passes all checks."""
        result = validator.validate("What are your thoughts on this topic?")
        assert result.valid is True
        assert result.validated_text == "What are your thoughts on this topic?"
        assert result.error_code is None
        assert result.error_message is None

    def test_valid_question_how(self, validator):
        """Test valid question starting with 'How' passes all checks."""
        result = validator.validate("How can we improve our community engagement?")
        assert result.valid is True
        assert result.validated_text == "How can we improve our community engagement?"
        assert result.error_code is None
        assert result.error_message is None

    def test_fail_fast_length_before_opening(self, validator):
        """Test pipeline fails on length before checking opening word."""
        result = validator.validate("Why?")  # Too short AND starts with Why
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_LENGTH
        # Fails on length first, doesn't reach prohibited word check

    def test_fail_fast_opening_before_ranking(self, validator):
        """Test pipeline fails on opening word before checking ranking."""
        result = validator.validate("Which is the best option?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_START
        # Fails on opening word, doesn't reach ranking check

    def test_fail_fast_prohibited_before_ranking(self, validator):
        """Test pipeline fails on prohibited word before ranking."""
        result = validator.validate("Why is this the best approach?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_PROHIBITED_WORD
        # Fails on prohibited word, doesn't reach ranking check

    def test_fail_fast_ranking_before_binary(self, validator):
        """Test pipeline fails on ranking before binary choice."""
        result = validator.validate("What is the best answer, yes or no?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD
        # Fails on ranking, doesn't reach binary choice check

    def test_multiple_violations_returns_first(self, validator):
        """Test that multiple violations return the first error in pipeline."""
        # Too short (length) + starts with Why (prohibited) + contains best (ranking)
        result = validator.validate("Why best?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_LENGTH
        # Length is checked first

    def test_edge_case_exactly_10_chars(self, validator):
        """Test question with exactly 10 characters."""
        result = validator.validate("What is x?")
        assert result.error_code != ValidationErrorCode.INVALID_LENGTH
        # Length passes, but may fail on other checks

    def test_edge_case_exactly_200_chars(self, validator):
        """Test question with exactly 200 characters."""
        # Create exactly 200 char valid question
        question = "What are your detailed thoughts on " + ("community participation and engagement with local initiatives, including feedback mechanisms and transparent decision-making processes that ensure everyone has a voice" + "?")
        question = question[:200]  # Truncate to exactly 200
        if not question.endswith("?"):
            question = question[:199] + "?"

        result = validator.validate(question)
        # Should pass length check
        assert result.error_code != ValidationErrorCode.INVALID_LENGTH

    def test_whitespace_handling(self, validator):
        """Test that leading/trailing whitespace is properly trimmed."""
        result = validator.validate("  What are your thoughts?  ")
        assert result.valid is True
        assert result.validated_text == "What are your thoughts?"
        # No leading/trailing whitespace in validated text


@pytest.mark.unit
class TestConvenienceFunction:
    """Test validate_question convenience function."""

    def test_convenience_function_valid(self):
        """Test convenience function with valid question."""
        result = validate_question("What are your thoughts on this?")
        assert result.valid is True
        assert isinstance(result, ValidationResult)

    def test_convenience_function_invalid(self):
        """Test convenience function with invalid question."""
        result = validate_question("Why?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_LENGTH


@pytest.mark.unit
class TestValidationResultModel:
    """Test ValidationResult Pydantic model (T034)."""

    def test_validation_result_structure_valid(self):
        """Test ValidationResult structure for valid question."""
        result = ValidationResult(
            valid=True,
            validated_text="What are your thoughts?"
        )
        assert result.valid is True
        assert result.validated_text == "What are your thoughts?"
        assert result.error_code is None
        assert result.error_message is None

    def test_validation_result_structure_invalid(self):
        """Test ValidationResult structure for invalid question."""
        result = ValidationResult(
            valid=False,
            error_code=ValidationErrorCode.INVALID_START,
            error_message="Question must start with 'What' or 'How'"
        )
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.INVALID_START
        assert result.error_message is not None
        assert result.validated_text is None


@pytest.mark.unit
class TestValidationErrorCodes:
    """Test ValidationErrorCode enum (T034)."""

    def test_error_codes_exist(self):
        """Test all required error codes exist."""
        assert ValidationErrorCode.INVALID_LENGTH
        assert ValidationErrorCode.INVALID_START
        assert ValidationErrorCode.CONTAINS_PROHIBITED_WORD
        assert ValidationErrorCode.CONTAINS_RANKING_KEYWORD
        assert ValidationErrorCode.BINARY_CHOICE

    def test_error_code_values(self):
        """Test error code string values."""
        assert ValidationErrorCode.INVALID_LENGTH == "INVALID_LENGTH"
        assert ValidationErrorCode.INVALID_START == "INVALID_START"
        assert ValidationErrorCode.CONTAINS_PROHIBITED_WORD == "CONTAINS_PROHIBITED_WORD"
        assert ValidationErrorCode.CONTAINS_RANKING_KEYWORD == "CONTAINS_RANKING_KEYWORD"
        assert ValidationErrorCode.BINARY_CHOICE == "BINARY_CHOICE"


# ============================================================================
# T036: Edge Cases and Additional Tests
# ============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_question_with_newlines(self, validator):
        """Test question with embedded newlines."""
        result = validator.validate("What are\nyour thoughts?")
        # Should treat as regular text
        if result.valid:
            assert "\n" in result.validated_text or result.validated_text
        # Behavior depends on implementation

    def test_question_with_multiple_spaces(self, validator):
        """Test question with multiple consecutive spaces."""
        result = validator.validate("What  are  your  thoughts?")
        # Should pass validation
        assert result.valid is True

    def test_question_with_tabs(self, validator):
        """Test question with tab characters."""
        result = validator.validate("What\tare your thoughts?")
        # Should treat as whitespace
        if result.valid:
            assert result.validated_text is not None

    def test_question_with_unicode(self, validator):
        """Test question with unicode characters."""
        result = validator.validate("What are your thoughts on café culture?")
        assert result.valid is True

    def test_mixed_case_ranking_keywords(self, validator):
        """Test mixed case ranking keywords are caught."""
        result = validator.validate("What is the BeSt approach to this?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD

    def test_ranking_keyword_as_substring(self, validator):
        """Test ranking keyword as part of larger word."""
        # "best" is part of "best practices" - should still be caught
        result = validator.validate("What are the best practices?")
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD

    def test_valid_question_with_numbers(self, validator):
        """Test valid question containing numbers."""
        result = validator.validate("What are your top 3 priorities?")
        # "top" is a ranking keyword
        assert result.valid is False
        assert result.error_code == ValidationErrorCode.CONTAINS_RANKING_KEYWORD

    def test_valid_question_with_punctuation(self, validator):
        """Test valid question with various punctuation."""
        result = validator.validate("What are your thoughts on this, specifically?")
        assert result.valid is True

    def test_question_without_question_mark(self, validator):
        """Test that question mark is not required."""
        result = validator.validate("What are your thoughts on this topic")
        assert result.valid is True
        # Question mark not required by validation rules


@pytest.mark.unit
class TestValidationRulesSummary:
    """Test get_validation_rules_summary helper."""

    def test_rules_summary_exists(self):
        """Test that rules summary can be retrieved."""
        summary = QuestionValidator.get_validation_rules_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_rules_summary_content(self):
        """Test that rules summary contains key information."""
        summary = QuestionValidator.get_validation_rules_summary()
        assert "What" in summary or "How" in summary
        assert "10-200" in summary or "length" in summary.lower()
        assert "ranking" in summary.lower() or "vote" in summary.lower()


# ============================================================================
# T097: Performance Test - Validation Speed
# ============================================================================


@pytest.mark.unit
class TestValidationPerformance:
    """T097: Performance test for validation speed."""

    def test_validation_speed_performance(self, validator):
        """
        T097: Test question validation speed performance.

        Metric: < 10ms per question validation
        Test: Validate 1000 questions, measure total time
        Verify: Average < 10ms per validation
        """
        import time

        # Generate 1000 test questions
        test_questions = [
            f"What are your thoughts on topic number {i}?" for i in range(1000)
        ]

        # Measure validation time
        start_time = time.time()

        for question in test_questions:
            validator.validate(question)

        end_time = time.time()

        # Calculate metrics
        total_time_ms = (end_time - start_time) * 1000
        avg_time_per_validation_ms = total_time_ms / len(test_questions)

        print(f"\n" + "="*80)
        print(f"Validation Performance Test (T097)")
        print("="*80)
        print(f"  Total questions validated: {len(test_questions)}")
        print(f"  Total time: {total_time_ms:.2f}ms")
        print(f"  Average per validation: {avg_time_per_validation_ms:.4f}ms")
        print(f"  Validations per second: {len(test_questions) / (total_time_ms / 1000):.0f}")
        print("="*80)

        # Verify: Average < 10ms per validation
        assert avg_time_per_validation_ms < 10.0, (
            f"Average validation time {avg_time_per_validation_ms:.4f}ms exceeds 10ms threshold"
        )

        print(f"✓ Average validation time {avg_time_per_validation_ms:.4f}ms < 10ms threshold\n")

    def test_validation_speed_worst_case(self, validator):
        """
        Test validation speed for worst-case scenarios.

        Validates complex questions with all checks triggered.
        """
        import time

        # Worst-case questions that trigger all validation checks
        worst_case_questions = [
            "What are the best practices for improving team collaboration in remote environments?",  # Ranking keyword
            "What is your approach to handling disagreements, yes or no?",  # Binary choice
            "Why should we implement this strategy in our organization?",  # Prohibited word
            "x" * 201,  # Too long
            "What?",  # Too short
        ] * 200  # 1000 total validations

        # Measure validation time
        start_time = time.time()

        for question in worst_case_questions:
            validator.validate(question)

        end_time = time.time()

        # Calculate metrics
        total_time_ms = (end_time - start_time) * 1000
        avg_time_per_validation_ms = total_time_ms / len(worst_case_questions)

        print(f"\nWorst-case validation performance:")
        print(f"  Average per validation: {avg_time_per_validation_ms:.4f}ms")

        # Even worst-case should be fast (relaxed threshold)
        assert avg_time_per_validation_ms < 20.0, (
            f"Worst-case validation time {avg_time_per_validation_ms:.4f}ms exceeds 20ms threshold"
        )
