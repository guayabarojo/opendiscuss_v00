# Implementation Plan: Micro-Summarization & Approval Protocol

**Branch**: `003-summarization-approval` | **Date**: 2026-01-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-summarization-approval/spec.md`

## Summary

The Micro-Summarization & Approval Protocol (Spec 3) serves as the critical trust gate between raw participant input and semantic aggregation. It generates normalized 1-2 sentence summaries via LLM, enforces explicit participant approval, implements bounded regeneration (2 auto + 1 correction-based), applies safety filtering, and ensures only approved summaries enter clustering. This protocol is the primary enforcer of the "Intent Fidelity" constitutional principle (Principle II).

## Technical Context

**Language/Version**: Python 3.11+ (async for LLM calls), TypeScript 5+ (React frontend for approval UI)
**Primary Dependencies**: OpenAI SDK (LLM), FastAPI, PostgreSQL, Redis (caching), Pydantic (validation)
**Storage**: PostgreSQL for summaries (Summary entity with status FSM); Redis for LLM response caching; raw submissions ephemeral (TTL-based deletion after approval)
**Testing**: pytest (backend), Jest + React Testing Library (frontend), contract tests for Spec 2 → 3 → 4 handoffs
**Target Platform**: Linux server (backend), Modern browsers (frontend approval UI)
**Project Type**: Web application (backend LLM integration + frontend approval interface)
**Performance Goals**: Summary generation <3 seconds (p95), approval round trip <5 seconds, support 100 concurrent summarization requests
**Constraints**: <500 chars per summary, max 3 regenerations per submission, approval deadline = submission_window_end + 10 minutes
**Scale/Scope**: 100 participants per round, 5 rounds per discussion, 10 parallel discussions per community

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Validate compliance with `.specify/memory/constitution.md`:

- [x] **Parallel-First Architecture**: Summaries generated independently for each participant; no cross-participant influence
- [x] **Intent Fidelity**: CRITICAL - This spec IS the approval gate; 100% explicit approval required; no timeout-based auto-approval
- [x] **Semantic Accuracy Over Aesthetics**: Summaries preserve participant language; no forced standardization for clustering convenience
- [x] **Temporal Transparency**: Approved summaries include approved_at timestamp for movement tracking
- [x] **Community-Bounded Context**: Summary generation includes community context from Spec 0
- [x] **Synchronous Deliberation**: Approval deadline enforces timeboxing (window_end + 10 minutes per Spec 0)
- [x] **Representation Not Adjudication**: Summaries are neutral representations; no persuasive framing or scoring
- [x] **MVP Boundaries**: No async approval (sync only), no collaborative editing, no summary discussions (all explicitly excluded)
- [x] **Complexity Justified**: Bounded regeneration prevents infinite loops while maximizing approval success

**Violations**: None

## Project Structure

### Documentation (this feature)

```text
specs/003-summarization-approval/
├── plan.md              # This file
├── research.md          # Phase 0: LLM selection, prompt engineering, safety filtering
├── data-model.md        # Phase 1: Summary entity, state machine, approval workflow
├── quickstart.md        # Phase 1: Developer setup, LLM API keys, testing
├── contracts/           # Phase 1: OpenAPI specs
│   ├── summarization-api.yaml     # Summary generation/approval endpoints
│   ├── spec2-to-spec3-contract.yaml  # Input Collection handoff
│   └── spec3-to-spec4-contract.yaml  # Clustering handoff
└── tasks.md             # Phase 2: Implementation task breakdown
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── summary.py               # Summary entity (FSM: PENDING → APPROVED/REJECTED/REJECTED_FINAL)
│   │   └── correction_signal.py     # CorrectionSignal entity (reason tags, feedback text)
│   ├── services/
│   │   ├── summarization_service.py # LLM integration, prompt construction, generation logic
│   │   ├── approval_service.py      # Approval workflow, last-approved-wins, approval deadline
│   │   ├── regeneration_service.py  # Bounded regeneration (max 3), correction signal handling
│   │   ├── safety_filter_service.py # Profanity detection/neutralization, threat blocking
│   │   └── llm_cache_service.py     # Redis caching for LLM responses (reduce API costs)
│   ├── api/
│   │   ├── summary_routes.py        # POST /summaries/generate, POST /summaries/{id}/approve, POST /summaries/{id}/reject
│   │   └── correction_routes.py     # POST /summaries/{id}/correction (correction signal submission)
│   ├── events/
│   │   └── handlers/
│   │       ├── submission_collected.py  # Spec 2 → Spec 3: Generate summaries from submissions
│   │       └── approval_complete.py     # Spec 3 → Spec 4: Forward approved summaries to clustering
│   └── prompts/
│       ├── base_summary_prompt.py   # Template for neutral summarization
│       ├── regeneration_prompts.py  # Variation strategies for regen attempts
│       └── correction_prompts.py    # Incorporate correction signals
├── tests/
│   ├── contract/
│   │   ├── test_spec2_to_spec3.py   # Validate submission → summary generation
│   │   └── test_spec3_to_spec4.py   # Validate approved summaries → clustering
│   ├── integration/
│   │   ├── test_approve_workflow.py      # Generate → approve → persist
│   │   ├── test_regeneration_workflow.py # Reject → regen (max 3)
│   │   ├── test_last_approved_wins.py    # Multiple approvals → latest used
│   │   └── test_safety_filtering.py      # Profanity/threats → filtered/blocked
│   └── unit/
│       ├── test_summarization_service.py # LLM call mocking, prompt construction
│       ├── test_approval_deadline.py     # Timeout handling
│       └── test_safety_filters.py        # Profanity detection logic

frontend/
├── src/
│   ├── components/
│   │   ├── SummaryReview/           # Approval UI (approve/reject buttons, summary display)
│   │   ├── CorrectionSignalForm/    # Reason tags + optional feedback input
│   │   └── SafetyNotice/            # Display disallowed content warnings
│   ├── pages/
│   │   └── ApprovalInterface.tsx    # Main approval page (show summary, handle actions)
│   └── services/
│       └── summaryApi.ts            # API client for summary endpoints
└── tests/
    └── integration/
        └── approval_flow.test.tsx   # Full approval workflow (mock summaries, click approve)
```

**Structure Decision**: Web application (Option 2) selected because Spec 3 requires both backend LLM integration (summarization, safety filtering) and frontend interactive approval UI (review, approve/reject, correction signals). Backend handles all LLM calls and state management; frontend provides participant-facing approval interface.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| None | N/A | N/A |

---

## Key Research Areas (Phase 0)

1. **LLM Selection**: OpenAI GPT-4-turbo vs GPT-3.5-turbo vs Anthropic Claude (decision: GPT-4-turbo for quality, GPT-3.5 fallback for cost)
2. **Prompt Engineering**: Neutral summarization prompts, regeneration variation strategies, correction signal incorporation
3. **Safety Filtering**: Profanity detection (library: better-profanity), threat detection (keywords + LLM safety API)
4. **Approval Deadline**: 10 minutes grace period (from Spec 0 resolution), timeout handling without auto-approval
5. **Last-Approved-Wins Logic**: Timestamp-based selection, handling race conditions in concurrent approvals

## Key Design Decisions (Phase 1)

**Summary State Machine**:
```
PENDING_REVIEW → APPROVED (explicit approval)
PENDING_REVIEW → REJECTED → PENDING_REVIEW (auto-regen, max 2)
PENDING_REVIEW → REJECTED → CORRECTION_SIGNAL_REQUESTED
CORRECTION_SIGNAL_REQUESTED → PENDING_REVIEW (correction-based regen)
PENDING_REVIEW → REJECTED_FINAL (after 3 total regens)
```

**Bounded Regeneration**:
- Attempt 0: Initial generation
- Attempt 1-2: Automatic regeneration (vary strategy: emphasize constraint vs solution, simplify language, focus different core point)
- Attempt 3: Correction signal-based regeneration
- After 3: REJECTED_FINAL, participant may resubmit input

**Last-Approved-Wins Rule**:
```sql
SELECT * FROM summaries
WHERE user_id = :user_id AND round_id = :round_id AND status = 'APPROVED'
ORDER BY approved_at DESC
LIMIT 1
```

**Safety Filtering Layers**:
1. **Profanity Neutralization**: Detect profanity → strip/replace in summary → allow approval
2. **Threat Blocking**: Detect illegal threats → return safety_flags=["DISALLOWED_CONTENT"] → prevent approval, notify participant

## Critical Integration Contracts

**Contract: Spec 2 → Spec 3 (Submission Collection → Summarization)**:
- Event: `submission_window.closed`
- Payload: `{round_id, submissions: [{submission_id, participant_id, submission_text, modality}]}`
- Spec 3 Action: Generate summary for each submission, emit `summarization.started`

**Contract: Spec 3 → Spec 4 (Approved Summaries → Clustering)**:
- Event: `summarization.complete`
- Payload: `{round_id, approved_summaries: [{summary_id, participant_id, summary_text, approved_at}]}`
- Guarantee: 100% status=APPROVED, exactly one per participant (last-approved-wins applied), summaries ready for clustering

**Approval Deadline Handling**:
- After `submission_window_end + 10 minutes`:
  - Unapproved summaries marked APPROVAL_TIMEOUT
  - Participants marked as dropouts for this round
  - Round proceeds with only approved summaries
  - Spec 3 emits `summarization.complete` with approved-only subset

---

## Implementation Phases

**Phase 0 (Research)**: LLM selection, prompt engineering, safety filtering evaluation
**Phase 1 (Design)**: Data model (Summary entity), API contracts, prompt templates
**Phase 2 (Implementation)**: Summarization service, approval workflow, safety filters
**Phase 3 (Integration)**: Spec 2 handoff, Spec 4 handoff, event bus coordination
**Phase 4 (Testing)**: Contract tests, integration tests, approval UI testing

---

## MVP Scope

**User Story 1 (P1)**: Generate and approve summary
- Generate 1-2 sentence neutral summary
- Explicit approval required
- Forward approved summaries to clustering

**Deferred to Post-MVP**:
- US2-US5 (regeneration, correction signals, safety filtering, multiple submissions) - can be added incrementally after US1 validates core approval gate

---

**Last Updated**: 2026-01-29
**Next Action**: Run `/speckit.plan` workflow to generate research.md, data-model.md, contracts/, quickstart.md
