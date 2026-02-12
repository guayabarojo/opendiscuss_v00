# Discussion Creation Flow Test Report

**Date:** 2026-02-06
**Test:** End-to-end discussion creation and live page flow
**Status:** FAILED (Page crashes after starting discussion)

## Test Overview

Created comprehensive Playwright E2E test that walks through the complete user journey:

1. Navigate to `/discussions/create` ✅
2. Fill form with constitutionally valid questions ✅
3. Submit form ✅
4. Verify redirect to `/discussions/:id/live` ✅
5. Click "Start Discussion" button ✅
6. Verify Round 1 status displays **❌ FAILED**

## What Works

The test successfully validates:
- Create page loads correctly
- Form accepts constitutional questions (What/How, no ranking, exploratory)
- Form validation (community selection, question length 10-200 chars)
- Discussion creation API call
- Redirect to live page
- Start Discussion button functionality
- Backend successfully starts discussion (status changes to ACTIVE in backend)

## Critical Bug Discovered

### Error: Page Crash After Starting Discussion

**Location:** `/frontend/src/pages/DiscussionLive.tsx:157`

**Error Message:**
```
TypeError: Cannot read properties of undefined (reading 'submitted_count')
```

**Root Cause:**
```tsx
// Line 157 - INCORRECT
{roundStatus?.participant_stats.submitted_count || 0}

// Should be:
{roundStatus?.participant_stats?.submitted_count ?? 0}
```

The optional chaining `?.` only applies to `roundStatus`, but then tries to access `.participant_stats.submitted_count` without checking if `participant_stats` exists.

### Additional 404 Error

The browser console also shows:
```
Failed to load resource: the server responded with a status of 404 (Not Found)
```

This suggests the round status API endpoint might not be returning the expected data structure or the endpoint URL is incorrect.

## Backend Status

Manual testing confirms:
- Discussion creates successfully
- Start endpoint returns success
- Discussion status changes to ACTIVE in database
- Current round advances to 1

Example:
```bash
curl -s http://localhost:8000/api/v1/discussions/374a472c-7193-40fe-b80a-7ee93dba657c
# Returns: "status": "ACTIVE", "current_round_num": 1, "started_at": "2026-02-06T06:56:47.829944"
```

## Impact

**Severity:** HIGH - Blocks all users from using live discussion page after starting

**User Experience:**
1. Host creates discussion successfully
2. Host clicks "Start Discussion"
3. Page crashes with white screen/error boundary
4. Discussion is actually started in backend, but UI is broken
5. Users cannot view round status, submit inputs, or participate

## Related Tasks

This issue is related to existing task #1:
- "Fix DiscussionLive page window endpoint mismatch"

## Test Files Created

**Test:** `/frontend/tests/e2e/test_discussion_creation_flow.spec.ts`
- Main flow test with screenshots
- Form validation test
- API error handling test

**Config:** `/frontend/playwright.config.test.ts`
- Custom config for testing with existing running servers
- No webServer startup (uses localhost:3000 and localhost:8000)

**Screenshots:**
- `01-create-page-loaded.png` ✅
- `02-form-filled.png` ✅
- `04-live-page-loaded.png` ✅
- `05-after-start-clicked.png` ❌ (shows error state)

## Recommended Fixes

### Immediate Fix (DiscussionLive.tsx)

Fix all unsafe optional chaining on line 157:

```tsx
// BEFORE (line 157)
{roundStatus?.participant_stats.submitted_count || 0} submitted

// AFTER
{roundStatus?.participant_stats?.submitted_count ?? 0} submitted
```

Also check lines 203, 209, 215 for similar issues in the participant stats section.

### Root Cause Investigation

1. **Check Round Status API Response:**
   ```bash
   # When discussion is ACTIVE, what does this return?
   curl -s http://localhost:8000/api/v1/rounds/{round_id}/status
   ```

2. **Verify Data Structure:**
   - Does `participant_stats` exist in the response?
   - Is the endpoint URL correct?
   - Is there a 404 happening on round status polling?

3. **Add Defensive Checks:**
   - Handle missing `participant_stats` gracefully
   - Show default/placeholder values when data isn't available
   - Add loading states for API calls

### Testing Improvements

Once fixed, re-run:
```bash
cd frontend
npx playwright test test_discussion_creation_flow.spec.ts --project=chromium --config=playwright.config.test.ts
```

## Constitutional Questions Used in Test

These questions passed all 5 validation checks:

1. "What perspectives do community members have on local transportation needs?" (75 chars)
2. "How could we improve communication between different community groups?" (72 chars)
3. "What approaches might help address environmental concerns in our neighborhood?" (79 chars)

All questions:
- Start with "What" or "How" ✅
- Are 10-200 characters ✅
- Avoid "Why", "Do you", "Should we" ✅
- Contain no ranking keywords ✅
- Are not binary choice questions ✅

## Next Steps

1. Fix the optional chaining bug on line 157 (and similar lines)
2. Investigate the 404 error for round status endpoint
3. Ensure `participant_stats` is always present in round status response (or handle its absence)
4. Re-run the Playwright test to verify the fix
5. Update task #1 status to completed

## Test Execution Details

**Command:**
```bash
cd frontend
npx playwright test test_discussion_creation_flow.spec.ts --project=chromium --config=playwright.config.test.ts --grep "should create discussion"
```

**Duration:** ~60 seconds (test timeout)

**Browser:** Chromium (Desktop Chrome)

**Services:**
- Backend: http://localhost:8000 ✅
- Frontend: http://localhost:3000 ✅

## Files Modified

- Created: `/frontend/tests/e2e/test_discussion_creation_flow.spec.ts` (299 lines)
- Created: `/frontend/playwright.config.test.ts` (27 lines)
- Created: `/frontend/screenshots/` (4 screenshots)

## Console Error Stack Trace

```
Page error: Cannot read properties of undefined (reading 'submitted_count')

ErrorBoundary caught error: TypeError: Cannot read properties of undefined (reading 'submitted_count')
    at DiscussionLive (http://localhost:3000/src/pages/DiscussionLive.tsx:196:41)
    at renderWithHooks
    at updateFunctionComponent
    at beginWork
    ...
```

Component crashed in React error boundary, preventing any further UI interaction.
