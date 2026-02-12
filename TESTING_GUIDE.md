# Testing Guide: Sankey Visualization Improvements

## Overview

The Sankey diagram improvements have been implemented. This guide will help you test them using Playwright.

## What Was Implemented

✅ **Round labels** show actual question text (not "Round X")
✅ **Horizontal scroll** enabled with increased column spacing
✅ **Gradient colors** for flow edges (source → target)
✅ **Smart label truncation** using first sentence extraction
✅ **3-round demo data** with AI in Education questions

## Current Status

The demo script ran successfully but only completed 2 of 3 rounds before encountering an error during Sankey generation. However, we have a discussion with data:

**Discussion ID:** `d72d4e69-497c-4909-8e07-a6210c642f76`

## Step-by-Step Testing

### Option 1: Automated Test with Playwright (Recommended)

1. **Start the services** (requires 2 terminals):

   **Terminal 1 - Backend:**
   ```bash
   cd backend
   poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
   ```

   **Terminal 2 - Frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Wait for services to be ready**:
   - Backend: http://localhost:8000/docs
   - Frontend: http://localhost:3000

3. **Run the test script**:
   ```bash
   cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00
   poetry run python test_sankey_improvements.py d72d4e69-497c-4909-8e07-a6210c642f76
   ```

   This will:
   - Open a Chromium browser window
   - Navigate to the Sankey diagram
   - Display verification results in terminal
   - Keep browser open for your inspection
   - Close when you press Ctrl+C

### Option 2: Manual Browser Testing

1. **Start the services** (same as Option 1, steps 1-2)

2. **Open your browser** to:
   ```
   http://localhost:3000/discussions/d72d4e69-497c-4909-8e07-a6210c642f76/sankey
   ```

3. **Verify improvements**:
   - [ ] Round labels show question text (hover for full question)
   - [ ] Horizontal scroll appears if content wider than viewport
   - [ ] Edge colors blend from source to target (not slate gray)
   - [ ] Cluster labels truncated at sentence boundaries

### Option 3: Create Fresh 3-Round Discussion

If you want to test with all 3 rounds:

1. **Fix the demo script** to properly handle 3 rounds:

   The script currently only runs 2 rounds. You need to add Round 3 execution between lines 440-480 in `run_async_e2e_demo.py`.

2. **Run the demo again**:
   ```bash
   cd backend
   poetry run python run_async_e2e_demo.py
   ```

3. **Use the new discussion_id** from the output

## What to Look For

### 1. Round Labels ✨
**Before:** "Round 1", "Round 2"
**After:** "What are the most promising benefits of AI..."

- Hover over labels to see full question text in tooltip
- Questions should be truncated at ~60 chars with "..."

### 2. Horizontal Scroll 📏
**Indicator:** Scrollbar appears at bottom of Sankey container

- Try scrolling left/right if you have 3+ rounds
- Column spacing should be visibly wider (~250px)
- Layout should not feel cramped

### 3. Gradient Colors 🌈
**Before:** Edges were slate gray (#94a3b8)
**After:** Edges blend from source cluster color to target cluster color

- Edges should have gradient fill
- Opacity should be higher than before (0.6 vs 0.4)
- Inspect element: `fill` attribute should be `url(#gradient-...)`

### 4. Smart Label Truncation ✂️
**Before:** Simple cut at 40 chars
**After:** Attempts to end at sentence boundary

- Labels should end with "." or "..."
- Should not cut mid-word
- Maximum 60 chars

## Troubleshooting

### Services Won't Start

**Issue:** "Address already in use" error

**Solution:**
```bash
# Find and kill existing processes
lsof -ti:8000 | xargs kill -9  # Backend
lsof -ti:3000 | xargs kill -9  # Frontend
```

### Frontend Shows White Screen

**Solution:**
```bash
cd frontend
rm -rf node_modules .next
npm install
npm run dev
```

### Backend Database Error

**Solution:**
```bash
cd backend
poetry run alembic upgrade head
```

### Playwright Not Installed

**Solution:**
```bash
cd backend
poetry run playwright install chromium
```

## API Verification

You can also test the backend API directly:

```bash
curl http://localhost:8000/api/v1/sankey/d72d4e69-497c-4909-8e07-a6210c642f76 | jq .
```

**Expected response:**
```json
{
  "sankey_graph": {
    "discussion_id": "...",
    "rounds": ["uuid-1", "uuid-2"],
    "columns": [...],
    "edges": [...]
  },
  "cached": true,
  "round_questions": {
    "uuid-1": "What are the most promising benefits...",
    "uuid-2": "What concerns should we address..."
  }
}
```

**Verify:** `round_questions` field exists and contains question text.

## Quick Verification Checklist

- [ ] Backend running on port 8000
- [ ] Frontend running on port 3000
- [ ] Browser opens to Sankey page
- [ ] Round labels show question text
- [ ] Hover shows full question in tooltip
- [ ] Edges use gradient colors (inspect fill attribute)
- [ ] Cluster labels end at sentence boundaries
- [ ] Horizontal scroll works (if applicable)
- [ ] No console errors in browser dev tools

## Screenshots

After testing, take screenshots to document:
1. Full Sankey diagram view
2. Round label with hover tooltip
3. Gradient edge colors (inspect element)
4. Horizontal scroll in action (if 3+ rounds)

## Need Help?

- Check `SANKEY_VISUALIZATION_IMPROVEMENTS_COMPLETE.md` for full documentation
- Check `SANKEY_IMPROVEMENTS_QUICK_START.md` for quick reference
- Inspect browser console for errors
- Check backend logs for API issues

---

**Status:** Ready for testing
**Last Updated:** 2026-02-06
