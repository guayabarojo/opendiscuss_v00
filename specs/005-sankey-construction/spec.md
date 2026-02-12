# Feature Specification: Temporal Sankey Construction Protocol

**Feature Branch**: `005-sankey-construction`
**Created**: 2026-01-27
**Status**: Draft
**Input**: User description: "Spec 4 — Temporal Sankey Construction Protocol - Construct movement-based Sankey diagram across rounds"

**Constitution Compliance**: All features MUST comply with `.specify/memory/constitution.md`.
Check MVP Boundaries section for explicit non-features before proceeding.

**Dependencies**: This spec depends on Spec 0 (Discussion Protocol - 001-discussion-protocol) and Spec 3 (Semantic Clustering & Hybrid Alignment - 004-clustering-alignment)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Construct Multi-Column Sankey from Cluster Data (Priority: P1)

A discussion completes 3 rounds with clusters generated for each round. The system constructs a
Sankey diagram with 3 columns (one per round), where each node represents a thought space and node
widths are proportional to participant counts.

**Why this priority**: This is the core visualization artifact of OpenDiscuss. Without the Sankey
diagram, participants cannot see collective thinking patterns. It validates the basic Sankey
construction from cluster data.

**Independent Test**: Can be fully tested by providing cluster data for 3 rounds and verifying a
3-column Sankey is generated with correct node counts and widths. Delivers immediate value by
visualizing thought space distribution per round.

**Acceptance Scenarios**:

1. **Given** a discussion with 3 completed rounds each with clusters from Spec 3, **When** Sankey
   construction runs, **Then** a 3-column Sankey is created with columns ordered temporally (Round
   1, Round 2, Round 3)
2. **Given** Round 1 has 3 clusters with 10, 15, and 5 participants respectively, **When** nodes are
   created, **Then** each cluster becomes a node with user_count and user_pct (33%, 50%, 17%)
3. **Given** nodes are created, **When** widths are assigned, **Then** node widths are proportional
   to user_pct (wider nodes for more participants)
4. **Given** each cluster has a label_summary from Spec 3, **When** nodes are labeled, **Then** the
   node label is the exact label_summary text (preserving medoid from Spec 3)
5. **Given** Sankey construction completes, **When** the output is generated, **Then** it includes
   discussion_id, rounds list, columns with nodes, and optional display metadata

---

### User Story 2 - Compute Movement-Based Edges Between Rounds (Priority: P2)

Participants move between thought spaces across rounds. The system computes edges between nodes in
adjacent columns based on actual participant movement, where edge width reflects the number of
participants making each transition.

**Why this priority**: This is the core innovation of movement-based representation. Edges show how
participants shift between ideas over time, enabling convergence/divergence analysis. Critical for
temporal transparency.

**Independent Test**: Can be tested by providing participant assignments for 2 rounds and verifying
edges are created with correct participant counts. Delivers value by showing thinking evolution.

**Acceptance Scenarios**:

1. **Given** Round 1 has clusters A, B, C and Round 2 has clusters D, E, **When** a participant
   assigned to A in Round 1 is assigned to D in Round 2, **Then** an edge from A→D is created or
   incremented
2. **Given** 5 participants move from cluster A (Round 1) to cluster D (Round 2), **When** edge
   calculation completes, **Then** the A→D edge has user_count=5
3. **Given** edges are computed, **When** deriving metrics, **Then** pct_of_from = user_count /
   from_cluster_user_count and pct_of_to = user_count / to_cluster_user_count (optional)
4. **Given** multiple participants make the same transition, **When** edges are aggregated, **Then**
   duplicate movements are counted correctly (A→D with 3 users shows user_count=3)
5. **Given** a participant moves from cluster B (Round 1) to cluster B (Round 2, different cluster
   with same ID), **When** edges are computed, **Then** cluster IDs are treated as per-round
   (distinct clusters despite ID collision)

---

### User Story 3 - Handle Participant Dropout Naturally (Priority: P3)

10 participants submit in Round 1 but only 7 submit in Round 2. The system computes edges based
only on the 7 continuing participants, resulting in natural flow mass shrinkage. No synthetic
"dropout" node is created.

**Why this priority**: Validates "temporal transparency" principle and Option A dropout behavior.
Makes engagement decay visible without artificial constructs. Critical for honest representation.

**Independent Test**: Can be tested by providing 10 participants in Round 1 and 7 in Round 2,
verifying edge totals sum to 7 (not 10), and confirming no dropout node exists. Delivers value
through accurate dropout representation.

**Acceptance Scenarios**:

1. **Given** 10 participants in Round 1 (clusters A, B) and 7 participants in Round 2 (clusters C,
   D), **When** edges are computed, **Then** only the 7 continuing participants generate edges
   (dropouts excluded)
2. **Given** 3 participants drop out after Round 1, **When** the Sankey is rendered, **Then** total
   edge width flowing from Round 1 to Round 2 is 7 (shrunk from 10)
3. **Given** dropout occurs, **When** nodes are rendered, **Then** no "dropout" or "no response"
   node is created in Round 2
4. **Given** Round 1 node widths sum to 10 and Round 2 node widths sum to 7, **When** percentages
   are computed, **Then** Round 1 percentages are relative to 10 and Round 2 percentages are
   relative to 7 (per-round normalization)
5. **Given** dropout causes mass shrinkage, **When** the Sankey is viewed, **Then** the visual
   narrowing of total flow is interpreted as dropout (not hidden by renormalization)

---

### User Story 4 - Integrate Alignment Metadata for Display Continuity (Priority: P4)

Clusters are aligned across rounds by Spec 3 with display_group_ids for visual continuity. The
system includes these display groups in the Sankey output for stable colors and labels, but edge
computation remains based strictly on participant movement.

**Why this priority**: Improves Sankey readability by providing stable visual cues across rounds.
Does not compromise data accuracy since alignment is presentational only. Integrates Spec 3's hybrid
alignment.

**Independent Test**: Can be tested by providing aligned clusters with display_group_ids, verifying
they appear in Sankey output, and confirming edge counts are unchanged. Delivers value through
improved user experience.

**Acceptance Scenarios**:

1. **Given** Spec 3 alignment assigns display_group_id=dg_12 to clusters in Rounds 1 and 2, **When**
   Sankey nodes are created, **Then** nodes include display_group_id in their metadata
2. **Given** display groups are assigned, **When** the Sankey is rendered, **Then** aligned clusters
   use consistent colors across columns (visual continuity)
3. **Given** alignment metadata is present, **When** edges are computed, **Then** edge counts are
   based solely on participant movement (alignment does NOT affect edge calculation)
4. **Given** one Round 1 cluster aligns with two Round 2 clusters (split), **When** display metadata
   is added, **Then** both Round 2 clusters have the same display_group_id (indicating split)
5. **Given** alignment metadata is optional, **When** Spec 3 provides no alignment, **Then** Sankey
   construction completes without display_group_ids (valid state)

---

### User Story 5 - Generate Discussion Report with Sankey and Statistics (Priority: P5)

After a discussion completes, the system generates a comprehensive report including the final Sankey
diagram, per-round cluster summaries, participant counts per round (dropout curve), and top movement
edges (largest flows).

**Why this priority**: Provides the final deliverable artifact for participants. Enables analysis
and understanding of the full discussion evolution. Critical for post-discussion review.

**Independent Test**: Can be tested by constructing a Sankey and verifying the report includes all
required sections. Delivers value by providing exportable discussion summary.

**Acceptance Scenarios**:

1. **Given** a discussion completes with Sankey constructed, **When** the report is generated,
   **Then** it includes the final SankeyGraph data structure with columns, nodes, and edges
2. **Given** the report is generated, **When** cluster summaries are included, **Then** each round's
   clusters are listed with label_summary and user_count
3. **Given** participant counts vary across rounds (e.g., 20, 18, 15), **When** the dropout curve
   is generated, **Then** it shows per-round totals indicating engagement decay
4. **Given** edges vary in size, **When** top movement edges are identified, **Then** the report
   includes the largest flows (e.g., top 5) per round transition
5. **Given** the report is complete, **When** it is exported, **Then** it is available in a
   structured format (JSON or similar) for archiving and analysis

---

### Edge Cases

- **Single round discussion**: Sankey has 1 column with nodes, zero edges (valid degenerate case)
- **Zero participants in Round 2 (all drop out)**: Sankey has Round 1 column with nodes, Round 2
  column empty, zero edges (valid)
- **All participants stay in same cluster across rounds**: One edge with user_count = total
  participants (100% stability)
- **Participant moves to identical cluster ID in next round (different cluster)**: Edge is computed
  correctly using per-round cluster namespacing
- **Alignment assigns same display_group_id to all clusters**: Valid - visual grouping is
  permissive, does not affect flows
- **Missing alignment metadata**: Sankey construction completes without display_group_ids (nodes lack
  that field)
- **Edge totals exceed participant intersection**: System error - indicates bug in assignment logic
  or dropout exclusion
- **Node widths in one column don't sum to 100%**: System error - indicates percentage calculation
  bug (should sum to 1.0 with rounding tolerance)

## Requirements *(mandatory)*

### Functional Requirements

#### Sankey Structure & Columns

- **FR-001**: System MUST construct a multi-column Sankey diagram with one column per round that has
  aggregated clusters
- **FR-002**: Columns MUST be ordered temporally (Round 1, Round 2, ..., Round N)
- **FR-003**: Each column MUST contain nodes representing the thought spaces (clusters) from that
  round
- **FR-004**: Column data MUST include round_index and nodes list

#### Nodes (Cluster Representation)

- **FR-005**: Each node MUST represent exactly one cluster from Spec 3
- **FR-006**: Node MUST include: node_id, cluster_id, label_summary, user_count, user_pct
- **FR-007**: Node label_summary MUST be the exact label from Spec 3 (medoid summary text)
- **FR-008**: Node user_count MUST match the cluster's user_count from Spec 3
- **FR-009**: Node user_pct MUST be calculated relative to that round's total participants (not
  cross-round normalized)
- **FR-010**: Node widths MUST be proportional to user_pct when rendered

#### Edges (Movement Representation)

- **FR-011**: System MUST create edges between nodes in adjacent rounds (r and r+1) based on
  participant movement
- **FR-012**: An edge MUST exist from cluster A (round r) to cluster B (round r+1) if and only if
  at least one participant is assigned to A in r and B in r+1
- **FR-013**: Edge user_count MUST equal the number of participants making that specific transition
- **FR-014**: Edge MUST include: from_round_index, to_round_index, from_cluster_id, to_cluster_id,
  user_count
- **FR-015**: Edge width MUST be proportional to user_count when rendered

#### Movement Computation

- **FR-016**: System MUST receive per-user assignment functions: cluster_of(user_id, round_r) ->
  cluster_id
- **FR-017**: For each adjacent pair (r, r+1), system MUST identify the user intersection: users
  present in both rounds
- **FR-018**: For each user in the intersection, system MUST increment the edge counter for
  (cluster_of(user, r), cluster_of(user, r+1))
- **FR-019**: Users who do not submit in round r+1 MUST NOT generate outgoing edges from round r
  (Option A dropout behavior)

#### Dropout Handling (Option A)

- **FR-020**: System MUST NOT create synthetic dropout nodes or "no response" nodes
- **FR-021**: Total flow mass MAY shrink across columns due to participant dropout
- **FR-022**: Dropout MUST be represented by reduced total edge width flowing into subsequent rounds
  (natural shrinkage)
- **FR-023**: System MUST NOT renormalize flows across rounds to hide dropout (per-round
  normalization only)

#### Alignment Metadata Integration

- **FR-024**: System MAY include display_group_id from Spec 3 alignment in node metadata
- **FR-025**: Display group IDs MUST affect presentation only (colors, label families)
- **FR-026**: Alignment metadata MUST NOT change edge counts or participant assignments
- **FR-027**: If alignment metadata is absent, Sankey construction MUST complete without
  display_group_ids

#### Derived Metrics (Optional)

- **FR-028**: System MAY compute derived edge metrics: pct_of_from = user_count /
  from_cluster_user_count
- **FR-029**: System MAY compute derived edge metrics: pct_of_to = user_count /
  to_cluster_user_count
- **FR-030**: Derived metrics are optional but useful for report readability and analysis

#### Data Contract

- **FR-031**: Sankey output MUST conform to the canonical SankeyGraph data structure with
  discussion_id, rounds, columns, edges
- **FR-032**: SankeyGraph MUST be serializable to JSON or equivalent structured format
- **FR-033**: Node IDs MUST be unique within a round (but may be reused across rounds)

#### Discussion Report

- **FR-034**: System MUST generate a discussion report including the final SankeyGraph
- **FR-035**: Report MUST include per-round cluster summaries (label, user_count)
- **FR-036**: Report MUST include participant counts per round (dropout curve data)
- **FR-037**: Report MUST include top movement edges (largest flows) per round transition
- **FR-038**: Report MUST be exportable in a structured format for archiving

#### Determinism and Correctness

- **FR-039**: Given fixed cluster assignments, Sankey construction MUST produce deterministic results
- **FR-040**: Edge totals between adjacent rounds MUST NOT exceed the user intersection size
- **FR-041**: Node user_pct values within a column MUST sum to 1.0 (100%) with sub-0.01% rounding
  tolerance

### Key Entities

- **SankeyGraph**: The complete multi-column Sankey diagram representation. Attributes:
  discussion_id, rounds list, columns list, edges list. Related to: Discussion, Round, Column, Node,
  Edge.

- **Column**: A vertical section of the Sankey representing one round's thought spaces. Attributes:
  round_index, nodes list. Related to: Round, Node.

- **Node**: A visual element representing a thought space (cluster) in a column. Attributes: node_id,
  cluster_id, label_summary, user_count, user_pct, display_group_id (optional). Related to: Thought
  Space (Spec 3), Column.

- **Edge (Flow)**: A connection between nodes in adjacent columns representing participant movement.
  Attributes: from_round_index, to_round_index, from_cluster_id, to_cluster_id, user_count,
  pct_of_from (optional), pct_of_to (optional). Related to: Node (source and target).

- **Movement**: The transition of a participant from one thought space to another across adjacent
  rounds. Attributes: user_id, from_cluster_id, to_cluster_id. Aggregated into Edges. Related to:
  Participant, Thought Space.

- **Dropout Curve**: A sequence of participant counts per round showing engagement decay. Attributes:
  round_index, participant_count. Derived from node user_counts. Related to: Round.

- **Discussion Report**: A comprehensive summary of the discussion including Sankey and statistics.
  Attributes: SankeyGraph, cluster summaries, dropout curve, top movements. Related to: Discussion,
  SankeyGraph.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sankey construction completes within 3 seconds for discussions with up to 100
  participants across 5 rounds (scalable performance)

- **SC-002**: 100% of clusters from Spec 3 are represented as nodes in the Sankey (no clusters lost)

- **SC-003**: Edge counts match participant movement with 100% accuracy (edge total equals user
  intersection size between rounds)

- **SC-004**: Dropout is represented naturally with 100% accuracy (no synthetic nodes, correct flow
  mass shrinkage)

- **SC-005**: Node user_pct values within a column sum to 1.0 (100%) with sub-0.01% rounding error
  tolerance

- **SC-006**: Alignment metadata integration does NOT change edge counts with 100% accuracy (strict
  invariant)

- **SC-007**: Sankey output conforms to canonical data contract with 100% schema compliance

- **SC-008**: Discussion reports include all required sections (SankeyGraph, cluster summaries,
  dropout curve, top movements) 100% of the time

- **SC-009**: Deterministic construction achieves 100% reproducibility (same cluster assignments
  produce identical Sankey)

- **SC-010**: Edge computation correctness achieves 100% accuracy on synthetic test datasets with
  known movements

### Protocol Correctness

- **SC-011**: All Sankey invariants (columns per round, nodes per cluster, movement-based edges,
  Option A dropout, alignment presentation-only) are verifiable through automated tests

- **SC-012**: Integration tests with synthetic rounds (stable users, shifting preferences, dropout)
  produce expected Sankey structures

- **SC-013**: Integration with Spec 3 (cluster input) and report generation (complete output) is
  verifiable through end-to-end tests

## Assumptions

1. **Cluster data availability**: Spec 3 has completed successfully and provided cluster data for
   all rounds before Sankey construction begins

2. **Per-user assignment function**: A reliable mapping from (user_id, round) -> cluster_id is
   available from Spec 3 cluster membership data

3. **Participant identity stability**: Participant user_ids are stable and consistent across rounds
   (same user has same ID in all rounds)

4. **Dropout identification**: Participants are considered dropped out if they have no approved
   summary in a round (handled by Spec 1/Spec 2)

5. **Alignment metadata optional**: Sankey construction does not depend on alignment metadata; it is
   an optional enhancement for visual continuity

6. **Single discussion context**: All rounds belong to the same discussion; cross-discussion Sankey
   comparisons are out of scope for MVP

7. **Temporal ordering**: Rounds are provided in chronological order (round_index 1, 2, 3, ...) with
   no gaps

8. **No retrospective re-computation**: Once a Sankey is constructed for a discussion, it is
   immutable; no retroactive updates occur

9. **Visualization rendering**: The actual visual rendering of the Sankey diagram (SVG, canvas, etc.)
   is implementation-defined; this spec defines the data structure only

10. **Report format**: The specific export format (JSON, PDF, etc.) for the discussion report is
    implementation-defined; JSON is recommended for MVP
