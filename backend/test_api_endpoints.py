"""
Quick test script to verify API endpoints implementation (T032-T034).

This is a manual test script to verify the API is working correctly.
Run with: python3 test_api_endpoints.py
"""

import sys
import asyncio
from uuid import uuid4

# Add src to path
sys.path.insert(0, 'src')

from api.discussion_routes import create_discussion, get_discussion, start_discussion
from api.schemas import CreateDiscussionRequest
from database import get_db, init_db, close_db


async def test_endpoints():
    """Test the three implemented endpoints."""
    print("Starting API endpoint tests...")

    # Initialize database
    await init_db()

    # Create a test discussion request
    community_id = uuid4()
    request = CreateDiscussionRequest(
        community_id=community_id,
        mode="HOST_DEFINED",
        total_rounds=3,
        questions=[
            "What are the main challenges?",
            "How can we address these challenges?",
            "What resources do we need?"
        ]
    )

    print("\n1. Testing POST /discussions (T032)...")
    try:
        # Get a database session
        db_gen = get_db()
        db = await db_gen.__anext__()

        # Create discussion
        discussion = await create_discussion(request, db)
        print(f"✓ Discussion created: {discussion.discussion_id}")
        print(f"  - Status: {discussion.status}")
        print(f"  - Mode: {discussion.mode}")
        print(f"  - Rounds: {discussion.total_rounds}")

        discussion_id = discussion.discussion_id

        # Test GET endpoint
        print("\n2. Testing GET /discussions/{id} (T033)...")
        discussion = await get_discussion(discussion_id, db)
        print(f"✓ Discussion retrieved: {discussion.discussion_id}")
        print(f"  - Status: {discussion.status}")
        print(f"  - Current round: {discussion.current_round_num}")

        # Test START endpoint
        print("\n3. Testing POST /discussions/{id}/start (T034)...")
        discussion = await start_discussion(discussion_id, db)
        print(f"✓ Discussion started: {discussion.discussion_id}")
        print(f"  - Status: {discussion.status}")
        print(f"  - Current round: {discussion.current_round_num}")
        print(f"  - Started at: {discussion.started_at}")

        # Clean up
        await db_gen.aclose()

        print("\n✅ All tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Close database
        await close_db()


if __name__ == "__main__":
    print("=" * 60)
    print("API Endpoints Test (T032-T034)")
    print("=" * 60)
    asyncio.run(test_endpoints())
