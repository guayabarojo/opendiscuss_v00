# User Story 5: Last-Approved-Wins Testing Guide

**Feature**: Multiple Submissions with Last-Approved-Wins
**Testing Date**: 2026-02-01

## Quick Test Scenarios

### Scenario 1: Basic Last-Approved-Wins

**Goal**: Verify that approving a second summary marks the first as SUPERSEDED.

**Steps**:
1. Create a participant and round
2. Submit first input, generate summary A, approve it
3. Submit second input, generate summary B, approve it
4. Verify summary A status = SUPERSEDED
5. Verify summary B status = APPROVED

**Expected Result**:
- Summary A: `status = 'superseded'`, has `approved_at` timestamp
- Summary B: `status = 'approved'`, has later `approved_at` timestamp
- Event handler forwards only Summary B to Spec 4

**API Test**:
```bash
# Approve first summary
curl -X POST http://localhost:8000/api/v1/summaries/{summary_a_id}/approve

# Approve second summary
curl -X POST http://localhost:8000/api/v1/summaries/{summary_b_id}/approve

# Get all summaries for participant
curl http://localhost:8000/api/v1/summaries/participant/{participant_id}/round/{round_id}
```

**Expected Response**:
```json
[
  {
    "summary_id": "summary_b_id",
    "status": "approved",
    "approved_at": "2026-02-01T10:05:00Z",
    ...
  },
  {
    "summary_id": "summary_a_id",
    "status": "superseded",
    "approved_at": "2026-02-01T10:00:00Z",
    ...
  }
]
```

### Scenario 2: Multiple Sequential Approvals

**Goal**: Test that last-approved-wins works with 3+ submissions.

**Steps**:
1. Create participant and round
2. Submit and approve summary A (10:00)
3. Submit and approve summary B (10:05)
4. Submit and approve summary C (10:10)

**Expected Result**:
- Summary A: SUPERSEDED
- Summary B: SUPERSEDED
- Summary C: APPROVED
- Only Summary C forwarded to Spec 4

### Scenario 3: Frontend Multiple Submissions View

**Goal**: Verify UI shows all submissions with correct status indicators.

**Steps**:
1. Navigate to ApprovalInterface with `?summaryId=X&participantId=Y&roundId=Z`
2. Approve first summary
3. Submit second input
4. Observe "Show All Submissions" button appears
5. Click button to view all submissions
6. Verify first summary shows "SUPERSEDED" badge (orange)
7. Verify second summary shows "PENDING_REVIEW" badge (yellow)

**Expected UI**:
- Multiple submissions notice at top
- "Show All Submissions" toggle button
- When toggled: list of all summaries in chronological order
- Color-coded status badges
- Superseded notice on old summaries

### Scenario 4: Event Handler Validation

**Goal**: Verify event handler correctly selects last-approved summary.

**Steps**:
1. Create multiple participants with approved summaries
2. Trigger summarization.complete event
3. Verify event payload contains exactly one summary per participant
4. Verify it's the most recently approved summary

**Expected Logs**:
```
[Spec 3→4] Collected N approved summaries for round {round_id}
(last-approved-wins applied, total approved in DB: M)
```

Where N = number of participants, M >= N

### Scenario 5: No Previous Approvals

**Goal**: Verify first approval doesn't break when no previous approvals exist.

**Steps**:
1. Create new participant and round
2. Submit input, generate summary
3. Approve summary

**Expected Result**:
- Summary status = APPROVED
- No errors in logs
- `_apply_last_approved_wins()` returns 0 (no summaries superseded)

## Automated Test Suite

### Running Tests

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend
pytest tests/test_last_approved_wins.py -v
```

### Test Coverage

1. **test_superseded_status_exists**: Verifies enum has SUPERSEDED status
2. **test_last_approved_wins_logic**: Tests core supersession logic
3. **test_get_last_approved_summary_for_participant**: Tests query method
4. **test_approved_at_in_summary_response**: Verifies timestamp field

### Expected Output

```
tests/test_last_approved_wins.py::test_superseded_status_exists PASSED
tests/test_last_approved_wins.py::test_last_approved_wins_logic PASSED
tests/test_last_approved_wins.py::test_get_last_approved_summary_for_participant PASSED
tests/test_last_approved_wins_py::test_approved_at_in_summary_response PASSED

==================== 4 passed in X.XXs ====================
```

## Manual Testing Checklist

### Backend
- [ ] SUPERSEDED status exists in database enum
- [ ] Approving second summary marks first as SUPERSEDED
- [ ] `approved_at` timestamp set correctly
- [ ] Logs show supersession events
- [ ] Event handler validates one summary per participant
- [ ] GET /participant/{id}/round/{id} returns all summaries
- [ ] Summaries ordered by approved_at DESC

### Frontend
- [ ] SummaryReview shows SUPERSEDED badge (orange)
- [ ] SummaryReview shows approved_at timestamp
- [ ] ApprovalInterface shows multiple submissions notice
- [ ] "Show All Submissions" button appears when >1 summary
- [ ] Clicking button shows all summaries
- [ ] All summaries view shows status badges
- [ ] Superseded summaries have faded appearance
- [ ] Superseded notice explains last-approved-wins

### Integration
- [ ] Approving summary triggers ApprovalService
- [ ] ApprovalService marks old approvals as SUPERSEDED
- [ ] Event handler forwards only latest to Spec 4
- [ ] Frontend refreshes after approval to show new status

## Edge Cases to Test

### 1. Concurrent Approvals
**Setup**: Two users approve two different summaries for same participant simultaneously

**Expected**: Timestamp ordering determines winner (later approved_at wins)

### 2. Approve → Supersede → Query
**Setup**:
1. Approve Summary A
2. Approve Summary B (A becomes SUPERSEDED)
3. Query summaries for participant

**Expected**: Both returned, ordered by approved_at DESC (B, then A)

### 3. Participant with No Summaries
**Setup**: Query summaries for participant with no submissions

**Expected**: Empty array `[]`, no errors

### 4. Round Completion with Mixed Status
**Setup**:
- Participant 1: APPROVED (latest), SUPERSEDED (old)
- Participant 2: PENDING_REVIEW
- Participant 3: REJECTED

**Expected**: Event handler only forwards Participant 1's APPROVED summary

## Performance Testing

### Load Test: Multiple Participants

**Setup**:
- 100 participants
- Each submits 3 times and approves all
- Measure time for event handler to process

**Expected**:
- Query executes in <100ms
- Event handler processes in <500ms
- 100 summaries forwarded (one per participant)
- 200 summaries marked as SUPERSEDED

### Database Query Performance

**Test Query**:
```sql
SELECT * FROM summaries
WHERE participant_id = ?
  AND round_id = ?
ORDER BY approved_at DESC NULLS LAST, created_at DESC;
```

**Expected**: Uses composite index, <10ms execution time

## Monitoring During Testing

### Key Metrics

1. **Supersession Count**:
   - Count of summaries with status=SUPERSEDED per round
   - Should match: (total approvals) - (number of participants)

2. **Validation Failures**:
   - Count of log entries with "VALIDATION FAILED"
   - Should be: 0

3. **Event Handler Success Rate**:
   - Percentage of summarization.complete events successfully emitted
   - Should be: 100%

### Log Monitoring

**Watch logs for**:
```bash
# Supersession events
grep "Last-Approved-Wins.*Superseded" backend/logs/app.log

# Validation failures (should be empty)
grep "VALIDATION FAILED" backend/logs/app.log

# Event emissions
grep "Emitted summarization.complete" backend/logs/app.log
```

## Rollback Plan

If issues found during testing:

1. **Database**: SUPERSEDED status already in migration, no rollback needed
2. **Backend Logic**: Can disable `_apply_last_approved_wins()` call in `approve_summary()`
3. **Frontend**: Can hide "Show All Submissions" button by setting feature flag
4. **Event Handler**: Falls back to last-approved-wins selection even if validation fails

## Success Criteria

✅ All automated tests pass
✅ Manual checklist complete
✅ No validation failures in logs
✅ Frontend correctly displays multiple submissions
✅ Event handler forwards exactly one summary per participant
✅ Performance within acceptable limits (<500ms for 100 participants)

## Post-Testing Actions

1. Review logs for any warnings or errors
2. Verify database indexes are being used (EXPLAIN ANALYZE)
3. Check frontend network tab for API call efficiency
4. Document any edge cases discovered
5. Update integration test suite with findings

## Contact

For questions or issues during testing, reference:
- Implementation Summary: `US5_LAST_APPROVED_WINS_IMPLEMENTATION.md`
- Spec 003 Plan: `/specs/003-summarization-approval/plan.md`
- Code: `/backend/src/summarization/services/approval_service.py`
