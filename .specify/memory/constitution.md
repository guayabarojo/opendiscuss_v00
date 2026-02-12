<!--
  SYNC IMPACT REPORT
  ==================
  Version Change: [INITIAL] → 1.0.0
  Change Type: INITIAL CONSTITUTION

  Principles Defined:
  - I. Parallel-First Architecture
  - II. Intent Fidelity
  - III. Semantic Accuracy Over Aesthetics
  - IV. Temporal Transparency
  - V. Community-Bounded Context
  - VI. Synchronous Deliberation (MVP)
  - VII. Representation Not Adjudication

  Sections Added:
  - Core Principles (7 principles)
  - Technical Constraints
  - MVP Boundaries
  - Governance

  Templates Status:
  ✅ .specify/templates/plan-template.md - Constitution Check section updated with all 7 principles
  ✅ .specify/templates/spec-template.md - Constitution compliance note added, independent testability preserved
  ✅ .specify/templates/tasks-template.md - Constitution compliance note added, parallel execution preserved
  ⚠ .claude/commands/*.md - Review for OpenDiscuss-specific guidance updates (follow-up recommended)

  Follow-up TODOs:
  - RATIFICATION_DATE set to initial constitution date (2026-01-27)
  - Future amendments will update LAST_AMENDED_DATE and increment version
-->

# OpenDiscuss Constitution

## Core Principles

### I. Parallel-First Architecture

All participant input MUST be collected simultaneously within each round. The system MUST NOT
support replies, threading, or turn-taking during input collection. Each participant's response
MUST be independent and non-reactive within a round.

**Rationale**: This eliminates the O(n) "who speaks next" bottleneck that limits participation
and efficiency in traditional discussions. Parallel input scales with participation rather than
being constrained by it.

**Implementation Requirements**:
- Input collection interfaces MUST NOT display other participants' responses during active input
- Round timers MUST enforce simultaneous collection windows
- No participant may respond to another participant's input within the same round

### II. Intent Fidelity

Each participant response MUST be interpreted and summarized individually. The normalized summary
MUST be approved by the participant before entering aggregation. No response may be included in
synthesis without explicit participant approval.

**Rationale**: Ensures that the system represents what participants actually mean, not what the
AI interprets without validation. Prevents amplification of rhetoric or verbosity. Maintains
trust through participant control over their represented position.

**Implementation Requirements**:
- Every response generates exactly one proposed summary
- Summary approval MUST be explicit (not implicit/timeout-based)
- Participants MUST be able to revise summaries before approval
- Unapproved summaries MUST NOT influence aggregation or visualization

### III. Semantic Accuracy Over Aesthetics

Aggregation into thought spaces MUST prioritize semantic clustering accuracy over visual
simplicity. Low-frequency ideas MUST persist as independent thought spaces rather than being
forced into nearby clusters. No merging may occur that distorts participant intent for the sake
of diagram neatness.

**Rationale**: Preserves minority views and prevents false consensus. A deliberation system that
sacrifices accuracy for aesthetics fails its core purpose of representing collective thinking
faithfully.

**Implementation Requirements**:
- Clustering MUST use non-LLM semantic methods with measurable similarity thresholds
- Minimum cluster size constraints are PROHIBITED
- Visual design MUST accommodate variable numbers of thought spaces per round
- Thought space labels MUST reflect actual participant language, not AI-generated abstractions

### IV. Temporal Transparency

The Sankey diagram MUST represent participant movement across rounds, not static idea snapshots.
Flow widths MUST reflect actual participant transitions between thought spaces. Engagement decay,
consolidation, and fragmentation MUST be visible without artificial normalization or constructs.

**Rationale**: Understanding how collective thinking evolves requires seeing both what people
think and how their thinking changes. Static representations hide the dynamics that reveal
convergence, divergence, and re-framing.

**Implementation Requirements**:
- Each participant MUST be associated with exactly one thought space per round they participate in
- Flows between columns MUST be computed strictly from participant movement (not similarity scores)
- Participants who stop responding MUST cause natural flow mass reduction (no backfilling)
- Cross-round visualization MUST preserve temporal ordering without retrospective adjustment

### V. Community-Bounded Context

All discussions MUST occur within communities. Communities MUST define governance rules, context
boundaries, and trust assumptions. Interpretation and synthesis MUST respect community context.

**Rationale**: Context frames meaning. Without community boundaries, "parallel input" becomes
noise and "thought spaces" become ambiguous. Communities provide the shared understanding needed
for coherent deliberation.

**Implementation Requirements**:
- Users MUST join a community before participating in discussions
- Community admins MUST be able to define discussion creation and participation rules
- System prompts for summarization and clustering MUST include community context
- Cross-community discussion references are PROHIBITED in MVP

### VI. Synchronous Deliberation (MVP)

Discussions MUST be time-boxed, synchronous events with enforced round timers. Typical sessions
MUST complete in under 60 minutes across 3-5 rounds. Asynchronous participation is explicitly
out of scope for MVP.

**Rationale**: MVP focuses on real-time collaborative sense-making. Async introduces complexity
around late arrivals, partial participation, and temporal alignment that is deferred post-MVP.

**Implementation Requirements**:
- Round timers MUST be enforced (3-6 min input, ~10 min total per round)
- Discussions MUST have defined start/end times
- Late arrivals after round start are PROHIBITED in MVP
- Partial-round participation (e.g., skipping rounds) causes natural flow dropout per Principle IV

### VII. Representation Not Adjudication

The system MUST represent collective thinking without producing decisions, votes, rankings,
probabilities, scores, or forced convergence. The Sankey diagram is the primary output; it shows
what people think and how thinking moves, not what the "right answer" is.

**Rationale**: Adjudication requires authority the system doesn't have. Premature convergence
mechanisms privilege speed over understanding. The system's value is making collective thinking
visible, not replacing human judgment about what to do with that understanding.

**Implementation Requirements**:
- No voting mechanisms in visualization or synthesis
- No "winning idea" highlights or rankings
- No confidence scores or probability estimates for thought spaces
- No automated convergence detection that implies "discussion is done"
- Final outputs MUST include the complete Sankey diagram, not derivative metrics

## Technical Constraints

### Clustering Model (Locked)

**Per-Round Clustering**: Each round MUST be clustered independently using pure semantic methods.

**Cross-Round Alignment**: Lightweight centroid matching MAY be used across rounds ONLY for label
continuity, color continuity, and interpretability. Cross-round alignment MUST NOT influence
within-round clustering or flow computation.

**Rationale**: Hybrid model balances data accuracy (pure per-round clustering) with user
experience (readable cross-round labels). Keeps alignment purely presentational.

### Sankey as Canonical Representation

The Sankey diagram MUST be the primary interface for participants to review collective thinking.
Alternative visualizations are secondary and MUST NOT contradict Sankey data.

**Rationale**: Sankey uniquely captures volume (width), distribution (relative presence), movement
(flows), and time (columns). No other visualization simultaneously represents what people think,
how many think it, and how thinking changes.

## MVP Boundaries

### Explicit Non-Features (MVP)

The following are explicitly OUT OF SCOPE for MVP and MUST NOT be implemented:

- Asynchronous participation or delayed round entry
- Cross-community discussion linking
- Decision-making mechanisms (voting, polling, ranking)
- Automated convergence detection or "discussion complete" signals
- Private/anonymous thought spaces within discussions
- Real-time collaborative editing of summaries
- Historical comparison across multiple discussions
- Export formats beyond final report artifact

### MVP Acceptance Criteria

The MVP is complete ONLY if all of the following hold:

1. Discussions run synchronously inside communities
2. Parallel input is collected per round with enforced timers
3. Summaries are individually generated and user-approved before aggregation
4. Thought spaces are clustered with semantic accuracy (no forced merging)
5. Participant movement is accurately reflected in Sankey flows
6. The Sankey diagram is understandable without narration
7. A final report artifact can be produced and exported
8. All 7 Core Principles are verifiably implemented

## Governance

### Amendment Procedure

This constitution may be amended only through the following process:

1. Proposed amendments MUST be documented with rationale and impact analysis
2. Version number MUST be incremented per semantic versioning rules (see Versioning Policy)
3. Sync Impact Report MUST be updated to reflect template and dependent artifact changes
4. All dependent templates MUST be reviewed for consistency
5. Constitution MUST be committed separately from implementation changes

### Versioning Policy

Constitution version follows semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Backward incompatible governance changes or principle removal/redefinition
- **MINOR**: New principle/section added or materially expanded guidance
- **PATCH**: Clarifications, wording, typo fixes, non-semantic refinements

### Compliance Review

All feature specifications, implementation plans, and pull requests MUST verify compliance with
this constitution:

- Feature specs MUST NOT include out-of-scope MVP features
- Implementation plans MUST include Constitution Check section validating principles
- Code reviews MUST reject implementations violating principles even if functionally correct
- No complexity may be added without explicit justification in plan.md Complexity Tracking table

### Constitution Supersedes Code

In any conflict between this constitution and existing code, documentation, or practices, this
constitution takes precedence. Code MUST be updated to align with constitutional principles.

**Version**: 1.0.0 | **Ratified**: 2026-01-27 | **Last Amended**: 2026-01-27
