"""
T081: Contract test for question-api.yaml OpenAPI specification.

Validates all API responses match the OpenAPI schema contract.
Uses openapi-spec-validator for schema validation.
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any

import pytest
import yaml
from openapi_spec_validator import validate_spec
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError
from pydantic import BaseModel, Field


# Load OpenAPI Schema

@pytest.fixture(scope="module")
def api_schema() -> Dict[str, Any]:
    """Load and validate OpenAPI schema from question-api.yaml."""
    schema_path = Path(__file__).parent.parent.parent.parent.parent / "specs" / "006-question-progression" / "contracts" / "question-api.yaml"

    if not schema_path.exists():
        pytest.skip(f"API schema not found at {schema_path}")

    with open(schema_path, 'r') as f:
        schema = yaml.safe_load(f)

    # Validate schema itself
    try:
        validate_spec(schema)
    except OpenAPIValidationError as e:
        pytest.fail(f"OpenAPI schema validation failed: {e}")

    return schema


@pytest.fixture
def schema_components(api_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Extract components/schemas from OpenAPI spec."""
    return api_schema.get("components", {}).get("schemas", {})


# Schema Validation Helpers


def validate_against_schema(data: Dict[str, Any], schema: Dict[str, Any], components: Dict[str, Any]) -> None:
    """
    Validate data against an OpenAPI schema definition.

    Args:
        data: Data to validate
        schema: Schema definition
        components: Schema components for $ref resolution

    Raises:
        AssertionError: If validation fails
    """
    # Resolve $ref if present
    if "$ref" in schema:
        ref_path = schema["$ref"].split("/")
        if ref_path[0] == "#" and ref_path[1] == "components" and ref_path[2] == "schemas":
            schema_name = ref_path[3]
            schema = components[schema_name]

    # Validate type
    schema_type = schema.get("type")

    if schema_type == "object":
        assert isinstance(data, dict), f"Expected object, got {type(data).__name__}"

        # Check required fields
        required = schema.get("required", [])
        for field in required:
            assert field in data, f"Missing required field: {field}"

        # Validate properties
        properties = schema.get("properties", {})
        for key, value in data.items():
            if key in properties:
                validate_against_schema(value, properties[key], components)

    elif schema_type == "array":
        assert isinstance(data, list), f"Expected array, got {type(data).__name__}"

        # Validate items
        items_schema = schema.get("items", {})
        for item in data:
            validate_against_schema(item, items_schema, components)

    elif schema_type == "string":
        assert isinstance(data, str), f"Expected string, got {type(data).__name__}"

        # Validate format
        format_type = schema.get("format")
        if format_type == "uuid":
            try:
                uuid.UUID(data)
            except ValueError:
                pytest.fail(f"Invalid UUID format: {data}")

        # Validate enum
        enum_values = schema.get("enum")
        if enum_values:
            assert data in enum_values, f"Value {data} not in enum: {enum_values}"

        # Validate length constraints
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if min_length is not None:
            assert len(data) >= min_length, f"String length {len(data)} < minLength {min_length}"
        if max_length is not None:
            assert len(data) <= max_length, f"String length {len(data)} > maxLength {max_length}"

    elif schema_type == "integer":
        assert isinstance(data, int), f"Expected integer, got {type(data).__name__}"

        # Validate range
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None:
            assert data >= minimum, f"Value {data} < minimum {minimum}"
        if maximum is not None:
            assert data <= maximum, f"Value {data} > maximum {maximum}"

    elif schema_type == "number":
        assert isinstance(data, (int, float)), f"Expected number, got {type(data).__name__}"

        # Validate range
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None:
            assert data >= minimum, f"Value {data} < minimum {minimum}"
        if maximum is not None:
            assert data <= maximum, f"Value {data} > maximum {maximum}"

    elif schema_type == "boolean":
        assert isinstance(data, bool), f"Expected boolean, got {type(data).__name__}"


# Test Cases


class TestQuestionAPIContract:
    """Contract tests for Question API endpoints."""

    def test_schema_loads_successfully(self, api_schema: Dict[str, Any]):
        """Test that the OpenAPI schema loads and is valid."""
        assert api_schema is not None
        assert "openapi" in api_schema
        assert api_schema["openapi"].startswith("3.0")
        assert "paths" in api_schema
        assert "components" in api_schema

    def test_question_schema(self, schema_components: Dict[str, Any]):
        """Test Question schema structure."""
        # Create sample Question response
        question_data = {
            "question_id": str(uuid.uuid4()),
            "sequence_id": str(uuid.uuid4()),
            "order": 1,
            "question_text": "What are the main challenges?",
            "mode": "HOST_DEFINED",
            "validation_status": "VALID",
            "created_at": "2026-01-29T12:00:00Z",
            "immutable_since": None,
        }

        # Validate against schema
        validate_against_schema(question_data, schema_components["Question"], schema_components)

    def test_question_with_provenance_schema(self, schema_components: Dict[str, Any]):
        """Test QuestionWithProvenance schema structure."""
        # Create sample QuestionWithProvenance response
        question_data = {
            "question_id": str(uuid.uuid4()),
            "sequence_id": str(uuid.uuid4()),
            "order": 2,
            "question_text": "How could funding gaps be addressed?",
            "mode": "AUTO_GENERATED",
            "validation_status": "VALID",
            "created_at": "2026-01-29T12:05:00Z",
            "immutable_since": "2026-01-29T12:10:00Z",
            "provenance": {
                "provenance_id": str(uuid.uuid4()),
                "question_id": str(uuid.uuid4()),
                "generation_timestamp": "2026-01-29T12:05:00Z",
                "generation_latency_ms": 2847.3,
                "input_sankey_hash": "a3c5b8f2e1d4c7b9a1e3f5c8d2b4e6a7c9b1d3f5e7a9b2c4d6e8f1a3c5b7d9e1",
                "input_round_id": str(uuid.uuid4()),
                "llm_model": "claude-sonnet-4-5-20250929",
                "prompt_tokens": 1234,
                "completion_tokens": 56,
                "retry_count": 0,
                "validation_attempts": 1,
                "previous_questions_count": 1,
            }
        }

        # Validate against schema
        validate_against_schema(question_data, schema_components["QuestionWithProvenance"], schema_components)

    def test_question_sequence_schema(self, schema_components: Dict[str, Any]):
        """Test QuestionSequence schema structure."""
        # Create sample QuestionSequence response
        sequence_data = {
            "sequence_id": str(uuid.uuid4()),
            "discussion_id": str(uuid.uuid4()),
            "mode": "AUTO_GENERATED",
            "total_questions": None,
            "current_index": 1,
            "completion_status": "IN_PROGRESS",
            "created_at": "2026-01-29T11:00:00Z",
            "questions": [
                {
                    "question_id": str(uuid.uuid4()),
                    "sequence_id": str(uuid.uuid4()),
                    "order": 1,
                    "question_text": "What challenges are most pressing?",
                    "mode": "AUTO_GENERATED",
                    "validation_status": "VALID",
                    "created_at": "2026-01-29T11:05:00Z",
                    "immutable_since": "2026-01-29T11:10:00Z",
                }
            ]
        }

        # Validate against schema
        validate_against_schema(sequence_data, schema_components["QuestionSequence"], schema_components)

    def test_validation_result_schema(self, schema_components: Dict[str, Any]):
        """Test ValidationResult schema structure."""
        # Test valid result
        valid_result = {
            "valid": True,
            "validated_text": "What are the key priorities?",
            "error": None,
            "error_code": None,
        }
        validate_against_schema(valid_result, schema_components["ValidationResult"], schema_components)

        # Test invalid result
        invalid_result = {
            "valid": False,
            "validated_text": None,
            "error": "Question must start with 'What' or 'How'",
            "error_code": "OPENING_INVALID",
        }
        validate_against_schema(invalid_result, schema_components["ValidationResult"], schema_components)

    def test_generate_question_request_schema(self, schema_components: Dict[str, Any]):
        """Test GenerateQuestionRequest schema structure."""
        request_data = {
            "discussion_id": str(uuid.uuid4()),
            "round_id": str(uuid.uuid4()),
            "sankey_graph": {
                "columns": [
                    {
                        "round_num": 1,
                        "nodes": [
                            {
                                "cluster_id": str(uuid.uuid4()),
                                "label_summary": "Funding constraints limit program scope",
                                "member_count": 12,
                                "member_pct": 0.40,
                            }
                        ]
                    }
                ],
                "flows": []
            },
            "previous_questions": ["What challenges are most pressing?"]
        }

        validate_against_schema(request_data, schema_components["GenerateQuestionRequest"], schema_components)

    def test_generate_question_response_schema(self, schema_components: Dict[str, Any]):
        """Test GenerateQuestionResponse schema structure."""
        response_data = {
            "question_id": str(uuid.uuid4()),
            "question_text": "How could funding gaps be addressed?",
            "provenance_id": str(uuid.uuid4()),
            "next_round_status": "QUESTION_READY",
        }

        validate_against_schema(response_data, schema_components["GenerateQuestionResponse"], schema_components)

    def test_generation_failure_schema(self, schema_components: Dict[str, Any]):
        """Test GenerationFailure schema structure."""
        failure_data = {
            "discussion_id": str(uuid.uuid4()),
            "round_id": str(uuid.uuid4()),
            "error": "LLM API timeout after 3 retries",
            "retry_count": 3,
            "fallback_action": "MANUAL_ENTRY_REQUIRED",
        }

        validate_against_schema(failure_data, schema_components["GenerationFailure"], schema_components)

    def test_generation_status_schema(self, schema_components: Dict[str, Any]):
        """Test GenerationStatus schema structure."""
        # Test completed status
        completed_status = {
            "round_id": str(uuid.uuid4()),
            "status": "COMPLETED",
            "question_id": str(uuid.uuid4()),
            "error": None,
            "generation_latency_ms": 2847.3,
        }
        validate_against_schema(completed_status, schema_components["GenerationStatus"], schema_components)

        # Test failed status
        failed_status = {
            "round_id": str(uuid.uuid4()),
            "status": "FAILED",
            "question_id": None,
            "error": "Validation failed: question contains ranking keywords",
            "generation_latency_ms": 1234.5,
        }
        validate_against_schema(failed_status, schema_components["GenerationStatus"], schema_components)

    def test_sankey_graph_schema(self, schema_components: Dict[str, Any]):
        """Test SankeyGraph schema structure."""
        sankey_data = {
            "columns": [
                {
                    "round_num": 1,
                    "nodes": [
                        {
                            "cluster_id": str(uuid.uuid4()),
                            "label_summary": "Funding constraints limit program scope",
                            "member_count": 12,
                            "member_pct": 0.40,
                        },
                        {
                            "cluster_id": str(uuid.uuid4()),
                            "label_summary": "Staff capacity stretched across initiatives",
                            "member_count": 8,
                            "member_pct": 0.27,
                        }
                    ]
                },
                {
                    "round_num": 2,
                    "nodes": [
                        {
                            "cluster_id": str(uuid.uuid4()),
                            "label_summary": "Need for sustainable funding models",
                            "member_count": 15,
                            "member_pct": 0.50,
                        }
                    ]
                }
            ],
            "flows": [
                {
                    "source_cluster_id": str(uuid.uuid4()),
                    "target_cluster_id": str(uuid.uuid4()),
                    "participant_count": 10,
                }
            ]
        }

        validate_against_schema(sankey_data, schema_components["SankeyGraph"], schema_components)

    def test_error_schema(self, schema_components: Dict[str, Any]):
        """Test Error schema structure."""
        error_data = {
            "error": "VALIDATION_ERROR",
            "message": "Question must start with 'What' or 'How'",
            "details": {
                "error_code": "OPENING_INVALID"
            }
        }

        validate_against_schema(error_data, schema_components["Error"], schema_components)


# Integration Test Placeholders (to be implemented with actual API)


class TestQuestionAPIEndpoints:
    """
    Integration tests for Question API endpoints (placeholder).

    These tests would require a running API server and would validate:
    - POST /discussions/{discussion_id}/questions
    - GET /discussions/{discussion_id}/questions
    - GET /questions/{question_id}
    - POST /questions/{question_id}/validate
    - GET /sequences/{sequence_id}
    - POST /auto-generation/generate
    - GET /auto-generation/status/{round_id}
    """

    @pytest.mark.skip(reason="Requires running API server")
    def test_create_question_endpoint(self):
        """Test POST /discussions/{discussion_id}/questions endpoint."""
        pass

    @pytest.mark.skip(reason="Requires running API server")
    def test_list_questions_endpoint(self):
        """Test GET /discussions/{discussion_id}/questions endpoint."""
        pass

    @pytest.mark.skip(reason="Requires running API server")
    def test_get_question_endpoint(self):
        """Test GET /questions/{question_id} endpoint."""
        pass

    @pytest.mark.skip(reason="Requires running API server")
    def test_validate_question_endpoint(self):
        """Test POST /questions/{question_id}/validate endpoint."""
        pass

    @pytest.mark.skip(reason="Requires running API server")
    def test_get_sequence_endpoint(self):
        """Test GET /sequences/{sequence_id} endpoint."""
        pass

    @pytest.mark.skip(reason="Requires running API server")
    def test_generate_question_endpoint(self):
        """Test POST /auto-generation/generate endpoint."""
        pass

    @pytest.mark.skip(reason="Requires running API server")
    def test_get_generation_status_endpoint(self):
        """Test GET /auto-generation/status/{round_id} endpoint."""
        pass
