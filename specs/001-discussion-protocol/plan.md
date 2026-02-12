# Implementation Plan: OpenDiscuss Discussion Protocol (System Spine)

**Branch**: `001-discussion-protocol` | **Date**: 2026-01-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-discussion-protocol/spec.md`

## Summary

The Discussion Protocol serves as the system spine orchestrating all sub-protocols (Input Collection, Summarization, Clustering, Sankey Construction, Question Progression). It manages the discussion lifecycle, enforces timing, coordinates round state machines, and ensures constitutional compliance across all protocol boundaries. The implementation requires a state-driven architecture with event-based coordination between sub-protocols.

## Technical Context

**Language/Version**: Python 3.11+ (async/await for concurrent sub-protocol coordination)
**Primary Dependencies**: FastAPI (API layer), PostgreSQL (state persistence), Redis (timing/locks), Pydantic (validation)
**Storage**: PostgreSQL for discussion/round state, approved summaries, thought spaces, flows; Redis for ephemeral submission data and timing coordination
**Testing**: pytest with async support, hypothesis for property-based testing of invariants
**Target Platform**: Linux server (containerized deployment)
**Project Type**: Web application (backend orchestration + frontend visualization)
**Performance Goals**: Complete 3-round discussion with 100 participants in <45 minutes; round state transitions <500ms
**Constraints**: <200ms p95 for state queries; strict timing enforcement (±100ms precision); zero data loss on state transitions
**Scale/Scope**: Support 100 concurrent participants per discussion; 10 parallel discussions per community

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Validate compliance with `.specify/memory/constitution.md`:

- [x] **Parallel-First Architecture**: Discussion Protocol enforces simultaneous input collection via timed windows (Spec 2); no threading/replies
- [x] **Intent Fidelity**: Orchestrates approval gate (Spec 3); blocks round progression until all summaries approved or timeout
- [x] **Semantic Accuracy Over Aesthetics**: Delegates clustering to Spec 4 with no forced merging; validates 100% participant coverage
- [x] **Temporal Transparency**: Tracks participant movement via participant_id persistence; validates flow accuracy (Spec 5 contract)
- [x] **Community-Bounded Context**: Discussions scoped to community_id; validates community membership before participation
- [x] **Synchronous Deliberation**: Enforces 3-6 min submission windows, ~10 min total per round; blocks late arrivals
- [x] **Representation Not Adjudication**: Produces Sankey diagram as final artifact; no voting/ranking/scoring mechanisms
- [x] **MVP Boundaries**: No async participation, no cross-community discussions, no branching rounds (all explicitly excluded)
- [x] **Complexity Justified**: State machine complexity required for timing enforcement and sub-protocol coordination

**Violations**: None

## Project Structure

### Documentation (this feature)

```text
specs/001-discussion-protocol/
├── plan.md              # This file
├── research.md          # Phase 0 output: State machine research, timing mechanisms
├── data-model.md        # Phase 1 output: Discussion, Round, Participant entities
├── quickstart.md        # Phase 1 output: Developer setup guide
├── contracts/           # Phase 1 output: OpenAPI specs for state transitions
│   ├── discussion-api.yaml
│   ├── round-state-machine.yaml
│   └── sub-protocol-events.yaml
└── tasks.md             # Phase 2 output: Implementation task breakdown
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── discussion.py        # Discussion entity (lifecycle, metadata)
│   │   ├── round.py              # Round entity (state machine, timing)
│   │   ├── participant.py        # Participant entity (identity, movement tracking)
│   │   └── protocol_state.py     # Shared state enums (DiscussionStatus, RoundStatus)
│   ├── services/
│   │   ├── discussion_service.py # Discussion lifecycle management
│   │   ├── round_service.py      # Round state machine coordination
│   │   ├── timing_service.py     # Submission window enforcement, countdown
│   │   ├── protocol_coordinator.py # Sub-protocol event bus coordination
│   │   └── invariant_validator.py  # Constitutional compliance validation
│   ├── api/
│   │   ├── discussion_routes.py  # Discussion CRUD, advancement triggers
│   │   ├── round_routes.py       # Round state queries, host controls
│   │   └── participant_routes.py # Participant registration, dropout detection
│   └── events/
│       ├── event_bus.py          # Event emitter for sub-protocol coordination
│       ├── handlers/
│       │   ├── submission_complete.py  # Spec 2 → Spec 3 handoff
│       │   ├── summarization_complete.py # Spec 3 → Spec 4 handoff
│       │   ├── clustering_complete.py    # Spec 4 → Spec 5 handoff
│       │   └── sankey_complete.py        # Spec 5 → Spec 6 handoff (auto mode)
│       └── event_types.py        # Event schema definitions
├── tests/
│   ├── contract/                 # Sub-protocol integration contract tests
│   │   ├── test_submission_to_summary.py
│   │   ├── test_summary_to_clustering.py
│   │   ├── test_clustering_to_sankey.py
│   │   └── test_sankey_to_question.py
│   ├── integration/              # End-to-end discussion flow tests
│   │   ├── test_single_round_discussion.py
│   │   ├── test_multi_round_movement.py
│   │   └── test_timing_enforcement.py
│   └── unit/                     # State machine, invariant validation tests
│       ├── test_discussion_lifecycle.py
│       ├── test_round_state_machine.py
│       └── test_invariant_validator.py

frontend/
├── src/
│   ├── components/
│   │   ├── DiscussionStatus/     # Real-time discussion state display
│   │   ├── RoundTimer/           # Countdown timer visualization
│   │   └── HostControls/         # Round advancement triggers
│   ├── pages/
│   │   ├── DiscussionCreate.tsx  # Discussion creation form
│   │   ├── DiscussionLive.tsx    # Active discussion view
│   │   └── DiscussionReport.tsx  # Final Sankey report display
│   └── services/
│       ├── discussionApi.ts      # API client for discussion endpoints
│       └── eventStream.ts        # SSE/WebSocket for state updates
└── tests/
    └── e2e/                      # Cypress end-to-end tests
        ├── single_round.cy.ts
        └── multi_round_movement.cy.ts
```

**Structure Decision**: Web application structure (Option 2) selected because the Discussion Protocol requires both backend state orchestration (managing lifecycle, timing, coordination) and frontend visualization (Sankey display, host controls, participant status). Backend handles all protocol logic; frontend provides real-time UI for participants and hosts.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| None | N/A | N/A |
