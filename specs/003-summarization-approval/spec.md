# Feature Specification: Micro-Summarization & Approval Protocol

**Feature Branch**: `003-summarization-approval`
**Created**: 2026-01-27
**Status**: Draft
**Input**: User description: "Spec 2 — Micro-Summarization & Approval Protocol - Convert raw user input into neutral semantic summaries gated by user approval"

**Constitution Compliance**: All features MUST comply with `.specify/memory/constitution.md`.
Check MVP Boundaries section for explicit non-features before proceeding.

**Dependencies**: This spec depends on Spec 0 (Discussion Protocol - 001-discussion-protocol) and Spec 1 (Input Collection - 002-input-collection)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate and Approve Summary (Priority: P1)

A participant submits input during a round. The system generates a normalized, 1-2 sentence summary
preserving the core intent. The participant reviews the summary and approves it, making it eligible
for aggregation into thought spaces.

**Why this priority**: This is the trust gate for the entire system. Without summary generation and
approval, no semantic content can enter aggregation. It validates the core "user-approved
interpretation" invariant.

**Independent Test**: Can be fully tested by submitting raw input, receiving a generated summary,
and approving it. Delivers immediate value by ensuring participant intent is faithfully represented.

**Acceptance Scenarios**:

1. **Given** a participant has submitted text input "I think we should adopt a hybrid model with 3
   days in office and 2 days remote", **When** the system generates a summary, **Then** it produces
   a 1-2 sentence neutral summary like "Proposes a hybrid work model with 3 office days and 2 remote
   days per week"
2. **Given** a summary is generated, **When** the participant reviews it, **Then** they see the
   summary text and options to approve or reject
3. **Given** a participant reviews a summary, **When** they click approve, **Then** the summary
   status changes to APPROVED and becomes eligible for aggregation
4. **Given** a summary is approved, **When** it is persisted, **Then** it includes approved_at
   timestamp, round_id, user_id, and summary_id
5. **Given** multiple summaries exist for different participants, **When** they are approved, **Then**
   only approved summaries are forwarded to clustering (unapproved summaries are excluded)

---

### User Story 2 - Reject and Regenerate Summary (Priority: P2)

A participant reviews a generated summary and finds it doesn't accurately capture their intent. They
reject it, triggering automatic regeneration. The system produces a new candidate summary for review,
allowing up to 2 automatic regenerations.

**Why this priority**: Enables participants to refine how they're represented without resubmitting
input. Critical for intent fidelity and trust in the summarization process.

**Independent Test**: Can be tested by submitting input, rejecting the first summary, and verifying
a new summary is automatically generated (up to 2 regenerations). Delivers value by improving
representation accuracy.

**Acceptance Scenarios**:

1. **Given** a participant reviews a generated summary, **When** they click reject, **Then** the
   system increments regen_count and automatically generates a new candidate summary
2. **Given** a participant has rejected once (regen_count=1), **When** they reject the second
   summary, **Then** the system regenerates again (regen_count=2, at automatic limit)
3. **Given** regeneration occurs, **When** the new summary is generated, **Then** it uses the same
   raw input but may vary the summarization strategy (e.g., emphasize constraint vs solution)
4. **Given** a participant rejects twice, **When** the second regeneration is presented, **Then**
   they can still approve or reject (automatic regeneration exhausted but user can still reject)
5. **Given** a participant approves after one rejection, **When** the summary is persisted, **Then**
   regen_count=1 is recorded for analytics

---

### User Story 3 - Persistent Rejection with Correction Signal (Priority: P3)

A participant rejects the summary after 2 automatic regenerations. The system prompts them to
provide a correction signal (reason tags and optional feedback). The system regenerates once more
using this signal. If still rejected, the summary is marked REJECTED_FINAL and the participant may
resubmit input.

**Why this priority**: Handles edge cases where automatic regeneration fails. Provides a path to
improve summary quality while maintaining bounded retries. Prevents participant frustration.

**Independent Test**: Can be tested by rejecting 2 summaries, providing correction signal, and
verifying final regeneration attempt. Delivers value by maximizing approval success rate.

**Acceptance Scenarios**:

1. **Given** a participant has rejected twice (regen_count=2), **When** they reject again, **Then**
   the system prompts for a correction signal with reason tags (WRONG_CRUX, TOO_VAGUE,
   MISREPRESENTS_ME, MISSED_CONSTRAINT, MISSED_SOLUTION, OTHER)
2. **Given** the correction signal prompt is displayed, **When** the participant selects a reason
   tag (e.g., WRONG_CRUX) and optionally adds feedback (<= 240 chars), **Then** the system
   regenerates using this signal
3. **Given** the correction signal is used, **When** regeneration occurs, **Then** the new summary
   attempts to address the identified issue (e.g., focus on a different core point if WRONG_CRUX)
4. **Given** the correction-based summary is presented, **When** the participant reviews it, **Then**
   they can approve or reject
5. **Given** the participant rejects after correction signal, **When** the rejection is recorded,
   **Then** the summary is marked REJECTED_FINAL and they are notified they may resubmit input (if
   time allows in the round window)

---

### User Story 4 - Safety and Profanity Filtering (Priority: P4)

A participant submits input containing profanity, slurs, or potentially illegal threats. The system
detects this during summarization, strips/neutralizes profanity, and blocks disallowed content. The
participant receives feedback and may resubmit appropriate content.

**Why this priority**: Ensures a safe, respectful deliberation environment. Prevents harmful content
from entering aggregation. Critical for community trust and legal compliance.

**Independent Test**: Can be tested by submitting input with profanity/threats, verifying filtering
occurs, and checking that disallowed content prevents approval. Delivers value by maintaining
community standards.

**Acceptance Scenarios**:

1. **Given** a participant submits input containing profanity (e.g., "This f***ing idea is
   terrible"), **When** the summary is generated, **Then** profanity is stripped or replaced with
   neutral language (e.g., "Opposes this idea strongly")
2. **Given** a participant submits input containing slurs or personal attacks, **When** the summary
   is generated, **Then** the language is neutralized to remove attacks while preserving the
   substantive point
3. **Given** a participant submits input containing illegal threats (if detected), **When**
   summarization occurs, **Then** the system returns safety_flags=["DISALLOWED_CONTENT"] and
   prevents approval
4. **Given** disallowed content is detected, **When** the participant is notified, **Then** they
   receive explicit feedback that the input cannot be used and may resubmit (within time window)
5. **Given** input is filtered for profanity, **When** the summary is approved, **Then** only the
   neutral summary is persisted (raw input with profanity is not stored long-term)

---

### User Story 5 - Multiple Submissions with Last-Approved-Wins (Priority: P5)

A participant submits multiple times during a round (per Spec 1), generating multiple summaries. They
approve different summaries at different times. The system ensures exactly one summary (the last
approved) represents them in aggregation per the "last approved wins" rule.

**Why this priority**: Integrates with Spec 1's multiple submission support. Ensures aggregation
invariants are maintained despite multiple approved summaries. Critical for movement tracking accuracy.

**Independent Test**: Can be tested by submitting 3 times, approving summaries at different points,
and verifying only the last approved summary is forwarded to clustering. Delivers value by supporting
iteration across submissions.

**Acceptance Scenarios**:

1. **Given** a participant submits twice in one round, **When** they approve the summary from
   submission #1, **Then** that summary is marked APPROVED with approved_at timestamp
2. **Given** a participant approves the summary from submission #1, **When** they submit again and
   approve the summary from submission #2, **Then** submission #2's summary has a later approved_at
   timestamp
3. **Given** multiple approved summaries exist for one participant in one round, **When** the system
   forwards summaries to clustering, **Then** only the summary with the latest approved_at timestamp
   is forwarded
4. **Given** a participant has approved summaries from submissions #1 and #2, **When** aggregation
   occurs, **Then** exactly one summary from that participant enters clustering (last approved wins)
5. **Given** a participant approves a summary but never approves any subsequent submissions, **When**
   the round ends, **Then** their first approved summary is used (no later approval exists)

---

### Edge Cases

- **Summary generation failure (LLM error)**: If summarization fails due to LLM error, participant
  receives error message and may resubmit input (if time allows)
- **Empty or extremely short input**: System should either request clarification or generate a minimal
  summary (e.g., "No substantive input provided") for rejection
- **Input exceeds length processable by summarizer**: System should truncate or request shorter input
  before summarization
- **Participant closes approval interface without decision**: Summary remains PENDING_REVIEW until
  participant returns or round ends (uncounted)
- **Participant approves then submission window closes**: Approval is valid even if window closed
  (approval can occur after submission window ends)
- **Summary exactly at 2-sentence boundary**: Both 1 and 2 sentences are valid (hard cap is 2, not a
  range)
- **Context includes previous-round labels but participant is new**: Previous labels are optional and
  may be empty (no error)
- **Correction signal with no feedback text**: Reason tag alone is sufficient (free-text is optional)

## Requirements *(mandatory)*

### Functional Requirements

#### Summary Generation

- **FR-001**: System MUST generate a normalized semantic summary from raw text input received from
  Spec 1
- **FR-002**: Generated summaries MUST be 1-2 sentences (hard cap, not a guideline)
- **FR-003**: Generated summaries MUST be neutral (no persuasion, no emotional framing)
- **FR-004**: Generated summaries MUST preserve the crux (primarily a constraint or solution based
  on discussion mode)
- **FR-005**: Generated summaries MUST NOT introduce facts or claims not present in the raw input
  (no hallucination)
- **FR-006**: Generated summaries MUST NOT name other participants or use "you/they" referencing
- **FR-007**: If input contains multiple points, the summary SHOULD pick the single core point (not
  list everything)

#### Summary Approval

- **FR-008**: System MUST present generated summaries to participants for review before aggregation
- **FR-009**: Participants MUST be able to approve or reject summaries (binary decision)
- **FR-010**: Participants MUST NOT be able to directly edit summary text (MVP constraint: approve
  or reject only)
- **FR-011**: System MUST mark approved summaries with status=APPROVED and approved_at timestamp
- **FR-012**: System MUST ensure no unapproved summaries enter aggregation (strict invariant
  enforcement)

#### Regeneration on Rejection

- **FR-013**: When a participant rejects a summary, the system MUST automatically regenerate a new
  candidate summary
- **FR-014**: System MUST support up to 2 automatic regenerations (MAX_REGEN_AUTOMATIC = 2)
- **FR-015**: Each regeneration MUST increment regen_count
- **FR-016**: Regenerations MUST use the same raw input but MAY vary summarization strategy
- **FR-017**: If a participant approves after rejection(s), the system MUST record the final
  regen_count

#### Correction Signal Handling

- **FR-018**: If a participant rejects after 2 automatic regenerations, the system MUST prompt for a
  correction signal
- **FR-019**: Correction signal MUST include enumerated reason tags: WRONG_CRUX, TOO_VAGUE,
  MISREPRESENTS_ME, MISSED_CONSTRAINT, MISSED_SOLUTION, OTHER
- **FR-020**: Correction signal MAY include optional free-text feedback (<= 240 characters)
- **FR-021**: System MUST regenerate once more using the correction signal
- **FR-022**: If participant rejects after correction-based regeneration, summary MUST be marked
  REJECTED_FINAL
- **FR-023**: When summary is REJECTED_FINAL, participant MUST be notified they may resubmit input
  (if time allows per Spec 1)

#### Safety and Profanity Handling

- **FR-024**: System MUST strip or neutralize profanity in generated summaries
- **FR-025**: System MUST neutralize slurs and personal attacks in generated summaries
- **FR-026**: System MUST detect illegal threats (if possible) and return
  safety_flags=["DISALLOWED_CONTENT"]
- **FR-027**: If disallowed content is detected, the system MUST prevent approval
- **FR-028**: When disallowed content prevents approval, the participant MUST be notified explicitly
- **FR-029**: Participants whose input contains disallowed content MAY resubmit appropriate content
  (if time allows)

#### Multiple Submissions Integration (Spec 1)

- **FR-030**: System MUST allow multiple approved summaries per participant per round (multiple
  submissions from Spec 1)
- **FR-031**: Each approved summary MUST be marked with approved_at timestamp, round_id, user_id,
  and summary_id
- **FR-032**: When forwarding to clustering, system MUST select only the summary with the latest
  approved_at timestamp per participant per round (last approved wins)

#### Data Retention

- **FR-033**: System MUST persist: summary_text, approval_status, regen_count, correction tags (if
  any), submission_id, timestamps
- **FR-034**: System MUST NOT persist raw input text beyond the immediate summarization process
  (ephemeral only)
- **FR-035**: Raw input MAY exist ephemerally for summarization, regeneration, and error handling only

#### Context Inputs

- **FR-036**: System MUST receive current question text as required context for summarization
- **FR-037**: System MAY receive optional discussion memo for additional context
- **FR-038**: System MAY receive optional previous-round cluster labels for context (read-only, not
  enforced)

#### Summary States

- **FR-039**: Summaries MUST exist in one of three states: PENDING_REVIEW, APPROVED, REJECTED_FINAL
- **FR-040**: Only summaries in APPROVED state MUST be eligible for clustering
- **FR-041**: Summaries in REJECTED_FINAL state MUST NOT enter aggregation under any circumstances

### Key Entities

- **Summary**: A normalized semantic representation of raw participant input. Attributes: summary_id,
  summary_text (1-2 sentences), approval_status (PENDING_REVIEW/APPROVED/REJECTED_FINAL),
  approved_at timestamp, regen_count, submission_id, round_id, user_id. Related to: Submission,
  Participant, Round.

- **Summary Constraint**: Rules governing valid summaries. Attributes: max_sentences (2),
  neutrality_required (true), no_hallucination (true), no_participant_references (true). Applied
  during generation.

- **Regeneration Attempt**: A retry of summary generation after rejection. Attributes:
  attempt_number, strategy_variant (optional), correction_signal (optional). Related to: Summary.

- **Correction Signal**: User feedback provided after 2 automatic regenerations. Attributes: reason_tag
  (enum), feedback_text (optional, <= 240 chars). Values: WRONG_CRUX, TOO_VAGUE, MISREPRESENTS_ME,
  MISSED_CONSTRAINT, MISSED_SOLUTION, OTHER. Related to: Summary.

- **Safety Flag**: Indicator of content issues detected during summarization. Values:
  DISALLOWED_CONTENT (illegal threats), PROFANITY_FILTERED, SLUR_NEUTRALIZED. Related to: Summary.

- **Approval Decision**: Participant's choice to approve or reject a summary. Attributes: decision
  (APPROVE/REJECT), decided_at timestamp, reason_tag (if reject with correction signal),
  feedback_text (optional). Related to: Summary, Participant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Summary generation completes within 3 seconds for 95% of inputs (responsive feedback
  to participants)

- **SC-002**: Generated summaries meet all constraints (1-2 sentences, neutral, no hallucination)
  100% of the time

- **SC-003**: 80% of participants approve summaries on first attempt (high intent-fidelity rate)

- **SC-004**: 95% of participants approve summaries within 2 regenerations (bounded retry
  effectiveness)

- **SC-005**: Zero unapproved summaries enter aggregation across all test scenarios (strict
  invariant enforcement)

- **SC-006**: Profanity filtering achieves 99% detection rate for common profanity (safe environment)

- **SC-007**: Illegal threat detection (if implemented) achieves 0% false negative rate (no threats
  in aggregation)

- **SC-008**: Last-approved-wins rule achieves 100% accuracy for participants with multiple approved
  summaries

- **SC-009**: Raw input retention is ephemeral - 0% of raw input persists beyond summarization
  completion

- **SC-010**: Correction signal improves approval rate by at least 20% compared to automatic
  regeneration alone

### Protocol Correctness

- **SC-011**: All summary constraint rules (1-2 sentences, neutral, no hallucination, no
  participant-references) are verifiable through automated tests

- **SC-012**: Regeneration logic (max 2 automatic, correction signal, bounded retries) is testable
  independently

- **SC-013**: Integration with Spec 1 (last-approved-wins) is verifiable through multi-submission
  test scenarios

## Assumptions

1. **LLM availability**: An LLM service is available for summary generation with reasonable latency
   (< 3 seconds for 95% of requests) and reliability

2. **LLM prompt engineering**: The summarization prompt structure can be tuned to achieve high
   intent-fidelity rates (80%+ approval on first attempt)

3. **Context availability**: Current question text is always available as required context;
   discussion memo and previous-round labels are optionally available

4. **Profanity detection**: A profanity/slur detection library or service is available with
   reasonable accuracy (not specified in this protocol)

5. **Threat detection scope**: MVP does not require sophisticated illegal threat detection beyond
   basic keyword matching (advanced threat detection is post-MVP)

6. **Summary length calculation**: "1-2 sentences" is determined by standard sentence boundary
   detection (not character count or word count)

7. **Approval timing**: Participants may approve summaries after the submission window closes (no
   approval deadline tied to submission window)

8. **Correction signal usage**: The correction signal improves regeneration quality but does not
   guarantee approval (participant may still reject)

9. **REJECTED_FINAL handling**: When a summary is marked REJECTED_FINAL, no further regeneration is
   attempted; participant must resubmit input via Spec 1 if they want to be counted

10. **Summarization strategy variance**: "Vary summarization strategy" means adjusting LLM prompt
    focus (e.g., emphasize constraint vs solution) without fundamentally changing the constraints
