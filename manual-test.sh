#!/bin/bash
# Manual Test Script - Test discussion creation flow

echo "=========================================="
echo "OpenDiscuss Manual Test Suite"
echo "=========================================="
echo ""

# Test 1: Backend Health
echo "Test 1: Backend Health Check"
response=$(curl -s http://localhost:8000/health)
if echo "$response" | grep -q "healthy"; then
    echo "✓ Backend is healthy"
else
    echo "✗ Backend health check failed"
    echo "Response: $response"
fi
echo ""

# Test 2: Create Valid Discussion
echo "Test 2: Create Discussion with Valid Questions"
response=$(curl -s -X POST http://localhost:8000/api/v1/discussions \
    -H "Content-Type: application/json" \
    -d '{
        "community_id": "00000000-0000-0000-0000-000000000001",
        "mode": "HOST_DEFINED",
        "total_rounds": 3,
        "questions": [
            "What are the main challenges we face?",
            "How can we address these challenges effectively?",
            "What resources would help us succeed?"
        ]
    }')

if echo "$response" | grep -q "discussion_id"; then
    echo "✓ Discussion created successfully"
    discussion_id=$(echo "$response" | grep -o '"discussion_id":"[^"]*"' | cut -d'"' -f4)
    echo "  Discussion ID: $discussion_id"
else
    echo "✗ Failed to create discussion"
    echo "Response: $response"
fi
echo ""

# Test 3: Invalid Question (Ranking Keyword)
echo "Test 3: Reject Question with Ranking Keyword"
response=$(curl -s -X POST http://localhost:8000/api/v1/discussions \
    -H "Content-Type: application/json" \
    -d '{
        "community_id": "00000000-0000-0000-0000-000000000001",
        "mode": "HOST_DEFINED",
        "total_rounds": 2,
        "questions": [
            "What is your favorite solution?",
            "How can we improve this?"
        ]
    }')

if echo "$response" | grep -q "favorite\|ranking"; then
    echo "✓ Ranking keyword properly rejected"
else
    echo "✗ Should have rejected 'favorite' keyword"
    echo "Response: $response"
fi
echo ""

# Test 4: Frontend Accessibility
echo "Test 4: Frontend Page Accessibility"
home_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/)
create_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/discussions/create)

if [ "$home_response" == "200" ]; then
    echo "✓ Home page accessible (HTTP $home_response)"
else
    echo "✗ Home page not accessible (HTTP $home_response)"
fi

if [ "$create_response" == "200" ]; then
    echo "✓ Create page accessible (HTTP $create_response)"
else
    echo "✗ Create page not accessible (HTTP $create_response)"
fi
echo ""

echo "=========================================="
echo "Test Suite Complete"
echo "=========================================="
echo ""
echo "To manually test the frontend:"
echo "1. Open http://localhost:3000/discussions/create in your browser"
echo "2. Fill out the form with valid questions (no 'favorite', 'best', etc.)"
echo "3. Submit and verify it redirects to /discussions/{id}/live"
echo ""
