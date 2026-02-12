# Participant Data Table - Architecture Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              SankeyView Page Component                     │  │
│  │  (frontend/src/pages/SankeyView.tsx)                      │  │
│  │                                                            │  │
│  │  ┌──────────────────────────────────────────────────┐    │  │
│  │  │        SankeyDiagram Component                     │    │  │
│  │  │        (Existing - shows flow visualization)       │    │  │
│  │  └──────────────────────────────────────────────────┘    │  │
│  │                                                            │  │
│  │  ┌──────────────────────────────────────────────────┐    │  │
│  │  │    ParticipantDataTable Component (NEW)           │    │  │
│  │  │    ┌──────────────────────────────────────────┐  │    │  │
│  │  │    │  Filters Section                         │  │    │  │
│  │  │    │  ├─ Round Dropdown                       │  │    │  │
│  │  │    │  └─ Search Input (debounced)             │  │    │  │
│  │  │    └──────────────────────────────────────────┘  │    │  │
│  │  │    ┌──────────────────────────────────────────┐  │    │  │
│  │  │    │  Data Table                              │  │    │  │
│  │  │    │  ├─ Round | Participant | Raw Input     │  │    │  │
│  │  │    │  ├─ Summary | Cluster | Label | Size    │  │    │  │
│  │  │    │  └─ ... (20 rows per page)              │  │    │  │
│  │  │    └──────────────────────────────────────────┘  │    │  │
│  │  │    ┌──────────────────────────────────────────┐  │    │  │
│  │  │    │  Pagination Controls                     │  │    │  │
│  │  │    │  └─ Previous | Page X/Y | Next           │  │    │  │
│  │  │    └──────────────────────────────────────────┘  │    │  │
│  │  └──────────────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          │ fetchParticipantData()               │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │        participantDataApi.ts (API Client)                 │  │
│  │        - Type-safe interfaces                             │  │
│  │        - Query parameter construction                     │  │
│  │        - Error handling                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP GET
                            │ /api/v1/participant-data/{id}
                            │ ?round_num=X&search=Y&limit=20&offset=0
┌───────────────────────────▼─────────────────────────────────────┐
│                      Backend (FastAPI)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │        FastAPI Router (participant_data.py)               │  │
│  │        - Route: GET /participant-data/{discussion_id}     │  │
│  │        - Query params validation (Pydantic)               │  │
│  │        - Error handling (404, 400, 500)                   │  │
│  └─────────────────────────┬────────────────────────────────┘  │
│                            │                                    │
│                            │ build SQL query                    │
│                            ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │        SQLAlchemy Query Builder                           │  │
│  │        - Join approved_summaries (anchor)                 │  │
│  │        - Join rounds, thought_spaces                      │  │
│  │        - LEFT JOIN submissions (ephemeral)                │  │
│  │        - Apply filters (round_num, search)                │  │
│  │        - Apply pagination (limit, offset)                 │  │
│  └─────────────────────────┬────────────────────────────────┘  │
│                            │                                    │
│                            │ execute query                      │
│                            ▼                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   PostgreSQL Database                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │    submissions   │  │      rounds       │                    │
│  │  (EPHEMERAL)     │  │  (PERSISTED)      │                    │
│  │  - submission_id │  │  - round_id       │                    │
│  │  - participant_id│  │  - round_num      │                    │
│  │  - submission_   │  │  - discussion_id  │                    │
│  │    text          │  │  - question_text  │                    │
│  │  - deleted_at    │  └──────────────────┘                    │
│  └──────────────────┘           ▲                               │
│           ▲                     │                               │
│           │ (LEFT JOIN)         │ (JOIN)                        │
│           │                     │                               │
│  ┌────────┴──────────┐  ┌──────┴──────────┐                    │
│  │ approved_summaries│  │  thought_spaces  │                    │
│  │   (PERSISTED)     │  │   (PERSISTED)    │                    │
│  │  - summary_id     │  │  - cluster_id    │                    │
│  │  - participant_id │  │  - label_summary │                    │
│  │  - submission_id  │  │  - member_count  │                    │
│  │  - summary_text   │  │  - round_id      │                    │
│  │  - cluster_id     │  └──────────────────┘                    │
│  │  - round_id       │           ▲                               │
│  └───────────────────┘           │ (JOIN)                        │
│                                  │                               │
└──────────────────────────────────┴───────────────────────────────┘
```

## Data Flow

### 1. User Interaction
```
User visits /discussions/{id}/sankey
    ↓
SankeyView component loads
    ↓
ParticipantDataTable component mounts
    ↓
useEffect triggers initial data fetch
```

### 2. API Request
```
fetchParticipantData(discussionId, filters)
    ↓
Construct query parameters
    ↓
axios.get('/api/v1/participant-data/{id}?...')
    ↓
FastAPI receives request
```

### 3. Database Query
```
Validate discussion exists (Discussion table)
    ↓
Build main query:
    FROM approved_summaries (anchor)
    JOIN rounds (for round_num)
    JOIN thought_spaces (for cluster labels)
    LEFT JOIN submissions (may be deleted)
    ↓
Apply filters (round_num, search)
    ↓
Apply pagination (limit, offset)
    ↓
Execute query
    ↓
Format results as JSON
```

### 4. Response Handling
```
FastAPI returns ParticipantDataResponse
    ↓
axios receives data
    ↓
Component updates state (setData, setTotal, etc.)
    ↓
React re-renders table with new data
    ↓
User sees updated table
```

## Component State Machine

```
┌──────────────┐
│   INITIAL    │ (loading: true, data: [], error: null)
└──────┬───────┘
       │
       │ componentDidMount / useEffect
       ▼
┌──────────────┐
│   LOADING    │ (loading: true, data: [], error: null)
└──────┬───────┘
       │
       │ API call
       │
       ├─ Success ──────┐
       │                │
       │                ▼
       │         ┌──────────────┐
       │         │   LOADED     │ (loading: false, data: [...], error: null)
       │         └──────┬───────┘
       │                │
       │                │ Filter change / Search / Pagination
       │                │
       │                └───────┐
       │                        │
       │ Error                  ▼
       │                 ┌──────────────┐
       └────────────────►│   LOADING    │ (re-fetch)
                         └──────┬───────┘
                                │
                                │ Error
                                ▼
                         ┌──────────────┐
                         │    ERROR     │ (loading: false, data: [], error: "...")
                         └──────┬───────┘
                                │
                                │ Retry button
                                │
                                └───────► (back to LOADING)
```

## Database Query Structure

```sql
-- Main query template
SELECT
    r.round_num,                    -- From rounds
    r.round_id,                     -- From rounds
    aps.participant_id,             -- From approved_summaries
    aps.submission_id,              -- From approved_summaries
    aps.summary_text,               -- From approved_summaries
    aps.cluster_id,                 -- From approved_summaries
    ts.label_summary,               -- From thought_spaces
    ts.member_count,                -- From thought_spaces
    s.submission_text               -- From submissions (may be NULL)
FROM approved_summaries aps
    INNER JOIN rounds r
        ON aps.round_id = r.round_id
    INNER JOIN thought_spaces ts
        ON aps.cluster_id = ts.cluster_id
    LEFT OUTER JOIN submissions s
        ON aps.submission_id = s.submission_id
WHERE
    r.discussion_id = :discussion_id
    AND (:round_num IS NULL OR r.round_num = :round_num)
    AND (
        :search IS NULL
        OR aps.summary_text ILIKE :search_pattern
        OR ts.label_summary ILIKE :search_pattern
        OR s.submission_text ILIKE :search_pattern
    )
ORDER BY
    r.round_num ASC,
    aps.participant_id ASC
LIMIT :limit
OFFSET :offset;
```

## Index Strategy

```sql
-- Indexes used by the query (should exist)

-- On rounds table
CREATE INDEX idx_rounds_discussion_round_num
    ON rounds(discussion_id, round_num);

-- On approved_summaries table
CREATE INDEX idx_approved_summary_round_participant
    ON approved_summaries(round_id, participant_id);

CREATE INDEX idx_approved_summary_cluster
    ON approved_summaries(cluster_id);

-- On thought_spaces table
CREATE INDEX idx_thought_spaces_round_id
    ON thought_spaces(round_id);

-- On submissions table (for LEFT JOIN)
CREATE INDEX idx_submission_id
    ON submissions(submission_id);
```

## Component Props & State Flow

```typescript
// ParticipantDataTable.tsx

// Props (input from parent)
interface ParticipantDataTableProps {
  discussionId: string;  // From URL params
}

// Internal State
interface State {
  // Data
  data: ParticipantDataRow[];
  total: number;
  totalRounds: number;

  // UI State
  loading: boolean;
  error: string | null;

  // Filters
  roundFilter: number | undefined;
  searchQuery: string;
  debouncedSearch: string;  // After 500ms delay

  // Pagination
  currentPage: number;
  rowsPerPage: number;  // Fixed at 20
}

// Derived State
const totalPages = Math.ceil(total / rowsPerPage);
const startRow = (currentPage - 1) * rowsPerPage + 1;
const endRow = Math.min(currentPage * rowsPerPage, total);
```

## File Dependencies

```
backend/
  src/
    api/
      routes/
        participant_data.py  ←──── Imports ────┐
                                                │
    models/                                     │
      submission.py  ────────────────────────┐ │
      approved_summary.py  ──────────────────┤ │
      thought_space.py  ─────────────────────┤←┘
      round.py  ─────────────────────────────┘
      participant.py

    database.py  (get_db session)
    main.py  (router registration)

frontend/
  src/
    components/
      ParticipantDataTable/
        ParticipantDataTable.tsx  ←─── Uses ───┐
        ParticipantDataTable.css               │
        index.ts                               │
                                               │
    services/                                  │
      participantDataApi.ts  ──────────────────┘

    pages/
      SankeyView.tsx  (integrates component)
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Error Scenarios                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Discussion Not Found (404)                               │
│     ┌─────────────────────────────────────────┐             │
│     │ FastAPI checks discussion exists        │             │
│     │ If not found → HTTPException(404)       │             │
│     │ Frontend shows: "Discussion not found"  │             │
│     │ Action: Verify discussion ID            │             │
│     └─────────────────────────────────────────┘             │
│                                                               │
│  2. Invalid Parameters (422)                                 │
│     ┌─────────────────────────────────────────┐             │
│     │ Pydantic validates query params         │             │
│     │ If invalid → ValidationError            │             │
│     │ Frontend shows: "Invalid parameters"    │             │
│     │ Action: Check round_num, limit values   │             │
│     └─────────────────────────────────────────┘             │
│                                                               │
│  3. Database Error (500)                                     │
│     ┌─────────────────────────────────────────┐             │
│     │ Query fails (connection, syntax, etc.)  │             │
│     │ FastAPI catches → HTTPException(500)    │             │
│     │ Frontend shows: "Failed to load data"   │             │
│     │ Action: Check logs, retry               │             │
│     └─────────────────────────────────────────┘             │
│                                                               │
│  4. Network Error (client-side)                              │
│     ┌─────────────────────────────────────────┐             │
│     │ axios request fails (timeout, CORS)     │             │
│     │ Catch in try/catch                      │             │
│     │ Frontend shows: "Network error"         │             │
│     │ Action: Check network, CORS settings    │             │
│     └─────────────────────────────────────────┘             │
│                                                               │
└─────────────────────────────────────────────────────────────┘

All errors show retry button for manual retry.
```

## Performance Characteristics

```
┌──────────────────────────────────────────────────────────────┐
│                  Performance Metrics                          │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Database Query Time:                                         │
│    Small discussion (<100 participants): 10-30ms              │
│    Medium discussion (<1000 participants): 30-100ms           │
│    Large discussion (>1000 participants): 100-500ms           │
│                                                                │
│  API Response Time (including serialization):                 │
│    Add ~50ms to query time                                    │
│                                                                │
│  Network Time:                                                │
│    Local: 1-5ms                                               │
│    Same datacenter: 5-20ms                                    │
│    Cross-region: 50-200ms                                     │
│                                                                │
│  Frontend Render Time:                                        │
│    Initial render (20 rows): 20-50ms                          │
│    Re-render (filter change): 10-30ms                         │
│                                                                │
│  Total User-Perceived Latency:                                │
│    Small discussion: 100-200ms                                │
│    Large discussion: 200-800ms                                │
│                                                                │
│  Memory Usage:                                                │
│    Backend: O(limit) - only current page in memory           │
│    Frontend: ~100KB for 20 rows                               │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

## Scaling Considerations

```
Current Implementation (MVP):
├─ Works well up to 10,000 participants
├─ Pagination keeps memory bounded
├─ Indexed queries keep performance acceptable
└─ Debounced search reduces load

For >10,000 participants:
├─ Consider full-text search (PostgreSQL FTS)
├─ Add result caching (Redis)
├─ Implement virtual scrolling (frontend)
└─ Consider ElasticSearch for complex searches

For >100,000 participants:
├─ Use read replicas for queries
├─ Implement background indexing
├─ Consider BigQuery or ClickHouse
└─ Add CDN caching for static data
```

## Security Considerations

```
✓ SQL Injection Protected
  └─ SQLAlchemy parameterized queries

✓ XSS Protected
  └─ React auto-escapes rendered text

✓ Privacy Protected
  └─ Returns participant_id, not user_id

✓ Rate Limiting
  └─ API-level rate limiting (100 req/min)

✓ Authorization
  └─ JWT token validation (future: check discussion access)

✗ Not Yet Implemented
  └─ Row-level access control
  └─ Audit logging
  └─ Data anonymization option
```

## Future Architecture Enhancements

```
1. Caching Layer
   ┌───────────────────────────────┐
   │ Redis Cache                   │
   │ - Cache completed discussions │
   │ - TTL: 1 hour                 │
   │ - Invalidate on data change   │
   └───────────────────────────────┘

2. Search Optimization
   ┌───────────────────────────────┐
   │ PostgreSQL Full-Text Search   │
   │ - Create tsvector columns     │
   │ - GIN indexes                 │
   │ - Faster text search          │
   └───────────────────────────────┘

3. Export Feature
   ┌───────────────────────────────┐
   │ Background Job Queue          │
   │ - Celery + Redis              │
   │ - Generate CSV/JSON/Excel     │
   │ - Email download link         │
   └───────────────────────────────┘

4. Real-time Updates
   ┌───────────────────────────────┐
   │ WebSocket Integration         │
   │ - Live discussion updates     │
   │ - Push new rows to table      │
   │ - No manual refresh needed    │
   └───────────────────────────────┘
```

This architecture provides a solid foundation for the Participant Data Table feature with room for future enhancements as usage scales.
