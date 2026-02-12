# Research: Temporal Sankey Construction Protocol

**Phase**: 0 (Research & Investigation)
**Date**: 2026-01-29
**Status**: Complete

## Overview

This document resolves technical unknowns and design decisions for constructing movement-based Sankey diagrams from cluster data. The primary challenges are: (1) accurately tracking participant movement across rounds, (2) handling dropout naturally without synthetic nodes, (3) integrating alignment metadata without affecting edge computation, and (4) ensuring graph invariants (percentage sums, edge totals) are maintained.

## Research Questions

### 1. How do we efficiently compute participant movement between adjacent rounds?

**Question**: Given cluster assignments for rounds r and r+1, how do we identify which participants moved between which clusters?

**Investigation**:

- **Option A: Nested Loop Approach**: For each participant in round r, look up their cluster in round r+1 and increment edge counter
  - Pros: Simple, straightforward
  - Cons: O(n * m) where n = participants in r, m = participants in r+1; inefficient for large participant counts

- **Option B: Set Intersection + Dictionary Lookup**:
  1. Compute user intersection between rounds: `users_r ∩ users_r+1`
  2. Build dictionaries: `cluster_of_r[user_id] → cluster_id` and `cluster_of_r+1[user_id] → cluster_id`
  3. For each user in intersection: `edge_counter[(cluster_of_r[user], cluster_of_r+1[user])] += 1`
  - Pros: O(n) time complexity; scales to 100+ participants
  - Cons: Requires in-memory dictionaries (acceptable for MVP scale)

- **Option C: Database JOIN Query**: Use SQL to join participant assignments across rounds
  - Pros: Leverages database indexing; handles large datasets
  - Cons: Requires careful query optimization; may hit database latency limits

**Decision**: **Option B (Set Intersection + Dictionary Lookup)** for MVP. Provides O(n) performance for target scale (100 participants). Database JOIN (Option C) can be considered post-MVP if scaling beyond 100 participants or if memory constraints arise.

**Rationale**: At 100 participants across 5 rounds, Option B requires ~500 dictionary lookups (worst case), well within Python's dictionary performance. Avoids database round-trip latency and simplifies testing with in-memory data structures.

---

### 2. How do we handle dropout naturally (Option A) without synthetic nodes?

**Question**: When participants drop out between rounds, how do we represent the flow mass shrinkage without creating "dropout" nodes?

**Investigation**:

**Option A Behavior (Spec-Defined)**:
- No synthetic "dropout" or "no response" nodes
- Total flow mass shrinks across columns (natural narrowing)
- Only continuing participants generate edges
- Per-round percentage normalization (Round 1: 10 users = 100%, Round 2: 7 users = 100%)

**Implementation Requirements**:
1. User intersection computation must exclude dropouts: `continuing_users = users_r ∩ users_r+1`
2. Edge totals between rounds equal intersection size, NOT round r size
3. Node widths in adjacent columns may have different absolute totals (visual shrinkage)
4. No backfilling or renormalization to hide dropout

**Edge Case: All Users Drop Out**:
- Round 1 has 10 participants
- Round 2 has 0 participants
- Result: Round 1 column has nodes, Round 2 column is empty, zero edges
- Valid state: represents complete dropout

**Validation Strategy**:
- Property-based test: `sum(edge.user_count for edges from r to r+1) == len(users_r ∩ users_r+1)`
- Visual test: Total flow width shrinks visibly in rendered Sankey

**Decision**: Implement strict user intersection logic in `MovementTracker` service. Edge computation must filter to continuing users only. No special-casing for dropout; it emerges naturally from the movement computation.

---

### 3. How do we integrate alignment metadata without affecting edge computation?

**Question**: Spec 4 provides `display_group_id` for visual continuity. How do we ensure this metadata doesn't influence edge counts?

**Investigation**:

**Alignment Metadata Use Cases**:
- Color continuity: Aligned clusters use same color across rounds
- Label families: Related clusters share label prefixes or groupings
- Split/merge indicators: Multiple clusters with same `display_group_id` indicate split

**Critical Invariant**: Alignment metadata is **presentation-only**. It MUST NOT affect:
- Edge user counts
- Participant assignments
- Cluster membership

**Implementation Strategy**:
1. Node creation includes `display_group_id` as optional field (pass-through from Spec 4)
2. Edge computation uses only `cluster_id` (ignores `display_group_id`)
3. Frontend uses `display_group_id` for color/label styling only

**Validation Strategy**:
- Contract test: Construct Sankey with and without alignment metadata → edge counts must be identical
- Property-based test: `display_group_id` changes do not affect edge computation output

**Decision**: Store `display_group_id` as optional node metadata. Edge builder service (`EdgeBuilder`) MUST NOT access this field. Frontend visualization layer consumes it for styling only.

---

### 4. How do we ensure graph invariants (percentage sums, edge totals)?

**Question**: What validation checks are required to ensure Sankey correctness?

**Investigation**:

**Required Invariants**:

1. **Percentage Sum Invariant**: Within a column, `sum(node.user_pct) == 1.0` (±0.01% rounding tolerance)
   - Validates per-round normalization
   - Catches percentage calculation bugs

2. **Edge Total Invariant**: For adjacent rounds r and r+1, `sum(edge.user_count) == len(users_r ∩ users_r+1)`
   - Validates dropout handling
   - Catches double-counting or missing edges

3. **Coverage Invariant**: Every participant in a round is assigned to exactly one node
   - Validates 100% cluster coverage from Spec 4
   - Catches missing participants

4. **Determinism Invariant**: Same cluster assignments produce identical Sankey
   - Validates reproducibility
   - Catches non-deterministic ordering issues

**Validation Approach**:
- `SankeyInvariantsValidator` service with explicit invariant checks
- Runs after graph construction, before returning SankeyGraph
- Raises exception if any invariant violated (fail-fast)

**Decision**: Implement `SankeyInvariantsValidator` with all 4 invariants. Gate Sankey construction completion on passing validation. Include invariant checks in integration tests.

---

### 5. What data structures best represent the SankeyGraph?

**Question**: How should we model the multi-column graph structure?

**Investigation**:

**Option A: Nested Dictionaries**:
```python
{
  "discussion_id": "...",
  "columns": {
    1: {"nodes": [...], "round_index": 1},
    2: {"nodes": [...], "round_index": 2}
  },
  "edges": [...]
}
```
- Pros: Fast column lookup by round index
- Cons: Awkward iteration, non-standard JSON serialization

**Option B: Flat Lists (Chosen)**:
```python
{
  "discussion_id": "...",
  "rounds": [1, 2, 3],
  "columns": [
    {"round_index": 1, "nodes": [...]},
    {"round_index": 2, "nodes": [...]}
  ],
  "edges": [...]
}
```
- Pros: Natural JSON serialization, easy iteration
- Cons: O(n) column lookup (acceptable for 10 rounds max)

**Node Structure**:
```python
{
  "node_id": "n_r1_c5",
  "cluster_id": "cluster_5",
  "label_summary": "Increase remote work flexibility",
  "user_count": 15,
  "user_pct": 0.30,
  "display_group_id": "dg_12"  # optional
}
```

**Edge Structure**:
```python
{
  "from_round_index": 1,
  "to_round_index": 2,
  "from_cluster_id": "cluster_5",
  "to_cluster_id": "cluster_8",
  "user_count": 10,
  "pct_of_from": 0.67,  # optional
  "pct_of_to": 0.50     # optional
}
```

**Decision**: Use **Option B (Flat Lists)** with Pydantic models for validation. Provides clean JSON serialization and strong typing. Node and edge structures match spec requirements.

---

### 6. How do we generate discussion reports with statistics?

**Question**: What statistics and summaries should be included in the discussion report?

**Investigation**:

**Required Report Sections** (per spec FR-034 to FR-038):

1. **Final SankeyGraph**: Complete `SankeyGraph` data structure with all columns, nodes, edges

2. **Per-Round Cluster Summaries**:
   - For each round: list of thought spaces with label and user count
   - Example: "Round 2: [Remote Work (15 users), Hybrid Model (10 users), Office Only (2 users)]"

3. **Dropout Curve**:
   - Per-round participant totals showing engagement decay
   - Example: [Round 1: 20, Round 2: 18, Round 3: 15]

4. **Top Movement Edges**:
   - Largest flows per round transition (e.g., top 5)
   - Example: "Round 1→2: Remote Work → Hybrid Model (12 users)"

5. **Export Format**:
   - JSON structure for archiving and analysis
   - Optional: PDF rendering (post-MVP)

**Report Generation Strategy**:
1. `ReportGenerator` service assembles report from constructed SankeyGraph
2. Derives dropout curve from per-round node totals
3. Sorts edges by user_count descending to identify top movements
4. Serializes to JSON for API response

**Decision**: Implement `DiscussionReport` entity with all required sections. JSON export for MVP. PDF export deferred post-MVP.

---

## Design Decisions Summary

| Decision Point | Choice | Rationale |
|---------------|--------|-----------|
| Movement Computation | Set Intersection + Dictionary Lookup (Option B) | O(n) performance for 100 participants; avoids database latency |
| Dropout Handling | Natural Shrinkage (Option A - spec-defined) | No synthetic nodes; user intersection for edges; per-round normalization |
| Alignment Integration | Pass-through metadata, edge computation ignores it | Strict separation: presentation vs. data accuracy |
| Invariant Validation | SankeyInvariantsValidator with 4 invariants | Fail-fast validation ensures correctness before returning SankeyGraph |
| Data Structure | Flat Lists (Pydantic models) | Clean JSON serialization, strong typing, easy iteration |
| Report Generation | JSON export with 5 sections | Meets MVP requirements; PDF export deferred post-MVP |

---

## Implementation Notes

### Performance Optimizations

1. **Batch Cluster Data Loading**: Single database query to fetch all cluster assignments for a discussion (avoid N+1 queries)

2. **In-Memory Movement Computation**: Build participant dictionaries in memory for fast lookup (acceptable for 100 participants)

3. **Lazy Edge Sorting**: Only sort edges for "top movements" report section; main Sankey construction doesn't require sorting

### Testing Strategy

1. **Synthetic Round Datasets**: Create test datasets with known movements (e.g., all users stay in same cluster, all users split evenly, gradual convergence)

2. **Property-Based Tests**: Use Hypothesis to generate random cluster assignments and validate invariants hold

3. **Integration with Spec 4**: Contract tests using actual cluster data from Spec 4 implementation

### Edge Cases to Test

- Single round discussion (1 column, 0 edges)
- Complete dropout (Round 2 has 0 participants)
- All participants stay in same cluster (1 edge with user_count = total)
- Cluster ID collision across rounds (distinct clusters with same ID)
- Missing alignment metadata (Sankey completes without display_group_ids)

---

## Open Questions for Phase 1

1. **Visualization Library**: Should frontend use D3.js, Plotly, or custom SVG rendering? (Deferred to Phase 1 design)

2. **Report Pagination**: If discussions grow beyond 10 rounds, should reports paginate columns? (Out of scope for MVP: max 10 rounds)

3. **Real-Time Updates**: Should Sankey update in real-time as rounds complete? (Out of scope for MVP: synchronous construction after discussion completes)

---

## Dependencies on Other Specs

- **Spec 4 (Clustering & Alignment)**: Provides cluster data, display_group_ids, participant assignments
- **Spec 1 (Discussion Protocol)**: Provides round sequencing, participant identity, discussion lifecycle events
- **Spec 3 (Summarization & Approval)**: Ensures only approved summaries are clustered (validated by Spec 4)

---

## Next Steps (Phase 1)

1. Define `data-model.md` with SankeyGraph, Column, Node, Edge, DiscussionReport entities
2. Create OpenAPI contracts for Sankey construction and report generation endpoints
3. Write `quickstart.md` with developer setup and example Sankey construction workflow
4. Validate Phase 1 artifacts against research decisions and spec requirements
