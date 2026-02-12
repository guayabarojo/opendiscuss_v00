# Tasks: OpenDiscuss Discussion Protocol (System Spine)

**Input**: Design documents from `/specs/001-discussion-protocol/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/discussion-api.yaml, quickstart.md

**Constitution Compliance**: Tasks align with `.specify/memory/constitution.md` principles.
Parallel tasks support concurrent implementation; independent user stories enable incremental delivery.

**Tests**: This implementation follows a pragmatic testing approach - tests are integrated where they validate critical invariants and integration points.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md: Web application structure
- **Backend**: `backend/src/`, `backend/tests/`
- **Frontend**: `frontend/src/`, `frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create backend project structure per plan.md (backend/src/{models,services,api,events}, backend/tests/{unit,integration,contract})
- [X] T002 Initialize Python 3.11 project with Poetry (dependencies: FastAPI, SQLAlchemy, Pydantic, Redis, pytest)
- [X] T003 [P] Configure linting tools (black, ruff, mypy) in backend/pyproject.toml
- [X] T004 [P] Create docker-compose.yml for PostgreSQL 14+ and Redis 7+ services
- [X] T005 [P] Setup environment configuration in backend/src/config.py (load from .env: DATABASE_URL, REDIS_URL, SECRET_KEY)
- [X] T006 [P] Create .env.example with required environment variables
- [X] T007 [P] Initialize Alembic for database migrations in backend/alembic/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 Setup database connection and session management in backend/src/database.py (SQLAlchemy async engine)
- [X] T009 Create FastAPI application instance in backend/src/main.py (with CORS, middleware, error handlers)
- [X] T010 [P] Implement protocol state enums in backend/src/models/protocol_state.py (DiscussionStatus, RoundStatus, DiscussionMode, DropoutReason)
- [X] T011 [P] Create base entity models in backend/src/models/__init__.py (SQLAlchemy declarative base)
- [X] T012 [P] Implement event bus with typed schemas in backend/src/events/event_bus.py (async emit/subscribe pattern)
- [X] T013 [P] Create event type schemas in backend/src/events/event_types.py (Pydantic models for all events)
- [X] T014 [P] Implement Redis timing service in backend/src/services/timing_service.py (sorted set for scheduled window closures, 50ms polling)
- [X] T015 Setup error handling middleware in backend/src/api/error_handlers.py (standardized error responses per OpenAPI spec)
- [X] T016 Configure structured logging in backend/src/logging_config.py (JSON logs with trace IDs)
- [X] T017 Create initial Alembic migration for foundational schema in backend/alembic/versions/001_foundation.py
- [X] T018 [P] Write pytest fixtures in backend/tests/conftest.py (db_session, redis_client, event_bus, test data factories)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Complete Single-Round Discussion (Priority: P1) 🎯 MVP

**Goal**: Enable a community admin to create a discussion with one question, collect parallel participant input, approve summaries, cluster into thought spaces, and render a single-column Sankey diagram.

**Independent Test**: Create discussion → 5+ participants submit → approve summaries → clustering produces thought spaces → Sankey column renders with correct proportions.

**Why MVP**: This is the atomic unit of the entire system. Validates all core protocol invariants without the complexity of multi-round coordination.

### Core Entities for User Story 1

- [X] T019 [P] [US1] Create Discussion model in backend/src/models/discussion.py (fields: discussion_id, community_id, mode, total_rounds, status, timestamps, host_user_id; relationships: rounds, participants)
- [X] T020 [P] [US1] Create Round model in backend/src/models/round.py (fields: round_id, discussion_id, round_num, question_text, status, timing fields; state machine methods)
- [X] T021 [P] [US1] Create Participant model in backend/src/models/participant.py (fields: participant_id, discussion_id, user_id, first_round, last_round, dropout_reason; privacy: user_id NOT exposed to sub-protocols)
- [X] T022 [P] [US1] Create Submission model in backend/src/models/submission.py (fields: submission_id, participant_id, round_id, submission_text, modality, submitted_at, summary_status, deleted_at; ephemeral TTL logic)
- [X] T023 [P] [US1] Create ApprovedSummary model in backend/src/models/approved_summary.py (fields: summary_id, participant_id, round_id, submission_id, summary_text, approved_at, cluster_id)
- [X] T024 [P] [US1] Create ThoughtSpace model in backend/src/models/thought_space.py (fields: cluster_id, round_id, label_summary, centroid_vector, member_count, member_pct, display_group_id)
- [X] T025 [P] [US1] Create Flow model in backend/src/models/flow.py (fields: flow_id, source_cluster_id, target_cluster_id, participant_count, participant_ids; computation logic for movement tracking)

### Services for User Story 1

- [X] T026 [US1] Implement DiscussionService.create_discussion in backend/src/services/discussion_service.py (HOST_DEFINED mode, validate questions, create rounds, return Discussion)
- [X] T027 [US1] Implement DiscussionService.start_discussion in backend/src/services/discussion_service.py (transition to ACTIVE, open Round 1, schedule timing, emit discussion.started event)
- [X] T028 [US1] Implement RoundService.open_submission_window in backend/src/services/round_service.py (set status=SUBMISSION_OPEN, compute window_end, schedule closure via TimingService)
- [X] T029 [US1] Implement RoundService.close_submission_window in backend/src/services/round_service.py (set status=SUBMISSION_CLOSED, emit submission_window.closed event with submissions)
- [X] T030 [US1] Implement ProtocolCoordinator in backend/src/services/protocol_coordinator.py (orchestrate round state transitions, subscribe to sub-protocol events, update Round status)
- [X] T031 [US1] Implement InvariantValidator in backend/src/services/invariant_validator.py (validate Intent Fidelity: 100% approved summaries, Semantic Accuracy: 100% participant coverage, Temporal Transparency: flow accuracy)

### API Endpoints for User Story 1

- [X] T032 [P] [US1] Implement POST /discussions in backend/src/api/discussion_routes.py (create discussion, validate community membership, return 201 with Discussion schema)
- [X] T033 [P] [US1] Implement GET /discussions/{id} in backend/src/api/discussion_routes.py (fetch discussion details, include current round status)
- [X] T034 [P] [US1] Implement POST /discussions/{id}/start in backend/src/api/discussion_routes.py (start discussion, open Round 1, return Discussion with ACTIVE status)
- [X] T035 [P] [US1] Implement GET /rounds/{id}/status in backend/src/api/round_routes.py (real-time status with remaining_time_sec for countdown timer, participant stats)
- [X] T036 [P] [US1] Implement GET /discussions/{id}/report in backend/src/api/discussion_routes.py (fetch final report with Sankey diagram, require status=COMPLETED)

### Event Handlers for User Story 1 (Sub-Protocol Integration)

- [X] T037 [P] [US1] Implement submission_complete handler in backend/src/events/handlers/submission_complete.py (subscribe to submission_window.closed, transition Round to SUMMARIZING, forward to Spec 3)
- [X] T038 [P] [US1] Implement summarization_complete handler in backend/src/events/handlers/summarization_complete.py (subscribe to summarization.complete, set approval_deadline, transition to APPROVING, validate 100% approved before clustering)
- [X] T039 [P] [US1] Implement clustering_complete handler in backend/src/events/handlers/clustering_complete.py (subscribe to clustering.complete, transition to SANKEY_BUILDING, validate 100% participant coverage)
- [X] T040 [P] [US1] Implement sankey_complete handler in backend/src/events/handlers/sankey_complete.py (subscribe to sankey.complete, transition Round to COMPLETE, emit round.complete event)

### Integration Tests for User Story 1

- [X] T041 [US1] Write end-to-end single-round test in backend/tests/integration/test_single_round_discussion.py (create discussion → start → mock submissions → mock approvals → mock clustering → verify Sankey column)
- [X] T042 [US1] Write invariant validation test in backend/tests/integration/test_us1_invariants.py (verify Intent Fidelity: zero unapproved summaries in clustering, Semantic Accuracy: 100% participant coverage, Temporal Transparency: correct proportions)
- [X] T043 [US1] Write timing enforcement test in backend/tests/integration/test_us1_timing.py (verify submission window closes within ±100ms, countdown timer accuracy, rejection after window close)

### Database Migration for User Story 1

- [X] T044 [US1] Create Alembic migration for US1 entities in backend/alembic/versions/002_user_story_1.py (Discussion, Round, Participant, Submission, ApprovedSummary, ThoughtSpace, Flow tables with indexes)

### Frontend for User Story 1 (MVP Visualization)

- [X] T045 [P] [US1] Create DiscussionCreate component in frontend/src/pages/DiscussionCreate.tsx (form for HOST_DEFINED mode, question input, community selection)
- [X] T046 [P] [US1] Create DiscussionLive component in frontend/src/pages/DiscussionLive.tsx (real-time discussion status, round timer countdown, participant count)
- [X] T047 [P] [US1] Create RoundTimer component in frontend/src/components/RoundTimer/index.tsx (countdown display, submission window end time, visual progress bar)
- [X] T048 [P] [US1] Create DiscussionReport component in frontend/src/pages/DiscussionReport.tsx (render single-column Sankey diagram from API response)
- [X] T049 [P] [US1] Implement discussionApi.ts in frontend/src/services/discussionApi.ts (API client methods: createDiscussion, startDiscussion, getRoundStatus, getReport)
- [X] T050 [P] [US1] Implement eventStream.ts in frontend/src/services/eventStream.ts (SSE or WebSocket for real-time round status updates)

**US1 Completion Criteria**:
- ✅ Discussion created with 1 question
- ✅ Submission window opens with countdown timer
- ✅ Parallel submissions accepted (simulated via mock sub-protocols)
- ✅ Approval gate enforced (only approved summaries clustered)
- ✅ Single-column Sankey renders with correct thought space proportions
- ✅ All constitutional invariants validated (Intent Fidelity, Semantic Accuracy, Temporal Transparency)

---

## Phase 4: User Story 2 - Multi-Round Discussion with Participant Movement (Priority: P2)

**Goal**: Enable discussions across 3-5 rounds with evolving Sankey diagram showing participant movement between thought spaces across rounds.

**Independent Test**: Run 3-round discussion → verify participants submit in multiple rounds → verify flows accurately represent participant transitions (not semantic similarity) → verify dropout reduces mass naturally.

**Dependencies**: US1 complete (single-round infrastructure exists)

### Services for User Story 2

- [X] T051 [P] [US2] Implement DiscussionService.advance_round in backend/src/services/discussion_service.py (validate current round COMPLETE or QUESTION_READY, open next round submission window, emit round.started event)
- [X] T052 [P] [US2] Implement FlowService.compute_flows in backend/src/services/flow_service.py (compute participant movement from Round N to N+1 via participant_id intersection, create Flow entities, validate counts <= intersection)
- [X] T053 [P] [US2] Implement DropoutDetectionService in backend/src/services/dropout_detection.py (detect participants who submitted in Round N but not N+1, mark as dropout with reason=NO_SUBMISSION, set last_round)

### API Endpoints for User Story 2

- [X] T054 [P] [US2] Implement POST /discussions/{id}/advance in backend/src/api/discussion_routes.py (host triggers round advancement, validate current round complete, open next submission window, return next Round)
- [X] T055 [P] [US2] Implement GET /discussions/{id}/participants in backend/src/api/participant_routes.py (list participants with dropout status, filter by include_dropouts query param)

### Integration Tests for User Story 2

- [X] T056 [US2] Write multi-round movement test in backend/tests/integration/test_multi_round_movement.py (3 rounds, track specific participant transitions, verify flow edges match actual movement)
- [X] T057 [US2] Write dropout test in backend/tests/integration/test_us2_dropout.py (participant submits Round 1 → skips Round 2 → verify zero outgoing flow from Round 1 cluster, mass shrinks naturally in Round 2)
- [X] T058 [US2] Write flow accuracy test in backend/tests/integration/test_us2_flow_accuracy.py (verify edge.participant_count = COUNT(DISTINCT participant_id in both source AND target), verify alignment metadata doesn't inflate counts)

### Contract Tests for User Story 2 (Sub-Protocol Integration)

- [X] T059 [P] [US2] Write clustering→Sankey contract test in backend/tests/contract/test_clustering_to_sankey.py (verify Spec 4 output includes user_to_cluster_map for O(1) lookups, verify 100% participant coverage)
- [X] T060 [P] [US2] Write Sankey→Question contract test in backend/tests/contract/test_sankey_to_question.py (verify sankey.complete event includes full SankeyGraph payload, verify emitted within 5 seconds)

### Database Migration for User Story 2

- [X] T061 [US2] Update Alembic migration in backend/alembic/versions/003_user_story_2.py (add indexes for flow computation: (source_cluster_id), (target_cluster_id), (participant_id))

### Frontend for User Story 2

- [X] T062 [P] [US2] Create HostControls component in frontend/src/components/HostControls/index.tsx (Advance Round button, disabled until round COMPLETE, confirmation dialog)
- [X] T063 [P] [US2] Update DiscussionReport component in frontend/src/pages/DiscussionReport.tsx (render multi-column Sankey with flows, highlight participant movement paths on hover)
- [X] T064 [P] [US2] Implement flow visualization in frontend/src/components/SankeyDiagram/FlowRenderer.tsx (draw edges between columns, width = participant_count, color = source cluster)

**US2 Completion Criteria**:
- ✅ Host can advance through 3-5 rounds
- ✅ Multi-column Sankey renders with temporal ordering
- ✅ Flows computed from participant movement (not similarity)
- ✅ Dropout reduces mass naturally (no synthetic nodes)
- ✅ Flow accuracy validated: edge counts = actual participant intersections

---

## Phase 5: User Story 3 - Participant Iteration Within Round (Priority: P3)

**Goal**: Enable participants to submit multiple times (up to 3) within a round's submission window, with only the last approved summary counted in aggregation.

**Independent Test**: Participant submits 3 times → approves different summaries → verify only last-approved-wins → attempt 4th submission → verify rate limit rejection.

**Dependencies**: US1 complete (submission and approval infrastructure exists)

### Services for User Story 3

- [X] T065 [P] [US3] Implement SubmissionService.handle_multiple_submissions in backend/src/services/submission_service.py (track submission count per participant per round, enforce rate limit = 3, apply last-approved-wins rule)
- [X] T066 [P] [US3] Implement SummarySupersessionService in backend/src/services/summary_service.py (mark previous summaries as SUPERSEDED when new approval occurs, ensure exactly one APPROVED summary per participant)

### API Endpoints for User Story 3

- [X] T067 [P] [US3] Update POST /submissions in backend/src/api/submission_routes.py (check rate limit before accept, return 429 if limit exceeded, include remaining_submissions in response)
- [X] T068 [P] [US3] Implement GET /submissions/history in backend/src/api/submission_routes.py (participant views their submission history for current round, see which summary is currently approved)

### Integration Tests for User Story 3

- [X] T069 [US3] Write multiple submissions test in backend/tests/integration/test_participant_iteration.py (submit 3 times, approve #2, verify #1 and #3 marked SUPERSEDED, verify only #2 enters clustering)
- [X] T070 [US3] Write rate limit test in backend/tests/integration/test_us3_rate_limit.py (submit 3 times, attempt 4th, verify 429 response with clear error message)
- [X] T071 [US3] Write last-approved-wins test in backend/tests/integration/test_us3_approval_rule.py (submit twice, approve both, verify last approval supersedes first, verify exactly one summary in final aggregation)

### Frontend for User Story 3

- [X] T072 [P] [US3] Create SubmissionHistory component in frontend/src/components/SubmissionHistory/index.tsx (show participant's submissions for current round, indicate which is approved, allow resubmission if under limit)
- [X] T073 [P] [US3] Update submission form in frontend/src/components/SubmissionForm/index.tsx (display remaining_submissions count, disable submit button when limit reached, show rate limit error)

**US3 Completion Criteria**:
- ✅ Participant can submit up to 3 times per round
- ✅ Rate limit enforced with clear feedback
- ✅ Last-approved-wins rule correctly applied
- ✅ Exactly one summary per participant enters clustering
- ✅ Previous summaries marked SUPERSEDED

---

## Phase 6: User Story 4 - Synchronous Time-Boxed Execution (Priority: P4)

**Goal**: Enforce strict timing constraints: 3-6 minute submission windows, ~10 minutes per round including processing, under 60 minutes total for 3-5 round discussions.

**Independent Test**: Schedule discussion → enforce submission window → measure round completion time → verify total time < 60 minutes → attempt late submission → verify rejection.

**Dependencies**: US1 complete (timing service exists), US2 complete (multi-round exists)

### Services for User Story 4

- [X] T074 [P] [US4] Implement TimingService.enforce_precision in backend/src/services/timing_service.py (verify window closure ±100ms precision, log timing violations, emit timing.violation event if >100ms drift)
- [X] T075 [P] [US4] Implement PerformanceBenchmarkService in backend/src/services/benchmark_service.py (measure round processing time: submission_close → clustering_complete → sankey_complete, track p95/p99 latencies)

### API Endpoints for User Story 4

- [X] T076 [P] [US4] Implement GET /discussions/{id}/timing in backend/src/api/discussion_routes.py (fetch timing metrics: round durations, total elapsed time, remaining time to 60-minute target)

### Integration Tests for User Story 4

- [X] T077 [US4] Write timing precision test in backend/tests/integration/test_timing_enforcement.py (set 5-minute window, measure actual closure time, assert ±100ms precision for 99th percentile)
- [X] T078 [US4] Write round performance test in backend/tests/integration/test_us4_performance.py (complete full round, measure elapsed time from submission_close to round_complete, assert <10 minutes)
- [X] T079 [US4] Write total discussion time test in backend/tests/integration/test_us4_total_time.py (run 5-round discussion, measure start to completion, assert <60 minutes)
- [X] T080 [US4] Write late submission rejection test in backend/tests/integration/test_us4_late_submission.py (submit after window_end, verify 400 error with "window closed" message)

### Performance Benchmarks for User Story 4

- [X] T081 [US4] Write Sankey construction benchmark in backend/tests/performance/test_sankey_performance.py (100 participants, 3 rounds, verify construction <2 seconds per round per SC-004)
- [X] T082 [US4] Write parallel submission load test in backend/tests/performance/test_parallel_input_load.py (100 concurrent participants submit within 5-second window, verify zero failures per SC-004)

**US4 Completion Criteria**:
- ✅ Submission window closes within ±100ms (99th percentile)
- ✅ Round processing completes in <10 minutes
- ✅ 5-round discussion completes in <60 minutes
- ✅ Late submissions rejected with clear error
- ✅ Countdown timer accuracy validated
- ✅ Performance benchmarks met (Spec 001 SC-004, SC-006, SC-008)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Production-readiness, observability, and constitutional compliance validation

- [X] T083 [P] Implement structured logging across all services (trace discussion_id and round_id through all operations)
- [X] T084 [P] Add OpenTelemetry instrumentation in backend/src/telemetry.py (trace spans for state transitions, event emissions, sub-protocol handoffs)
- [X] T085 [P] Implement health check endpoints in backend/src/api/health_routes.py (GET /health, GET /health/ready for liveness/readiness probes)
- [X] T086 [P] Add database connection pooling optimization in backend/src/database.py (configure pool size based on load testing results)
- [X] T087 [P] Implement approval deadline timeout handler in backend/src/services/approval_timeout.py (mark unapproved summaries as APPROVAL_TIMEOUT after deadline, mark participants as dropouts)
- [X] T088 [P] Add ephemeral data cleanup job in backend/src/services/cleanup_service.py (delete submissions after approval + 5-minute grace, schedule via background worker)
- [X] T089 [P] Write constitutional compliance audit tests in backend/tests/compliance/test_constitutional_principles.py (verify all 7 principles across all user stories: Parallel-First, Intent Fidelity, Semantic Accuracy, Temporal Transparency, Community-Bounded, Synchronous Deliberation, Representation Not Adjudication)
- [X] T090 [P] Create API documentation generator in backend/src/docs.py (serve OpenAPI spec at /docs, include contract schemas from contracts/discussion-api.yaml)
- [X] T091 [P] Write deployment guide in backend/docs/deployment.md (Docker compose production config, environment variables, database migrations, monitoring setup)
- [X] T092 [P] Add error recovery mechanisms in backend/src/services/error_recovery.py (Round state rollback on FAILED, discussion termination on unrecoverable errors)
- [X] T093 [P] Implement frontend error boundary in frontend/src/components/ErrorBoundary.tsx (catch React errors, display user-friendly message, log to backend)
- [X] T094 [P] Add end-to-end Cypress tests in frontend/tests/e2e/complete_discussion.cy.ts (full user journey: create → start → wait for timer → view report)

---

## Task Dependencies & Parallel Execution

### Critical Path (Must Complete in Order)

1. **Phase 1 (Setup)** → **Phase 2 (Foundation)** → **User Stories can begin**
2. **Within each user story**: Tests (if present) → Models → Services → Endpoints → Integration

### Parallel Opportunities

**Within Phase 1 (Setup)**: T003, T004, T005, T006, T007 can run in parallel after T001-T002

**Within Phase 2 (Foundation)**: T010-T016, T018 can run in parallel after T008-T009

**Within US1 Implementation**:
- Models (T019-T025): All parallel after foundation
- Services (T026-T031): Can run in parallel after models complete
- API Endpoints (T032-T036): All parallel after services
- Event Handlers (T037-T040): All parallel after ProtocolCoordinator exists
- Frontend (T045-T050): All parallel, independent of backend beyond API contract

**Between User Stories**:
- US2 can begin after US1 models/services exist (T051-T064 only depend on US1 core, not US1 integration tests)
- US3 can begin in parallel with US2 (different concerns: US2 = multi-round, US3 = iteration)
- US4 can begin in parallel with US2-US3 (performance validation doesn't change functionality)

### User Story Dependency Graph

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundation)
    ↓
    ├──> US1 (Single Round) ──> US2 (Multi-Round)
    ├──> US3 (Iteration) ────────┘
    └──> US4 (Timing) ───────────┘
         ↓
    Phase 7 (Polish)
```

**Recommended MVP Scope**: US1 only (Tasks T001-T050)
- Delivers: Complete single-round discussion with Sankey visualization
- Validates: All core protocol invariants
- Time estimate: ~4-6 weeks for team of 2-3 developers

**Post-MVP Increments**:
- **Increment 2**: US2 (Multi-Round) - adds temporal dimension
- **Increment 3**: US3 + US4 (Iteration + Timing) - production readiness

---

## Testing Strategy Summary

**Unit Tests** (backend/tests/unit/):
- State machine transitions (Discussion, Round)
- Invariant validation logic (InvariantValidator)
- Timing calculations (TimingService)
- Event emission/subscription (EventBus)

**Integration Tests** (backend/tests/integration/):
- End-to-end discussion flows (single-round, multi-round)
- Sub-protocol coordination (event handlers)
- Database transactions and rollback
- Redis timing enforcement

**Contract Tests** (backend/tests/contract/):
- Spec 2 → Spec 3 (submission_window.closed payload)
- Spec 3 → Spec 4 (summarization.complete payload)
- Spec 4 → Spec 5 (clustering.complete payload)
- Spec 5 → Spec 6 (sankey.complete payload)

**Performance Tests** (backend/tests/performance/):
- Sankey construction (<2s for 100 participants)
- Parallel submission load (100 concurrent, <5s)
- Round completion time (<10 minutes)

**E2E Tests** (frontend/tests/e2e/):
- Full user journey (create → participate → view report)
- Real-time updates (round status, countdown timer)
- Error handling (late submission, rate limit)

---

## Implementation Strategy

### Week 1-2: Foundation + US1 Core
- Complete Phase 1 (Setup) and Phase 2 (Foundation)
- Implement US1 models and services (T019-T031)
- Target: Discussion can be created and started

### Week 3-4: US1 Integration + Frontend
- Implement US1 API endpoints (T032-T036)
- Implement event handlers (T037-T040)
- Build frontend visualization (T045-T050)
- Target: Single-round discussion works end-to-end

### Week 5: US1 Testing + MVP Validation
- Write integration tests (T041-T043)
- Run MVP acceptance tests from MVP_ACCEPTANCE_TEST_PLAN.md
- Performance benchmarking
- Target: US1 production-ready

### Week 6-7: US2 Multi-Round (If continuing beyond MVP)
- Implement multi-round services and API (T051-T055)
- Flow computation and dropout detection
- Multi-column Sankey visualization
- Target: Temporal movement tracking works

### Week 8: US3 + US4 + Polish (Production Hardening)
- Rate limiting and iteration (US3)
- Timing precision and performance (US4)
- Cross-cutting concerns (Phase 7)
- Target: Production-ready system

---

## Task Validation Checklist

- ✅ All tasks follow format: `- [ ] [ID] [P?] [Story] Description with file path`
- ✅ Task IDs sequential (T001-T094)
- ✅ User story labels present for story tasks (US1, US2, US3, US4)
- ✅ Parallel markers ([P]) only on truly independent tasks
- ✅ File paths included in all implementation tasks
- ✅ Dependencies clearly documented
- ✅ Each user story independently testable
- ✅ MVP scope identified (US1)
- ✅ Constitutional compliance validated (Task T089)

---

**Total Tasks**: 94
**Breakdown**:
- Setup (Phase 1): 7 tasks
- Foundation (Phase 2): 11 tasks
- US1 (P1): 32 tasks (T019-T050)
- US2 (P2): 14 tasks (T051-T064)
- US3 (P3): 9 tasks (T065-T073)
- US4 (P4): 9 tasks (T074-T082)
- Polish (Phase 7): 12 tasks (T083-T094)

**Parallel Opportunities**: 45 tasks marked [P] (48% of total)

**Independent Test Criteria Met**: ✅
- US1: Single-round discussion with Sankey
- US2: Multi-round movement tracking
- US3: Participant iteration with rate limiting
- US4: Timing precision and performance

**Suggested MVP Scope**: US1 (Tasks T001-T050) = 50 tasks

---

**Generated**: 2026-01-29
**Based on**: plan.md, spec.md, research.md, data-model.md, contracts/discussion-api.yaml
**Next Action**: Begin Phase 1 (Setup) implementation
