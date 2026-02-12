# OpenDiscuss API Quick Reference

## Base URL
- Development: `http://localhost:8000`
- API Version 1: `/api/v1`

## Implemented Endpoints (Phase 3)

### 1. Create Discussion
```http
POST /api/v1/discussions
Content-Type: application/json

{
  "community_id": "uuid",
  "mode": "HOST_DEFINED",
  "total_rounds": 3,
  "questions": [
    "What are the main challenges?",
    "How can we address these challenges?",
    "What resources do we need?"
  ]
}
```

**Response (201 Created)**:
```json
{
  "discussion_id": "uuid",
  "community_id": "uuid",
  "mode": "HOST_DEFINED",
  "total_rounds": 3,
  "current_round_num": 0,
  "status": "CREATED",
  "created_at": "2026-01-29T12:00:00Z",
  "started_at": null,
  "completed_at": null,
  "terminated_reason": null,
  "host_user_id": "uuid"
}
```

### 2. Get Discussion
```http
GET /api/v1/discussions/{discussion_id}
```

**Response (200 OK)**:
```json
{
  "discussion_id": "uuid",
  "community_id": "uuid",
  "mode": "HOST_DEFINED",
  "total_rounds": 3,
  "current_round_num": 0,
  "status": "CREATED",
  "created_at": "2026-01-29T12:00:00Z",
  "started_at": null,
  "completed_at": null,
  "terminated_reason": null,
  "host_user_id": "uuid"
}
```

### 3. Start Discussion
```http
POST /api/v1/discussions/{discussion_id}/start
```

**Response (200 OK)**:
```json
{
  "discussion_id": "uuid",
  "community_id": "uuid",
  "mode": "HOST_DEFINED",
  "total_rounds": 3,
  "current_round_num": 1,
  "status": "ACTIVE",
  "created_at": "2026-01-29T12:00:00Z",
  "started_at": "2026-01-29T12:05:00Z",
  "completed_at": null,
  "terminated_reason": null,
  "host_user_id": "uuid"
}
```

## Discussion Modes

### HOST_DEFINED
- Questions provided upfront at creation
- Number of questions must match `total_rounds`
- All rounds created at discussion creation

**Example**:
```json
{
  "mode": "HOST_DEFINED",
  "total_rounds": 3,
  "questions": [
    "What are the challenges?",
    "How can we solve them?",
    "What resources do we need?"
  ]
}
```

### AUTO_GENERATED
- Questions generated from Sankey patterns
- Only seed question required at creation
- Subsequent questions generated after each round

**Example**:
```json
{
  "mode": "AUTO_GENERATED",
  "total_rounds": 5,
  "seed_question": "What are your thoughts on this topic?"
}
```

## Discussion Status Flow

```
CREATED → ACTIVE → COMPLETED
            ↓
        TERMINATED
```

- **CREATED**: Discussion created, not yet started
- **ACTIVE**: Discussion running, rounds in progress
- **COMPLETED**: All rounds finished successfully
- **TERMINATED**: Early termination by host

## Question Validation Rules

1. Length: 10-200 characters
2. Must start with "What" or "How" (case-insensitive)
3. No voting/ranking keywords: "vote", "rank", "best", "worst"

## Submission Window Timing

- Default duration: 300 seconds (5 minutes)
- Valid range: 180-360 seconds (3-6 minutes)
- Approval deadline: window_end + 10 minutes

## Error Responses

All errors follow standardized format:
```json
{
  "error": "error_code",
  "message": "Human readable message",
  "details": {
    "additional": "context"
  },
  "timestamp": "2026-01-29T12:00:00Z"
}
```

### Common Error Codes

- `discussion_not_found` (404): Discussion ID doesn't exist
- `invalid_state_transition` (400): Invalid status transition
- `validation_error` (422): Request validation failed
- `timing_violation` (400): Timing constraint violated
- `rate_limit_exceeded` (429): Too many requests

## Testing with curl

### Create and Start Discussion
```bash
# 1. Create discussion
DISCUSSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/discussions \
  -H "Content-Type: application/json" \
  -d '{
    "community_id": "123e4567-e89b-12d3-a456-426614174000",
    "mode": "HOST_DEFINED",
    "total_rounds": 3,
    "questions": [
      "What are the main challenges?",
      "How can we address these challenges?",
      "What resources do we need?"
    ]
  }' | jq -r '.discussion_id')

echo "Created discussion: $DISCUSSION_ID"

# 2. Get discussion
curl -s http://localhost:8000/api/v1/discussions/$DISCUSSION_ID | jq

# 3. Start discussion
curl -s -X POST http://localhost:8000/api/v1/discussions/$DISCUSSION_ID/start | jq
```

## OpenAPI Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Next Endpoints (Coming Soon)

- `GET /api/v1/rounds/{round_id}/status` (T035)
- `GET /api/v1/discussions/{discussion_id}/report` (T036)
- `POST /api/v1/discussions/{discussion_id}/advance` (T054)
- `GET /api/v1/discussions/{discussion_id}/participants` (T055)

## Authentication (TODO)

Currently using placeholder `host_user_id`. Future implementation will require:
- JWT Bearer token in Authorization header
- Community membership validation
- Host permission checks

```http
Authorization: Bearer <token>
```
