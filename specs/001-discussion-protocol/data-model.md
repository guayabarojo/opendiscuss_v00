# Data Model: OpenDiscuss Discussion Protocol

**Feature**: 001-discussion-protocol
**Date**: 2026-01-29
**Status**: Complete

## Overview

This document defines all entities, relationships, and validation rules for the Discussion Protocol system spine. The data model supports discussion lifecycle management, round state machines, participant tracking, and sub-protocol coordination.

---

## Entity Relationship Diagram

```
Community (1) ─────< (N) Discussion
                           │
                           ├─────< (N) Round
                           │        │
                           │        └─────< (N) Submission (ephemeral)
                           │
                           └─────< (N) Participant
                                    │
                                    ├─────< (N) Submission
                                    └─────< (N) ApprovedSummary
                                             │
                                             └────> (1) ThoughtSpace
                                                     │
                                                     ├─────< (N) Flow (outgoing)
                                                     └─────< (N) Flow (incoming)
```

---

## Core Entities

### 1. Discussion

**Purpose**: Container for a bounded, synchronous deliberation event within a community.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `discussion_id` | UUID | PK, NOT NULL | Unique identifier |
| `community_id` | UUID | FK, NOT NULL | Owning community |
| `mode` | Enum | NOT NULL | HOST_DEFINED \| AUTO_GENERATED |
| `total_rounds` | Integer | NOT NULL, 1-10 | Maximum rounds (set at creation) |
| `status` | Enum | NOT NULL | CREATED \| ACTIVE \| COMPLETED \| TERMINATED |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `started_at` | Timestamp | NULL | First round start time |
| `completed_at` | Timestamp | NULL | Final report generation time |
| `terminated_reason` | String | NULL | Reason if TERMINATED |
| `host_user_id` | UUID | FK, NOT NULL | User who created discussion |

**Relationships**:
- Belongs to Community (`community_id`)
- Has many Rounds (1:N)
- Has many Participants (1:N)

**State Transitions**:
```
CREATED → ACTIVE (when first round starts)
ACTIVE → COMPLETED (when all rounds complete + final report generated)
ACTIVE → TERMINATED (host terminates early)
```

**Validation Rules**:
- `total_rounds` MUST be between 1 and 10 (MVP constraint)
- `mode` cannot be changed after discussion starts
- `started_at` MUST be NULL when `status = CREATED`
- `completed_at` MUST be NULL unless `status = COMPLETED | TERMINATED`
- All rounds MUST be COMPLETE before status can transition to COMPLETED

**Indexes**:
- `(community_id, created_at)` - List discussions by community
- `(host_user_id, created_at)` - List discussions by host
- `(status)` - Query active discussions

---

### 2. Round

**Purpose**: Timed phase within a discussion associated with one question.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `round_id` | UUID | PK, NOT NULL | Unique identifier |
| `discussion_id` | UUID | FK, NOT NULL | Parent discussion |
| `round_num` | Integer | NOT NULL, >= 1 | Sequential round number (1-indexed) |
| `question_text` | String | NOT NULL, 10-200 chars | Validated question (What/How only) |
| `status` | Enum | NOT NULL | Round lifecycle state (see below) |
| `submission_window_start` | Timestamp | NULL | Window opened timestamp |
| `submission_window_end` | Timestamp | NULL | Window closed timestamp |
| `submission_window_duration_sec` | Integer | NOT NULL, 180-360 | 3-6 minutes in seconds |
| `approval_deadline` | Timestamp | NULL | Computed: window_end + 10 minutes |
| `completed_at` | Timestamp | NULL | All sub-protocols finished |

**RoundStatus Enum**:
```
PENDING              # Awaiting host advancement
QUESTION_READY       # AUTO mode only: question generated, awaiting host trigger
SUBMISSION_OPEN      # Timer active, accepting submissions
SUBMISSION_CLOSED    # Timer expired, forwarding to Spec 3
SUMMARIZING          # Spec 3 generating summaries
APPROVING            # Participants reviewing summaries (until approval_deadline)
CLUSTERING           # Spec 4 semantic clustering
SANKEY_BUILDING      # Spec 5 constructing diagram
COMPLETE             # All sub-protocols done
FAILED               # Unrecoverable error
```

**Relationships**:
- Belongs to Discussion (`discussion_id`)
- Has many Submissions (1:N, ephemeral)
- Has many ApprovedSummaries (1:N, via Participants)
- Has many ThoughtSpaces (1:N)

**State Transitions**:
```
PENDING → QUESTION_READY (AUTO mode: Spec 6 generates question)
PENDING/QUESTION_READY → SUBMISSION_OPEN (host triggers advancement)
SUBMISSION_OPEN → SUBMISSION_CLOSED (timer expires)
SUBMISSION_CLOSED → SUMMARIZING (Spec 2 emits submissions.collected)
SUMMARIZING → APPROVING (Spec 3 emits summaries.generated)
APPROVING → CLUSTERING (all summaries approved OR approval_deadline expires)
CLUSTERING → SANKEY_BUILDING (Spec 4 emits clustering.complete)
SANKEY_BUILDING → COMPLETE (Spec 5 emits sankey.complete)
Any state → FAILED (unrecoverable error)
```

**Validation Rules**:
- `round_num` MUST be unique within discussion
- `round_num` MUST be <= `discussion.total_rounds`
- `question_text` MUST start with "What" or "How" (case-insensitive)
- `question_text` MUST NOT contain voting/ranking keywords ("vote", "rank", "best", "worst")
- `submission_window_duration_sec` MUST be between 180 and 360 (3-6 minutes)
- `approval_deadline` MUST be computed as `submission_window_end + 10 minutes`
- `submission_window_start` MUST be NULL when `status = PENDING | QUESTION_READY`
- Round cannot transition to COMPLETE unless all previous rounds are COMPLETE

**Indexes**:
- `(discussion_id, round_num)` - Unique constraint, ordered round lookup
- `(status)` - Query rounds by state
- `(approval_deadline)` - Find rounds with pending approvals

---

### 3. Participant

**Purpose**: Identity tracker for participant movement across rounds. Decouples user identity from discussion-scoped participation.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `participant_id` | UUID | PK, NOT NULL | Unique discussion-scoped identifier |
| `discussion_id` | UUID | FK, NOT NULL | Parent discussion |
| `user_id` | UUID | FK, NOT NULL | User account (NOT exposed to sub-protocols) |
| `first_round` | Integer | NOT NULL | Round number of first submission |
| `last_round` | Integer | NULL | Round number of last submission (NULL if still active) |
| `dropout_reason` | Enum | NULL | APPROVAL_TIMEOUT \| NO_SUBMISSION \| VOLUNTARY |
| `created_at` | Timestamp | NOT NULL | First submission timestamp |

**Relationships**:
- Belongs to Discussion (`discussion_id`)
- Belongs to User (`user_id`)
- Has many Submissions (1:N)
- Has many ApprovedSummaries (1:N)

**Validation Rules**:
- `(discussion_id, user_id)` MUST be unique (one Participant per user per discussion)
- `first_round` MUST be <= `last_round` (if last_round is not NULL)
- `dropout_reason` MUST be NULL if `last_round` is NULL (still active)
- `user_id` MUST be validated against community membership before Participant creation

**Indexes**:
- `(discussion_id, user_id)` - Unique constraint
- `(participant_id)` - Fast lookups for sub-protocols

**Privacy Notes**:
- `user_id` is NEVER passed to sub-protocols (Specs 2-6)
- Sub-protocols use only `participant_id` to preserve privacy
- LLM services log `participant_id`, not `user_id`

---

### 4. Submission (Ephemeral)

**Purpose**: Raw participant input for a round. Deleted after summary approval.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `submission_id` | UUID | PK, NOT NULL | Unique identifier |
| `participant_id` | UUID | FK, NOT NULL | Submitter |
| `round_id` | UUID | FK, NOT NULL | Target round |
| `submission_text` | Text | NOT NULL, max 2000 chars | Raw input (transcribed if voice) |
| `modality` | Enum | NOT NULL | TEXT \| VOICE |
| `submitted_at` | Timestamp | NOT NULL | Submission timestamp |
| `summary_status` | Enum | NOT NULL | PENDING \| APPROVED \| REJECTED \| SUPERSEDED \| APPROVAL_TIMEOUT |
| `deleted_at` | Timestamp | NULL | Soft delete timestamp |

**Relationships**:
- Belongs to Participant (`participant_id`)
- Belongs to Round (`round_id`)
- Has one Summary (1:1, in Spec 3)

**Validation Rules**:
- `submission_text` MUST NOT be empty
- `submission_text` MUST be <= 2000 characters
- Participant can submit MAX 3 times per round (rate limit enforced by Spec 2)
- `submitted_at` MUST be within `round.submission_window_start` and `round.submission_window_end`

**TTL (Time-To-Live)**:
- Deleted after `summary_status = APPROVED` (grace period: 5 minutes)
- Deleted after `round.approval_deadline` expires (for unapproved submissions)
- Deleted when discussion transitions to COMPLETED or TERMINATED

**Last-Approved-Wins Rule**:
- If participant submits multiple times, only the LAST approved summary is counted
- Previous submissions marked `summary_status = SUPERSEDED`

**Indexes**:
- `(round_id, participant_id, submitted_at)` - Find participant's submissions ordered by time
- `(deleted_at)` - TTL cleanup job queries

---

### 5. ApprovedSummary

**Purpose**: Canonical 1-2 sentence representation of submission. Persisted for clustering and reporting.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `summary_id` | UUID | PK, NOT NULL | Unique identifier |
| `participant_id` | UUID | FK, NOT NULL | Submitter |
| `round_id` | UUID | FK, NOT NULL | Target round |
| `submission_id` | UUID | FK, NULL | Source submission (set NULL after ephemeral deletion) |
| `summary_text` | String | NOT NULL, max 500 chars | Approved normalized text |
| `approved_at` | Timestamp | NOT NULL | Participant approval timestamp |
| `cluster_id` | UUID | FK, NULL | ThoughtSpace assignment (set by Spec 4) |

**Relationships**:
- Belongs to Participant (`participant_id`)
- Belongs to Round (`round_id`)
- Belongs to ThoughtSpace (`cluster_id`, set after clustering)

**Validation Rules**:
- `summary_text` MUST be 1-2 sentences (validated by Spec 3)
- `summary_text` MUST be <= 500 characters
- `approved_at` MUST be <= `round.approval_deadline`
- Exactly ONE ApprovedSummary per Participant per Round (last-approved-wins enforced)
- 100% of ApprovedSummaries MUST have `cluster_id` set after clustering completes

**Constitutional Guarantee** (Intent Fidelity - Principle II):
- ONLY approved summaries enter clustering
- Zero summaries with status != APPROVED in ApprovedSummary table

**Indexes**:
- `(round_id, participant_id)` - Unique constraint
- `(cluster_id)` - Find all summaries in ThoughtSpace
- `(round_id)` - List all summaries for round

---

### 6. ThoughtSpace

**Purpose**: Semantic cluster of approved summaries within a round. Represents a coherent idea.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `cluster_id` | UUID | PK, NOT NULL | Unique identifier |
| `round_id` | UUID | FK, NOT NULL | Parent round |
| `label_summary` | String | NOT NULL, max 200 chars | Medoid text (actual participant language) |
| `centroid_vector` | Float[] | NOT NULL | Embedding vector (for cross-round alignment only) |
| `member_count` | Integer | NOT NULL, >= 1 | Number of participants |
| `member_pct` | Float | NOT NULL, 0.0-1.0 | Percentage of round participants |
| `display_group_id` | String | NULL | Hybrid alignment ID (cosmetic, Spec 4) |

**Relationships**:
- Belongs to Round (`round_id`)
- Has many ApprovedSummaries (1:N)
- Has many outgoing Flows (1:N, as source)
- Has many incoming Flows (1:N, as target)

**Validation Rules**:
- `label_summary` MUST be actual participant language (medoid method, NOT AI-generated)
- `member_count` MUST equal COUNT(ApprovedSummaries with this cluster_id)
- `member_pct` MUST be `member_count / total_round_participants`
- SUM(`member_pct`) across all ThoughtSpaces in a round MUST equal 1.0 (±0.001 rounding)
- `display_group_id` is presentational only; NEVER affects clustering or flows (Principle III)

**Constitutional Guarantee** (Semantic Accuracy - Principle III):
- Singleton clusters (member_count = 1) are preserved (no forced merging)
- No minimum cluster size constraint

**Indexes**:
- `(round_id)` - List all ThoughtSpaces for round
- `(cluster_id)` - Fast lookups for flow computation

---

### 7. Flow

**Purpose**: Represents participant movement between ThoughtSpaces across consecutive rounds.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `flow_id` | UUID | PK, NOT NULL | Unique identifier |
| `source_cluster_id` | UUID | FK, NOT NULL | ThoughtSpace in round N |
| `target_cluster_id` | UUID | FK, NOT NULL | ThoughtSpace in round N+1 |
| `participant_count` | Integer | NOT NULL, >= 1 | Number of participants moving source→target |
| `participant_ids` | UUID[] | NOT NULL | Array of participant_ids (for audit) |

**Relationships**:
- From ThoughtSpace (`source_cluster_id`)
- To ThoughtSpace (`target_cluster_id`)

**Computation Logic**:
```sql
-- Flow weight = COUNT(DISTINCT participants in BOTH source AND target)
SELECT COUNT(DISTINCT s1.participant_id)
FROM ApprovedSummary s1
JOIN ApprovedSummary s2 ON s1.participant_id = s2.participant_id
WHERE s1.cluster_id = :source_cluster_id
  AND s2.cluster_id = :target_cluster_id
  AND s1.round_id = :round_n
  AND s2.round_id = :round_n_plus_1
```

**Validation Rules**:
- `source_cluster_id` and `target_cluster_id` MUST be in consecutive rounds
- `participant_count` MUST equal actual intersection count (see computation logic)
- `participant_count` MUST NOT exceed MIN(source.member_count, target.member_count)
- SUM(flow.participant_count) from source MUST <= source.member_count (dropouts reduce total)
- Flows are ONLY computed from participant movement, NEVER from semantic similarity (Principle IV)

**Constitutional Guarantee** (Temporal Transparency - Principle IV):
- Edge widths = actual participant counts, not similarity scores
- `display_group_id` alignment does NOT inflate flow counts

**Indexes**:
- `(source_cluster_id)` - Find all outgoing flows
- `(target_cluster_id)` - Find all incoming flows

---

## Dropout Handling (Option A: Natural Mass Shrinkage)

**Rule**: Participants who don't submit in round N+1 generate NO outgoing flows from round N.

**Implementation**:
1. Participant submits in Round 1 → assigned to ThoughtSpace A
2. Participant does NOT submit in Round 2 → no ApprovedSummary for Round 2
3. Flow computation finds zero intersection → no flow created from A
4. Total flow mass in Round 2 < Round 1 (natural shrinkage)

**No Synthetic Nodes**:
- Zero "Dropout" or "No Response" nodes created
- Dropout visible through reduced node widths in later rounds

**Participant Re-entry**:
- Participant can resume in Round 3 (no permanent exclusion)
- New flow created from Round 3 cluster (no connection to Round 1 cluster)

---

## State Machine Summary

### Discussion Lifecycle
```
CREATE discussion
  ↓
CREATED (awaiting start)
  ↓ host.start_discussion()
ACTIVE (rounds in progress)
  ↓ all rounds COMPLETE + generate final report
COMPLETED (final artifact ready)

OR

ACTIVE
  ↓ host.terminate_discussion()
TERMINATED (ended early)
```

### Round Lifecycle (HOST_DEFINED mode)
```
PENDING (awaiting host trigger)
  ↓ host.advance_round()
SUBMISSION_OPEN (timer active, 3-6 min)
  ↓ timer expires
SUBMISSION_CLOSED
  ↓ Spec 2 → Spec 3 handoff
SUMMARIZING (LLM generating summaries)
  ↓ Spec 3 → participants
APPROVING (participants reviewing, max 10 min)
  ↓ all approved OR approval_deadline expires
CLUSTERING (Spec 4 semantic clustering)
  ↓ Spec 4 → Spec 5 handoff
SANKEY_BUILDING (Spec 5 constructing diagram)
  ↓ Spec 5 emits sankey.complete
COMPLETE (ready for next round)
```

### Round Lifecycle (AUTO_GENERATED mode, rounds 2+)
```
PENDING
  ↓ Spec 6 generates question from previous Sankey
QUESTION_READY (question generated, awaiting host trigger)
  ↓ host.advance_round()
SUBMISSION_OPEN
  ↓ [same as HOST_DEFINED mode]
```

---

## Validation Summary

| Entity | Critical Validations |
|--------|---------------------|
| Discussion | total_rounds 1-10, mode immutable, state transitions enforce completion |
| Round | question starts What/How, no voting keywords, approval_deadline = window_end + 10m |
| Participant | unique per (discussion, user), user_id never exposed to sub-protocols |
| Submission | rate limit 3/round, TTL after approval, last-approved-wins |
| ApprovedSummary | 100% approved, 1-2 sentences, exactly one per participant per round |
| ThoughtSpace | singleton clusters preserved, member_pct sums to 1.0, medoid labels only |
| Flow | movement-based (not similarity), counts <= intersection, alignment doesn't inflate |

---

## Performance Considerations

**Indexes**: All foreign keys indexed for join performance

**Partitioning** (future):
- Partition Submissions by `deleted_at` for TTL cleanup efficiency
- Partition ApprovedSummaries by `round_id` for large discussions (post-MVP)

**Caching** (Redis):
- Round status (frequently queried, changes infrequently)
- Participant counts (computed from aggregations)
- Thought space labels (for quick Sankey rendering)

---

**Last Updated**: 2026-01-29
**Schema Version**: 1.0.0
**Next Action**: Generate OpenAPI contracts
