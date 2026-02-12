# Feature Specification: Input Collection Protocol

**Feature Branch**: `002-input-collection`
**Created**: 2026-01-27
**Status**: Draft
**Input**: User description: "Spec 1 — Input Collection Protocol - Defines how raw participant input is collected, constrained, and prepared for summarization"

**Constitution Compliance**: All features MUST comply with `.specify/memory/constitution.md`.
Check MVP Boundaries section for explicit non-features before proceeding.

**Dependencies**: This spec depends on Spec 0 (Discussion Protocol - 001-discussion-protocol)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit Text Input During Active Round (Priority: P1)

A participant joins an active discussion round and submits their thoughts via text input. The system
accepts the submission within the time window, normalizes it to text, and forwards it to the
summarization process without modifying the content.

**Why this priority**: This is the most fundamental input mechanism. Without text input collection,
no discussion can occur. It validates the core submission window enforcement and input acceptance.

**Independent Test**: Can be fully tested by opening a round, having a participant type and submit
text within the window, and verifying the submission is accepted and forwarded. Delivers immediate
value by enabling basic participation.

**Acceptance Scenarios**:

1. **Given** a round is active with a 5-minute submission window, **When** a participant types text
   and clicks submit at minute 2, **Then** the submission is accepted and forwarded to summarization
2. **Given** a submission is accepted, **When** it is forwarded to summarization, **Then** the
   original text is preserved without modification
3. **Given** a participant is typing text, **When** they edit their draft before submitting, **Then**
   they can freely modify the text
4. **Given** a participant submits text, **When** the submission is recorded, **Then** the text
   becomes immutable and cannot be edited
5. **Given** the submission window closes, **When** summarization completes, **Then** the raw input
   text is not persisted long-term (ephemeral only)

---

### User Story 2 - Submit Voice Input with Transcription (Priority: P2)

A participant uses voice input during a round. The system transcribes the audio, displays the
transcript to the participant for review, allows re-recording if needed, and forwards the final
transcript text to summarization.

**Why this priority**: Enables lower-friction participation for users who prefer speaking over
typing. Critical for accessibility and mobile use cases.

**Independent Test**: Can be tested by recording voice input, verifying transcription displays
correctly, allowing re-record, and confirming final transcript is forwarded. Delivers value by
expanding participation modes.

**Acceptance Scenarios**:

1. **Given** a round is active, **When** a participant records voice input, **Then** the audio is
   transcribed to text and displayed for review
2. **Given** a transcription is displayed, **When** the participant is not satisfied, **Then** they
   can re-record (audio is replaced, transcript regenerated)
3. **Given** a transcription is reviewed, **When** the participant accepts it, **Then** the
   transcript text is forwarded to summarization (audio is not persisted)
4. **Given** voice input is submitted, **When** summarization completes, **Then** both audio and
   transcript are discarded (ephemeral retention)
5. **Given** a participant re-records, **When** the new recording is transcribed, **Then** the
   previous transcript is completely replaced

---

### User Story 3 - Multiple Submissions Within Round (Priority: P3)

A participant refines their thinking during a round by submitting multiple times (up to the rate
limit). The system accepts each submission, but ensures only one approved summary represents them
in aggregation per the "last approved wins" rule.

**Why this priority**: Enables thoughtful iteration without breaking aggregation invariants. Improves
input quality by allowing participants to evolve their position during the window.

**Independent Test**: Can be tested by having a participant submit 3 times in one round, approving
different summaries, and verifying only the last approved summary is counted. Delivers value by
supporting iteration.

**Acceptance Scenarios**:

1. **Given** a round is active with max 3 submissions allowed, **When** a participant submits once,
   **Then** they can submit again (rate limit not exceeded)
2. **Given** a participant has submitted twice, **When** they attempt a third submission, **Then**
   it is accepted (at rate limit)
3. **Given** a participant has submitted 3 times, **When** they attempt a 4th submission, **Then**
   the system rejects it with explicit feedback about the rate limit
4. **Given** a participant submits multiple times, **When** they approve different summaries,
   **Then** only the last approved summary is forwarded as "counted"
5. **Given** multiple submissions exist, **When** a participant never approves any summary, **Then**
   no submission from them is counted for that round

---

### User Story 4 - Submission Window Enforcement (Priority: P4)

The system enforces strict time boundaries for submission windows. Submissions before the window
opens or after it closes are rejected with explicit, user-visible feedback. Participants see a
countdown timer showing remaining time.

**Why this priority**: Validates synchronous execution constraints and ensures fair timing for all
participants. Critical for protocol invariant enforcement.

**Independent Test**: Can be tested by attempting submissions before/during/after the window and
verifying acceptance/rejection behavior matches timing. Delivers value by ensuring fairness.

**Acceptance Scenarios**:

1. **Given** a round is scheduled to start at 2:00 PM, **When** a participant attempts to submit at
   1:59 PM, **Then** the submission is rejected with feedback that the window is not yet open
2. **Given** a round opens at 2:00 PM with a 5-minute window, **When** the current time is 2:00 PM,
   **Then** submissions are accepted (inclusive start boundary)
3. **Given** a submission window closes at 2:05 PM, **When** a participant attempts to submit at
   2:05:01 PM, **Then** the submission is rejected (exclusive end boundary)
4. **Given** a submission window is active, **When** participants view the interface, **Then** a
   countdown timer displays remaining time
5. **Given** a submission is rejected (outside window), **When** the rejection occurs, **Then**
   explicit user-visible feedback explains why (before/after window)

---

### User Story 5 - Participant Dropout Handling (Priority: P5)

A participant submits in Round 1 but does not submit in Round 2. The system handles this gracefully
by producing no outgoing flow from their Round 1 position, naturally shrinking the total flow mass
without creating synthetic placeholder nodes.

**Why this priority**: Validates dropout semantics critical to temporal transparency. Ensures Sankey
flow accuracy without artificial constructs.

**Independent Test**: Can be tested by having a participant submit in Round 1, skip Round 2, and
verifying no outgoing flow is created (no "no response" node). Delivers value by accurate dropout
representation.

**Acceptance Scenarios**:

1. **Given** a participant submits and approves a summary in Round 1, **When** Round 2 begins and
   they do not submit, **Then** no outgoing flow originates from their Round 1 thought space
2. **Given** 10 participants in Round 1 and 5 drop out in Round 2, **When** flows are calculated,
   **Then** total flow mass shrinks from 10 to 5 (natural reduction)
3. **Given** a participant drops out, **When** the Sankey diagram is rendered, **Then** no
   placeholder or "no response" node is created for them
4. **Given** a participant drops out in Round 2, **When** Round 3 begins, **Then** they can re-enter
   by submitting (no permanent exclusion)
5. **Given** dropout occurs, **When** aggregation completes, **Then** participant identifiers remain
   stable (dropout doesn't break identity tracking)

---

### Edge Cases

- **Submission at exact window boundary**: System must have deterministic behavior - recommended
  inclusive start (accepted at 2:00:00 PM) and exclusive end (rejected at 2:05:00 PM exactly)
- **Rate limit exactly at boundary**: If max is 3 submissions and participant has 3, the 4th must
  be rejected consistently
- **Transcription service failure**: If voice transcription fails, participant receives error and
  may retry or switch to text input (within window)
- **Network interruption during submission**: Partial submissions should either complete via retry
  logic or fail explicitly (no silent data loss)
- **Participant submits multiple modalities**: System accepts both text and voice submissions (each
  counts toward rate limit separately, last approved wins)
- **Empty or whitespace-only submission**: System should reject or handle gracefully (no empty
  summaries)
- **Extremely long text input**: System should enforce reasonable length limits (e.g., 5000
  characters) to prevent abuse

## Requirements *(mandatory)*

### Functional Requirements

#### Input Acceptance & Modalities

- **FR-001**: System MUST accept text input from participants during active submission windows
- **FR-002**: System MUST accept voice input and transcribe it to text during active submission
  windows
- **FR-003**: System MUST normalize both text and voice input to text format before forwarding to
  summarization
- **FR-004**: System MUST preserve original text content without modification during acceptance (no
  interpretation or meaning changes)

#### Submission Window Management

- **FR-005**: System MUST enforce a configurable submission window duration per round (MVP target:
  3-6 minutes)
- **FR-006**: System MUST reject submissions attempted before the window opens with explicit
  user-visible feedback
- **FR-007**: System MUST reject submissions attempted after the window closes with explicit
  user-visible feedback
- **FR-008**: System MUST display a countdown timer to participants showing remaining submission time
- **FR-009**: Submission window boundaries MUST be deterministic (recommended: inclusive start,
  exclusive end)

#### Multiple Submissions & Rate Limiting

- **FR-010**: System MUST allow participants to submit multiple times during a single round
- **FR-011**: System MUST enforce a configurable rate limit per participant per round (MVP
  recommended: max 3 submissions)
- **FR-012**: System MUST reject submissions exceeding the rate limit with explicit feedback
- **FR-013**: System MUST ensure exactly one submission per participant per round is forwarded as
  "counted" (MVP rule: last approved summary wins)

#### Text Input Handling

- **FR-014**: Participants MUST be able to edit text freely before submission (draft state)
- **FR-015**: Once submitted, text input MUST become immutable (no post-submission editing)
- **FR-016**: System MUST forward submitted text to the summarization protocol without content
  modification

#### Voice Input Handling

- **FR-017**: System MUST transcribe voice input and display the transcript to the participant for
  review
- **FR-018**: Participants MUST be able to re-record voice input (replacing previous audio and
  transcript)
- **FR-019**: Participants MUST NOT be able to directly edit transcript text (re-record only)
- **FR-020**: System MUST forward the final accepted transcript to summarization (audio is not
  forwarded)

#### Data Retention

- **FR-021**: System MUST NOT persist raw submissions (text or transcript) long-term beyond
  ephemeral use
- **FR-022**: Raw input MAY exist ephemerally for summarization and error handling only
- **FR-023**: System MUST discard raw audio recordings after transcription is accepted (not persisted)
- **FR-024**: Only approved summaries MUST persist beyond the round completion

#### Dropout Handling

- **FR-025**: If a participant submits in round r but not in round r+1, they MUST produce no
  outgoing Sankey flow
- **FR-026**: Participant dropout MUST cause total flow mass to shrink naturally (no backfilling or
  normalization)
- **FR-027**: System MUST NOT create placeholder or "no response" nodes for dropouts in MVP

#### Error Handling

- **FR-028**: Submission rejections (outside window, rate limit exceeded) MUST be explicit and
  user-visible
- **FR-029**: If summarization fails for a submission, it MUST be considered uncounted
- **FR-030**: Participants whose submission fails summarization MAY resubmit if time allows within
  the window

#### Identity & Participant Tracking

- **FR-031**: System MUST maintain stable participant identifiers across rounds to enable movement
  tracking
- **FR-032**: Participant identifiers MUST link submissions to the same participant across multiple
  rounds

### Key Entities

- **Submission Window**: A time-bounded period during which participants may submit input for a
  specific round. Attributes: start time, end time, duration, round ID. Related to: Round.

- **Submission**: A single unit of raw participant input (text or voice transcript) made during a
  round. Attributes: submission ID, participant ID, round ID, submission text, submission timestamp,
  modality (text/voice), counted status. Related to: Participant, Round, Summary.

- **Input Modality**: The method by which a participant provides input. Values: TEXT, VOICE.
  Determines processing path (direct text vs transcription).

- **Rate Limit**: A constraint on the maximum number of submissions a participant may make in a
  single round. Attributes: max submissions (default: 3), current count. Related to: Participant,
  Round.

- **Counted Submission**: The single submission from a participant in a round that is forwarded to
  aggregation (per "last approved wins" rule). Related to: Submission, Summary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Participants can successfully submit text input within a 5-minute window with 95%
  first-attempt success rate

- **SC-002**: Voice input transcription completes and displays to participants within 3 seconds of
  recording completion

- **SC-003**: Submission window enforcement achieves 100% accuracy (no submissions accepted outside
  window boundaries)

- **SC-004**: Rate limiting enforcement achieves 100% accuracy (4th submission always rejected when
  limit is 3)

- **SC-005**: System supports at least 100 concurrent participants submitting within the same
  5-second window without degradation

- **SC-006**: Countdown timer displays with sub-second accuracy and updates in real-time for
  participants

- **SC-007**: Exactly one submission per participant per round is forwarded as "counted" with 100%
  accuracy

- **SC-008**: Participant dropout handling achieves 100% correctness (no synthetic nodes, accurate
  flow mass reduction)

- **SC-009**: Raw input data retention is ephemeral - 0% of raw submissions persist beyond
  summarization completion

- **SC-010**: Submission rejections (outside window, rate limit) provide explicit feedback to users
  100% of the time

### Protocol Correctness

- **SC-011**: Input Collection Protocol can be tested independently using a reference test harness
  with simulated participants

- **SC-012**: Test harness can generate N simulated participants with randomized submission timing,
  multiple submissions, and dropout behavior

- **SC-013**: All correctness criteria (window enforcement, rate limits, counted submission rule,
  ephemeral retention, dropout handling) are verifiable through automated tests

## Assumptions

1. **Transcription service availability**: Voice input transcription is handled by an external
   service or library with adequate accuracy and latency (not specified in this protocol)

2. **Network reliability**: Basic retry logic exists for submission failures, but extended offline
   support is out of scope for MVP

3. **Participant authentication**: Participants are authenticated before entering discussions
   (identity verification handled by community/authentication layer)

4. **Summarization protocol dependency**: This protocol forwards submissions to Spec 2
   (Micro-Summarization & Approval Protocol) which handles summary generation and approval

5. **Rate limit configurability**: Default rate limit of 3 submissions per participant per round is
   configurable by community admins or discussion creators

6. **Timer synchronization**: System clock synchronization across all participants is sufficient for
   countdown timer display (sub-second precision not critical for MVP)

7. **Input length limits**: Reasonable maximum input length (e.g., 5000 characters) is enforced to
   prevent abuse and ensure summarization feasibility

8. **Ephemeral storage scope**: "Ephemeral" means raw input may exist in memory or temporary storage
   for minutes (summarization duration) but is not persisted in databases beyond that

9. **Submission immutability**: Once submitted, text cannot be edited - participants must submit
   again (within rate limits) to revise their input

10. **Dropout re-entry**: Participants who drop out in one round can re-enter in subsequent rounds
    by submitting (no permanent exclusion mechanism)
