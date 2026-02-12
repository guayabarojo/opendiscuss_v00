# Large-Scale Discussion Test Plan

## Overview

Comprehensive stress test of the discussion system with:
- **100 participants**
- **10 rounds** with thoughtful questions
- **1,000 total submissions** (100 × 10)
- Complete pipeline: Submission → Summarization → Clustering → Sankey

## Test Objectives

1. **Scale Testing**: Verify system handles 100 participants across 10 rounds
2. **Summarization Accuracy**: Test LLM summarization of 1,000 submissions
3. **Clustering Quality**: Analyze HDBSCAN's ability to identify thought spaces
4. **Flow Tracking**: Generate Sankey diagram showing participant movement
5. **UI Performance**: Test visualization rendering with 10 rounds
6. **Round Label Wrapping**: Verify question text wraps properly in labels

## Discussion Topic: AI Ethics and Society

###10 Questions:

1. What are the most important ethical principles that should guide AI development?
2. How can we ensure AI systems remain transparent and accountable to society?
3. What role should government regulation play in AI development and deployment?
4. How might AI impact employment and economic inequality over the next decade?
5. What safeguards are needed to prevent AI bias and discrimination?
6. How should we balance AI innovation with privacy rights and data protection?
7. What are the risks and benefits of AI in critical infrastructure and healthcare?
8. How can we ensure AI development benefits all of humanity, not just wealthy nations?
9. What educational changes are needed to prepare society for an AI-driven future?
10. How should we approach the development of artificial general intelligence (AGI)?

## Response Generation Strategy

Each round has 7 thoughtfully crafted response templates addressing different perspectives:

**Example (Round 1 - Ethical Principles):**
- "Transparency must be the foundation..."
- "Human oversight and accountability should be mandatory..."
- "Fairness and non-discrimination should be built in..."
- "Privacy protection is essential..."
- "Safety and robustness must be tested extensively..."
- "Beneficial intent - AI should improve human wellbeing..."
- "Democratic values and human rights must guide development..."

Participants are assigned responses with natural variations to create realistic clustering patterns.

## Expected Clustering Patterns

### Hypothesis
With 100 participants and 7 core perspectives per round, we expect:
- **5-8 major clusters** per round (grouping similar perspectives)
- **2-3 outliers** (unique viewpoints)
- **Cluster size range**: 8-25 participants per major cluster

### Alignment Tracking
Participants should maintain general ideological consistency across rounds:
- Privacy-focused participants cluster together consistently
- Regulation-focused participants cluster together
- Innovation-focused participants cluster together

## Analysis Metrics

### Per-Round Metrics
- Total submissions (expected: 100)
- Total summaries generated (expected: 100)
- Number of clusters identified
- Cluster size distribution
- Medoid quality (representative of cluster)

### Cross-Round Metrics
- Participant retention rate (should be 100% - no dropouts in test)
- Movement patterns (how many participants change clusters)
- Alignment persistence (do clusters maintain themes?)
- Edge weight distribution (flow sizes)

### Sankey Visualization
- Total columns: 10 (one per round)
- Total nodes: ~60-80 (5-8 clusters × 10 rounds)
- Total edges: ~500-700 (tracking all movements)
- Visual coherence: Can users understand the flow?
- Round label wrapping: Questions fully visible

## Success Criteria

### Functional Requirements
✅ All 100 participants successfully submit in all 10 rounds
✅ All 1,000 submissions successfully summarized
✅ Clustering completes for all 10 rounds
✅ Sankey diagram generated with all flows
✅ No system crashes or errors

### Quality Requirements
✅ Clusters are semantically meaningful (similar perspectives grouped)
✅ Medoids accurately represent each cluster
✅ Participant flow tracking is accurate
✅ Sankey visualization is readable and informative
✅ Round labels wrap properly showing full question text

### Performance Requirements
✅ Processing completes within 10 minutes
✅ Sankey rendering loads within 5 seconds
✅ UI remains responsive with 10 rounds visible
✅ Database queries performant (<100ms)

## Playwright Simulation

After generating the discussion, we'll use Playwright to:

1. **Navigate** to discussion page
2. **Simulate** one participant submitting responses
3. **Verify** submission workflow works end-to-end
4. **Capture** screenshots of Sankey visualization
5. **Test** horizontal scroll with 10 rounds
6. **Verify** round label wrapping

## Analysis Report Structure

The automated report will include:

### Section 1: Executive Summary
- Discussion ID
- Total participants, rounds, submissions
- Processing time and completion status

### Section 2: Round-by-Round Analysis
For each round:
- Question text
- Submission count
- Summary count
- Cluster count and distribution
- Top 3 clusters with medoids

### Section 3: Participant Flow Analysis
- Sankey metrics (columns, nodes, edges)
- Movement patterns between rounds
- Top 10 largest flows
- Alignment persistence analysis

### Section 4: Summary Statistics
- Average clusters per round
- Participant retention rate
- Clustering quality metrics
- Performance benchmarks

### Section 5: Clustering Accuracy Assessment
- Semantic coherence of clusters
- Medoid representativeness
- Outlier handling
- Comparison to expected patterns

## Files Generated

1. `create_large_scale_discussion.py` - Test script
2. `discussion_analysis_{discussion_id}.txt` - Analysis report
3. Screenshots via Playwright:
   - `sankey-10rounds-full.png`
   - `sankey-10rounds-round-labels.png`
   - `sankey-10rounds-scroll.png`

## Timeline

- **Phase 1:** Discussion creation (30 seconds)
- **Phase 2:** Round execution (5-8 minutes)
  - 100 submissions per round
  - Summarization pipeline
  - HDBSCAN clustering
- **Phase 3:** Sankey generation (10-20 seconds)
- **Phase 4:** Analysis report (5 seconds)
- **Phase 5:** Playwright testing (30 seconds)

**Total Estimated Time:** 6-10 minutes

## Constitutional Compliance

All aspects maintain constitutional compliance:

✅ **Intent Fidelity**: Clusters use actual participant text (medoids)
✅ **Semantic Accuracy**: All perspectives preserved, not filtered
✅ **Temporal Transparency**: Full movement tracking across rounds
✅ **Representation Not Adjudication**: No ranking or scoring

---

**Status:** In Progress
**Started:** 2026-02-06T11:18:00Z
**Est. Completion:** 2026-02-06T11:25:00Z
