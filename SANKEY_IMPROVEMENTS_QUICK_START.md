# Sankey Visualization Improvements - Quick Start Guide

## What Changed?

### 🎯 Round Labels
- **Before:** "Round 1", "Round 2", "Round 3"
- **After:** Actual question text (e.g., "What are the most promising benefits of AI...")
- **Hover:** Full question text in tooltip

### 📏 Layout & Spacing
- **Before:** Columns close together (~150px), fixed width
- **After:** Columns spread out (250px), horizontal scroll for 3+ rounds
- **Benefit:** Better readability, no overlap

### 🌈 Flow Colors
- **Before:** Slate gray (#94a3b8) flat color
- **After:** Gradient from source cluster color → target cluster color
- **Opacity:** Increased from 0.4 to 0.6 for visibility

### ✂️ Cluster Labels
- **Before:** Simple truncation at 40 chars
- **After:** Smart first-sentence extraction at 60 chars
- **Logic:** Tries to end at sentence boundary (. ! ?)

### 📊 Demo Data
- **Before:** 2 rounds
- **After:** 3 rounds with comprehensive AI in Education discussion

## Quick Test

### 1. Start Services
```bash
# Terminal 1: Backend
cd backend
python -m uvicorn src.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

### 2. Run Demo
```bash
cd backend
python run_async_e2e_demo.py
```

**Copy the discussion_id from output:**
```
✅ Created discussion: 12345678-1234-1234-1234-123456789abc
```

### 3. View Sankey
Navigate to:
```
http://localhost:3000/discussions/12345678-1234-1234-1234-123456789abc/sankey
```

### 4. Verify Features

✅ **Round Labels:** Should show question text, not "Round 1"
✅ **Horizontal Scroll:** Try scrolling left/right
✅ **Gradient Colors:** Edges should blend from source to target color
✅ **Smart Labels:** Cluster labels should end at sentence boundaries

## API Changes

### Backend Response
```json
{
  "sankey_graph": {
    "discussion_id": "...",
    "rounds": ["round-uuid-1", "round-uuid-2", "round-uuid-3"],
    "columns": [...],
    "edges": [...]
  },
  "cached": true,
  "round_questions": {
    "round-uuid-1": "What are the most promising benefits...",
    "round-uuid-2": "What concerns should we address...",
    "round-uuid-3": "How can we implement AI..."
  }
}
```

### Frontend Types
```typescript
export interface SankeyGraph {
  discussion_id: string;
  rounds: string[];
  round_questions?: Record<string, string>;  // NEW
  columns: SankeyColumn[];
  edges: SankeyEdge[];
  created_at: string;
  metadata?: Record<string, string> | null;
}
```

## Troubleshooting

### Round labels still show "Round 1"
- Check backend response includes `round_questions` field
- Verify frontend fetches and merges `round_questions` into `sankeyGraph`
- Clear browser cache

### No horizontal scroll
- Verify discussion has 3+ rounds
- Check container has `overflow-x: auto` in CSS
- Confirm SVG width exceeds container width

### Edges still gray (no gradient)
- Check `sourceColor` and `targetColor` props passed to `<SankeyEdge>`
- Verify gradient `<defs>` rendered in SVG
- Inspect edge `fill` attribute (should be `url(#gradient-...)`)

### Labels not truncating at sentences
- Verify `getFirstSentence()` function in `SankeyNode.tsx`
- Check medoid text has sentence boundaries (. ! ?)
- Test with longer text (>60 chars)

## Files to Check

### Backend
- `backend/src/api/routes/sankey.py:330-350` - round_questions query
- `backend/run_async_e2e_demo.py:46-58` - 3-round demo data

### Frontend
- `frontend/src/services/sankeyApi.ts:39` - SankeyGraph interface
- `frontend/src/components/SankeyDiagram/SankeyDiagram.tsx:24-46` - formatRoundQuestion
- `frontend/src/components/SankeyDiagram/SankeyDiagram.tsx:141-158` - Round label rendering
- `frontend/src/components/SankeyDiagram/SankeyDiagram.css:1-31` - Horizontal scroll
- `frontend/src/components/SankeyEdge/SankeyEdge.tsx:105-120` - Gradient definition
- `frontend/src/components/SankeyNode/SankeyNode.tsx:17-48` - getFirstSentence

## Performance Tips

- **Large Discussions (10+ rounds):** Horizontal scroll handles gracefully
- **Many Clusters (50+):** Gradient rendering is GPU-accelerated
- **Long Labels (200+ chars):** Truncation happens client-side (no server overhead)

## Browser Support

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

**Note:** SVG gradients and CSS smooth scrolling are well-supported in modern browsers.

## Need Help?

1. Check full documentation: `SANKEY_VISUALIZATION_IMPROVEMENTS_COMPLETE.md`
2. Run E2E tests: `pytest tests/e2e/test_sankey_visualization.py -v -s`
3. Check browser console for errors
4. Verify backend logs for API issues

---

**Status:** ✅ Ready for testing
**Last Updated:** 2026-02-06
