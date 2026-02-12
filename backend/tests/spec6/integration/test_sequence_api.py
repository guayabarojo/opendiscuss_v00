"""
Integration tests for Question Progression API (Phase 3 - Spec 006).

Tests T020-T021: API endpoints for host-defined question sequences.
"""

import pytest
import uuid
from httpx import AsyncClient

from src.models.discussion import Discussion, DiscussionMode


@pytest.mark.asyncio
class TestCreateSequenceEndpoint:
    """Tests for T020: POST /questions/sequences"""

    async def test_create_sequence_success(
        self, async_client: AsyncClient, async_session
    ):
        """T020: Create sequence with valid questions"""
        # Create discussion first
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        async_session.add(discussion)
        await async_session.commit()

        # Create sequence
        request_data = {
            "discussion_id": str(discussion.discussion_id),
            "mode": "HOST_DEFINED",
            "questions": [
                "What are the main challenges?",
                "How can we improve accessibility?",
                "What resources are needed?",
            ],
        }

        response = await async_client.post(
            "/api/v1/questions/sequences",
            json=request_data,
        )

        assert response.status_code == 201
        data = response.json()

        assert data["discussion_id"] == str(discussion.discussion_id)
        assert data["mode"] == "HOST_DEFINED"
        assert data["total_questions"] == 3
        assert data["current_index"] == 0
        assert data["completion_status"] == "IN_PROGRESS"
        assert len(data["questions"]) == 3

        # Verify question details
        for i, question in enumerate(data["questions"], start=1):
            assert question["order"] == i
            assert question["mode"] == "HOST_DEFINED"
            assert question["validation_status"] == "VALID"
            assert question["immutable_since"] is None

    async def test_create_sequence_validation_error_invalid_start(
        self, async_client: AsyncClient, async_session
    ):
        """T020: Return 400 for question not starting with What/How"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        request_data = {
            "discussion_id": str(discussion.discussion_id),
            "mode": "HOST_DEFINED",
            "questions": ["Why is this important?"],
        }

        response = await async_client.post(
            "/api/v1/questions/sequences",
            json=request_data,
        )

        assert response.status_code == 400
        data = response.json()
        assert "VALIDATION_ERROR" in data["detail"]["error"]
        assert "CONTAINS_PROHIBITED_WORD" in data["detail"]["details"]["error_code"]

    async def test_create_sequence_validation_error_ranking_keyword(
        self, async_client: AsyncClient, async_session
    ):
        """T020: Return 400 for question with ranking keywords"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        request_data = {
            "discussion_id": str(discussion.discussion_id),
            "mode": "HOST_DEFINED",
            "questions": ["What is the best option?"],
        }

        response = await async_client.post(
            "/api/v1/questions/sequences",
            json=request_data,
        )

        assert response.status_code == 400
        data = response.json()
        assert "VALIDATION_ERROR" in data["detail"]["error"]
        assert "CONTAINS_RANKING_KEYWORD" in data["detail"]["details"]["error_code"]

    async def test_create_sequence_validation_error_too_short(
        self, async_client: AsyncClient, async_session
    ):
        """T020: Return 400 for question too short"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        request_data = {
            "discussion_id": str(discussion.discussion_id),
            "mode": "HOST_DEFINED",
            "questions": ["What?"],
        }

        response = await async_client.post(
            "/api/v1/questions/sequences",
            json=request_data,
        )

        assert response.status_code == 400
        data = response.json()
        assert "VALIDATION_ERROR" in data["detail"]["error"]

    async def test_create_sequence_duplicate(
        self, async_client: AsyncClient, async_session
    ):
        """T020: Return 409 if sequence already exists"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
        )
        async_session.add(discussion)
        await async_session.commit()

        request_data = {
            "discussion_id": str(discussion.discussion_id),
            "mode": "HOST_DEFINED",
            "questions": ["What is A?", "What is B?"],
        }

        # Create first sequence
        response1 = await async_client.post(
            "/api/v1/questions/sequences",
            json=request_data,
        )
        assert response1.status_code == 201

        # Attempt duplicate
        response2 = await async_client.post(
            "/api/v1/questions/sequences",
            json=request_data,
        )
        assert response2.status_code == 409
        assert "SEQUENCE_ALREADY_EXISTS" in response2.json()["detail"]["error"]

    async def test_create_sequence_invalid_count(
        self, async_client: AsyncClient, async_session
    ):
        """T020: Return 422 for invalid question count (Pydantic validation)"""
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=10,
        )
        async_session.add(discussion)
        await async_session.commit()

        request_data = {
            "discussion_id": str(discussion.discussion_id),
            "mode": "HOST_DEFINED",
            "questions": [f"What is question {i}?" for i in range(1, 12)],
        }

        response = await async_client.post(
            "/api/v1/questions/sequences",
            json=request_data,
        )

        assert response.status_code == 422  # Pydantic validation error for max_length


@pytest.mark.asyncio
class TestGetSequenceEndpoint:
    """Tests for T021: GET /questions/sequences/{sequence_id}"""

    async def test_get_sequence_success(
        self, async_client: AsyncClient, async_session
    ):
        """T021: Get sequence by ID with all questions"""
        # Create discussion
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
        )
        async_session.add(discussion)
        await async_session.commit()

        # Create sequence
        create_request = {
            "discussion_id": str(discussion.discussion_id),
            "mode": "HOST_DEFINED",
            "questions": ["What is A?", "What is B?"],
        }

        create_response = await async_client.post(
            "/api/v1/questions/sequences",
            json=create_request,
        )
        assert create_response.status_code == 201
        sequence_id = create_response.json()["sequence_id"]

        # Get sequence
        get_response = await async_client.get(
            f"/api/v1/questions/sequences/{sequence_id}"
        )

        assert get_response.status_code == 200
        data = get_response.json()

        assert data["sequence_id"] == sequence_id
        assert data["discussion_id"] == str(discussion.discussion_id)
        assert data["mode"] == "HOST_DEFINED"
        assert data["total_questions"] == 2
        assert data["current_index"] == 0
        assert data["completion_status"] == "IN_PROGRESS"
        assert len(data["questions"]) == 2

    async def test_get_sequence_not_found(
        self, async_client: AsyncClient
    ):
        """T021: Return 404 for non-existent sequence"""
        fake_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/questions/sequences/{fake_id}"
        )

        assert response.status_code == 404
        assert "NOT_FOUND" in response.json()["detail"]["error"]

    async def test_get_sequence_includes_immutability(
        self, async_client: AsyncClient, async_session
    ):
        """T021: Include immutable_since in response"""
        from src.question_progression.services.sequence import QuestionSequenceService

        # Create discussion and sequence
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        async_session.add(discussion)
        await async_session.commit()

        service = QuestionSequenceService(async_session)
        sequence = await service.create_host_sequence(
            discussion_id=discussion.discussion_id,
            questions=["What is the question?"],
        )

        # Mark question immutable
        question = sequence.questions[0]
        await service.mark_question_immutable(question.question_id)

        # Get sequence via API
        response = await async_client.get(
            f"/api/v1/questions/sequences/{sequence.sequence_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["questions"][0]["immutable_since"] is not None


@pytest.mark.asyncio
class TestGetDiscussionQuestionsEndpoint:
    """Tests for GET /discussions/{discussion_id}/questions"""

    async def test_get_discussion_questions_success(
        self, async_client: AsyncClient, async_session
    ):
        """Get all questions for a discussion"""
        # Create discussion
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        async_session.add(discussion)
        await async_session.commit()

        # Create sequence
        create_request = {
            "discussion_id": str(discussion.discussion_id),
            "mode": "HOST_DEFINED",
            "questions": [
                "What is question 1?",
                "What is question 2?",
                "What is question 3?",
            ],
        }

        await async_client.post(
            "/api/v1/questions/sequences",
            json=create_request,
        )

        # Get questions for discussion
        response = await async_client.get(
            f"/api/v1/questions/discussions/{discussion.discussion_id}/questions"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["discussion_id"] == str(discussion.discussion_id)
        assert len(data["questions"]) == 3
        assert data["questions"][0]["question_text"] == "What is question 1?"
        assert data["questions"][1]["question_text"] == "What is question 2?"
        assert data["questions"][2]["question_text"] == "What is question 3?"

    async def test_get_discussion_questions_not_found(
        self, async_client: AsyncClient
    ):
        """Return 404 if no sequence for discussion"""
        fake_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/questions/discussions/{fake_id}/questions"
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestValidateQuestionEndpoint:
    """Tests for POST /questions/validate"""

    async def test_validate_valid_question(
        self, async_client: AsyncClient
    ):
        """Validate a valid question"""
        response = await async_client.post(
            "/api/v1/questions/validate",
            json={"question_text": "What are the main challenges?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["validated_text"] == "What are the main challenges?"
        assert data["error"] is None
        assert data["error_code"] is None

    async def test_validate_invalid_question(
        self, async_client: AsyncClient
    ):
        """Validate an invalid question"""
        response = await async_client.post(
            "/api/v1/questions/validate",
            json={"question_text": "Why is this important?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["error"] is not None
        assert "CONTAINS_PROHIBITED_WORD" in data["error_code"]


# ============================================================================
# T098: Performance Test - Question Query Speed
# ============================================================================


@pytest.mark.asyncio
class TestSequenceQueryPerformance:
    """T098: Performance test for question sequence query speed."""

    async def test_sequence_query_speed_performance(
        self, async_client: AsyncClient, async_session
    ):
        """
        T098: Test question query speed performance.

        Metric: < 5ms for GET /questions/sequences/{id}
        Test: Query 100 sequences, measure response time
        Verify: p95 < 5ms (indexed query)
        """
        import time
        import statistics

        # Create 100 test sequences
        sequence_ids = []
        for i in range(100):
            discussion = Discussion(
                community_id=uuid.uuid4(),
                host_user_id=uuid.uuid4(),
                mode=DiscussionMode.HOST_DEFINED,
                total_rounds=1,
            )
            async_session.add(discussion)
            await async_session.flush()

            request_data = {
                "discussion_id": str(discussion.discussion_id),
                "mode": "HOST_DEFINED",
                "questions": [f"What is question {i}?"],
            }

            response = await async_client.post(
                "/api/v1/questions/sequences",
                json=request_data,
            )
            assert response.status_code == 201
            sequence_ids.append(response.json()["sequence_id"])

        await async_session.commit()

        print(f"\n" + "="*80)
        print(f"Question Query Performance Test (T098)")
        print("="*80)
        print(f"  Created {len(sequence_ids)} sequences for testing")

        # Measure query times
        query_times_ms = []

        for sequence_id in sequence_ids:
            start_time = time.time()

            response = await async_client.get(
                f"/api/v1/questions/sequences/{sequence_id}"
            )

            end_time = time.time()

            assert response.status_code == 200
            query_time_ms = (end_time - start_time) * 1000
            query_times_ms.append(query_time_ms)

        # Calculate statistics
        mean_time = statistics.mean(query_times_ms)
        median_time = statistics.median(query_times_ms)
        min_time = min(query_times_ms)
        max_time = max(query_times_ms)

        # Calculate p95
        sorted_times = sorted(query_times_ms)
        p95_index = int(len(sorted_times) * 0.95)
        p95_time = sorted_times[p95_index]

        print(f"\n  Query Performance Metrics:")
        print(f"  - Queries executed: {len(query_times_ms)}")
        print(f"  - Mean:   {mean_time:.2f}ms")
        print(f"  - Median: {median_time:.2f}ms")
        print(f"  - Min:    {min_time:.2f}ms")
        print(f"  - Max:    {max_time:.2f}ms")
        print(f"  - p95:    {p95_time:.2f}ms")
        print("="*80)

        # Verify: p95 < 5ms (indexed query)
        assert p95_time < 5.0, (
            f"p95 query time {p95_time:.2f}ms exceeds 5ms threshold"
        )

        print(f"✓ p95 query time {p95_time:.2f}ms < 5ms threshold\n")

    async def test_discussion_questions_query_speed(
        self, async_client: AsyncClient, async_session
    ):
        """
        Test query speed for GET /discussions/{id}/questions endpoint.

        Verifies fast retrieval of all questions for a discussion.
        """
        import time

        # Create discussion with 10 questions
        discussion = Discussion(
            community_id=uuid.uuid4(),
            host_user_id=uuid.uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=10,
        )
        async_session.add(discussion)
        await async_session.commit()

        request_data = {
            "discussion_id": str(discussion.discussion_id),
            "mode": "HOST_DEFINED",
            "questions": [f"What is question {i}?" for i in range(1, 11)],
        }

        response = await async_client.post(
            "/api/v1/questions/sequences",
            json=request_data,
        )
        assert response.status_code == 201

        # Measure query time for all questions
        query_times_ms = []

        for _ in range(50):
            start_time = time.time()

            response = await async_client.get(
                f"/api/v1/questions/discussions/{discussion.discussion_id}/questions"
            )

            end_time = time.time()

            assert response.status_code == 200
            data = response.json()
            assert len(data["questions"]) == 10

            query_time_ms = (end_time - start_time) * 1000
            query_times_ms.append(query_time_ms)

        # Calculate average
        import statistics
        avg_time = statistics.mean(query_times_ms)
        p95_index = int(len(query_times_ms) * 0.95)
        p95_time = sorted(query_times_ms)[p95_index]

        print(f"\n  Discussion questions query performance:")
        print(f"  - Average: {avg_time:.2f}ms")
        print(f"  - p95: {p95_time:.2f}ms")

        # Relaxed threshold for multi-question retrieval
        assert p95_time < 10.0, (
            f"p95 query time {p95_time:.2f}ms exceeds 10ms threshold"
        )
