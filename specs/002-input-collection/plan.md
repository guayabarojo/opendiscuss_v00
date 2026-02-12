# Implementation Plan: Input Collection Protocol

**Branch**: `002-input-collection` | **Date**: 2026-01-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-input-collection/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement parallel input collection with text and voice modalities during synchronous discussion rounds. System accepts multiple submissions per participant (rate-limited), enforces time-bounded submission windows, normalizes inputs to text, and forwards exactly one counted submission per participant per round to summarization. Raw inputs are ephemeral (not persisted beyond summarization). Supports graceful dropout handling without synthetic placeholder nodes.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.109+, OpenAI Whisper API v1, PostgreSQL 15+, React 18+, TypeScript 5+
**Storage**: PostgreSQL 15+ (persistent: participants, rounds, submission_metadata) + In-Memory Dict (ephemeral: raw submissions, rate limits, audio recordings, transcripts)
**Testing**: pytest 7.4+ with pytest-asyncio for async tests
**Target Platform**: Web application (single VM for MVP, Linux server with FastAPI + PostgreSQL + nginx)
**Project Type**: web (backend: FastAPI, frontend: React + TypeScript)
**Performance Goals**: Support 100 concurrent participants submitting within same 5-second window without degradation; voice transcription < 3 seconds (Whisper API); countdown timer sub-second accuracy (WebSocket broadcast every 1s)
**Constraints**: Submission window enforcement 100% accuracy (no submissions outside boundaries); rate limiting 100% accuracy; exactly one counted submission per participant per round; raw input ephemeral only (0% persistence beyond summarization)
**Scale/Scope**: MVP target 100 concurrent users per discussion, 3-5 rounds per session, 3-6 minute submission windows, max 3 submissions per participant per round

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Validate compliance with `.specify/memory/constitution.md`:

- [x] **Parallel-First Architecture**: ✅ PASS - FR-001 through FR-004 enforce parallel input collection, FR-005 enforces simultaneous submission windows, no reactive mechanisms
- [x] **Intent Fidelity**: ✅ PASS - This spec collects raw input; approval handled by Spec 3 (Summarization & Approval Protocol)
- [x] **Semantic Accuracy Over Aesthetics**: ✅ PASS - Not applicable to input collection (handled by Spec 4 clustering)
- [x] **Temporal Transparency**: ✅ PASS - FR-031/FR-032 maintain stable participant identifiers, FR-025/FR-026/FR-027 handle dropout correctly (no backfilling, natural flow reduction)
- [x] **Community-Bounded Context**: ✅ PASS - Discussions occur within rounds, participant authentication assumed (Assumption 3)
- [x] **Synchronous Deliberation**: ✅ PASS - FR-005 through FR-009 enforce time-boxed submission windows (3-6 min MVP target), FR-006/FR-007 reject submissions outside window
- [x] **Representation Not Adjudication**: ✅ PASS - No voting/ranking mechanisms, collects raw input only
- [x] **MVP Boundaries**: ✅ PASS - No prohibited features included (no async participation, no cross-community linking, etc.)
- [x] **Complexity Justified**: ✅ PASS - Multiple submission support (FR-010 to FR-013) necessary for iteration, voice input (FR-017 to FR-020) necessary for accessibility

**Violations**: None

**Pre-Phase 0 Status**: ✅ CLEARED TO PROCEED

---

### Post-Phase 1 Re-Evaluation

**Date**: 2026-01-29
**Phase**: After completing data model, API contracts, and quickstart

**Re-validation Results**:

- [x] **Parallel-First Architecture**: ✅ PASS - API design enforces non-reactive input (POST /submissions accepts independent inputs), WebSocket only broadcasts timer (one-way), no threading or replies
- [x] **Intent Fidelity**: ✅ PASS - Data model separates raw submission (ephemeral) from approval status (handled by Spec 3), no interpretation of content in normalization
- [x] **Semantic Accuracy Over Aesthetics**: ✅ PASS - Not applicable (input collection layer)
- [x] **Temporal Transparency**: ✅ PASS - Participant identifiers stable across rounds (participants table persists), dropout correctly modeled (no counted submission = no outgoing flow)
- [x] **Community-Bounded Context**: ✅ PASS - Participants linked to community_id (foreign key), discussions scoped to communities
- [x] **Synchronous Deliberation**: ✅ PASS - Round window enforcement (inclusive start, exclusive end) implemented, WebSocket countdown enforces real-time participation
- [x] **Representation Not Adjudication**: ✅ PASS - No ranking/voting/scoring in data model or API, raw input forwarded without judgment
- [x] **MVP Boundaries**: ✅ PASS - No async participation (window enforcement prevents), no cross-community features, no decision mechanisms
- [x] **Complexity Justified**: ✅ PASS - Complexity introduced (voice transcription, multiple submissions, WebSocket timer) all justified by spec requirements and constitutional principles

**New Violations Introduced**: None

**Technology Choices Review**:
- Python/FastAPI: Supports async for concurrent submissions (Parallel-First)
- PostgreSQL persistent + In-memory ephemeral: Enforces ephemeral data principles (Intent Fidelity)
- WebSocket broadcast: One-way timer updates (Parallel-First, no reactive input)
- OpenAI Whisper API: Transcription accuracy (Intent Fidelity - participant review required)

**Post-Phase 1 Status**: ✅ CLEARED FOR IMPLEMENTATION

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── submission.{ext}         # Submission entity
│   │   ├── participant.{ext}        # Participant tracking
│   │   └── rate_limit.{ext}         # Rate limit tracking
│   ├── services/
│   │   ├── input_collection.{ext}   # Core submission acceptance logic
│   │   ├── window_enforcement.{ext} # Time boundary validation
│   │   ├── rate_limiter.{ext}       # Submission rate limiting
│   │   ├── transcription.{ext}      # Voice-to-text transcription
│   │   └── normalization.{ext}      # Text normalization
│   └── api/
│       ├── routes/
│       │   ├── submissions.{ext}    # POST /submissions, GET /submissions/{id}
│       │   └── windows.{ext}        # GET /rounds/{id}/window (timer sync)
│       └── websocket/
│           └── submission_ws.{ext}  # Real-time countdown updates
└── tests/
    ├── contract/
    │   └── test_submission_to_summarization.{ext}
    ├── integration/
    │   ├── test_window_enforcement.{ext}
    │   ├── test_rate_limiting.{ext}
    │   └── test_voice_transcription.{ext}
    └── unit/
        ├── test_input_collection.{ext}
        ├── test_window_enforcement.{ext}
        └── test_rate_limiter.{ext}

frontend/
├── src/
│   ├── components/
│   │   ├── TextInputForm.{ext}      # Text submission UI
│   │   ├── VoiceInputRecorder.{ext} # Voice recording UI
│   │   ├── TranscriptReview.{ext}   # Transcript approval UI
│   │   └── CountdownTimer.{ext}     # Submission window timer
│   ├── pages/
│   │   └── RoundInputPage.{ext}     # Main input collection page
│   └── services/
│       ├── submissionApi.{ext}      # API client for submissions
│       └── websocketClient.{ext}    # WebSocket for timer sync
└── tests/
    ├── unit/
    │   ├── TextInputForm.test.{ext}
    │   └── CountdownTimer.test.{ext}
    └── e2e/
        ├── test_text_submission.{ext}
        ├── test_voice_submission.{ext}
        └── test_window_enforcement.{ext}
```

**Structure Decision**: Web application structure with separate backend and frontend. Backend handles submission acceptance, window enforcement, rate limiting, and transcription service integration. Frontend provides parallel input interfaces with real-time countdown timer. WebSocket connection maintains timer synchronization across all participants.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
