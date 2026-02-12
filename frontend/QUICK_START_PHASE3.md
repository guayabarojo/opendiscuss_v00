# Quick Start Guide - Phase 3 Frontend Components

## Prerequisites

- Node.js 18+ and npm installed
- Backend API running on `http://localhost:8000`
- PostgreSQL and Redis services running

## Setup (5 minutes)

### 1. Install Dependencies

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend
npm install
```

This installs:
- d3 (^7.9.0) - Sankey visualization
- recharts (^2.12.7) - Alternative charting library
- @types/d3 (^7.4.3) - TypeScript definitions

### 2. Configure Environment

Create `.env.local`:

```bash
cp .env.example .env.local
```

Edit `.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000/v1
```

### 3. Add Routes to App

Edit `src/App.tsx`:

```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import DiscussionReport from './pages/DiscussionReport'

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <header className="app-header">
          <h1>OpenDiscuss</h1>
        </header>
        <main className="app-main">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/discussions/:discussionId/report" element={<DiscussionReport />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
```

### 4. Start Development Server

```bash
npm run dev
```

Visit: `http://localhost:5173`

## Usage Examples

### Example 1: Create and View Discussion

```typescript
import { discussionApi } from '@/services/discussionApi';
import { useNavigate } from 'react-router-dom';

function CreateDiscussion() {
  const navigate = useNavigate();

  const handleCreate = async () => {
    try {
      const discussion = await discussionApi.createDiscussion({
        community_id: 'your-community-uuid',
        mode: 'HOST_DEFINED',
        total_rounds: 1,
        questions: ['What are your thoughts on this topic?']
      });

      // Start the discussion
      await discussionApi.startDiscussion(discussion.discussion_id);

      // Navigate to report (when complete)
      navigate(`/discussions/${discussion.discussion_id}/report`);
    } catch (error) {
      console.error('Failed to create discussion:', error);
    }
  };

  return <button onClick={handleCreate}>Create Discussion</button>;
}
```

### Example 2: Real-time Round Monitoring

```typescript
import { useState, useEffect } from 'react';
import { eventStream } from '@/services/eventStream';
import type { RoundStatusResponse } from '@/types/api';

function RoundMonitor({ roundId }: { roundId: string }) {
  const [status, setStatus] = useState<RoundStatusResponse | null>(null);

  useEffect(() => {
    const source = eventStream.subscribe(roundId, (event) => {
      if (event.type === 'round.status') {
        setStatus(event.data);
      }
    });

    // Cleanup on unmount
    return () => {
      source.close();
    };
  }, [roundId]);

  if (!status) return <div>Connecting...</div>;

  return (
    <div>
      <h2>Round Status: {status.status}</h2>
      {status.remaining_time_sec && (
        <p>Time remaining: {status.remaining_time_sec} seconds</p>
      )}
      <p>Submissions: {status.participant_stats.submitted_count}</p>
      <p>Approved: {status.participant_stats.approved_count}</p>
    </div>
  );
}
```

### Example 3: View Discussion Report

Simply navigate to:
```
http://localhost:5173/discussions/{discussion-uuid}/report
```

Or programmatically:

```typescript
import { useNavigate } from 'react-router-dom';

function ViewReport({ discussionId }: { discussionId: string }) {
  const navigate = useNavigate();

  return (
    <button onClick={() => navigate(`/discussions/${discussionId}/report`)}>
      View Report
    </button>
  );
}
```

## Testing with Mock Data

### 1. Create Test Discussion

```bash
curl -X POST http://localhost:8000/v1/discussions \
  -H "Content-Type: application/json" \
  -d '{
    "community_id": "test-uuid",
    "mode": "HOST_DEFINED",
    "total_rounds": 1,
    "questions": ["Test question?"]
  }'
```

### 2. Test API Client

```typescript
// In browser console
import { discussionApi } from '@/services/discussionApi';

// Get discussion
discussionApi.getDiscussion('discussion-uuid')
  .then(console.log)
  .catch(console.error);

// Get report
discussionApi.getReport('discussion-uuid')
  .then(console.log)
  .catch(console.error);
```

### 3. Test Event Stream

```typescript
// In browser console
import { eventStream } from '@/services/eventStream';

const source = eventStream.subscribe('round-uuid', (event) => {
  console.log('Event received:', event);
});

// Close after testing
source.close();
```

## Common Issues

### Issue 1: API Connection Failed

**Symptom:** "Network Error: Unable to reach the server"

**Solution:**
1. Check backend is running: `curl http://localhost:8000/health`
2. Verify `VITE_API_BASE_URL` in `.env.local`
3. Check CORS configuration on backend
4. Restart dev server after env change: `npm run dev`

### Issue 2: SSE Not Connecting

**Symptom:** Event stream keeps reconnecting

**Solution:**
1. Backend must implement `/rounds/{id}/events` endpoint
2. Check browser console for SSE errors
3. Verify EventSource is supported (not IE11)
4. Check backend SSE headers:
   ```
   Content-Type: text/event-stream
   Cache-Control: no-cache
   Connection: keep-alive
   ```

### Issue 3: Sankey Not Rendering

**Symptom:** Blank white box where Sankey should be

**Solution:**
1. Check browser console for D3 errors
2. Verify report data has `sankey_diagram` property
3. Check container has width/height
4. Try with simple test data:
   ```typescript
   const testReport = {
     discussion_id: 'test',
     sankey_diagram: {
       columns: [{
         round_num: 1,
         thought_spaces: [{
           cluster_id: '1',
           label: 'Test Space',
           member_count: 10,
           member_pct: 1.0
         }]
       }],
       flows: []
     },
     metadata: {
       total_rounds: 1,
       total_participants: 10,
       duration_minutes: 5,
       questions: ['Test?']
     }
   };
   ```

### Issue 4: TypeScript Errors

**Symptom:** Red squiggly lines in IDE

**Solution:**
1. Run type check: `npm run build`
2. Ensure types are imported: `import type { ... } from '@/types/api'`
3. Restart TypeScript server in VSCode: `Cmd+Shift+P` → "Restart TS Server"

### Issue 5: Authentication 401

**Symptom:** "Unauthorized" error on API calls

**Solution:**
1. Set auth token: `localStorage.setItem('auth_token', 'your-jwt')`
2. Check token format is valid JWT
3. Verify backend accepts Bearer token
4. Check token hasn't expired

## Verification Checklist

- [ ] Dependencies installed (`npm install` successful)
- [ ] Environment configured (`.env.local` exists)
- [ ] Backend running (`curl http://localhost:8000/health`)
- [ ] Dev server running (`npm run dev`)
- [ ] No TypeScript errors (`npm run build`)
- [ ] API client can fetch data (test in console)
- [ ] Routes added to App.tsx
- [ ] Can navigate to report page
- [ ] Sankey renders with test data

## Performance Tips

1. **API Client**
   - Requests timeout after 30 seconds
   - Use React Query for caching:
     ```typescript
     import { useQuery } from '@tanstack/react-query';

     const { data } = useQuery({
       queryKey: ['discussion', discussionId],
       queryFn: () => discussionApi.getDiscussion(discussionId)
     });
     ```

2. **Event Stream**
   - Always cleanup subscriptions in useEffect
   - Don't create multiple subscriptions to same round
   - Use connection pooling (built-in)

3. **Sankey Visualization**
   - Renders efficiently up to ~50 nodes
   - For larger datasets, consider pagination
   - Debounce hover events if needed

## Next Steps

1. **Add Authentication**
   - Implement login flow
   - Store JWT in localStorage
   - Handle token refresh

2. **Enhance Visualizations**
   - Add animations to Sankey
   - Implement zoom/pan
   - Add filtering options

3. **Add Error Boundaries**
   - Catch React errors
   - Show user-friendly messages
   - Log to error tracking service

4. **Optimize Bundle**
   - Code split by route
   - Lazy load D3
   - Tree-shake unused code

## Resources

- **API Documentation:** `specs/001-discussion-protocol/contracts/discussion-api.yaml`
- **Type Definitions:** `frontend/src/types/api.ts`
- **Service Docs:** `frontend/src/services/README.md`
- **Implementation Notes:** `frontend/IMPLEMENTATION_NOTES.md`
- **D3.js Docs:** https://d3js.org/
- **React Router:** https://reactrouter.com/

## Support

For issues or questions:
1. Check console for errors
2. Review implementation notes
3. Test with curl/Postman first
4. Check backend logs
5. Verify environment variables

---

**Last Updated:** 2026-01-29
**Phase:** 3 (Frontend Integration)
**Tasks:** T048-T050 ✅
