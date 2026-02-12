# API Usage Guide: T035-T036 Endpoints

## Quick Reference

### T035: Real-Time Round Status
```bash
GET /api/v1/rounds/{round_id}/status
```

### T036: Discussion Report
```bash
GET /api/v1/discussions/{discussion_id}/report
```

---

## T035: GET /rounds/{id}/status

### Purpose
Provides real-time round status for frontend countdown timers and progress indicators.

### Example Request
```bash
curl -X GET "http://localhost:8000/api/v1/rounds/550e8400-e29b-41d4-a716-446655440000/status"
```

### Example Response (SUBMISSION_OPEN)
```json
{
  "round_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUBMISSION_OPEN",
  "current_time": "2026-01-29T10:30:15Z",
  "submission_window_end": "2026-01-29T10:35:00Z",
  "approval_deadline": "2026-01-29T10:45:00Z",
  "remaining_time_sec": 285,
  "participant_stats": {
    "submitted_count": 15,
    "approved_count": 0,
    "pending_approval_count": 0
  }
}
```

### Example Response (APPROVING)
```json
{
  "round_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "APPROVING",
  "current_time": "2026-01-29T10:36:00Z",
  "submission_window_end": "2026-01-29T10:35:00Z",
  "approval_deadline": "2026-01-29T10:45:00Z",
  "remaining_time_sec": 540,
  "participant_stats": {
    "submitted_count": 18,
    "approved_count": 12,
    "pending_approval_count": 6
  }
}
```

### Frontend Integration Pattern

#### React Example - Countdown Timer
```typescript
import { useState, useEffect } from 'react';

function RoundCountdownTimer({ roundId }: { roundId: string }) {
  const [status, setStatus] = useState(null);
  
  useEffect(() => {
    const fetchStatus = async () => {
      const response = await fetch(`/api/v1/rounds/${roundId}/status`);
      const data = await response.json();
      setStatus(data);
    };
    
    // Poll every 1 second for real-time updates
    fetchStatus();
    const interval = setInterval(fetchStatus, 1000);
    
    return () => clearInterval(interval);
  }, [roundId]);
  
  if (!status || !status.remaining_time_sec) {
    return <div>No active timer</div>;
  }
  
  const minutes = Math.floor(status.remaining_time_sec / 60);
  const seconds = status.remaining_time_sec % 60;
  
  return (
    <div className="countdown-timer">
      <div className="time-remaining">
        {minutes}:{seconds.toString().padStart(2, '0')}
      </div>
      <div className="phase-label">
        {status.status === 'SUBMISSION_OPEN' ? 'Submission Time' : 'Approval Time'}
      </div>
      <div className="participant-stats">
        Submitted: {status.participant_stats.submitted_count} |
        Approved: {status.participant_stats.approved_count}
      </div>
    </div>
  );
}
```

#### JavaScript Example - Progress Indicator
```javascript
async function updateRoundProgress(roundId) {
  const response = await fetch(`/api/v1/rounds/${roundId}/status`);
  const status = await response.json();
  
  // Update progress bar
  const progressBar = document.getElementById('approval-progress');
  const { submitted_count, approved_count } = status.participant_stats;
  const percentage = (approved_count / submitted_count) * 100;
  progressBar.style.width = `${percentage}%`;
  progressBar.textContent = `${approved_count}/${submitted_count} approved`;
  
  // Update countdown
  if (status.remaining_time_sec !== null) {
    const timer = document.getElementById('countdown');
    const minutes = Math.floor(status.remaining_time_sec / 60);
    const seconds = status.remaining_time_sec % 60;
    timer.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
}

// Poll every 2 seconds
setInterval(() => updateRoundProgress(roundId), 2000);
```

### Error Responses

#### 404 Round Not Found
```json
{
  "error": "not_found",
  "message": "Round 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

### Response Fields Explained

| Field | Type | Description | When Available |
|-------|------|-------------|----------------|
| `round_id` | UUID | Round identifier | Always |
| `status` | String | Current round status | Always |
| `current_time` | DateTime | Server time (for sync) | Always |
| `submission_window_end` | DateTime | When submissions close | After round starts |
| `approval_deadline` | DateTime | When approvals close | After round starts |
| `remaining_time_sec` | Integer\|null | Countdown seconds | During timed phases |
| `participant_stats` | Object\|null | Submission/approval counts | After submissions start |

---

## T036: GET /discussions/{id}/report

### Purpose
Retrieve final discussion report with complete Sankey diagram visualization data.

### Requirements
- Discussion must have status `COMPLETED`
- Returns 400 if discussion not completed

### Example Request
```bash
curl -X GET "http://localhost:8000/api/v1/discussions/550e8400-e29b-41d4-a716-446655440000/report"
```

### Example Response
```json
{
  "discussion_id": "550e8400-e29b-41d4-a716-446655440000",
  "sankey_diagram": {
    "columns": [
      {
        "round_num": 1,
        "thought_spaces": [
          {
            "cluster_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "label": "Remote work increases productivity",
            "member_count": 12,
            "member_pct": 0.60
          },
          {
            "cluster_id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "label": "Hybrid model balances flexibility",
            "member_count": 8,
            "member_pct": 0.40
          }
        ]
      },
      {
        "round_num": 2,
        "thought_spaces": [
          {
            "cluster_id": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "label": "Need clearer communication tools",
            "member_count": 15,
            "member_pct": 0.75
          },
          {
            "cluster_id": "d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "label": "Focus on outcomes not hours",
            "member_count": 5,
            "member_pct": 0.25
          }
        ]
      }
    ],
    "flows": [
      {
        "flow_id": "f0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "source_cluster_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "target_cluster_id": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "participant_count": 10
      },
      {
        "flow_id": "f1eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "source_cluster_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "target_cluster_id": "d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "participant_count": 2
      },
      {
        "flow_id": "f2eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "source_cluster_id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "target_cluster_id": "c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "participant_count": 5
      },
      {
        "flow_id": "f3eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "source_cluster_id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "target_cluster_id": "d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "participant_count": 3
      }
    ]
  },
  "metadata": {
    "total_rounds": 2,
    "total_participants": 20,
    "active_participants": 18,
    "dropout_count": 2,
    "duration_minutes": 32.5,
    "questions": [
      "What are your thoughts on remote work?",
      "How can we improve our remote work policy?"
    ],
    "started_at": "2026-01-29T10:00:00Z",
    "completed_at": "2026-01-29T10:32:30Z"
  }
}
```

### Frontend Integration Pattern

#### React Example - Sankey Diagram
```typescript
import { useEffect, useState } from 'react';
import { Sankey } from 'react-sankey-diagram'; // Example library

function DiscussionReport({ discussionId }: { discussionId: string }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    const fetchReport = async () => {
      try {
        const response = await fetch(`/api/v1/discussions/${discussionId}/report`);
        
        if (response.status === 400) {
          const errorData = await response.json();
          setError('Discussion not yet completed');
          return;
        }
        
        if (!response.ok) {
          throw new Error('Failed to fetch report');
        }
        
        const data = await response.json();
        setReport(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchReport();
  }, [discussionId]);
  
  if (loading) return <div>Loading report...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!report) return null;
  
  return (
    <div className="discussion-report">
      <div className="report-header">
        <h2>Discussion Report</h2>
        <div className="metadata">
          <p>Duration: {report.metadata.duration_minutes} minutes</p>
          <p>Participants: {report.metadata.total_participants} (
            {report.metadata.active_participants} completed,
            {report.metadata.dropout_count} dropped out)
          </p>
          <p>Rounds: {report.metadata.total_rounds}</p>
        </div>
      </div>
      
      <div className="sankey-container">
        <Sankey
          columns={report.sankey_diagram.columns}
          flows={report.sankey_diagram.flows}
          width={1200}
          height={600}
        />
      </div>
      
      <div className="questions">
        <h3>Questions Asked</h3>
        <ol>
          {report.metadata.questions.map((q, i) => (
            <li key={i}>{q}</li>
          ))}
        </ol>
      </div>
    </div>
  );
}
```

#### D3.js Example - Custom Sankey
```javascript
async function renderSankeyDiagram(discussionId, containerId) {
  const response = await fetch(`/api/v1/discussions/${discussionId}/report`);
  const report = await response.json();
  
  const { columns, flows } = report.sankey_diagram;
  
  // Transform data for D3 Sankey
  const nodes = [];
  const links = [];
  
  // Build nodes from columns
  columns.forEach((column, colIndex) => {
    column.thought_spaces.forEach((ts) => {
      nodes.push({
        id: ts.cluster_id,
        name: ts.label,
        round: column.round_num,
        value: ts.member_count
      });
    });
  });
  
  // Build links from flows
  flows.forEach((flow) => {
    links.push({
      source: flow.source_cluster_id,
      target: flow.target_cluster_id,
      value: flow.participant_count
    });
  });
  
  // Render with D3 Sankey
  const sankey = d3.sankey()
    .nodeWidth(15)
    .nodePadding(10)
    .extent([[1, 1], [width - 1, height - 6]]);
  
  const { nodes: sankeyNodes, links: sankeyLinks } = sankey({
    nodes: nodes.map(d => Object.assign({}, d)),
    links: links.map(d => Object.assign({}, d))
  });
  
  // Draw diagram (simplified)
  const svg = d3.select(`#${containerId}`)
    .append('svg')
    .attr('width', width)
    .attr('height', height);
  
  // Add nodes, links, labels...
  // (Full D3 Sankey implementation)
}
```

### Error Responses

#### 400 Discussion Not Completed
```json
{
  "error": "invalid_state",
  "message": "Discussion report only available for COMPLETED discussions. Current status: ACTIVE",
  "details": {
    "discussion_id": "550e8400-e29b-41d4-a716-446655440000",
    "current_status": "ACTIVE",
    "required_status": "COMPLETED"
  }
}
```

#### 404 Discussion Not Found
```json
{
  "error": "not_found",
  "message": "Discussion 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

### Response Fields Explained

#### Sankey Diagram Structure
- **columns**: Array of rounds, each containing thought spaces
- **flows**: Array of participant movements between thought spaces

#### Metadata
- **total_rounds**: Number of completed rounds
- **total_participants**: Unique participants across all rounds
- **active_participants**: Participants who completed the discussion
- **dropout_count**: Participants who dropped out
- **duration_minutes**: Total discussion time
- **questions**: All questions asked (in order)

---

## Performance Considerations

### T035 (Round Status)
- **Polling Frequency**: Recommended 1-5 seconds during active phases
- **Bandwidth**: ~500 bytes per request (minimal)
- **Database Load**: Indexed queries, efficient aggregations
- **Optimization**: Consider WebSocket for production (future enhancement)

### T036 (Discussion Report)
- **Response Size**: Varies by discussion size
  - Small (20 participants, 3 rounds): ~10KB
  - Large (100 participants, 5 rounds): ~100KB+
- **Computation Time**: <100ms for typical discussions
- **Caching**: Immutable after completion (recommended for production)

---

## Testing Endpoints

### Manual Testing with curl

#### Test T035
```bash
# Get round status
curl -X GET \
  "http://localhost:8000/api/v1/rounds/YOUR_ROUND_ID/status" \
  -H "Content-Type: application/json"
```

#### Test T036 (Success)
```bash
# Get completed discussion report
curl -X GET \
  "http://localhost:8000/api/v1/discussions/YOUR_DISCUSSION_ID/report" \
  -H "Content-Type: application/json"
```

#### Test T036 (Error - Not Completed)
```bash
# Try to get report for active discussion (should fail)
curl -X GET \
  "http://localhost:8000/api/v1/discussions/ACTIVE_DISCUSSION_ID/report" \
  -H "Content-Type: application/json"
```

---

## Troubleshooting

### T035 Issues

**Problem**: `remaining_time_sec` is null
- **Cause**: Round not in timed phase (SUBMISSION_OPEN or APPROVING)
- **Solution**: This is expected behavior for other phases

**Problem**: Participant stats showing 0
- **Cause**: No submissions yet, or round in early phase
- **Solution**: Wait for submissions to occur

### T036 Issues

**Problem**: 400 error "Discussion not completed"
- **Cause**: Discussion status is not COMPLETED
- **Solution**: Wait for discussion to complete, or use test data

**Problem**: Empty flows array
- **Cause**: Single-round discussion, or no participant movement
- **Solution**: Expected for single-round discussions

---

## Security Considerations

### Authentication (Future)
Both endpoints will require authentication once auth is implemented:
- Verify user is community member
- Respect discussion visibility settings
- Rate limit report generation requests

### Authorization (Future)
- T035: Any community member can view round status
- T036: Only community members can view reports

---

## Next Steps

1. **Frontend Integration**: Build countdown timer and Sankey visualization components
2. **Testing**: Add integration tests for both endpoints
3. **Monitoring**: Add telemetry for response times and usage patterns
4. **Optimization**: Consider caching and WebSocket upgrades
