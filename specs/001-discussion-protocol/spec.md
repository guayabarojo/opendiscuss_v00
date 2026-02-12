# Feature Specification: OpenDiscuss Discussion Protocol (System Spine)

**Feature Branch**: `001-discussion-protocol`
**Created**: 2026-01-27
**Status**: Draft
**Input**: User description: "Spec 0 — OpenDiscuss Discussion Protocol (System Spine) - Defines the overall discussion protocol, lifecycle, invariants, and composition of sub-protocols"

**Constitution Compliance**: All features MUST comply with `.specify/memory/constitution.md`.
Check MVP Boundaries section for explicit non-features before proceeding.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete Single-Round Discussion (Priority: P1)

A community administrator creates a discussion with a single question. Participants join, submit their
input in parallel during the timed window, approve their summaries, and view the resulting Sankey
diagram showing how their contributions clustered into thought spaces.

**Why this priority**: This is the atomic unit of the entire system. Without a working single-round
discussion, no other functionality is possible. It validates all core protocol invariants.

**Independent Test**: Can be fully tested by creating a discussion, collecting 5+ participant inputs,
generating summaries, clustering them into thought spaces, and rendering a single-column Sankey
diagram. Delivers immediate value by showing what people think in structured form.

**Acceptance Scenarios**:

1. **Given** a community exists with 10 members, **When** an admin creates a discussion with Question
   "Should we adopt remote work?", **Then** the system opens a timed submission window (3-6 minutes)
2. **Given** a submission window is open, **When** participants submit text/voice input in parallel,
   **Then** each submission is accepted without blocking others
3. **Given** participants have submitted input, **When** the submission window closes, **Then** the
   system generates normalized summaries for each submission
4. **Given** summaries are generated, **When** participants review and approve their summaries,
   **Then** only approved summaries enter aggregation
5. **Given** approved summaries exist, **When** the system performs semantic clustering, **Then**
   thought spaces are created representing coherent ideas (no forced merging)
6. **Given** thought spaces are defined, **When** the Sankey column is rendered, **Then** each
   thought space width reflects the proportion of participants aligned with that idea

---

### User Story 2 - Multi-Round Discussion with Participant Movement (Priority: P2)

A community runs a discussion across 3-5 rounds with different questions each round. Participants see
the evolving Sankey diagram showing how collective thinking shifts, consolidates, or fragments. The
system tracks how individual participants move between thought spaces across rounds.

**Why this priority**: This validates the temporal aspect of the protocol and the core innovation of
movement-based representation. Enables understanding how ideas evolve over multiple rounds.

**Independent Test**: Can be tested by running a 3-round discussion, ensuring participants submit in
multiple rounds, and verifying that Sankey flows accurately represent participant transitions between
thought spaces. Delivers value by showing thinking evolution over time.

**Acceptance Scenarios**:

1. **Given** Round 1 completed with 3 thought spaces (A, B, C), **When** Round 2 begins with a new
   question, **Then** participants can submit new input without seeing others' Round 2 responses
2. **Given** a participant was in thought space A (Round 1) and submits input clustered to thought
   space D (Round 2), **When** flows are calculated, **Then** a flow from A→D is created with width
   reflecting that participant's movement
3. **Given** multiple rounds have completed, **When** the Sankey diagram is displayed, **Then**
   columns represent rounds in temporal order with flows showing participant transitions
4. **Given** 5 participants drop out after Round 2, **When** Round 3 completes, **Then** total flow
   mass naturally shrinks (no synthetic "dropout" nodes created)
5. **Given** a discussion completes all rounds, **When** the final report is generated, **Then** it
   includes the complete multi-column Sankey showing convergence/divergence patterns

---

### User Story 3 - Participant Iteration Within Round (Priority: P3)

During a single round's submission window, a participant submits multiple times to refine their
thinking. The system accepts multiple submissions but ensures only one approved summary represents
that participant in aggregation.

**Why this priority**: Enables thoughtful participation and iteration without breaking the "one
counted representation per participant per round" invariant. Improves input quality.

**Independent Test**: Can be tested by having a participant submit 3 times in one round, approving
different summaries, and verifying only the last approved summary is counted. Delivers value by
allowing participants to refine their contributions.

**Acceptance Scenarios**:

1. **Given** a submission window is open, **When** a participant submits input, receives a summary,
   and decides to refine their thinking, **Then** they can submit again (up to rate limit)
2. **Given** a participant has submitted twice, **When** they approve the summary from submission #2,
   **Then** submission #1's summary is discarded and only #2 is counted
3. **Given** a participant submits 3 times (at rate limit), **When** they attempt a 4th submission,
   **Then** the system rejects it with clear feedback about the rate limit
4. **Given** a participant iterates multiple times, **When** aggregation occurs, **Then** exactly one
   summary from that participant enters the thought space clustering

---

### User Story 4 - Synchronous Time-Boxed Execution (Priority: P4)

A discussion runs as a real-time event with strict timing: 3-6 minute input windows per round, ~10
minutes total per round including summarization and clustering, completing in under 60 minutes for
3-5 rounds.

**Why this priority**: Validates the synchronous execution constraint critical to MVP. Ensures the
system can handle real-time coordination at scale.

**Independent Test**: Can be tested by scheduling a discussion, enforcing time windows, and measuring
that rounds complete within timing constraints. Delivers value by enabling focused, time-efficient
deliberation.

**Acceptance Scenarios**:

1. **Given** a discussion is scheduled to start at 2:00 PM, **When** the start time is reached,
   **Then** Round 1's submission window opens and displays a countdown timer to participants
2. **Given** a 5-minute submission window, **When** 5 minutes elapse, **Then** the window closes and
   no further submissions are accepted for that round
3. **Given** the submission window closes, **When** summarization and clustering begin, **Then** the
   entire round processing (summary generation + approval + clustering + rendering) completes in ~10
   minutes
4. **Given** a 5-round discussion, **When** all rounds complete, **Then** total elapsed time is under
   60 minutes
5. **Given** a participant attempts to submit after window closes, **When** they hit submit, **Then**
   the system rejects it with clear feedback that the window is closed

---

### Edge Cases

- **Participant submits exactly at window boundary**: System must have deterministic behavior for
  submissions at the exact start/end timestamp (inclusive start, exclusive end recommended)
- **All participants choose the same thought space**: Sankey column should show single wide node, no
  artificial splitting for visual variety
- **Single participant has unique view**: Even with 1 participant, a thought space must be created
  (no minimum cluster size)
- **Participant approves summary in Round 1 but never returns**: Natural dropout - no flow originates
  from their Round 1 position in Round 2 Sankey
- **Summarization fails for a submission**: Participant sees error, may resubmit if time allows, but
  if window closes, they're uncounted for that round
- **Zero participants submit in Round 2**: Valid state - Round 2 produces empty Sankey column (or
  discussion ends)
- **Participant submits twice, approves both summaries**: Only last approval counts (MVP rule: last
  approved wins)

## Requirements *(mandatory)*

### Functional Requirements

#### Core Protocol Execution

- **FR-001**: System MUST execute discussions as a sequence of synchronous rounds, each associated
  with exactly one question
- **FR-002**: System MUST enforce a timed submission window per round (configurable, 3-6 minutes MVP
  target)
- **FR-003**: System MUST accept text and voice (transcribed to text) input during submission windows
- **FR-004**: System MUST allow participants to submit multiple times within a round, subject to rate
  limits (MVP: max 3 submissions per participant per round)
- **FR-005**: System MUST reject submissions outside the active submission window with explicit error
  feedback

#### Parallelism & Independence

- **FR-006**: System MUST collect participant input in parallel without displaying other participants'
  current-round submissions during input collection
- **FR-007**: System MUST NOT provide reply, threading, or turn-taking mechanisms within rounds
- **FR-008**: Each participant's submission MUST be processed independently (no dependencies on other
  participants' submission order or timing)

#### Summarization & Approval

- **FR-009**: System MUST generate a normalized semantic summary for each submission
- **FR-010**: System MUST require explicit participant approval before any summary enters aggregation
  (no implicit approval or timeout-based approval)
- **FR-011**: Participants MUST be able to revise or reject proposed summaries
- **FR-012**: System MUST ensure exactly one approved summary per participant per round enters
  aggregation (MVP rule: last approved wins if multiple)

#### Thought Space Aggregation

- **FR-013**: System MUST cluster approved summaries into thought spaces using semantic similarity
  without forced merging
- **FR-014**: System MUST preserve low-frequency ideas as independent thought spaces (no minimum
  cluster size enforced)
- **FR-015**: System MUST define thought spaces per round (round-local semantics, no cross-round
  semantic enforcement)
- **FR-016**: Thought space labels MUST reflect actual participant language, not AI-generated
  abstractions

#### Sankey Construction & Movement

- **FR-017**: System MUST render a Sankey column for each completed round showing thought spaces with
  widths proportional to participant counts
- **FR-018**: System MUST compute flows between rounds based strictly on participant movement (each
  participant associated with exactly one thought space per round)
- **FR-019**: Flow widths MUST reflect the actual number of participants transitioning between
  thought spaces
- **FR-020**: System MUST handle participant dropout naturally by reducing total flow mass (no
  synthetic "dropout" nodes)
- **FR-021**: Sankey columns MUST be ordered temporally (Round 1, Round 2, ..., Round N)

#### Invariant Enforcement

- **FR-022**: System MUST NOT produce votes, decisions, rankings, probabilities, or forced consensus
  outputs
- **FR-023**: System MUST NOT persist raw submissions (text or transcripts) beyond ephemeral use for
  summarization
- **FR-024**: System MUST maintain participant identity across rounds to enable movement tracking
- **FR-025**: System MUST ensure no unapproved semantic content enters aggregation under any
  circumstances

#### Discussion Lifecycle

- **FR-026**: Discussions MUST be bounded events with defined start and end times
- **FR-027**: System MUST support 3-5 rounds per discussion (MVP target)
- **FR-028**: System MUST complete discussions in under 60 minutes total (MVP target)
- **FR-029**: System MUST produce a final report artifact containing the complete Sankey diagram
  after discussion completion

### Key Entities

- **Discussion**: A bounded, synchronous event within a community consisting of a sequence of rounds.
  Attributes: start time, end time, community ID, round count. Related to: Community, Rounds.

- **Round**: A timed interval within a discussion associated with one question. Attributes: round
  number, question text, submission window duration, start time, end time. Related to: Discussion,
  Submissions, Thought Spaces.

- **Participant**: A community member who submits input during rounds. Attributes: participant ID,
  community membership. Related to: Submissions, Approved Summaries.

- **Submission**: Raw participant input for a round. Attributes: participant ID, round ID, submission
  text, submission timestamp, modality (text/voice). Related to: Participant, Round, Summary.

- **Summary**: Normalized semantic representation of a submission. Attributes: submission ID,
  summary text, approval status, approval timestamp. Related to: Submission, Thought Space.

- **Thought Space**: Semantic cluster of approved summaries within a round. Attributes: round ID,
  thought space ID, label, participant count, centroid (for cross-round alignment only). Related to:
  Round, Summaries, Flows.

- **Flow**: Participant movement between thought spaces across rounds. Attributes: source thought
  space, target thought space, participant count. Related to: Thought Spaces (source and target).

- **Sankey Column**: Visual representation of thought spaces for a single round. Attributes: round
  ID, thought spaces, total participant count. Related to: Round, Thought Spaces.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A discussion with 10 participants completes 3 rounds in under 45 minutes from start to
  final report generation

- **SC-002**: 100% of approved summaries are accurately represented in thought space clustering (no
  summaries lost or duplicated)

- **SC-003**: Participant movement tracking achieves 100% accuracy (every participant who submits in
  consecutive rounds generates exactly one flow)

- **SC-004**: Parallel input collection supports at least 100 concurrent participants submitting
  within the same 5-second window without degradation

- **SC-005**: Zero unapproved summaries enter aggregation across all test scenarios (strict invariant
  enforcement)

- **SC-006**: Sankey diagram renders within 5 seconds after clustering completes for discussions with
  up to 100 participants

- **SC-007**: Participant dropout (not submitting in subsequent rounds) is correctly reflected by
  reduced flow mass with zero synthetic nodes created

- **SC-008**: 95% of participants successfully submit input within a 5-minute submission window on
  first attempt (low friction)

- **SC-009**: Multiple submissions per participant are handled correctly with exactly one counted
  summary 100% of the time

- **SC-010**: Final report artifact includes complete Sankey diagram, all thought space labels, and
  participant counts for 100% of completed discussions

### Protocol Correctness

- **SC-011**: All protocol invariants (Parallelism, One Counted Representation, User-Approved
  Interpretation, Round-Local Semantics, Movement-Based Representation, No Forced Convergence,
  Synchronous Execution) are verifiable through automated test harness

- **SC-012**: Sub-protocol composition is testable independently (Input Collection, Summarization,
  Clustering, Sankey Construction can be validated in isolation)

## Assumptions

1. **Community infrastructure exists**: This spec assumes communities are already implemented as
   containers for discussions (dependency on community management feature)

2. **Semantic clustering algorithm**: Assumes a non-LLM semantic clustering method is available (e.g.,
   embedding-based clustering with configurable similarity thresholds)

3. **Transcription service**: Voice input transcription is handled by an external service or library,
   not specified here

4. **Rate limiting**: Default rate limit of 3 submissions per participant per round is configurable
   by community admins

5. **Timing precision**: System clock synchronization across all participants is sufficient for
   synchronous execution (sub-second precision not required for MVP)

6. **Network resilience**: Basic retry logic for submission failures exists, but extended offline
   support is out of scope for MVP

7. **Participant authentication**: Assumes participants are authenticated community members (identity
   verification handled by community layer)

8. **Cross-round question selection**: Assumes questions for each round are predefined or selected by
   the discussion creator (question progression logic is a sub-protocol)

9. **Data retention compliance**: Ephemeral raw input handling assumes compliance requirements allow
   discarding raw submissions after summary approval

10. **Visualization rendering**: Sankey diagram rendering assumes a standard visualization library or
    component is available (rendering details not specified here)
