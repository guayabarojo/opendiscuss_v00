# Theme-Based Discussion Generation - Quick Guide

## ✅ Good News

**You already have a working discussion generator!**

File: `backend/create_varied_discussion.py`

## 🎯 How to Get Realistic Clustering (7±2 Clusters)

The key is to modify the response generation to use **theme-based vocabulary** instead of truly random responses.

### Current Behavior (Random):
```python
response = f"{random.choice(ACTIONS)} + {random.choice(CONTEXTS)}"
# Result: "blockchain supply chain" + "mental health remote work" = 0 clusters (correct!)
```

### Needed Behavior (Theme-Based):
```python
# Each participant assigned to 1-2 themes
participant_themes = {
    "participant_1": ["cost_reduction"],
    "participant_2": ["cost_reduction", "transparency"],
    ...
}

# 75% of responses use primary theme vocabulary
if random.random() < 0.75:
    vocabulary = COST_REDUCTION_VOCAB
else:
    vocabulary = random theme

response = f"{random.choice(vocabulary)}"
# Result: "reduce costs" + "cut expenses" + "save money" = 1 cluster!
```

## 📝 Quick Fix for create_varied_discussion.py

### Step 1: Define 7 Theme Vocabularies

Add after line 23 (after RANDOM_PARTICIPANTS):

```python
# 7 Major Themes for Realistic Clustering
THEME_VOCABULARIES = {
    "cost_efficiency": [
        "We need to reduce operational costs significantly",
        "Focus on cutting unnecessary expenses and waste",
        "Optimize our budget allocation for better efficiency",
        "Streamline spending to save money",
        "Improve financial efficiency across operations",
        "Eliminate wasteful practices and overhead"
    ],
    "transparency": [
        "We need more transparency in decision-making",
        "Improve communication channels between teams",
        "Share information openly with everyone",
        "Provide clear and honest updates regularly",
        "Build trust through open dialogue",
        "Ensure everyone has access to important information"
    ],
    "innovation": [
        "Embrace new technologies and modern solutions",
        "Modernize our systems and processes",
        "Invest in AI and automation tools",
        "Drive digital transformation forward",
        "Adopt cutting-edge solutions for growth",
        "Leverage technology to stay competitive"
    ],
    "employee_wellbeing": [
        "Prioritize employee mental health and wellness",
        "Support better work-life balance for teams",
        "Build a positive and supportive culture",
        "Invest in employee satisfaction programs",
        "Create supportive work environments",
        "Focus on team morale and happiness"
    ],
    "sustainability": [
        "Focus on environmental sustainability goals",
        "Reduce our carbon footprint significantly",
        "Adopt eco-friendly practices across operations",
        "Invest in renewable energy solutions",
        "Make green choices in all decisions",
        "Prioritize environmental responsibility"
    ],
    "customer_focus": [
        "Improve customer experience and satisfaction",
        "Focus on delivering the highest quality",
        "Listen to customer feedback actively",
        "Build truly user-centric products",
        "Enhance service delivery excellence",
        "Prioritize customer needs above all"
    ],
    "growth_expansion": [
        "Focus on sustainable growth strategies",
        "Expand into new markets strategically",
        "Scale operations for future success",
        "Increase our market share systematically",
        "Drive business development forward",
        "Pursue expansion opportunities"
    ]
}
```

### Step 2: Assign Participants to Themes

Replace lines 140-145 with:

```python
# Assign each participant to a primary theme
theme_keys = list(THEME_VOCABULARIES.keys())
for idx, participant in enumerate(RANDOM_PARTICIPANTS):
    # Distribute participants across themes
    primary_theme = theme_keys[idx % len(theme_keys)]

    # 40% also have a secondary theme
    secondary_theme = None
    if random.random() < 0.4:
        other_themes = [t for t in theme_keys if t != primary_theme]
        secondary_theme = random.choice(other_themes)

    PARTICIPANT_THEMES[participant["id"]] = {
        "primary": primary_theme,
        "secondary": secondary_theme
    }
```

### Step 3: Generate Theme-Based Responses

Replace the response generation (around line 200) with:

```python
# Get participant's theme
participant_theme_info = PARTICIPANT_THEMES[participant["participant_id"]]

# 75% use primary theme, 20% secondary, 5% random
roll = random.random()
if roll < 0.75:
    theme = participant_theme_info["primary"]
elif roll < 0.95 and participant_theme_info["secondary"]:
    theme = participant_theme_info["secondary"]
else:
    theme = random.choice(list(THEME_VOCABULARIES.keys()))

# Generate response from theme vocabulary
response = random.choice(THEME_VOCABULARIES[theme])

# Add natural variation
prefixes = ["", "I strongly believe: ", "In my view, ", "It's essential that "]
response = random.choice(prefixes) + response

# Optional: Extend with round-specific context
if "priority" in round_question.lower():
    response += ". This should be our top priority."
elif "challenge" in round_question.lower():
    response += ". This is our biggest challenge."
```

## 🎯 Expected Results

With theme-based generation:

**Before (Random)**:
- 0-5 real clusters per round
- 95+ singletons
- Correct behavior (no false clustering)

**After (Theme-Based)**:
- 7±2 natural clusters per round
- 10-20 singletons (truly unique views)
- Matches real human discussions!

## 🚀 Quick Test

```bash
cd backend
poetry run python create_varied_discussion.py
```

Check the output:
- Should see "5-9 clusters" per round
- Inspector modal will show clear thematic groupings
- Sankey will show natural theme evolution

## 📊 Verification

1. Generate discussion
2. Open Sankey: `http://localhost:3000/discussions/{id}/sankey`
3. Click "🔍 Inspect Clustering"
4. Select any round
5. Look at cluster labels - should see themes like:
   - "Cost Reduction & Efficiency" (18 participants)
   - "Transparency & Communication" (16 participants)
   - "Innovation & Technology" (15 participants)
   - etc.

## ✨ Why This Works

**Semantic Similarity:**
```
"reduce costs" vs "cut expenses":
Embedding similarity: ~0.85 → Same cluster!

"reduce costs" vs "mental health":
Embedding similarity: ~0.15 → Different clusters!
```

**Miller's Law:**
- 7 themes = 7±2 clusters naturally
- Participants distributed across themes
- Natural variation within themes
- Realistic cluster sizes (10-20 each)

## 📝 Alternative: Full Theme-Based Script

If you prefer a completely new script, the file `create_themed_discussion.py` is available but needs fixing of database constraints. The quick fix above is faster!

---

## Summary

✅ **Modify `create_varied_discussion.py`** with 3 simple changes
✅ **Theme-based vocabulary** creates semantic similarity
✅ **7 themes** = 7±2 natural clusters
✅ **Realistic results** that match real human discussions

**Total effort**: ~30 minutes of editing
**Result**: Production-quality test data with realistic clustering!
