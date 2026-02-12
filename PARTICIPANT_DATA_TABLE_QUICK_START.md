# Participant Data Table - Quick Start Guide

## What is it?

A responsive, paginated table component that displays participant submission data below the Sankey diagram. Shows raw inputs, summaries, and cluster assignments for all participants across all rounds.

## Quick Access

**URL**: `/discussions/{discussion_id}/sankey`

**Location**: Below the Sankey diagram on the Sankey View page

## API Endpoint

```
GET /api/v1/participant-data/{discussion_id}
```

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `round_num` | integer | None | Filter by specific round (1-indexed) |
| `search` | string | None | Search in raw input, summary, cluster label |
| `limit` | integer | 20 | Rows per page (max 100) |
| `offset` | integer | 0 | Pagination offset |

### Example Requests

```bash
# Get first page (20 rows)
curl http://localhost:8000/api/v1/participant-data/{discussion_id}

# Filter by round 2
curl http://localhost:8000/api/v1/participant-data/{discussion_id}?round_num=2

# Search for "climate"
curl http://localhost:8000/api/v1/participant-data/{discussion_id}?search=climate

# Get page 2 (rows 21-40)
curl http://localhost:8000/api/v1/participant-data/{discussion_id}?limit=20&offset=20

# Combine filters
curl http://localhost:8000/api/v1/participant-data/{discussion_id}?round_num=1&search=climate&limit=10
```

### Response Format

```json
{
  "data": [
    {
      "round_num": 1,
      "round_id": "550e8400-e29b-41d4-a716-446655440000",
      "participant_id": "650e8400-e29b-41d4-a716-446655440000",
      "submission_id": "750e8400-e29b-41d4-a716-446655440000",
      "raw_input": "We need to address climate change urgently...",
      "summary": "Urgent climate action needed.",
      "cluster_id": "850e8400-e29b-41d4-a716-446655440000",
      "cluster_label": "Climate action and environmental concerns",
      "cluster_size": 15
    }
  ],
  "total": 100,
  "discussion_id": "550e8400-e29b-41d4-a716-446655440000",
  "rounds": 3
}
```

## Component Usage

### Import

```tsx
import { ParticipantDataTable } from '../components/ParticipantDataTable';
```

### Basic Usage

```tsx
<ParticipantDataTable discussionId={discussionId} />
```

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `discussionId` | string | Yes | Discussion UUID |

## Features

### 1. Round Filtering

Select specific round from dropdown:
- "All Rounds" - Shows data from all rounds
- "Round 1", "Round 2", etc. - Shows only selected round

### 2. Search

Type in search box to filter results:
- Searches across raw input, summary, and cluster label
- Case-insensitive
- Debounced (500ms delay)
- Clear button (×) to reset search

### 3. Pagination

Navigate through data:
- 20 rows per page
- "Previous" and "Next" buttons
- Page indicator shows current page and total pages
- Info text shows "Showing X-Y of Z rows"

### 4. Data Display

**Columns**:
1. **Round** - Round number (1-indexed)
2. **Participant ID** - Truncated UUID (hover for full)
3. **Raw Input** - Original submission or "(Deleted - ephemeral data)"
4. **Summary** - Approved summary text
5. **Cluster** - Truncated cluster UUID
6. **Cluster Label** - Medoid summary (cluster name)
7. **Cluster Size** - Number of participants in cluster

**Text Handling**:
- Long text truncated to 100 characters
- Hover over cell to see full text in tooltip
- "N/A" shown for null values

## Database Schema

### Tables Queried

```sql
-- Main query structure
SELECT
    r.round_num,
    r.round_id,
    aps.participant_id,
    aps.submission_id,
    aps.summary_text,
    aps.cluster_id,
    ts.label_summary,
    ts.member_count,
    s.submission_text  -- May be NULL (ephemeral)
FROM approved_summaries aps
JOIN rounds r ON aps.round_id = r.round_id
JOIN thought_spaces ts ON aps.cluster_id = ts.cluster_id
LEFT OUTER JOIN submissions s ON aps.submission_id = s.submission_id
WHERE r.discussion_id = ?
ORDER BY r.round_num ASC, aps.participant_id ASC;
```

### Why Outer Join?

Submissions are **ephemeral** and deleted after approval + 5 minute grace period. The outer join allows showing approved summaries even after raw submissions are deleted.

## File Structure

```
backend/
  src/
    api/
      routes/
        participant_data.py          # API endpoint
    main.py                          # Route registration
  tests/
    api/
      test_participant_data_endpoint.py  # Tests

frontend/
  src/
    components/
      ParticipantDataTable/
        ParticipantDataTable.tsx     # Component
        ParticipantDataTable.css     # Styles
        index.ts                     # Exports
    services/
      participantDataApi.ts          # API client
    pages/
      SankeyView.tsx                 # Integration
```

## Development

### Adding the Component to a Page

```tsx
import { ParticipantDataTable } from '../components/ParticipantDataTable';

function MyPage() {
  const { discussionId } = useParams();

  return (
    <div>
      {/* Other content */}
      <ParticipantDataTable discussionId={discussionId} />
    </div>
  );
}
```

### Customizing Styles

Edit `frontend/src/components/ParticipantDataTable/ParticipantDataTable.css`:

```css
/* Example: Change row hover color */
.participant-data-table tbody tr:hover {
  background: #f0f9ff; /* Light blue */
}

/* Example: Adjust table font size */
.participant-data-table {
  font-size: 0.9rem; /* Larger */
}
```

### Testing the API

```python
# backend/tests/api/test_participant_data_endpoint.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_my_scenario(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/participant-data/your-discussion-id"
    )
    assert response.status_code == 200
```

## Common Scenarios

### Scenario 1: Debugging Cluster Assignments

**Goal**: See which participants are in a specific cluster

1. Navigate to Sankey view
2. Note cluster label from diagram
3. Search for cluster label in table
4. See all participants in that cluster

### Scenario 2: Tracking Participant Journey

**Goal**: See a participant's input across all rounds

1. Navigate to Sankey view
2. Copy participant ID from table
3. Use browser's find (Ctrl+F / Cmd+F)
4. Search for participant ID
5. See all rows for that participant

### Scenario 3: Comparing Raw Input to Summary

**Goal**: Verify summary accuracy

1. Find row in table
2. Compare "Raw Input" column to "Summary" column
3. Check if summary preserves intent

### Scenario 4: Analyzing Round Participation

**Goal**: See how many participants submitted in each round

1. Filter by "Round 1", note row count
2. Filter by "Round 2", note row count
3. Compare counts to identify dropouts

## Performance Tips

### For Large Discussions

1. **Use Round Filtering**: Reduces data volume
2. **Search Specifically**: Narrow results before pagination
3. **Limit Results**: Use smaller page sizes if needed

### For Slow Queries

1. Check database indexes exist:
   - `idx_approved_summary_round_participant`
   - `idx_approved_summary_cluster`
   - `idx_approved_summary_round`
2. Consider caching for completed discussions
3. Monitor query execution time in logs

## Troubleshooting

### Empty Table

**Symptoms**: Table shows "No participant data found"

**Causes**:
1. Discussion has no approved summaries
2. Clustering hasn't completed yet
3. Filters exclude all data

**Solutions**:
1. Verify discussion completed clustering
2. Check `approved_summaries` table has data
3. Clear filters (select "All Rounds", clear search)

### Missing Raw Input

**Symptoms**: All rows show "(Deleted - ephemeral data)"

**Explanation**: Normal behavior after 5-minute grace period

**Why**: Raw submissions are ephemeral per constitutional principles. They're deleted after summary approval + grace period.

**Not a bug**: Approved summaries are canonical representation.

### Slow Loading

**Symptoms**: Table takes >3 seconds to load

**Causes**:
1. Large discussion (>1000 participants)
2. Missing database indexes
3. Inefficient search query

**Solutions**:
1. Use round filtering to reduce dataset
2. Verify indexes with `EXPLAIN ANALYZE`
3. Consider pagination with smaller page size

## API Integration Examples

### React Hook

```tsx
import { useState, useEffect } from 'react';
import { fetchParticipantData } from '../services/participantDataApi';

function useParticipantData(discussionId: string) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const result = await fetchParticipantData(discussionId);
        setData(result);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [discussionId]);

  return { data, loading, error };
}
```

### Python Request

```python
import requests

def get_participant_data(discussion_id, round_num=None):
    url = f"http://localhost:8000/api/v1/participant-data/{discussion_id}"
    params = {"round_num": round_num} if round_num else {}

    response = requests.get(url, params=params)
    response.raise_for_status()

    return response.json()

# Usage
data = get_participant_data("550e8400-...")
print(f"Total rows: {data['total']}")
print(f"Rounds: {data['rounds']}")
```

## References

- **Full Documentation**: `PARTICIPANT_DATA_TABLE_IMPLEMENTATION.md`
- **API Spec**: `backend/src/api/routes/participant_data.py`
- **Component Code**: `frontend/src/components/ParticipantDataTable/`
- **Tests**: `backend/tests/api/test_participant_data_endpoint.py`
