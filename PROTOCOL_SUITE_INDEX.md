# OpenDiscuss Protocol Suite Index

**Version**: MVP v0.1
**Date**: 2026-01-29
**Status**: Planning Complete - Ready for Implementation

## Overview

The OpenDiscuss Protocol Suite defines a complete system for synchronous, movement-based collective deliberation. The suite consists of 6 interdependent protocols that orchestrate parallel input collection, semantic clustering, temporal visualization, and autonomous question progression.

## Protocol Composition

### Spec 1: Discussion Protocol (System Spine)
**Path**: `specs/001-discussion-protocol/`
**Branch**: `001-discussion-protocol`
**Role**: Orchestration layer coordinating all sub-protocols
**Dependencies**: Specs 2, 3, 4, 5, 6

**Responsibilities**:
- Discussion lifecycle management (creation → rounds → completion/termination)
- Round state machine (submission → summarization → clustering → Sankey → complete)
- Timing enforcement (submission windows, round transitions)
- Host control coordination (advancement triggers, termination)
- Constitutional principle enforcement across protocol boundaries

**Key Outputs**: Discussion state, round status, final report artifact

---

### Spec 2: Input Collection Protocol
**Path**: `specs/002-input-collection/`
**Branch**: `002-input-collection`
**Role**: Parallel participant input acceptance
**Dependencies**: Spec 1 (discussion context), Spec 6 (question text)

**Responsibilities**:
- Timed submission window enforcement (3-6 minutes)
- Multi-modality input (text + voice with transcription)
- Rate limiting (max 3 submissions per participant per round)
- Countdown timer synchronization
- Dropout detection (absence in round r+1)

**Key Outputs**: Raw submissions forwarded to Spec 3, participant presence indicators

---

### Spec 3: Micro-Summarization & Approval Protocol
**Path**: `specs/003-summarization-approval/`
**Branch**: `003-summarization-approval`
**Role**: LLM-assisted summarization with approval gate
**Dependencies**: Spec 2 (raw submissions), Spec 1 (round context)

**Responsibilities**:
- Per-submission 1-2 sentence summarization (LLM)
- Explicit participant approval requirement (no timeout-based approval)
- Bounded regeneration (2 automatic + 1 correction-based, then REJECTED_FINAL)
- Safety filtering (profanity neutralization, illegal threat blocking)
- Last-approved-wins rule enforcement (multiple submissions per participant)

**Key Outputs**: Approved summaries (exactly one per participant) to Spec 4

---

### Spec 4: Semantic Clustering & Hybrid Alignment Protocol
**Path**: `specs/004-clustering-alignment/`
**Branch**: `004-clustering-alignment`
**Role**: Non-LLM semantic clustering with cosmetic cross-round alignment
**Dependencies**: Spec 3 (approved summaries)

**Responsibilities**:
- Per-round density-based clustering (HDBSCAN-style, no forced merging)
- Outlier preservation as singleton clusters (no minimum cluster size)
- Medoid-based labeling (actual participant language, not AI-generated)
- Cross-round hybrid alignment (visual continuity via display_group_id)
- Centroid persistence for movement tracking

**Key Outputs**: ThoughtSpace clusters with member assignments, centroids, and optional display groups to Spec 5

---

### Spec 5: Temporal Sankey Construction Protocol
**Path**: `specs/005-sankey-construction/`
**Branch**: `005-sankey-construction`
**Role**: Movement-based Sankey diagram generation
**Dependencies**: Spec 4 (cluster assignments), Spec 1 (round ordering)

**Responsibilities**:
- Multi-column Sankey structure (one column per round)
- Node creation from clusters (width = participant percentage)
- Movement-based edge computation (participant transitions between clusters)
- Dropout representation (Option A: natural mass shrinkage, no synthetic nodes)
- Alignment metadata integration (presentational only, does NOT affect edges)

**Key Outputs**: SankeyGraph data structure, Discussion Report (final artifact)

---

### Spec 6: Question Progression Protocol
**Path**: `specs/006-question-progression/`
**Branch**: `006-question-progression`
**Role**: Question sequencing and autonomous generation
**Dependencies**: Spec 1 (round lifecycle), Spec 5 (Sankey for auto-generation)

**Responsibilities**:
- Two modes: Host-Defined (1-10 questions upfront) and Auto-Generated (autonomous LLM-based)
- Question constraint enforcement (What/How only, no Why/voting/ranking)
- Autonomous auto-question generation from Sankey patterns (no host approval)
- Host-controlled round advancement timing (explicit trigger in both modes)
- Linear sequence enforcement (no branching, no skipping)

**Key Outputs**: Validated question text for each round to Spec 2

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                    Spec 1: Discussion Protocol              │
│                       (System Spine)                         │
│  • Orchestrates lifecycle                                    │
│  • Enforces timing                                           │
│  • Coordinates host control                                  │
└────┬──────────────────┬──────────────────┬──────────────────┘
     │                  │                  │
     ▼                  ▼                  ▼
┌─────────┐      ┌─────────────┐    ┌──────────────┐
│ Spec 6  │─────▶│   Spec 2    │───▶│   Spec 3     │
│Question │      │Input Collect│    │Summarization │
│Progress │      │             │    │  & Approval  │
└─────────┘      └─────────────┘    └──────┬───────┘
     ▲                                      │
     │                                      ▼
     │                                ┌──────────────┐
     │                                │   Spec 4     │
     │                                │ Clustering & │
     │                                │  Alignment   │
     │                                └──────┬───────┘
     │                                       │
     │                                       ▼
     │                                ┌──────────────┐
     └────────────────────────────────│   Spec 5     │
                                      │   Sankey     │
                                      │Construction  │
                                      └──────────────┘
```

**Data Flow (Single Round)**:
1. Spec 6 provides question → Spec 2 displays to participants
2. Spec 2 collects submissions → forwards to Spec 3
3. Spec 3 generates summaries → participants approve → forwards to Spec 4
4. Spec 4 clusters summaries → produces ThoughtSpaces → forwards to Spec 5
5. Spec 5 constructs Sankey from clusters + movement → produces SankeyGraph
6. **[Auto mode only]** Spec 5 signals complete → Spec 6 generates next question
7. Host triggers round advancement → cycle repeats

---

## Constitutional Principles (Enforced Across Suite)

All protocols implement and respect the 7 constitutional principles defined in `.specify/memory/constitution.md`:

1. **Parallel-First Architecture** (Spec 2): Independent, simultaneous input collection
2. **Intent Fidelity** (Spec 3): Participant approval required before aggregation
3. **Semantic Accuracy Over Aesthetics** (Spec 4): No forced merging, minority preservation
4. **Temporal Transparency** (Spec 5): Movement-based flows, natural dropout
5. **Community-Bounded Context** (Spec 1): Discussions scoped to communities
6. **Synchronous Deliberation** (Spec 1, 2, 6): Time-boxed rounds, host-controlled timing
7. **Representation Not Adjudication** (Spec 5, 6): No voting, ranking, or forced convergence

---

## Critical Integration Contracts

### Contract 1: Submission → Summarization (Spec 2 → Spec 3)
**Interface**: Submission records with fields: `submission_id`, `user_id`, `round_id`, `submission_text`, `timestamp`, `modality`
**Guarantee**: Raw text normalized (voice transcribed), exactly one submission per participant after last-approved-wins

### Contract 2: Summarization → Clustering (Spec 3 → Spec 4)
**Interface**: Approved summaries with fields: `summary_id`, `user_id`, `summary_text`, `round_id`, `approved_at`
**Guarantee**: 100% approved status, exactly one summary per participant (last-approved-wins rule applied)

### Contract 3: Clustering → Sankey (Spec 4 → Spec 5)
**Interface**: ThoughtSpace clusters with fields: `cluster_id`, `member_user_ids`, `user_count`, `user_pct`, `label_summary`, `centroid_vector`, `display_group_id`
**Guarantee**: 100% user coverage (every participant in exactly one cluster), percentages sum to 1.0 per round

### Contract 4: Sankey → Auto-Question (Spec 5 → Spec 6, Auto mode only)
**Interface**: SankeyGraph with columns (nodes per round), edges (movement), metadata (participant counts)
**Guarantee**: Deterministic structure, movement-based edges (not similarity), alignment metadata presentational only
**CRITICAL GAP**: Signal mechanism for "Sankey complete" event is UNDERSPECIFIED

### Contract 5: Question → Input Collection (Spec 6 → Spec 2)
**Interface**: Question text string (10-200 chars, starts with What/How)
**Guarantee**: Validated, immutable once round begins, constraints enforced (no Why/voting/ranking)
**CRITICAL GAP**: Question display responsibility is UNDERSPECIFIED

---

## Known Conflicts & Ambiguities

### CRITICAL: Auto-Question Autonomy Contradiction (Spec 6)
**Conflict**: Shared invariant states "Auto-question mode runs autonomously once started (no host approval or intervention)" BUT Spec 6 FR-031 requires "Host MUST explicitly trigger round advancement in both modes"

**Resolution Required**: Clarify that "autonomous" means:
- Question generation executes without host intervention
- Question does NOT require host approval
- BUT host still manually triggers round advancement after generation completes

### High Priority: Approval Deadline (Spec 3)
**Ambiguity**: Spec 3 allows approval "after submission window closes" but provides no deadline, potentially blocking round progression indefinitely

**Resolution Required**: Define approval timeout (recommend: submission window + 10 minutes) with dropout for uncompleted approvals

### High Priority: Sankey Completion Signal (Spec 5 → Spec 6)
**Gap**: Spec 6 assumes Spec 5 provides "clear completion event/signal" but Spec 5 does NOT define this mechanism

**Resolution Required**: Define explicit signal contract (event bus message, status flag, or callback)

### Medium Priority: Question Display Responsibility (Spec 6 → Spec 2)
**Gap**: Spec 6 produces question text, Spec 2 collects input, but neither explicitly owns question display to participants

**Resolution Required**: Assign display responsibility to Spec 2 input collection interface

### Medium Priority: Ephemeral Data Retention (Spec 2, Spec 3)
**Ambiguity**: "Ephemeral" retention is underspecified - how long do raw submissions persist for regeneration?

**Resolution Required**: Define max retention as "until summary reaches terminal state (APPROVED or REJECTED_FINAL) or round closes, whichever comes first"

### Low Priority: Cluster Assignment Lookup API (Spec 4 → Spec 5)
**Performance Issue**: Spec 5 needs efficient `cluster_of(user_id, round)` lookups but Spec 4 only provides `member_user_ids` lists

**Resolution Required**: Spec 4 should provide per-round inverted index `{user_id: cluster_id}` or Spec 5 builds this on receipt

---

## MVP Acceptance Criteria

From individual spec success criteria and constitutional requirements:

### End-to-End Flow (3-5 Rounds)
- [ ] Discussion creation with mode selection (host-defined or auto-generated)
- [ ] 3-5 synchronous rounds complete within 60 minutes total
- [ ] Each round: input (3-6 min) → summarization → approval → clustering → Sankey (~10 min total)
- [ ] Final Sankey diagram with movement-based flows generated
- [ ] Discussion report artifact exported

### Parallel Input & Multiple Submissions
- [ ] 100 concurrent participants submit within 5-second window (Spec 2 SC-004)
- [ ] Participants can submit up to 3 times per round
- [ ] Last-approved-wins rule correctly selects counted submission
- [ ] No participant sees others' current-round submissions (Parallel-First Architecture)

### Summary Approval & Rejection
- [ ] Every submission generates normalized 1-2 sentence summary (Spec 3 SC-002)
- [ ] Participant explicitly approves or rejects summary (no timeout-based approval)
- [ ] Rejected summaries trigger automatic regeneration (max 2) then correction signal
- [ ] REJECTED_FINAL summaries never enter aggregation (Spec 3 SC-005)
- [ ] 100% of clustered summaries have APPROVED status (Intent Fidelity)

### Non-LLM Clustering with Minority Preservation
- [ ] Clustering uses density-based algorithm (HDBSCAN or equivalent, non-LLM)
- [ ] Outliers preserved as singleton clusters (no forced merging, Spec 4 SC-004)
- [ ] Low-frequency positions remain visible (Semantic Accuracy Over Aesthetics)
- [ ] Cluster labels use actual participant language (medoid method, not AI-generated)
- [ ] 100% of participants assigned to exactly one cluster per round (Spec 4 SC-002, SC-003)

### Movement-Based Sankey Edges
- [ ] Edges computed from participant transitions (not semantic similarity)
- [ ] Edge width = actual participant count moving between clusters (Spec 5 FR-013, FR-018)
- [ ] Edge totals never exceed user intersection between rounds (Spec 5 SC-003)
- [ ] Alignment metadata (display_group_id) affects presentation ONLY, not edge counts (Spec 4 FR-037, FR-039)

### Dropout with Mass Shrinkage (Option A)
- [ ] Participants who don't submit in round r+1 generate no outgoing edges from round r
- [ ] Total flow mass shrinks naturally across rounds (no backfilling, Spec 5 FR-021)
- [ ] Zero synthetic "dropout" or "no response" nodes created (Spec 2 FR-027, Spec 5 FR-020)
- [ ] Dropout visible through reduced node widths in later rounds

### Autonomous Auto-Question with Constraints
- [ ] **[Auto mode]** After Sankey completes, system generates next question without host approval (Spec 6 FR-015, FR-016)
- [ ] All questions start with "What" or "How" (never "Why") - 100% validation (Spec 6 SC-003)
- [ ] Questions focus on constraints, solutions, or needs (no voting/ranking/binary choice)
- [ ] Auto-generated questions reference Sankey patterns (clusters, movement, labels)
- [ ] Auto-generation completes within 30 seconds (Spec 6 SC-002: 95% of cases)
- [ ] Failed validation triggers regeneration (max 3 attempts) then manual fallback

### Timing & Synchronous Control
- [ ] Submission windows enforce 3-6 minute duration with <100ms precision
- [ ] Round advancement blocked until all sub-protocols complete (Spec 6 FR-032, FR-033)
- [ ] Host explicitly triggers round advancement (no automatic progression, Spec 6 FR-031)
- [ ] Host can terminate discussion at any point (except during active input collection)

### Constitutional Compliance
- [ ] Zero unapproved summaries in clustering (Intent Fidelity - Principle II)
- [ ] Zero forced merges of semantically distinct clusters (Semantic Accuracy - Principle III)
- [ ] Movement tracking 100% accurate (Temporal Transparency - Principle IV)
- [ ] No voting, ranking, or convergence mechanisms (Representation Not Adjudication - Principle VII)

---

## Implementation Sequence Recommendation

### Phase 1: Foundation (Specs 1, 2)
1. **Spec 1 - Discussion Protocol**: Core state machine, round lifecycle, timing enforcement
2. **Spec 2 - Input Collection**: Submission windows, rate limiting, countdown timers

**Milestone**: Single-round discussion with timed input collection

### Phase 2: Summarization & Approval (Spec 3)
3. **Spec 3 - Micro-Summarization**: LLM integration, approval workflow, regeneration logic

**Milestone**: Participants approve summaries before clustering

### Phase 3: Clustering & Visualization (Specs 4, 5)
4. **Spec 4 - Clustering & Alignment**: HDBSCAN clustering, medoid labeling, hybrid alignment
5. **Spec 5 - Sankey Construction**: Multi-column diagram, movement-based edges, Option A dropout

**Milestone**: Multi-round discussion with complete Sankey visualization

### Phase 4: Question Progression (Spec 6)
6. **Spec 6 - Question Progression**: Host-defined mode, auto-question generation, constraint validation

**Milestone**: Fully autonomous multi-round discussions (auto mode)

---

## Version History

- **v0.1 (2026-01-29)**: Initial planning suite compilation, conflicts identified, acceptance criteria defined

---

## Next Steps

1. **Resolve Critical Conflicts**: Auto-question autonomy, approval deadline, Sankey signal mechanism
2. **Define Missing Contracts**: Question display responsibility, cluster lookup API, ephemeral retention TTL
3. **Generate Canonical Glossary**: Standardize terminology across specs (see CANONICAL_GLOSSARY.md)
4. **Create Conflict Resolution Report**: Detailed analysis with recommendations (see CONFLICTS_RESOLUTIONS.md)
5. **Define MVP Acceptance Tests**: Executable test plan with pass/fail criteria (see MVP_ACCEPTANCE_TEST_PLAN.md)
6. **Begin Implementation**: Phase 1 (Specs 1, 2) after conflicts resolved
