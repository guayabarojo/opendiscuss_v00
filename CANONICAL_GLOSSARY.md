# OpenDiscuss Canonical Glossary

**Purpose**: Standardize terminology across all 6 protocol specifications
**Status**: Planning Phase - Subject to Refinement
**Date**: 2026-01-29

---

## Core Entities

### Discussion
**Definition**: A complete deliberation session consisting of 1 or more rounds, bounded by a community context.

**Canonical Fields**:
- `discussion_id` (UUID): Unique identifier
- `community_id` (UUID): Community scope
- `progression_mode` (enum): `host_defined` | `auto_generated`
- `total_rounds` (integer | null): Fixed count for host-defined mode, null for auto-generated mode
- `current_round` (integer): Current round number (1-indexed)
- `status` (enum): `created` | `round_N_active` | `round_N_collecting` | `round_N_processing` | `round_N_complete` | `completed` | `terminated`
- `created_by` (UUID): Host user ID
- `scheduled_start_at` (timestamp): When discussion begins
- `ended_at` (timestamp | null): When discussion completes or terminates

**Used in**: Specs 1, 6 (primary), Specs 2-5 (referenced)

---

### Round
**Definition**: A single iteration of the discussion cycle: question → input collection → summarization → clustering → Sankey construction.

**Canonical Fields**:
- `round_id` (UUID): Unique identifier
- `discussion_id` (UUID): Parent discussion
- `round_number` (integer): Sequential position (1-indexed)
- `question_text` (string): The question participants respond to
- `submission_window_duration` (integer): Duration in seconds (180-360)
- `window_open_at` (timestamp): Submission window start
- `window_close_at` (timestamp): Submission window end
- `status` (enum): `pending` | `input_collection` | `summarization` | `approval` | `clustering` | `sankey_construction` | `completed`

**Used in**: All specs (universal reference point)

---

### Participant
**Definition**: A user who contributes to a discussion within a community.

**Canonical Fields**:
- `participant_id` (UUID): Stable identifier **[PREFERRED TERM]**
- `user_id` (UUID): **[ALTERNATE TERM - same as participant_id]**
- `community_id` (UUID): Community membership
- `display_name` (string): Public identifier

**Terminology Note**: Specs use both `participant_id` and `user_id` interchangeably. **Recommendation**: Standardize on `user_id` for consistency with authentication systems.

**Used in**: All specs

---

### Submission
**Definition**: Raw participant input for a single round, prior to summarization.

**Canonical Fields**:
- `submission_id` (UUID): Unique identifier
- `round_id` (UUID): Round context
- `user_id` (UUID): Participant who submitted
- `submission_text` (string): Raw text content (max 2000 chars)
- `modality` (enum): `TEXT` | `VOICE`
- `transcript_text` (string | null): Transcription if modality is VOICE
- `submitted_at` (timestamp): Submission time
- **Lifecycle**: Ephemeral (deleted after summary approval per Spec 3 FR-034)

**Used in**: Spec 2 (produces), Spec 3 (consumes)

---

### Summary
**Definition**: Normalized 1-2 sentence representation of a submission, requiring explicit participant approval.

**Canonical Fields**:
- `summary_id` (UUID): Unique identifier
- `submission_id` (UUID): Source submission
- `user_id` (UUID): Participant who owns this summary
- `round_id` (UUID): Round context
- `summary_text` (string): Normalized text (1-2 sentences, max 500 chars)
- `status` (enum): `pending_approval` | `approved` | `rejected` | `superseded` | `rejected_final`
- `approved_at` (timestamp | null): Approval timestamp (for last-approved-wins rule)
- `regen_count` (integer): Number of regenerations (0-3)
- **Lifecycle**: Persistent for APPROVED summaries, discarded for REJECTED_FINAL

**Used in**: Spec 3 (produces), Spec 4 (consumes)

---

### ThoughtSpace (Cluster)
**Definition**: A semantic grouping of participant summaries within a single round, representing a coherent position or perspective.

**Canonical Fields**:
- `thought_space_id` (UUID): Unique identifier **[SPEC 1 TERM]**
- `cluster_id` (string): Round-scoped identifier **[SPEC 4 TERM]**
- `round_id` (UUID): Round context
- `member_user_ids` (UUID[]): Participants in this cluster
- `user_count` (integer): Number of participants
- `user_pct` (float): Percentage of round participants (0.0-1.0)
- `label_summary` (string): Medoid summary text (actual participant language)
- `centroid_vector` (float[]): Embedding centroid for alignment
- `display_group_id` (string | null): Cross-round visual continuity group (optional)

**Terminology Note**: Specs use both "ThoughtSpace" (Spec 1) and "Cluster" (Spec 4, 5). **Recommendation**: Use "ThoughtSpace" in user-facing contexts, "Cluster" in internal implementation.

**Used in**: Spec 4 (produces), Spec 5 (consumes), Spec 1 (orchestrates)

---

### SankeyGraph
**Definition**: Temporal visualization structure showing participant movement across rounds via thought space transitions.

**Canonical Fields**:
- `discussion_id` (UUID): Parent discussion
- `columns` (SankeyColumn[]): One column per round
- `edges` (SankeyEdge[]): Movement flows between adjacent rounds
- `metadata` (object): Discussion stats, participant counts, dropout curve

**Sub-Structures**:

**SankeyColumn**:
- `round_number` (integer): Round index
- `nodes` (SankeyNode[]): Thought spaces in this round

**SankeyNode**:
- `node_id` (string): Namespaced as `(round_number, cluster_id)`
- `cluster_id` (string): Source cluster identifier
- `label_summary` (string): Cluster label text
- `user_count` (integer): Participants in this node
- `user_pct` (float): Percentage within round
- `display_group_id` (string | null): Visual continuity group

**SankeyEdge**:
- `from_round` (integer): Source round number
- `to_round` (integer): Target round number (always from_round + 1)
- `from_cluster_id` (string): Source cluster
- `to_cluster_id` (string): Target cluster
- `user_count` (integer): Participants who moved along this edge
- `pct_of_from` (float): Percentage of source node (optional)
- `pct_of_to` (float): Percentage of target node (optional)

**Used in**: Spec 5 (produces), Spec 6 (consumes for auto-generation), Spec 1 (final report)

---

### Question
**Definition**: The prompt that participants respond to in each round.

**Canonical Fields**:
- `question_id` (UUID): Unique identifier
- `round_id` (UUID): Associated round
- `question_text` (string): The question (10-200 chars)
- `source` (enum): `host_defined` | `auto_generated`
- `validation_status` (enum): `valid` | `rejected`
- `provenance` (object): Metadata
  - For auto-generated: `generation_timestamp`, `input_sankey_hash`, `previous_questions`, `retry_count`
  - For host-defined: `creation_timestamp`, `sequence_position`

**Constraints**: Must start with "What" or "How", no "Why", no voting/ranking/binary choice

**Used in**: Spec 6 (produces), Spec 2 (displays), Spec 1 (orchestrates)

---

## Lifecycle States

### Discussion States
**Canonical Enum**: `DiscussionStatus`

```
created              # Discussion initialized, not started
round_N_active       # Round N has begun, question available
round_N_collecting   # Round N input collection window open
round_N_processing   # Round N summarization/clustering/Sankey in progress
round_N_complete     # Round N all processing done, ready for host advancement
completed            # All rounds finished (host-defined mode when questions exhausted)
terminated           # Host manually ended discussion
```

**Note**: `N` is the round number (1-indexed). Example: `round_2_collecting`, `round_3_complete`

**Used in**: Spec 1 (primary), Spec 6 (references)

---

### Round States
**Canonical Enum**: `RoundStatus`

```
pending                # Round created but not started
input_collection       # Submission window open (3-6 min)
summarization          # Generating summaries from submissions
approval               # Waiting for participant approvals
clustering             # Semantic clustering of approved summaries
sankey_construction    # Building Sankey column and edges
completed              # Round processing finished
```

**Used in**: Spec 1 (orchestrates), Specs 2-6 (report)

---

### Summary States
**Canonical Enum**: `SummaryStatus`

```
pending_approval  # Generated, awaiting participant review
approved          # Explicitly approved by participant
rejected          # Rejected, will be regenerated (if retries remain)
superseded        # Was approved, but newer submission approved (last-approved-wins)
rejected_final    # Rejected after max regenerations (3 total), won't enter clustering
```

**Used in**: Spec 3 (primary)

---

## Key Actions

### Host Actions
**Canonical Terms**:
- **Create Discussion**: Initialize new discussion with mode and questions
- **Start Discussion**: Begin first round (transition from `created` to `round_1_active`)
- **Advance Round**: Move from round N to round N+1 (explicit trigger required)
- **Terminate Discussion**: End discussion prematurely (any round, except during active input collection)
- **View Results**: Access Sankey diagrams, cluster summaries, reports (non-mutating)

### Participant Actions
**Canonical Terms**:
- **Submit Input**: Provide text or voice response during submission window
- **Approve Summary**: Explicitly accept generated summary (required gate)
- **Reject Summary**: Decline summary, trigger regeneration or correction signal
- **Provide Correction Signal**: Give feedback after rejections to guide regeneration (optional free text, max 240 chars)
- **Resubmit**: Create new submission after REJECTED_FINAL (if time allows)

### System Actions
**Canonical Terms**:
- **Generate Summary**: LLM-based summarization of raw submission (Spec 3)
- **Regenerate Summary**: Automatic retry after rejection (max 2 automatic + 1 correction-based)
- **Cluster Summaries**: Non-LLM semantic clustering of approved summaries (Spec 4)
- **Compute Alignment**: Cross-round centroid matching for visual continuity (Spec 4)
- **Construct Sankey**: Build multi-column diagram from cluster assignments (Spec 5)
- **Generate Auto-Question**: LLM-based next question from Sankey patterns (Spec 6, auto mode only)
- **Validate Question**: Check question constraints (What/How, no Why/voting/ranking)

---

## Configuration Parameters

### Rate Limits
- **Max Submissions Per Participant Per Round**: 3 (Spec 2 FR-011)
- **Max Automatic Regenerations**: 2 (Spec 3 FR-014)
- **Max Correction-Based Regenerations**: 1 (Spec 3 FR-021)
- **Total Max Regenerations**: 3 (2 automatic + 1 correction)

### Timing
- **Submission Window Duration**: 3-6 minutes (configurable, Spec 2 FR-005)
- **Target Round Duration**: ~10 minutes total (Spec 1 FR-028)
- **Target Discussion Duration**: <60 minutes for 3-5 rounds (MVP, Spec 1 User Story 4)
- **Auto-Question Timeout**: 30 seconds (Spec 6 FR-021)

### Constraints
- **Summary Length**: 1-2 sentences, max 500 characters (Spec 3 FR-002)
- **Submission Length**: Max 2000 characters (Spec 2 FR-020)
- **Question Length**: 10-200 characters (Spec 6 FR-027)
- **Host-Defined Questions**: 1-10 per discussion (Spec 6 FR-004)

### Thresholds
- **Alignment Threshold**: 0.7 cosine similarity (default, Spec 4 FR-032, configurable)
- **Rounding Tolerance**: 0.01% for percentage sums (Spec 4 FR-019, Spec 5 FR-041)

---

## Modes & Options

### Progression Modes
**Canonical Enum**: `ProgressionMode`

```
host_defined      # Host provides ordered list of 1-10 questions at creation
auto_generated    # System generates questions autonomously after each round's Sankey
```

**Used in**: Spec 6 (primary), Spec 1 (configuration)

---

### Input Modalities
**Canonical Enum**: `InputModality`

```
TEXT   # Direct text entry by participant
VOICE  # Audio recording transcribed to text
```

**Used in**: Spec 2 (primary)

---

### Dropout Handling
**Canonical Option**: **Option A (Natural Mass Shrinkage)**

**Definition**: Participants who don't submit in round r+1 after submitting in round r generate no outgoing edges. Total flow mass shrinks naturally across rounds. No synthetic "dropout" or "no response" nodes are created.

**Implementation**: Spec 5 FR-019 through FR-023

**Alternative (OUT OF SCOPE)**: Option B would normalize flows or create dropout nodes (rejected per Constitution Principle IV)

---

## Alignment Terminology

### Hybrid Alignment Model
**Definition**: Two-phase clustering approach combining per-round independence (semantic accuracy) with cross-round continuity (presentation).

**Phase 1 - Per-Round Clustering** (Spec 4 FR-040):
- Clusters computed independently within each round
- No influence from previous rounds
- Pure semantic similarity grouping

**Phase 2 - Cross-Round Alignment** (Spec 4 FR-029-039):
- Centroid-based matching between adjacent rounds
- Assigns `display_group_id` for visual continuity
- **Presentational only** - does NOT affect cluster membership or Sankey edge counts

**Used in**: Spec 4 (implements), Spec 5 (consumes display_group_id)

---

### Display Group
**Definition**: A cross-round visual grouping used for label/color continuity in Sankey diagrams.

**Canonical Fields**:
- `display_group_id` (string): Unique identifier (e.g., "dg_1", "dg_2", ...)
- `member_cluster_ids` (string[]): Clusters across rounds with this display group
- `color_family` (string | null): Visual presentation hint (optional)
- `label_family` (string | null): Labeling hint (optional)

**Invariants**:
- Display groups affect presentation ONLY (Spec 4 FR-039)
- Display groups do NOT affect Sankey edge counts (Spec 5 FR-026)
- Display groups do NOT influence per-round clustering (Spec 4 FR-037)

**Used in**: Spec 4 (produces), Spec 5 (consumes for visualization)

---

## Semantic Clustering Terms

### Medoid
**Definition**: The cluster member whose embedding is closest to the cluster centroid, used as the representative label.

**Usage**: Spec 4 selects the medoid summary from each cluster and uses its exact text as the cluster label (FR-022-024). This preserves participant language (no AI-generated labels).

**Tie-Breaking**: If multiple summaries are equidistant from centroid, use lexicographic order of `summary_id` (Spec 4 FR-044)

---

### Centroid
**Definition**: The mean embedding vector of all cluster members.

**Usage**:
- **Per-Round**: Computed after clustering for each thought space (Spec 4 FR-027)
- **Cross-Round Alignment**: Used for centroid-to-centroid similarity matching (Spec 4 FR-030-031)
- **Persistence**: Stored for movement tracking and alignment (Spec 4 FR-026, FR-028)

---

### Outlier
**Definition**: A data point (approved summary) that does not fit well into any semantic cluster.

**Handling**: Converted to a singleton cluster (Spec 4 FR-014-015). No forced merging; outliers remain visible as independent thought spaces.

---

### Singleton Cluster
**Definition**: A thought space containing exactly one participant.

**Invariants**:
- Always allowed (no minimum cluster size, Spec 4 FR-012)
- Must be visible in Sankey diagram (Spec 4 FR-015, Spec 5 FR-010)
- Counts equally in percentage calculations (Spec 4 FR-019)

---

## Movement & Flow Terms

### Participant Movement
**Definition**: A participant transitioning from thought space A in round r to thought space B in round r+1.

**Computation**: Based on cluster membership assignments, NOT semantic similarity between clusters (Spec 5 FR-011-013, FR-016-018)

---

### Edge (Flow)
**Definition**: A visual connection in the Sankey diagram representing participant movement between two thought spaces in adjacent rounds.

**Canonical Fields**:
- `from_cluster_id`, `to_cluster_id`: Source and target clusters
- `user_count`: Number of participants who moved along this edge
- **Width**: Proportional to `user_count`

**Invariants**:
- Edge exists iff ≥1 participant moved (Spec 5 FR-012)
- Edge count = actual participant transition count (Spec 5 FR-013)
- Edge totals never exceed user intersection between rounds (Spec 5 FR-040)

---

### Dropout
**Definition**: A participant who submits in round r but not in round r+1, generating no outgoing edge from their round r cluster.

**Representation**: Natural mass shrinkage (Option A) - no synthetic nodes, reduced flow width in later rounds (Spec 5 FR-019-023)

---

### User Intersection
**Definition**: The set of participants who submitted (and had approved summaries) in BOTH round r and round r+1.

**Usage**: Used to compute edge totals and validate flow conservation (Spec 5 FR-017, FR-040)

---

## Data Retention Terms

### Ephemeral Data
**Definition**: Data that exists temporarily for processing but is not persisted long-term.

**Ephemeral in OpenDiscuss**:
- Raw submission text (Spec 2 FR-034, Spec 3 FR-034): Deleted after summary approval
- Audio recordings (Spec 2): Not persisted, only transcript retained temporarily
- Draft text (Spec 2): Exists only during active editing session

**Retention Duration**: "Until summary reaches terminal state (APPROVED or REJECTED_FINAL) or round closes" - **NEEDS CLARIFICATION**

---

### Persistent Data
**Definition**: Data retained for the lifetime of the discussion and beyond.

**Persistent in OpenDiscuss**:
- Approved summaries (Spec 3): Required for clustering and Sankey construction
- Thought spaces (Spec 4): Required for Sankey nodes
- Centroids (Spec 4): Required for cross-round alignment
- SankeyGraph (Spec 5): Final report artifact
- Questions (Spec 6): Discussion history with provenance

---

## Terminology Conflicts & Resolutions

### Conflict 1: "Participant ID" vs "User ID"
**Status**: Both terms used interchangeably across specs
**Resolution**: **Standardize on `user_id`** for consistency with authentication systems and external identity providers

### Conflict 2: "ThoughtSpace" vs "Cluster"
**Status**: Spec 1 uses "ThoughtSpace", Specs 4-5 use "Cluster"
**Resolution**: Use "ThoughtSpace" in user-facing contexts (reports, UI), "Cluster" in internal implementation and data structures

### Conflict 3: "Summary" vs "Approved Summary"
**Status**: Specs sometimes ambiguous about whether "summary" includes unapproved
**Resolution**: Default "summary" to APPROVED status in contexts where only approved summaries flow (Spec 3→4, Spec 4→5). Use explicit "unapproved summary" or "pending summary" when status is ambiguous.

### Conflict 4: "Auto-Question" vs "Auto-Generated Question"
**Status**: Both terms used in Spec 6
**Resolution**: **Standardize on "auto-generated question"** (matches `ProgressionMode` enum value)

### Conflict 5: "Round Number" vs "Round Index"
**Status**: Some specs use 0-indexed, some 1-indexed
**Resolution**: **Standardize on 1-indexed `round_number`** (Round 1, Round 2, ..., Round N) for user-facing contexts. Internally, implementations may use 0-indexed arrays.

---

## Abbreviations & Acronyms

- **FR**: Functional Requirement (e.g., FR-001, FR-012)
- **SC**: Success Criterion (e.g., SC-001, SC-005)
- **LLM**: Large Language Model (used in Spec 3 summarization, Spec 6 auto-question generation)
- **HDBSCAN**: Hierarchical Density-Based Spatial Clustering of Applications with Noise (recommended clustering algorithm, Spec 4 Assumption 3)
- **SBERT**: Sentence-BERT (example embedding model, Spec 4 FR-006)
- **MiniLM**: Minimal Language Model (example embedding model, Spec 4 FR-006)
- **MVP**: Minimum Viable Product (scope boundary for initial implementation)
- **P1, P2, P3**: Priority levels in user stories (P1 = highest priority)

---

## Next Steps

1. **Review with Stakeholders**: Validate terminology choices, resolve remaining conflicts
2. **Update All Specs**: Apply canonical terms consistently across Specs 1-6
3. **Generate Type Definitions**: Create shared type schemas (TypeScript interfaces, JSON schemas, or protocol buffers) based on canonical fields
4. **Update Code Comments**: Ensure implementation uses canonical terminology
