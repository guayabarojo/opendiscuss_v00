# Sankey Improvements - Testing Guide

## Quick Start Testing

### 1. Start the Application

```bash
# Terminal 1 - Backend
cd backend
python -m uvicorn src.main:app --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

### 2. Navigate to a Sankey Diagram

Visit: `http://localhost:5173/discussions/{discussion_id}/sankey`

Replace `{discussion_id}` with a completed discussion that has clustering data.

**Example discussion IDs** (if available):
- Check your database for completed discussions
- Run: `python backend/create_large_scale_discussion.py` to create test data

---

## Visual Inspection Checklist

### ✅ Node Spacing (Phase 5)
**What to look for**:
- Nodes should be tightly packed with minimal gaps (1px)
- Should look like a traditional Sankey diagram
- No large vertical whitespace between nodes in same column

**Before**: 15px gaps made diagram look scattered
**After**: 1px gaps create cohesive flow appearance

---

### ✅ Short Labels (Phase 3)
**What to look for**:
- Labels show only first 4 words + "..."
- Labels are easy to scan quickly
- Full text still available in tooltip on hover

**Examples**:
- "AI tutoring systems provide..." (instead of full sentence)
- "Over-reliance on AI could..." (instead of full sentence)
- "Public funding for AI..." (instead of full sentence)

**Test**:
1. Hover over several nodes
2. Verify short label inside node
3. Verify full label in tooltip

---

### ✅ Labels Inside Nodes (Phase 4)
**What to look for**:
- Labels are white text **inside** colored node rectangles
- Labels are centered horizontally and vertically
- Participant count appears below label (if space permits)
- No need to hover to see label text

**Before**: Labels were positioned outside nodes to the right
**After**: Labels are inside nodes, always visible

**Test**:
1. Check that labels are visible without hovering
2. Verify white text has good contrast against node colors
3. Confirm text-shadow makes text readable on all backgrounds

---

### ✅ Cluster Granularity Slider (Phases 1 & 2)
**What to look for**:
- Slider control appears above Sankey diagram
- Blue-themed panel with left border accent
- Shows current threshold: "Showing clusters with X+ participants"
- Three label positions: "All Details" | "Balanced" | "Major Themes"

**Test 1: Default View**
1. On page load, slider should be at ~5 (medium detail)
2. Should show approximately 20-30 major clusters
3. Label reads "Showing clusters with 5+ participants"

**Test 2: Show All Details**
1. Move slider all the way left (to 2)
2. Should show all clusters (e.g., 344 clusters)
3. Label reads "Showing clusters with 2+ participants"
4. Verify small minority clusters (1-2 participants) become visible

**Test 3: Major Themes Only**
1. Move slider all the way right (to max, e.g., 15)
2. Should show only largest clusters
3. Label reads "Showing clusters with 15+ participants"
4. Verify only strong consensus clusters remain

**Test 4: Edge Filtering**
1. Move slider to middle position
2. Verify edges (flows) only connect visible clusters
3. No "dangling" edges pointing to hidden clusters

**Test 5: Participant Count Accuracy**
1. After filtering, column participant counts should reflect visible clusters only
2. Check bottom of each column for "X participants" label
3. Verify counts decrease as you hide small clusters

---

## Interactive Testing

### Test 1: Real-time Slider Response
1. Click on slider and drag slowly from left to right
2. **Expected**: Nodes disappear/reappear smoothly
3. **Expected**: No lag or delay
4. **Expected**: Edges update in sync with nodes

### Test 2: Label Truncation Edge Cases
1. Find a cluster with exactly 4 words
   - **Expected**: No "..." appended
2. Find a cluster with 5+ words
   - **Expected**: Shows first 4 words + "..."
3. Find a cluster with very long first word
   - **Expected**: Still shows first 4 words (doesn't break)

### Test 3: Small Node Behavior
1. Set slider to show all details (left position)
2. Find very small nodes (1-2 participants)
3. **Expected**: Nodes with height < 15px don't show labels (prevents overlap)
4. **Expected**: Nodes with height 15-30px show label only (no count)
5. **Expected**: Nodes with height > 30px show both label and count

### Test 4: Tooltip Still Works
1. Hover over any node
2. **Expected**: Tooltip appears with full cluster text
3. **Expected**: Tooltip shows participant count and percentage
4. **Expected**: Tooltip shows display_group_id (if available)

---

## Cross-Browser Testing

### Chrome/Edge
- [ ] Slider thumb is circular and blue
- [ ] Labels render correctly inside nodes
- [ ] No layout issues

### Firefox
- [ ] Slider styling matches Chrome (check `-moz-range-thumb`)
- [ ] Text rendering is smooth
- [ ] Performance is acceptable

### Safari (if available)
- [ ] Slider styling works (`-webkit-slider-thumb`)
- [ ] SVG text positioning correct
- [ ] No font rendering issues

---

## Responsive Testing

### Desktop (1920x1080)
- [ ] Slider is easy to grab and drag
- [ ] Labels are readable
- [ ] Diagram fits horizontally (with scroll)

### Tablet (768px)
- [ ] Slider control adapts to smaller width
- [ ] Labels remain visible
- [ ] Touch interaction works

### Mobile (375px)
- [ ] Slider is touch-friendly
- [ ] Labels don't overlap
- [ ] Diagram is scrollable

---

## Performance Testing

### Large Discussion (100+ participants, 10 rounds)
1. Load Sankey diagram
2. Move slider rapidly left-right multiple times
3. **Expected**: No lag or stutter
4. **Expected**: Filtering completes in < 100ms

### Many Clusters (300+ clusters)
1. Set slider to minimum (show all)
2. Check page responsiveness
3. **Expected**: Page remains interactive
4. **Expected**: Scrolling is smooth

---

## Metadata Verification

### Backend Response Check
1. Open browser DevTools (Network tab)
2. Load Sankey diagram
3. Find GET request to `/api/v1/sankey/{discussion_id}`
4. Inspect response JSON

**Expected metadata**:
```json
{
  "metadata": {
    "construction_time_ms": 1234,
    "cluster_size_distribution": {
      "min": 1,
      "max": 45,
      "median": 8,
      "total_clusters": 344
    },
    "cluster_granularity_suggestions": {
      "high_detail": 2,
      "medium_detail": 5,
      "low_detail": 12
    }
  }
}
```

5. Verify `cluster_granularity_suggestions.low_detail` matches slider max value

---

## Edge Cases

### Case 1: Single Cluster Per Round
- **Scenario**: Discussion with only 1 cluster per round
- **Expected**: Slider has no visible effect (all clusters always visible)
- **Status**: Expected behavior

### Case 2: All Clusters Same Size
- **Scenario**: All clusters have exactly 5 participants
- **Expected**: Slider at 5 shows all, slider at 6 shows none
- **Status**: Expected behavior

### Case 3: No Metadata
- **Scenario**: Old Sankey graph without metadata
- **Expected**: Slider defaults to max=15, still functional
- **Status**: Graceful degradation

### Case 4: Very Small Discussion (5 participants)
- **Scenario**: Discussion with only 5 total participants
- **Expected**: Most clusters have 1-2 participants, slider shows all by default
- **Status**: Works as designed

---

## Regression Testing

### Ensure No Breaking Changes
- [ ] Existing Sankey diagrams load correctly
- [ ] All original features still work:
  - [ ] Node hover shows tooltip
  - [ ] Edges render correctly
  - [ ] Colors are consistent
  - [ ] Round labels appear
  - [ ] Participant counts show at bottom
- [ ] No console errors
- [ ] No TypeScript compilation errors

---

## Acceptance Criteria

### Must Pass
✅ **Phase 5**: Nodes are tightly packed (1px gaps)
✅ **Phase 3**: Labels show first 4 words max
✅ **Phase 4**: Labels visible inside nodes without hover
✅ **Phase 1**: Backend returns cluster size metadata
✅ **Phase 2**: Slider controls cluster visibility dynamically

### Nice to Have
- [ ] Slider has smooth animation when adjusting
- [ ] Cluster count indicator (e.g., "25 of 344 clusters shown")
- [ ] Preset buttons for common granularity levels
- [ ] Remember user's last slider position

---

## Known Issues (Not Bugs)

1. **Very small nodes (< 15px height) don't show labels**
   - Intentional: prevents label overlap and clutter
   - Tooltip still shows full info on hover

2. **Slider max value varies by discussion**
   - Expected: based on participant distribution
   - Larger discussions → higher max value

3. **Filtering recalculates percentages**
   - Intentional: visible nodes should sum to 100%
   - Original percentages available in tooltip

---

## Reporting Issues

If you find a bug, please report:
1. **What you did**: Step-by-step reproduction
2. **What you expected**: Desired behavior
3. **What happened**: Actual behavior
4. **Browser/OS**: Chrome 120 on Windows 11, etc.
5. **Screenshot**: If visual issue
6. **Console errors**: Check browser console for errors

---

## Success Metrics

After testing, the improvements should deliver:
- ✅ **Clarity**: Users can quickly understand major themes
- ✅ **Control**: Users can drill down to minority views
- ✅ **Visibility**: Labels visible without hover
- ✅ **Aesthetics**: Diagram looks like traditional Sankey (tightly packed)
- ✅ **Performance**: Filtering is instant (no lag)
