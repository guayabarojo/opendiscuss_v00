# Data Model: Micro-Summarization & Approval Protocol

**Feature**: 003-summarization-approval
**Date**: 2026-01-29
**Status**: Complete

## Overview

This document defines all entities, relationships, and validation rules for the Micro-Summarization & Approval Protocol. The data model supports summary generation, bounded regeneration, explicit approval workflow, safety filtering, and last-approved-wins rule.

---

## Entity Relationship Diagram

```
Submission (from Spec 2) ─────< (1:N) Summary
                                    │
                                    ├─────< (0:1) CorrectionSignal
                                    │
                                    └────> (N:1) Participant (from Spec 0)

Summary (status=APPROVED) ──────> ApprovedSummary (Spec 0)
                                         │
                                         └────> ThoughtSpace (Spec 4)
```

---

## Core Entities

### 1. Summary

**Purpose**: Normalized semantic representation of participant submission. Central entity for approval workflow and trust gate.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `summary_id` | UUID | PK, NOT NULL | Unique identifier |
| `submission_id` | UUID | FK, NOT NULL | Source submission (Spec 2) |
| `participant_id` | UUID | FK, NOT NULL | Submitter |
| `round_id` | UUID | FK, NOT NULL | Target round |
| `summary_text` | String | NOT NULL, max 500 chars | 1-2 sentence normalized summary |
| `status` | Enum | NOT NULL | Summary lifecycle state (see below) |
| `regen_count` | Integer | NOT NULL, default 0 | Number of regeneration attempts (0-3) |
| `llm_model` | String | NOT NULL | Model used (gpt-4-turbo | gpt-3.5-turbo) |
| `approved_at` | Timestamp | NULL | Explicit approval timestamp |
| `created_at` | Timestamp | NOT NULL | Initial generation timestamp |
| `safety_flags` | String[] | NULL | If filtered: ["PROFANITY_NEUTRALIZED", "DISALLOWED_CONTENT"] |

**SummaryStatus Enum**:
```
PENDING_REVIEW           # Generated, awaiting participant decision
APPROVED                 # Explicitly approved, enters clustering
REJECTED                 # Rejected by participant, triggers regeneration
SUPERSEDED               # Previously approved but replaced by later approval
REJECTED_FINAL           # Rejected after max regenerations, participant may resubmit
APPROVAL_TIMEOUT         # Approval deadline expired without decision
DISALLOWED_CONTENT       # Safety filter blocked (illegal threats)
```

**Relationships**:
- Belongs to Submission (`submission_id`) - Spec 2 entity
- Belongs to Participant (`participant_id`) - Spec 0 entity
- Belongs to Round (`round_id`) - Spec 0 entity
- May have CorrectionSignal (1:0-1) - correction feedback from participant

**State Transitions**:
```
PENDING_REVIEW → APPROVED (explicit participant approval)
PENDING_REVIEW → REJECTED (participant rejection, regen_count < 2)
  → PENDING_REVIEW (auto-regeneration)
PENDING_REVIEW → REJECTED (participant rejection, regen_count = 2)
  → CORRECTION_SIGNAL_REQUESTED (prompt for correction)
CORRECTION_SIGNAL_REQUESTED → PENDING_REVIEW (correction-based regen)
PENDING_REVIEW → REJECTED_FINAL (rejection after regen_count = 3)
PENDING_REVIEW → APPROVAL_TIMEOUT (approval_deadline expired)
PENDING_REVIEW → DISALLOWED_CONTENT (safety filter blocked approval)
APPROVED → SUPERSEDED (newer approval for same participant + round)
```

**Validation Rules**:
- `summary_text` MUST be 1-2 sentences (validated by LLM prompt, not enforced programmatically)
- `summary_text` MUST be <= 500 characters (hard constraint)
- `regen_count` MUST be 0-3 (bounded regeneration)
- `approved_at` MUST be NULL unless `status = APPROVED`
- `approved_at` MUST be <= `round.approval_deadline`
- Multiple APPROVED summaries for same `(participant_id, round_id)` allowed, but only latest `approved_at` used (last-approved-wins)

**Constitutional Guarantee** (Intent Fidelity - Principle II):
- ONLY summaries with `status = APPROVED` enter clustering (Spec 4)
- Zero summaries with status != APPROVED forwarded to clustering
- Approval is ALWAYS explicit (timeout does NOT auto-approve)

**Indexes**:
- `(submission_id)` - Lookup summary for submission
- `(participant_id, round_id, status)` - Find approved summary per participant per round
- `(round_id, status)` - List all approved summaries for clustering
- `(approved_at)` - Order summaries by approval time (last-approved-wins)

---

### 2. CorrectionSignal

**Purpose**: Participant feedback after 2 automatic regenerations. Guides final regeneration attempt (attempt 3).

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `signal_id` | UUID | PK, NOT NULL | Unique identifier |
| `summary_id` | UUID | FK, NOT NULL | Summary being corrected |
| `reason_tag` | Enum | NOT NULL | Structured feedback category |
| `feedback_text` | String | NULL, max 240 chars | Optional free-text clarification |
| `created_at` | Timestamp | NOT NULL | Signal submission time |

**ReasonTag Enum**:
```
WRONG_CRUX           # Summary focused on wrong core point
TOO_VAGUE            # Summary not specific enough
MISREPRESENTS_ME     # Summary doesn't reflect participant intent
MISSED_CONSTRAINT    # Summary missed a key constraint
MISSED_SOLUTION      # Summary missed a proposed solution
OTHER                # Free-text feedback required
```

**Relationships**:
- Belongs to Summary (`summary_id`) - 1:0-1 relationship (summary may have correction signal)

**Validation Rules**:
- `reason_tag` MUST be provided (required field)
- `feedback_text` is optional (NULL allowed)
- `feedback_text` MUST be <= 240 characters if provided
- CorrectionSignal only created after `regen_count = 2` (after 2 auto-regenerations)

**Usage in Regeneration**:
```python
# Incorporate correction signal into prompt
if reason_tag == ReasonTag.WRONG_CRUX:
    prompt_addition = f"The participant's main point is about: {feedback_text}"
elif reason_tag == ReasonTag.TOO_VAGUE:
    prompt_addition = f"Be more specific about: {feedback_text or 'the core point'}"
elif reason_tag == ReasonTag.MISREPRESENTS_ME:
    prompt_addition = f"Emphasize: {feedback_text}"
```

**Indexes**:
- `(summary_id)` - Lookup signal for summary
- `(reason_tag)` - Analytics on common rejection reasons

---

## Integration with Spec 0 Entities

### ApprovedSummary (Spec 0)

**Forwarding Logic**:
When `summarization.complete` event is emitted, Spec 3 forwards approved summaries to Spec 4:

```python
async def forward_to_clustering(round_id: str):
    """Select approved summaries per last-approved-wins rule"""
    # Get all APPROVED summaries for round
    approved = await db.query(Summary).filter(
        Summary.round_id == round_id,
        Summary.status == SummaryStatus.APPROVED
    ).all()

    # Group by participant, select latest approved_at
    by_participant = {}
    for summary in approved:
        participant_id = summary.participant_id
        if participant_id not in by_participant:
            by_participant[participant_id] = summary
        else:
            # Keep summary with later approved_at
            if summary.approved_at > by_participant[participant_id].approved_at:
                # Mark previous as SUPERSEDED
                by_participant[participant_id].status = SummaryStatus.SUPERSEDED
                by_participant[participant_id] = summary

    # Forward exactly one summary per participant
    await event_bus.emit("summarization.complete", {
        "round_id": round_id,
        "approved_summaries": [
            {
                "summary_id": s.summary_id,
                "participant_id": s.participant_id,
                "summary_text": s.summary_text,
                "approved_at": s.approved_at
            }
            for s in by_participant.values()
        ]
    })
```

**Contract Guarantee**:
- 100% of forwarded summaries have `status = APPROVED`
- Exactly ONE summary per participant per round
- Last-approved-wins rule applied (latest `approved_at` timestamp)
- Summaries ready for clustering (no further approval needed)

---

## State Machine Summary

### Summary Lifecycle

```
INITIAL GENERATION
  ↓
PENDING_REVIEW (regen_count=0)
  ↓
  ├─ APPROVE → APPROVED ✓ (enters clustering)
  │
  ├─ REJECT → PENDING_REVIEW (regen_count=1, auto-regeneration)
  │   ↓
  │   ├─ APPROVE → APPROVED ✓
  │   │
  │   └─ REJECT → PENDING_REVIEW (regen_count=2, auto-regeneration)
  │       ↓
  │       ├─ APPROVE → APPROVED ✓
  │       │
  │       └─ REJECT → CORRECTION_SIGNAL_REQUESTED
  │           ↓
  │           CORRECTION PROVIDED → PENDING_REVIEW (regen_count=3)
  │           ↓
  │           ├─ APPROVE → APPROVED ✓
  │           │
  │           └─ REJECT → REJECTED_FINAL ✗ (participant may resubmit input)
  │
  └─ TIMEOUT (approval_deadline) → APPROVAL_TIMEOUT ✗ (dropout, may participate next round)
```

### Approval Workflow

```
Submission (Spec 2)
  ↓
Generate Summary (LLM)
  ↓
Apply Safety Filters
  ↓ (if disallowed)
  DISALLOWED_CONTENT ✗
  ↓ (if safe)
PENDING_REVIEW
  ↓
Participant Reviews
  ↓
  ├─ APPROVE → APPROVED → Forward to Clustering (Spec 4)
  │
  ├─ REJECT → Check regen_count
  │   ↓
  │   ├─ regen_count < 2 → Auto-Regenerate (vary strategy)
  │   │
  │   └─ regen_count = 2 → Request Correction Signal
  │       ↓
  │       Regenerate with Correction → PENDING_REVIEW
  │       ↓
  │       └─ REJECT → REJECTED_FINAL
  │
  └─ NO ACTION (wait for deadline) → APPROVAL_TIMEOUT
```

---

## Validation Summary

| Entity | Critical Validations |
|--------|---------------------|
| Summary | status=APPROVED required for clustering, regen_count 0-3, summary_text <= 500 chars, approved_at <= deadline |
| CorrectionSignal | Only after regen_count=2, reason_tag required, feedback_text <= 240 chars |
| Approval Workflow | Exactly one APPROVED summary per participant per round (last-approved-wins), zero unapproved summaries forwarded |

---

## Performance Considerations

**Indexes**: All foreign keys indexed for join performance

**Caching** (Redis):
- LLM responses cached by `hash(submission_text + prompt)` for 1 hour (reduce API costs for identical inputs)
- Approval status cached per participant per round (frequently queried by UI)

**Ephemeral Cleanup**:
- Raw `Submission.submission_text` deleted 5 minutes after `Summary.status = APPROVED`
- Summary entities retained indefinitely (needed for audit, analytics)

**Query Optimization**:
```sql
-- Efficient last-approved-wins query
SELECT DISTINCT ON (participant_id) *
FROM summaries
WHERE round_id = :round_id
  AND status = 'APPROVED'
ORDER BY participant_id, approved_at DESC;
```

---

## Safety Filtering Data Flow

```
Participant Input (raw)
  ↓
Layer 1: Profanity Detection (better-profanity)
  ↓ (if profanity found)
  Neutralize → Clean Text + safety_flags=["PROFANITY_NEUTRALIZED"]
  ↓ (if no profanity)
  Clean Text (unchanged)
  ↓
Generate Summary (LLM with clean text)
  ↓
Layer 2: Threat Detection (OpenAI Moderation API)
  ↓ (if threats detected)
  status=DISALLOWED_CONTENT + safety_flags=["DISALLOWED_CONTENT"] ✗
  ↓ (if safe)
  status=PENDING_REVIEW (normal workflow) ✓
```

**Safety Flags in Summary**:
- `["PROFANITY_NEUTRALIZED"]` - Input contained profanity, neutralized in summary, approval allowed
- `["DISALLOWED_CONTENT"]` - Input contains illegal threats, summary blocked, participant notified to resubmit

---

## Example Data Flow

**Scenario**: Participant submits, rejects twice, provides correction, approves

```
1. Submission created (Spec 2)
   submission_id=A, text="We need more funding and better tools"

2. Generate initial summary
   summary_id=S1, submission_id=A, status=PENDING_REVIEW, regen_count=0
   summary_text="Identifies funding as a key constraint."

3. Participant rejects
   → Regenerate (vary focus: emphasize tools instead of funding)
   summary_id=S1 (updated), status=PENDING_REVIEW, regen_count=1
   summary_text="Proposes improved tools for the project."

4. Participant rejects again
   → Regenerate (simplify language)
   summary_id=S1 (updated), status=PENDING_REVIEW, regen_count=2
   summary_text="Suggests better tools."

5. Participant rejects third time
   → Request correction signal
   summary_id=S1, status=CORRECTION_SIGNAL_REQUESTED

6. Participant provides correction
   signal_id=CS1, summary_id=S1, reason_tag=WRONG_CRUX
   feedback_text="Focus on the funding issue, not tools"

7. Regenerate with correction
   summary_id=S1 (updated), status=PENDING_REVIEW, regen_count=3
   summary_text="Identifies funding as the primary constraint."

8. Participant approves
   summary_id=S1, status=APPROVED, approved_at=2026-01-29T10:05:00Z

9. Forward to clustering (Spec 4)
   Event: summarization.complete, payload includes S1
```

---

**Last Updated**: 2026-01-29
**Schema Version**: 1.0.0
**Next Action**: Generate OpenAPI contracts
