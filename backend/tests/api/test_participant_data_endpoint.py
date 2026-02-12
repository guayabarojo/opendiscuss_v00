"""
Tests for participant data API endpoint.

Tests the GET /api/v1/participant-data/{discussion_id} endpoint including:
- Basic retrieval
- Round filtering
- Search functionality
- Pagination
"""

import pytest
from uuid import uuid4
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_participant_data_not_found(async_client: AsyncClient):
    """Test 404 response for non-existent discussion."""
    non_existent_id = uuid4()
    response = await async_client.get(f"/api/v1/participant-data/{non_existent_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_participant_data_success(
    async_client: AsyncClient,
    sample_discussion_with_data
):
    """
    Test successful retrieval of participant data.

    Requires fixture that creates:
    - Discussion with multiple rounds
    - Participants with submissions
    - Approved summaries with cluster assignments
    """
    discussion_id = sample_discussion_with_data["discussion_id"]

    response = await async_client.get(f"/api/v1/participant-data/{discussion_id}")

    assert response.status_code == 200

    data = response.json()
    assert "data" in data
    assert "total" in data
    assert "discussion_id" in data
    assert "rounds" in data

    # Verify structure of data rows
    if len(data["data"]) > 0:
        row = data["data"][0]
        assert "round_num" in row
        assert "participant_id" in row
        assert "summary" in row
        assert "cluster_id" in row
        assert "cluster_label" in row
        assert "cluster_size" in row


@pytest.mark.asyncio
async def test_get_participant_data_round_filter(
    async_client: AsyncClient,
    sample_discussion_with_data
):
    """Test filtering by round number."""
    discussion_id = sample_discussion_with_data["discussion_id"]
    round_num = 1

    response = await async_client.get(
        f"/api/v1/participant-data/{discussion_id}",
        params={"round_num": round_num}
    )

    assert response.status_code == 200

    data = response.json()
    # All rows should be from the specified round
    for row in data["data"]:
        assert row["round_num"] == round_num


@pytest.mark.asyncio
async def test_get_participant_data_search(
    async_client: AsyncClient,
    sample_discussion_with_data
):
    """Test search functionality."""
    discussion_id = sample_discussion_with_data["discussion_id"]
    search_term = sample_discussion_with_data["search_term"]

    response = await async_client.get(
        f"/api/v1/participant-data/{discussion_id}",
        params={"search": search_term}
    )

    assert response.status_code == 200

    data = response.json()
    # Results should contain the search term (case-insensitive)
    for row in data["data"]:
        found = False
        for field in ["raw_input", "summary", "cluster_label"]:
            if row.get(field) and search_term.lower() in row[field].lower():
                found = True
                break
        assert found, f"Search term '{search_term}' not found in row"


@pytest.mark.asyncio
async def test_get_participant_data_pagination(
    async_client: AsyncClient,
    sample_discussion_with_data
):
    """Test pagination functionality."""
    discussion_id = sample_discussion_with_data["discussion_id"]
    limit = 5

    # First page
    response1 = await async_client.get(
        f"/api/v1/participant-data/{discussion_id}",
        params={"limit": limit, "offset": 0}
    )

    assert response1.status_code == 200
    data1 = response1.json()
    assert len(data1["data"]) <= limit

    # Second page
    response2 = await async_client.get(
        f"/api/v1/participant-data/{discussion_id}",
        params={"limit": limit, "offset": limit}
    )

    assert response2.status_code == 200
    data2 = response2.json()

    # Verify total is consistent
    assert data1["total"] == data2["total"]

    # Verify different data on different pages (if enough rows)
    if data1["total"] > limit:
        assert data1["data"] != data2["data"]


@pytest.mark.asyncio
async def test_get_participant_data_empty_discussion(
    async_client: AsyncClient,
    empty_discussion
):
    """Test response for discussion with no participant data."""
    discussion_id = empty_discussion["discussion_id"]

    response = await async_client.get(f"/api/v1/participant-data/{discussion_id}")

    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 0
    assert len(data["data"]) == 0
    assert data["discussion_id"] == str(discussion_id)


@pytest.mark.asyncio
async def test_get_participant_data_validates_limit(async_client: AsyncClient):
    """Test that limit parameter is validated (max 100)."""
    discussion_id = uuid4()

    # Should reject limit > 100
    response = await async_client.get(
        f"/api/v1/participant-data/{discussion_id}",
        params={"limit": 150}
    )

    # FastAPI validation should catch this
    assert response.status_code == 422


# Note: Fixtures like sample_discussion_with_data, empty_discussion
# need to be created in conftest.py or imported from existing fixtures
