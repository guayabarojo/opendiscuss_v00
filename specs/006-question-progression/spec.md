# Feature Specification: Question Progression Protocol

**Feature Branch**: `006-question-progression`
**Created**: 2026-01-28
**Status**: Draft
**Input**: User description: "Spec 5 — Question Progression Protocol"

**Constitution Compliance**: All features MUST comply with `.specify/memory/constitution.md`.
Check MVP Boundaries section for explicit non-features before proceeding.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Host-Defined Question Sequence (Priority: P1)

A host prepares a discussion by defining all questions upfront. As the discussion progresses through rounds, each pre-defined question appears in sequence. The host controls round advancement timing, but questions follow the predetermined order without requiring further host input.

**Why this priority**: Foundational mode for hosts who want full control over discussion direction and have planned their facilitation strategy in advance.

**Independent Test**: Can be fully tested by creating a discussion with 3 host-defined questions, advancing through all rounds, and verifying questions appear in correct sequence without modification.

**Acceptance Scenarios**:

1. **Given** a host has defined questions ["What challenges do you face?", "How could these be addressed?", "What resources are needed?"] at discussion creation, **When** the discussion starts Round 1, **Then** participants see "What challenges do you face?" as the current question
2. **Given** Round 1 has completed and Sankey has been constructed, **When** the host advances to Round 2, **Then** participants see "How could these be addressed?" without host re-entry
3. **Given** a host-defined question sequence has 5 questions, **When** Round 5 completes, **Then** the system indicates no further rounds are available and discussion can only be terminated

---

### User Story 2 - Auto-Generated Question Flow (Priority: P2)

A host initiates a discussion with only the first question defined. After each round completes and the Sankey diagram is constructed, the system autonomously generates the next question based on the movement patterns and thought spaces visible in the Sankey. Participants see new questions that naturally follow from collective deliberation without host intervention.

**Why this priority**: Enables adaptive discussions where questions emerge from actual participant responses rather than predetermined agenda, reducing host burden.

**Independent Test**: Can be fully tested by creating a discussion with one initial question, completing Round 1, verifying autonomous question generation after Sankey construction, and confirming Round 2 begins with the auto-generated question.

**Acceptance Scenarios**:

1. **Given** a host has created a discussion in auto-question mode with initial question "What are the main barriers?", **When** Round 1 completes and Sankey is constructed, **Then** the system generates a new question (e.g., "How could funding challenges be addressed?") based on observed thought spaces
2. **Given** the auto-generated question is "How could we improve access?", **When** the question is generated, **Then** it appears without host review or approval and Round 2 begins automatically after timing window
3. **Given** a discussion in auto-mode has completed 3 rounds, **When** the host decides to terminate, **Then** no further auto-questions are generated even if the system would have continued

---

### User Story 3 - Question Quality Constraints (Priority: P3)

Regardless of mode (host-defined or auto-generated), all questions follow consistent constraints: they ask "What" or "How" (never "Why"), focus on exploring constraints, solutions, or needs, and avoid forcing convergence through voting or ranking mechanisms.

**Why this priority**: Maintains discussion quality and prevents questions that would violate constitutional principles like "Representation Not Adjudication."

**Independent Test**: Can be fully tested by attempting to create questions that violate constraints (Why questions, yes/no questions, ranking prompts) and verifying the system blocks or transforms them.

**Acceptance Scenarios**:

1. **Given** a host attempts to define the question "Why did you choose that option?", **When** the question is submitted, **Then** the system rejects it with message "Questions must start with 'What' or 'How'"
2. **Given** the auto-question generator produces a question "Do you agree with the funding proposal?", **When** the question is validated, **Then** the system regenerates to produce an open-ended alternative like "What aspects of the funding proposal need discussion?"
3. **Given** a question "Rank these solutions from best to worst", **When** the question is validated, **Then** the system rejects it as violating "Representation Not Adjudication" principle

---

### User Story 4 - Round Advancement Control (Priority: P2)

The host maintains synchronous control over when rounds advance. In host-defined mode, they manually trigger round transitions. In auto-question mode, after the autonomous question generation completes, the host still controls timing of when the next round begins. The host can terminate the discussion at any point without completing all questions.

**Why this priority**: Preserves host agency and prevents runaway autonomous discussions while still benefiting from automated question generation.

**Independent Test**: Can be fully tested by creating discussions in both modes, verifying host can pause before round advancement, and confirming termination works at any stage.

**Acceptance Scenarios**:

1. **Given** a host-defined discussion has completed Round 1, **When** the host is viewing results, **Then** Round 2 does NOT automatically begin until host explicitly advances
2. **Given** an auto-question discussion has generated the next question, **When** the generation completes, **Then** the question is staged but Round 2 waits for host trigger
3. **Given** a discussion is on Round 3 of a 5-question host-defined sequence, **When** the host selects "End Discussion", **Then** no further rounds occur and the final Sankey from Round 3 is marked as the discussion outcome

---

### User Story 5 - Discussion Completion and Termination (Priority: P3)

When all questions are exhausted (host-defined mode) or the host manually terminates (either mode), the discussion enters a completed state. Participants can no longer submit input. The final Sankey diagram and discussion report from the last completed round become the permanent record.

**Why this priority**: Provides clear closure mechanism and ensures discussions don't remain indefinitely open.

**Independent Test**: Can be fully tested by completing all rounds of a host-defined discussion and verifying state changes to "completed" with no further input accepted.

**Acceptance Scenarios**:

1. **Given** a 3-question discussion has completed Round 3, **When** the final Sankey is constructed, **Then** the discussion status becomes "completed" and no "Next Round" option appears
2. **Given** an auto-question discussion is on Round 4, **When** the host clicks "Terminate Discussion", **Then** the Round 4 Sankey is marked as final and discussion report is generated
3. **Given** a discussion is marked "completed", **When** a participant attempts to access the input interface, **Then** they see "Discussion has ended" message and the final Sankey visualization

---

### Edge Cases

- What happens when auto-question generation produces a question that violates constraints (Why/voting/ranking)?
  - System must regenerate (up to MAX_RETRIES, e.g., 3 attempts) or fall back to host-defined mode if generation consistently fails
- How does the system handle a host abandoning an active discussion?
  - Discussion remains "active" but no rounds advance; system may mark as "stalled" after timeout (e.g., 7 days)
- What happens if auto-question generation encounters an LLM API failure after Sankey construction?
  - System retries with exponential backoff; if all retries fail, host is notified to either provide manual question or terminate
- How does the system prevent infinite auto-question loops?
  - Host retains termination control at all times; no maximum round limit enforced by system (MVP scope)
- What happens when a host changes questions mid-round?
  - Not permitted; questions are immutable once round begins (constitutional integrity)
- How does the system handle a host-defined sequence that skips a question?
  - Not permitted; sequence is linear and complete (questions 1, 2, 3, 4... with no gaps)
- What happens if a host wants to switch from host-defined to auto-mode mid-discussion?
  - Not permitted in MVP; mode is set at discussion creation (architectural simplicity)
- How does the system handle partial rounds (e.g., host terminates during input collection)?
  - Round must complete input collection window before termination; host can terminate after collection but before Sankey construction

## Requirements *(mandatory)*

### Functional Requirements

#### Configuration & Modes

- **FR-001**: System MUST support two distinct question progression modes: Host-Defined and Auto-Generated
- **FR-002**: Host MUST specify progression mode at discussion creation time (mode is immutable thereafter)
- **FR-003**: Host-Defined mode MUST accept a complete ordered list of questions at discussion creation
- **FR-004**: Host-Defined mode MUST enforce minimum 1 question and maximum 10 questions per discussion (MVP scope)
- **FR-005**: Auto-Generated mode MUST accept exactly 1 initial question at discussion creation
- **FR-006**: Auto-Generated mode MUST have no maximum round limit (host controls termination)

#### Host-Defined Question Mode

- **FR-007**: System MUST display questions in exact order provided by host (Q1, Q2, Q3, ...)
- **FR-008**: System MUST NOT allow host to modify question text once round has begun
- **FR-009**: System MUST NOT allow host to skip questions in the sequence
- **FR-010**: System MUST NOT allow host to reorder questions after discussion creation
- **FR-011**: When all host-defined questions are exhausted, system MUST mark discussion as "completed" automatically

#### Auto-Generated Question Mode

- **FR-012**: Auto-question generation MUST execute AFTER Sankey construction (Spec 4) completes for the current round
- **FR-013**: Auto-question generation MUST use the previous round's Sankey graph (nodes, edges, dropout, labels) as primary input
- **FR-014**: Auto-question generation MUST use the current round's question and all previous questions as context
- **FR-015**: Auto-question generation MUST execute autonomously without host intervention
- **FR-016**: Generated question MUST be staged for next round (does not require host approval before use)
- **FR-017**: System MUST persist all auto-generated questions with provenance metadata (round number, generation timestamp, input Sankey hash)

#### Auto-Question Generation Timing

- **FR-018**: Auto-question generation MUST begin immediately upon Sankey construction completion
- **FR-019**: Auto-question generation MUST NOT delay host's ability to view current round's Sankey results
- **FR-020**: Auto-question generation MUST complete before next round can begin (blocking operation)
- **FR-021**: If generation exceeds timeout threshold (e.g., 30 seconds), system MUST notify host and offer manual question entry as fallback

#### Question Content Constraints (Both Modes)

- **FR-022**: All questions MUST begin with "What" or "How" (case-insensitive validation)
- **FR-023**: System MUST reject questions that begin with "Why", "Do you", "Should we", "Would you", or similar patterns
- **FR-024**: Questions MUST focus on exploring constraints, solutions, needs, or participant perspectives
- **FR-025**: Questions MUST NOT request voting, ranking, or forced preference selection (e.g., "Which is best?", "Rank these options")
- **FR-026**: Questions MUST NOT include yes/no binary choice prompts
- **FR-027**: Questions MUST be between 10 and 200 characters in length
- **FR-028**: Host-defined questions that violate constraints MUST be rejected at discussion creation with specific error messages
- **FR-029**: Auto-generated questions that violate constraints MUST trigger regeneration (up to MAX_RETRIES = 3 attempts)
- **FR-030**: If auto-generation fails validation after MAX_RETRIES, system MUST notify host and request manual question input

#### Round Advancement Control

- **FR-031**: Host MUST explicitly trigger round advancement in both modes (no automatic progression)
- **FR-032**: Round advancement MUST be blocked until current round's Sankey construction completes
- **FR-033**: In Auto-Generated mode, round advancement MUST be blocked until auto-question generation completes
- **FR-034**: Host MUST be able to view current round results (Sankey, report) before advancing to next round
- **FR-035**: System MUST display "Ready for Next Round" indicator when all blocking operations complete
- **FR-036**: Host MUST be able to terminate discussion at any point (does not require completing all questions)

#### Discussion Termination

- **FR-037**: Host MUST be able to manually terminate discussion from any round in both modes
- **FR-038**: Manual termination MUST be blocked if current round is in active input collection (host must wait for window to close)
- **FR-039**: Manual termination MUST be allowed after input collection but before Sankey construction (partial round termination)
- **FR-040**: When discussion is terminated, system MUST mark the last completed round's Sankey as the final output
- **FR-041**: If partial round termination occurs, system MUST compute partial Sankey from collected inputs before marking as final
- **FR-042**: Terminated discussions MUST NOT allow further participant input or round creation
- **FR-043**: System MUST generate final discussion report upon termination (identical to Spec 4 report for last round)

#### State Management & Persistence

- **FR-044**: System MUST maintain discussion state: created, round_N_active, round_N_collecting, round_N_processing, round_N_complete, completed, terminated
- **FR-045**: System MUST persist current question for each round (immutable once round begins)
- **FR-046**: System MUST persist question provenance: host-defined vs auto-generated, generation timestamp, input context
- **FR-047**: System MUST track current round number (starts at 1, increments on advancement)
- **FR-048**: System MUST track total round count (dynamic in auto-mode, fixed in host-defined mode)

#### Protocol Composition (Spec 0 Compliance)

- **FR-049**: Question Progression MUST enforce linear sequence (Round 1 → Round 2 → Round 3, no branching)
- **FR-050**: Question Progression MUST ensure exactly one active question per round (no parallel questions)
- **FR-051**: Question Progression MUST respect synchronous control principle (host triggers all round transitions)
- **FR-052**: Question Progression MUST allow host to terminate at any time (host-bounded progression)
- **FR-053**: In Auto-Generated mode, question generation MUST execute autonomously between rounds without host action (autonomous auto-question execution)

## Key Entities *(include if feature involves data)*

- **Question**: Represents a single question in the discussion. Attributes: text (string), order (integer), mode (host_defined | auto_generated), provenance (metadata), validation_status (valid | rejected), round_number (integer)
- **Question Sequence**: Ordered collection of questions for host-defined mode. Attributes: questions (array), total_count (integer), current_index (integer), completion_status (in_progress | completed)
- **Round Progression**: Tracks discussion state across rounds. Attributes: current_round (integer), total_rounds (integer | null for auto-mode), advancement_status (ready | blocked | waiting_generation), termination_allowed (boolean)
- **Auto-Question Generator**: Encapsulates autonomous question generation. Attributes: input_sankey (graph reference), previous_questions (array), generation_timestamp (datetime), retry_count (integer), validation_result (pass | fail | retry)
- **Discussion State Machine**: Manages discussion lifecycle. States: created, active, collecting, processing, ready_for_advancement, completed, terminated. Transitions: host_advance(), auto_generate(), host_terminate()
- **Question Constraints Validator**: Validates question content against requirements. Rules: starts_with_what_how, no_why_questions, no_ranking, no_yes_no, length_bounds, no_voting
- **Host Control Interface**: Provides host with round advancement and termination controls. Actions: advance_round(), terminate_discussion(), view_results(). Status indicators: sankey_complete, question_ready, input_collection_active

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Host-defined discussions with N questions must complete exactly N rounds before automatic completion
- **SC-002**: Auto-generated discussions must produce valid next questions within 30 seconds of Sankey completion for 95% of cases
- **SC-003**: 100% of questions (host-defined and auto-generated) must pass constraint validation before round begins
- **SC-004**: Host must be able to terminate discussion from any round state with confirmation appearing within 2 seconds
- **SC-005**: Round advancement must be blocked until all prerequisite operations (input collection, summarization, clustering, Sankey, auto-generation) complete
- **SC-006**: Question provenance metadata must be persisted for 100% of auto-generated questions for audit and analysis
- **SC-007**: Auto-question regeneration must succeed within MAX_RETRIES (3 attempts) for 98% of cases
- **SC-008**: Host-defined questions that violate constraints must be rejected at creation with specific error messages for 100% of cases
- **SC-009**: Manual termination during active input collection must be gracefully blocked with clear messaging ("Wait for input window to close")
- **SC-010**: Final discussion report must be generated within 5 seconds of termination for discussions up to 10 rounds

### Protocol Correctness

- **SC-011**: System MUST maintain linear question sequence without gaps or branches for 100% of discussions
- **SC-012**: System MUST enforce one-question-per-round invariant verified through state machine testing
- **SC-013**: System MUST preserve host synchronous control: round advancement only on explicit host trigger

### Integration Validation

- **SC-014**: Question Progression must integrate with Spec 0 Discussion Protocol: one question per round, linear advancement, host-controlled timing
- **SC-015**: Auto-question generation must receive Sankey graph output from Spec 4 as input (structured JSON or equivalent)
- **SC-016**: Question text must be consumed by Spec 1 Input Collection as the prompt displayed to participants

## Assumptions *(external dependencies or design decisions)*

1. **LLM Availability**: Auto-question generation assumes LLM API is available and responsive (failure handling: retries + fallback)
2. **Sankey Completion Signal**: Spec 4 provides clear completion event/signal that triggers auto-generation (e.g., webhook, message queue, status flag)
3. **Host Interface Exists**: Host has UI/API to view results, advance rounds, and terminate discussions (not specified in this protocol)
4. **Participant Visibility**: Participants automatically see new question when round begins (handled by Spec 1 Input Collection)
5. **Question Immutability**: Once round begins, question cannot be edited (constitutional integrity over host flexibility)
6. **No Parallel Questions**: MVP scope explicitly prohibits multiple simultaneous questions in a round (architectural simplicity)
7. **No Question Branching**: MVP scope prohibits conditional question paths or participant-specific questions (architectural simplicity)
8. **Max Host-Defined Questions**: 10-question limit for host-defined mode is arbitrary MVP scope (may expand based on testing)
9. **Auto-Question Context Window**: Auto-generator receives full Sankey graph + all previous questions (no context length limit assumed)
10. **Termination Finality**: Terminated discussions cannot be resumed or extended (one-way state transition)

## Out of Scope *(MVP boundaries from constitution)*

- Asynchronous discussions (violates Synchronous Deliberation principle)
- Multiple simultaneous questions per round (violates One Active Question invariant)
- Conditional question branching based on participant responses (architectural complexity)
- Participant-proposed questions (violates host control and could introduce coordination overhead)
- Question editing after round begins (violates immutability and could confuse participants mid-input)
- Automatic round advancement without host trigger (violates synchronous control principle)
- Cross-discussion question templates or libraries (MVP scope limitation)
- Question voting or participant-driven question selection (violates Representation Not Adjudication and host control)
- Multi-language question translation (localization out of MVP scope)
- Question recommendation engine for host (UX enhancement beyond protocol scope)

## Dependencies

- **Spec 0 (Discussion Protocol)**: Question Progression implements Round entity and linear sequence invariant
- **Spec 1 (Input Collection)**: Question text is consumed by input collection protocol as participant prompt
- **Spec 4 (Sankey Construction)**: Auto-question generation requires Sankey graph as input (nodes, edges, labels, dropout)
- **LLM Service**: Auto-question generation requires external LLM API (e.g., Claude API, GPT-4 API)
- **Host Interface**: Requires host UI/API to trigger round advancement and termination (implementation detail)

## Risks & Mitigations *(optional but recommended)*

- **Risk**: Auto-generation produces repetitive or low-quality questions
  - **Mitigation**: Include all previous questions in generation context to avoid repetition; implement constraint validation with regeneration
- **Risk**: LLM API failure causes discussion to stall between rounds
  - **Mitigation**: Retry with exponential backoff; fallback to host-defined question entry after MAX_RETRIES
- **Risk**: Host abandons discussion mid-flow leaving participants confused
  - **Mitigation**: Mark discussions as "stalled" after timeout; notify participants of host absence
- **Risk**: Auto-generated questions inadvertently bias next round's responses
  - **Mitigation**: Constraint validation ensures questions remain open-ended and exploratory (no leading questions)
- **Risk**: Question immutability prevents hosts from correcting typos/errors
  - **Mitigation**: Accept as MVP limitation; provide preview with confirmation before round begins
