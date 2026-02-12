# Frontend Services

This directory contains API client services and real-time event handling for the OpenDiscuss frontend.

## Services

### discussionApi.ts

Typed API client for interacting with the Discussion Protocol API.

**Features:**
- Full TypeScript type safety from OpenAPI spec
- Automatic authentication token handling
- Error handling with typed error responses
- Request/response interceptors
- 30-second timeout with proper error messages

**Usage:**

```typescript
import { discussionApi } from '@/services/discussionApi';

// Create a discussion
const discussion = await discussionApi.createDiscussion({
  community_id: 'uuid',
  mode: 'HOST_DEFINED',
  total_rounds: 3,
  questions: ['Question 1', 'Question 2', 'Question 3']
});

// Start discussion
const started = await discussionApi.startDiscussion(discussion.discussion_id);

// Get round status
const status = await discussionApi.getRoundStatus(roundId);

// Get final report
const report = await discussionApi.getReport(discussion.discussion_id);
```

**Error Handling:**

```typescript
try {
  const discussion = await discussionApi.getDiscussion(id);
} catch (error: ApiError) {
  console.error(error.message);
  // Handle specific error types
  if (error.error === 'NotFound') {
    // Show 404 UI
  }
}
```

### eventStream.ts

Server-Sent Events (SSE) client for real-time round status updates.

**Features:**
- Automatic reconnection with exponential backoff
- Connection pooling and cleanup
- TypeScript event types
- React hook support

**Usage:**

```typescript
import { eventStream } from '@/services/eventStream';
import { useEffect, useState } from 'react';

function RoundMonitor({ roundId }: { roundId: string }) {
  const [status, setStatus] = useState<RoundStatusResponse | null>(null);

  useEffect(() => {
    const source = eventStream.subscribe(roundId, (event) => {
      if (event.type === 'round.status') {
        setStatus(event.data);
      }
    });

    return () => {
      source.close();
    };
  }, [roundId]);

  return (
    <div>
      Status: {status?.status}
      {status?.remaining_time_sec && (
        <p>Time remaining: {status.remaining_time_sec}s</p>
      )}
    </div>
  );
}
```

**Reconnection:**

The service automatically handles connection failures:
- Exponential backoff: 1s, 2s, 4s, 8s, 16s
- Max 5 reconnection attempts
- Emits error event after max attempts

**Cleanup:**

Always close connections when unmounting:

```typescript
useEffect(() => {
  const source = eventStream.subscribe(roundId, callback);
  return () => source.close();
}, [roundId]);
```

## Environment Variables

Set these in `.env` or `.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000/v1
```

## Type Safety

All API types are imported from `@/types/api.ts` which is generated from the OpenAPI specification at:

`specs/001-discussion-protocol/contracts/discussion-api.yaml`

## Authentication

The API client automatically includes the Bearer token from `localStorage.auth_token` in all requests. Set this token after successful login:

```typescript
localStorage.setItem('auth_token', 'your-jwt-token');
```

## Error Types

All API methods can throw `ApiError`:

```typescript
interface ApiError {
  error: string;        // Error type (e.g., "NotFound", "ValidationError")
  message: string;      // Human-readable error message
  details?: object;     // Optional additional error details
}
```

Common error types:
- `NotFound` (404)
- `ValidationError` (400)
- `Unauthorized` (401)
- `Forbidden` (403)
- `NetworkError` (connection failed)
- `RequestError` (malformed request)
