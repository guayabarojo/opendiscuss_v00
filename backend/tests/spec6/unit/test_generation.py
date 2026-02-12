"""
Unit tests for QuestionGenerationService error handling (Phase 9).

Tests LLM error scenarios:
- TimeoutError with exponential backoff
- RateLimitError with retry
- ServiceUnavailableError with fallback
- AuthenticationError (no retry)
- Validation failures with regeneration
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from anthropic import (
    APITimeoutError,
    RateLimitError,
    APIStatusError,
    AuthenticationError,
    APIError
)

from src.question_progression.services.generation import (
    QuestionGenerationService,
    QuestionGenerationError,
    QuestionValidationExhausted
)


@pytest.fixture
def generation_service():
    """Create QuestionGenerationService with mock API key."""
    return QuestionGenerationService(
        api_key="test-api-key",
        model="claude-3-5-sonnet-20241022",
        timeout=30,
        max_retries=3
    )


@pytest.fixture
def mock_valid_response():
    """Mock valid Claude API response."""
    mock_response = Mock()
    mock_response.content = [Mock(text="What are the main challenges?")]
    mock_response.usage = Mock(input_tokens=500, output_tokens=50)
    return mock_response


@pytest.fixture
def mock_invalid_response():
    """Mock invalid Claude API response (fails validation)."""
    mock_response = Mock()
    mock_response.content = [Mock(text="Why is this important?")]  # Invalid: starts with "Why"
    mock_response.usage = Mock(input_tokens=500, output_tokens=30)
    return mock_response


@pytest.mark.asyncio
async def test_timeout_error_retry_then_success(generation_service, mock_valid_response):
    """
    Test TimeoutError → retry with backoff → eventual success.

    Scenario:
    - First call: TimeoutError
    - Second call: Success
    Expected: Successful generation with retry_count=1
    """
    sankey_data = {
        "nodes": [{"label_summary": "Test", "member_count": 10, "member_pct": 0.5}],
        "flows": [],
        "total_participants": 20
    }

    with patch.object(generation_service.client.messages, 'create', new_callable=AsyncMock) as mock_create:
        # First call times out, second succeeds
        mock_create.side_effect = [
            APITimeoutError("Request timed out"),
            mock_valid_response
        ]

        result = await generation_service.generate_from_sankey(
            round_num=2,
            previous_questions=["What are the key priorities?"],
            sankey_data=sankey_data,
            input_round_id=uuid4()
        )

    # Verify successful generation
    assert result["question_text"] == "What are the main challenges?"
    assert result["provenance"]["retry_count"] == 1
    assert result["provenance"]["validation_attempts"] == 1

    # Verify exponential backoff was applied (2 calls total)
    assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_rate_limit_error_exponential_backoff(generation_service, mock_valid_response):
    """
    Test RateLimitError → exponential backoff → success on retry 2.

    Scenario:
    - First call: RateLimitError (429)
    - Second call: RateLimitError (429)
    - Third call: Success
    Expected: Successful generation with retry_count=2
    """
    sankey_data = {
        "nodes": [{"label_summary": "Test", "member_count": 10, "member_pct": 0.5}],
        "flows": [],
        "total_participants": 20
    }

    with patch.object(generation_service.client.messages, 'create', new_callable=AsyncMock) as mock_create:
        # First two calls rate limited, third succeeds
        mock_create.side_effect = [
            RateLimitError("Rate limit exceeded", response=Mock(status_code=429), body={}),
            RateLimitError("Rate limit exceeded", response=Mock(status_code=429), body={}),
            mock_valid_response
        ]

        result = await generation_service.generate_from_sankey(
            round_num=2,
            previous_questions=["What are the key priorities?"],
            sankey_data=sankey_data,
            input_round_id=uuid4()
        )

    # Verify successful generation after retries
    assert result["question_text"] == "What are the main challenges?"
    assert result["provenance"]["retry_count"] == 2

    # Verify 3 calls were made
    assert mock_create.call_count == 3


@pytest.mark.asyncio
async def test_service_unavailable_3_retries_then_fallback(generation_service):
    """
    Test ServiceUnavailableError → 3 retries → fallback to QUESTION_GENERATION_FAILED.

    Scenario:
    - All 3 calls: APIStatusError (503)
    Expected: QuestionGenerationError raised after 3 retries
    """
    sankey_data = {
        "nodes": [{"label_summary": "Test", "member_count": 10, "member_pct": 0.5}],
        "flows": [],
        "total_participants": 20
    }

    with patch.object(generation_service.client.messages, 'create', new_callable=AsyncMock) as mock_create:
        # All calls return 503
        mock_create.side_effect = [
            APIStatusError("Service unavailable", response=Mock(status_code=503), body={}),
            APIStatusError("Service unavailable", response=Mock(status_code=503), body={}),
            APIStatusError("Service unavailable", response=Mock(status_code=503), body={})
        ]

        with pytest.raises(QuestionGenerationError) as exc_info:
            await generation_service.generate_from_sankey(
                round_num=2,
                previous_questions=["What are the key priorities?"],
                sankey_data=sankey_data,
                input_round_id=uuid4()
            )

        # Verify error message mentions retries
        assert "failed after 3 retries" in str(exc_info.value).lower()

        # Verify 3 retries were attempted (3 calls per validation attempt)
        assert mock_create.call_count == 3


@pytest.mark.asyncio
async def test_authentication_error_immediate_failure(generation_service):
    """
    Test AuthenticationError → immediate failure (no retry).

    Scenario:
    - First call: AuthenticationError
    Expected: QuestionGenerationError raised immediately, no retries
    """
    sankey_data = {
        "nodes": [{"label_summary": "Test", "member_count": 10, "member_pct": 0.5}],
        "flows": [],
        "total_participants": 20
    }

    with patch.object(generation_service.client.messages, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = AuthenticationError("Invalid API key", response=Mock(status_code=401), body={})

        with pytest.raises(QuestionGenerationError) as exc_info:
            await generation_service.generate_from_sankey(
                round_num=2,
                previous_questions=["What are the key priorities?"],
                sankey_data=sankey_data,
                input_round_id=uuid4()
            )

        # Verify error message mentions authentication
        assert "authentication" in str(exc_info.value).lower()

        # Verify no retries (only 1 call)
        assert mock_create.call_count == 1


@pytest.mark.asyncio
async def test_validation_failure_then_success(generation_service, mock_invalid_response, mock_valid_response):
    """
    Test validation fails → regenerate with stricter prompt → success.

    Scenario:
    - First call: Invalid question (starts with "Why")
    - Second call: Valid question
    Expected: Successful generation with validation_attempts=2
    """
    sankey_data = {
        "nodes": [{"label_summary": "Test", "member_count": 10, "member_pct": 0.5}],
        "flows": [],
        "total_participants": 20
    }

    with patch.object(generation_service.client.messages, 'create', new_callable=AsyncMock) as mock_create:
        # First response invalid, second valid
        mock_create.side_effect = [mock_invalid_response, mock_valid_response]

        result = await generation_service.generate_from_sankey(
            round_num=2,
            previous_questions=["What are the key priorities?"],
            sankey_data=sankey_data,
            input_round_id=uuid4()
        )

    # Verify successful generation
    assert result["question_text"] == "What are the main challenges?"
    assert result["provenance"]["validation_attempts"] == 2
    assert result["provenance"]["retry_count"] == 0  # No API retries, only validation retries

    # Verify 2 calls were made (1 invalid, 1 valid)
    assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_all_retries_exhausted_validation_failure(generation_service, mock_invalid_response):
    """
    Test all retries exhausted due to validation failures.

    Scenario:
    - All 3 validation attempts: Invalid question
    Expected: QuestionValidationExhausted raised
    """
    sankey_data = {
        "nodes": [{"label_summary": "Test", "member_count": 10, "member_pct": 0.5}],
        "flows": [],
        "total_participants": 20
    }

    with patch.object(generation_service.client.messages, 'create', new_callable=AsyncMock) as mock_create:
        # All responses are invalid
        mock_create.side_effect = [
            mock_invalid_response,
            mock_invalid_response,
            mock_invalid_response
        ]

        with pytest.raises(QuestionValidationExhausted) as exc_info:
            await generation_service.generate_from_sankey(
                round_num=2,
                previous_questions=["What are the key priorities?"],
                sankey_data=sankey_data,
                input_round_id=uuid4()
            )

        # Verify error message mentions validation attempts
        assert "validation failed after 3 attempts" in str(exc_info.value).lower()

        # Verify 3 validation attempts were made
        assert mock_create.call_count == 3


@pytest.mark.asyncio
async def test_timeout_then_rate_limit_then_success(generation_service, mock_valid_response):
    """
    Test mixed error types: TimeoutError → RateLimitError → Success.

    Scenario:
    - First call: TimeoutError
    - Second call: RateLimitError
    - Third call: Success
    Expected: Successful generation with retry_count=2
    """
    sankey_data = {
        "nodes": [{"label_summary": "Test", "member_count": 10, "member_pct": 0.5}],
        "flows": [],
        "total_participants": 20
    }

    with patch.object(generation_service.client.messages, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = [
            APITimeoutError("Request timed out"),
            RateLimitError("Rate limit exceeded", response=Mock(status_code=429), body={}),
            mock_valid_response
        ]

        result = await generation_service.generate_from_sankey(
            round_num=2,
            previous_questions=["What are the key priorities?"],
            sankey_data=sankey_data,
            input_round_id=uuid4()
        )

    # Verify successful generation
    assert result["question_text"] == "What are the main challenges?"
    assert result["provenance"]["retry_count"] == 2

    # Verify 3 calls were made
    assert mock_create.call_count == 3
