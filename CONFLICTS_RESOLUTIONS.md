# OpenDiscuss Protocol Suite: Conflicts & Resolutions

**Version**: MVP v0.1
**Date**: 2026-01-29
**Status**: Conflicts Identified - Resolution Recommendations Provided

## Overview

This document identifies critical conflicts, ambiguities, and integration gaps discovered during parallel planning of the 6-spec OpenDiscuss Protocol Suite. Each conflict includes severity assessment, impact analysis, and recommended resolution.

## Conflict Classification

- **CRITICAL**: Blocks implementation or creates contradictory requirements
- **HIGH**: Creates ambiguity that will cause integration issues
- **MEDIUM**: Affects implementation clarity or performance
- **LOW**: Minor optimization or documentation improvement

---

## CRITICAL Conflicts

### C1: Auto-Question Autonomy Contradiction

**Severity**: CRITICAL
**Affected Specs**: Spec 1 (Discussion Protocol), Spec 6 (Question Progression)
**Status**: UNRESOLVED

**Conflict Description**:
- **Shared Invariant** states: "Auto-question mode runs autonomously once started (no host approval or intervention)"
- **Spec 6 FR-031** states: "Host MUST explicitly trigger round advancement in both modes"
- **Spec 6 User Story 2** states: Round "begins automatically after timing window"

**Impact**:
- Implementation teams will have contradictory requirements
- Host control vs. automation boundary is undefined
- Could lead to UX confusion about when host intervention is needed

**Recommended Resolution**:
Clarify that "autonomous" applies ONLY to question generation, not round advancement:

1. **Auto-Generated Mode Behavior**:
   - Question generation executes automatically without host approval (autonomous)
   - Generated question does NOT require host review or approval
   - Host STILL explicitly triggers round advancement after generation completes
   - "Timing window" in User Story 2 refers to generation time, not round progression

2. **Updated Shared Invariant**:
   ```
   OLD: "Auto-question mode runs autonomously once started (no host approval or intervention)"
   NEW: "Auto-question mode generates questions autonomously without host approval,
        but host still explicitly triggers round advancement in both modes"
   ```

3. **Implementation Guidance**:
   - Spec 6 generates question immediately after Sankey completion
   - System displays "Question ready - Host may advance round when ready"
   - Host clicks "Start Next Round" to begin submission window
   - This maintains synchronous control while automating question creation

**Files to Update**:
- Spec 1: Discussion Protocol - Update round advancement trigger specification
- Spec 6: Question Progression - Clarify FR-031 and User Story 2
- Shared Invariants: Update auto-question autonomy definition

**Test Cases Required**:
- Auto mode: Verify question generates without host input
- Auto mode: Verify round does NOT advance until host trigger
- Host-defined mode: Verify host controls both question and advancement

---

### C2: Approval Deadline Undefined

**Severity**: CRITICAL
**Affected Specs**: Spec 1 (Discussion Protocol), Spec 3 (Summarization & Approval)
**Status**: UNRESOLVED

**Conflict Description**:
- Spec 3 allows participants to approve summaries "after submission window closes"
- No maximum approval deadline is defined
- Could block round progression indefinitely if participants never approve

**Impact**:
- Discussions could stall indefinitely waiting for approvals
- Host has no mechanism to proceed if participants abandon approval
- Violates Synchronous Deliberation principle (Principle VI)

**Recommended Resolution**:
Define explicit approval timeout with dropout mechanism:

1. **Approval Deadline Formula**:
   ```
   approval_deadline = submission_window_end + 10 minutes
   ```

2. **Timeout Behavior**:
   - Participants who submit but don't approve within deadline are marked as dropouts
   - Their unapproved submissions are NOT included in clustering
   - Round proceeds after deadline even if some approvals incomplete
   - System logs dropout with reason: `APPROVAL_TIMEOUT`

3. **UI Requirements**:
   - Display countdown timer during approval phase
   - Show warning at 2 minutes remaining
   - Show final warning at 30 seconds remaining

4. **Edge Cases**:
   - If 100% of participants timeout: Round completes with zero clusters
   - If partial timeout: Round proceeds with approved submissions only
   - Timed-out participants CAN still participate in next round (not permanently excluded)

**Files to Update**:
- Spec 1: Add approval phase timing to round state machine
- Spec 3: Add FR for approval deadline and timeout behavior
- Spec 2: Update dropout detection to include approval timeouts

**Test Cases Required**:
- Partial approval timeout: Verify round proceeds with approved-only
- 100% approval timeout: Verify round completes empty
- Late approval (after deadline): Verify summary rejected as stale

---

### C3: Sankey Completion Signal Mechanism Undefined

**Severity**: CRITICAL
**Affected Specs**: Spec 5 (Sankey Construction), Spec 6 (Question Progression)
**Status**: UNRESOLVED

**Conflict Description**:
- Spec 6 assumes Spec 5 provides "clear completion event/signal" to trigger auto-generation
- Spec 5 does NOT explicitly define this signal mechanism
- Integration contract is incomplete

**Impact**:
- Implementation teams cannot integrate Spec 5 → Spec 6 data flow
- Auto-question generation doesn't know when to start
- Could lead to race conditions or polling inefficiency

**Recommended Resolution**:
Define explicit event-based signaling contract:

1. **Signal Mechanism** (Event Bus Pattern):
   ```python
   # Spec 5 emits event when Sankey construction completes
   event_bus.emit(
       event_type="sankey.construction.complete",
       payload={
           "discussion_id": str,
           "round_id": str,
           "sankey_graph": SankeyGraph,
           "timestamp": datetime
       }
   )
   ```

2. **Spec 6 Listener**:
   ```python
   # Spec 6 subscribes to event
   @event_bus.on("sankey.construction.complete")
   def on_sankey_complete(payload):
       if discussion.mode == "AUTO_GENERATED":
           generate_next_question(payload["sankey_graph"])
   ```

3. **Fallback Mechanism** (if event bus unavailable):
   - Spec 5 sets `round.sankey_status = COMPLETED` in database
   - Spec 6 polls every 2 seconds with max 30-second timeout
   - After timeout, Spec 6 logs error and notifies host for manual intervention

4. **Contract Specification**:
   - Event MUST be emitted within 5 seconds of Sankey computation completing
   - Event MUST include complete SankeyGraph structure
   - Event is idempotent (re-emission safe if needed)

**Files to Update**:
- Spec 5: Add FR for completion signal emission
- Spec 6: Add FR for signal subscription and handling
- Contract 4 in PROTOCOL_SUITE_INDEX.md: Define signal specification

**Test Cases Required**:
- Normal path: Verify signal triggers auto-generation within 2 seconds
- Missing signal: Verify fallback polling activates
- Double signal: Verify idempotency (no duplicate question generation)

---

## HIGH Priority Conflicts

### H1: Question Display Responsibility Unclear

**Severity**: HIGH
**Affected Specs**: Spec 2 (Input Collection), Spec 6 (Question Progression)
**Status**: UNRESOLVED

**Conflict Description**:
- Spec 6 produces validated question text
- Spec 2 collects input in response to question
- Neither spec explicitly owns question display to participants

**Impact**:
- UI implementation unclear about where to show question
- Could lead to inconsistent display or missing question text
- Affects participant understanding of what they're responding to

**Recommended Resolution**:
Assign display responsibility to Spec 2 with explicit contract:

1. **Interface Contract**:
   ```python
   # Spec 6 → Spec 2 contract
   class RoundQuestion:
       question_id: str
       question_text: str  # 10-200 chars, validated
       round_id: str
       display_config: {
           "position": "top",  # or "overlay"
           "emphasis": "high",
           "lock": True  # immutable once round starts
       }
   ```

2. **Display Requirements** (Spec 2):
   - Question MUST be visible above submission input area
   - Question MUST remain visible throughout submission window
   - Question MUST be immutable (cannot change once displayed)
   - Question MUST be accessible (screen reader compatible)

3. **Handoff Timing**:
   - Spec 6 provides question BEFORE round begins
   - Spec 1 validates question exists before advancing round
   - Spec 2 displays question simultaneously with submission window opening

**Files to Update**:
- Spec 2: Add FR for question display requirements
- Spec 6: Add contract specification for question handoff
- Contract 5 in PROTOCOL_SUITE_INDEX.md: Add display responsibility

**Test Cases Required**:
- Question visible throughout submission window
- Question immutable during active round
- Question accessible via screen reader

---

### H2: Ephemeral Data Retention Duration Underspecified

**Severity**: HIGH
**Affected Specs**: Spec 2 (Input Collection), Spec 3 (Summarization & Approval)
**Status**: UNRESOLVED

**Conflict Description**:
- Specs use term "ephemeral" for raw submission retention
- No explicit time-to-live (TTL) or deletion trigger defined
- Could lead to unnecessary storage costs or premature deletion

**Impact**:
- Implementation teams don't know when to delete raw submissions
- Could retain PII longer than necessary (privacy concern)
- Could delete too early and break regeneration feature

**Recommended Resolution**:
Define explicit TTL with state-based deletion:

1. **Retention Policy**:
   ```
   Raw submission persists until FIRST of:
   1. Summary reaches terminal state (APPROVED or REJECTED_FINAL)
   2. Approval deadline expires (submission_window_end + 10 minutes)
   3. Round advances to next round
   4. Discussion terminates
   ```

2. **Deletion Trigger**:
   ```python
   # Spec 3 triggers deletion after approval
   def on_summary_approved(summary):
       submission = get_submission(summary.submission_id)
       submission.schedule_deletion(delay_seconds=300)  # 5-minute grace period

   # Spec 1 triggers deletion on round advance
   def on_round_advance(round):
       submissions = get_submissions(round_id=round.id)
       for s in submissions:
           if s.status != "DELETED":
               s.delete_immediately()
   ```

3. **Grace Period Rationale**:
   - 5-minute grace period allows for correction-based regeneration
   - After grace period, raw text irretrievable (approved summary is canonical)
   - Host can export discussion report before termination to preserve approved summaries

**Files to Update**:
- Spec 2: Add FR for retention policy and deletion triggers
- Spec 3: Add deletion coordination logic
- Data model: Add `scheduled_deletion_at` field to Submission entity

**Test Cases Required**:
- Approved summary: Verify raw submission deleted after 5 minutes
- Round advance: Verify all unapproved submissions deleted immediately
- Regeneration window: Verify raw text available for correction

---

## MEDIUM Priority Conflicts

### M1: Cluster Assignment Lookup Performance

**Severity**: MEDIUM
**Affected Specs**: Spec 4 (Clustering), Spec 5 (Sankey Construction)
**Status**: UNRESOLVED

**Conflict Description**:
- Spec 5 needs efficient `cluster_of(user_id, round)` lookups for edge computation
- Spec 4 provides only `member_user_ids: List[str]` in ThoughtSpace entity
- Requires O(n*m) iteration to find user's cluster (n=users, m=clusters)

**Impact**:
- Inefficient edge computation for large participant counts
- Could violate Spec 5 performance requirement (process 100 users <2 seconds)
- Forces Spec 5 to build inverted index, duplicating work

**Recommended Resolution**:
Spec 4 provides pre-built inverted index:

1. **Enhanced ThoughtSpace Output**:
   ```python
   class ClusteringResult:
       clusters: List[ThoughtSpace]
       user_to_cluster_map: Dict[str, str]  # {user_id: cluster_id}
       round_id: str
   ```

2. **Index Construction** (Spec 4):
   ```python
   def build_user_index(clusters):
       index = {}
       for cluster in clusters:
           for user_id in cluster.member_user_ids:
               index[user_id] = cluster.cluster_id
       return index
   ```

3. **Spec 5 Usage**:
   ```python
   # O(1) lookup instead of O(m) iteration
   prev_cluster = result_r.user_to_cluster_map[user_id]
   curr_cluster = result_r1.user_to_cluster_map[user_id]
   edge = Edge(prev_cluster, curr_cluster, weight=1)
   ```

**Files to Update**:
- Spec 4: Add user_to_cluster_map to ClusteringResult output
- Contract 3 in PROTOCOL_SUITE_INDEX.md: Update interface contract

**Test Cases Required**:
- 100 users: Verify index construction <200ms
- Edge computation: Verify O(1) lookups used

---

### M2: Terminology Inconsistencies

**Severity**: MEDIUM
**Affected Specs**: All specs (cross-cutting)
**Status**: PARTIALLY RESOLVED (glossary created)

**Conflict Description**:
- Multiple terms for same concept across specs:
  - `participant_id` vs `user_id`
  - `ThoughtSpace` vs `Cluster`
  - `submission_window` vs `input_window`
  - `advance_round()` vs `progress_round()`

**Impact**:
- Implementation confusion about entity relationships
- Code review friction
- API inconsistency

**Recommended Resolution**:
Adopt CANONICAL_GLOSSARY.md terms (already created):

1. **Standard Terms**:
   - `user_id` (everywhere, not participant_id)
   - `ThoughtSpace` (entity name in code and docs)
   - `submission_window` (timing term)
   - `advance_round()` (method name)

2. **Enforcement**:
   - Add linter rules to flag deprecated terms
   - Update all 6 spec documents with standard terminology
   - Include glossary reference in PR template

**Files to Update**:
- All 6 spec documents: Replace non-standard terms
- API contracts: Standardize field names
- Code style guide: Reference CANONICAL_GLOSSARY.md

**Test Cases Required**:
- Linter: Verify deprecated terms flagged in new code

---

## LOW Priority Conflicts

### L1: Spec Numbering Documentation Inconsistency

**Severity**: LOW
**Affected Specs**: Spec 3, Spec 4
**Status**: UNRESOLVED

**Conflict Description**:
- Spec 3 header says "Spec 2" but filename is `003-summarization-approval`
- Spec 4 says "Spec 3" but filename is `004-clustering-alignment`

**Impact**:
- Minor documentation confusion
- Search/reference errors

**Recommended Resolution**:
Update spec headers to match filenames:
- `specs/003-*/spec.md` → "# Spec 3: Micro-Summarization & Approval Protocol"
- `specs/004-*/spec.md` → "# Spec 4: Semantic Clustering & Hybrid Alignment Protocol"

**Files to Update**:
- `specs/003-summarization-approval/spec.md` (line 1)
- `specs/004-clustering-alignment/spec.md` (line 1)

---

## Resolution Implementation Checklist

### Phase 1: Critical Path (Must resolve before implementation)
- [ ] C1: Update shared invariants and Spec 1/6 for auto-question autonomy
- [ ] C2: Define approval deadline (10 minutes) in Spec 1/3
- [ ] C3: Implement event bus signal for Sankey completion

### Phase 2: High Priority (Resolve during Phase 1 implementation)
- [ ] H1: Assign question display to Spec 2
- [ ] H2: Define ephemeral data retention policy

### Phase 3: Medium Priority (Resolve during Phase 2-3 implementation)
- [ ] M1: Add user_to_cluster_map to Spec 4 output
- [ ] M2: Update all specs with CANONICAL_GLOSSARY.md terms

### Phase 4: Low Priority (Resolve in polish phase)
- [ ] L1: Fix spec numbering in headers

---

## Conflict Resolution Authority

**Decision Process**:
1. Technical conflicts (C1-C3, H1-H2): Lead architect reviews, team votes if needed
2. Performance conflicts (M1): Tech lead decides based on benchmarks
3. Documentation conflicts (M2, L1): Documentation owner updates

**Escalation Path**:
If resolution blocked → Create RFC → 48-hour review period → Team decision → Update specs

---

## Version History

- **v0.1 (2026-01-29)**: Initial conflict analysis from parallel planning sessions

---

## Related Documents

- `PROTOCOL_SUITE_INDEX.md`: Protocol architecture and dependencies
- `CANONICAL_GLOSSARY.md`: Standardized terminology
- `MVP_ACCEPTANCE_TEST_PLAN.md`: Verification criteria
- `.specify/memory/constitution.md`: Constitutional principles
