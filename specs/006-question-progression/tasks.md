# Tasks: Question Progression Protocol

**Input**: Design documents from `/specs/006-question-progression/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Constitution Compliance**: Tasks MUST align with `.specify/memory/constitution.md` principles.
Parallel tasks support Parallel-First Architecture; independent user stories enable incremental delivery.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend service**: `src/question_progression/`, `tests/spec6/`
- Paths follow the structure defined in plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for Spec 6 module

- [X] T001 Create question_progression module structure in src/question_progression/ (models.py, validators.py, services/, api/, prompts.py, event_handlers.py, workers/)
- [X] T002 [P] Initialize Python 3.11+ backend with Anthropic Claude API, FastAPI, SQLAlchemy dependencies
- [X] T003 [P] Configure pytest, pytest-asyncio, pytest-mock for testing
- [X] T004 [P] Create test directory structure in tests/spec6/ (unit/, integration/, contract/, e2e/)
- [X] T005 [P] Setup environment configuration for Claude API key in src/config/settings.py
- [X] T006 [P] Configure logging for question progression module in src/utils/logging.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Create database schema for QuestionSequence entity in migrations/
- [X] T008 Create database schema for Question entity with mode enum (HOST_DEFINED, AUTO_GENERATED) in migrations/
- [X] T009 Create database schema for QuestionProvenance entity in migrations/
- [X] T010 Extend Round entity with question_id FK in src/discussion_protocol/models.py
- [X] T011 [P] Create QuestionSequence SQLAlchemy model in src/question_progression/models.py
- [X] T012 [P] Create Question SQLAlchemy model in src/question_progression/models.py
- [X] T013 [P] Create QuestionProvenance SQLAlchemy model in src/question_progression/models.py
- [X] T014 [P] Setup Redis connection for event bus in src/events/redis_client.py
- [X] T015 [P] Create event bus infrastructure for sankey.complete subscription in src/events/bus.py
- [X] T016 Create QuestionValidator with 5-check pipeline in src/question_progression/validators.py (starts_with_what_how, no_why, no_ranking, no_yes_no, length_bounds)
- [X] T017 Add constitutional constraint keywords (vote, rank, best, worst, choose) to validator in src/question_progression/validators.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Host-Defined Question Sequence (Priority: P1) 🎯 MVP

**Goal**: Host provides all questions upfront at discussion creation. Questions appear in sequence as rounds progress. Host controls advancement timing.

**Independent Test**: Create discussion with 3 host-defined questions → advance through all rounds → verify questions appear in correct sequence without modification

### Implementation for User Story 1

- [X] T018 [P] [US1] Create QuestionSequenceService.create_host_sequence() in src/question_progression/services/sequence.py (validates 1-10 questions)
- [X] T019 [P] [US1] Implement question validation at creation in QuestionSequenceService (call QuestionValidator)
- [X] T020 [P] [US1] Implement POST /questions/sequences endpoint in src/question_progression/api/questions.py (create host-defined sequence)
- [X] T021 [P] [US1] Implement GET /questions/sequences/{sequence_id} endpoint in src/question_progression/api/questions.py
- [X] T022 [US1] Implement QuestionSequenceService.get_next_question() in src/question_progression/services/sequence.py (returns question by order)
- [X] T023 [US1] Implement question immutability enforcement in src/question_progression/services/sequence.py (prevent edits after round starts)
- [X] T024 [US1] Implement sequence completion detection in src/question_progression/services/sequence.py (all questions used → discussion completed)
- [X] T025 [US1] Add question_id FK constraint to Round entity in src/discussion_protocol/models.py (already exists from Phase 2)
- [X] T026 [US1] Integrate QuestionSequenceService with Discussion creation flow in src/discussion_protocol/services/discussion_service.py
- [X] T027 [US1] Add validation error responses for host-defined questions in src/question_progression/api/questions.py (specific error messages per constraint)
- [X] T028 [US1] Add logging for host-defined question creation and validation in src/question_progression/services/sequence.py

**Checkpoint**: Host-defined mode fully functional - hosts can create discussions with pre-planned questions

---

## Phase 4: User Story 3 - Question Quality Constraints (Priority: P3)

**Goal**: All questions (host-defined or auto-generated) follow constitutional constraints: What/How only, no voting/ranking, no yes/no questions.

**Independent Test**: Attempt to create questions that violate constraints → verify system blocks or transforms them with specific error messages

**Note**: Implemented before US2 because validation is foundational for auto-generation

### Implementation for User Story 3

- [X] T029 [P] [US3] Implement starts_with_what_how check in src/question_progression/validators.py (case-insensitive)
- [X] T030 [P] [US3] Implement no_why_questions check in src/question_progression/validators.py (reject "Why", "Do you", "Should we", "Would you")
- [X] T031 [P] [US3] Implement no_ranking check in src/question_progression/validators.py (reject "rank", "order", "best", "worst")
- [X] T032 [P] [US3] Implement no_yes_no check in src/question_progression/validators.py (reject binary choice patterns)
- [X] T033 [P] [US3] Implement length_bounds check in src/question_progression/validators.py (10-200 characters)
- [X] T034 [US3] Add validation error codes to QuestionValidator in src/question_progression/validators.py (INVALID_START, CONTAINS_WHY, CONTAINS_RANKING, BINARY_CHOICE, INVALID_LENGTH)
- [X] T035 [US3] Implement QuestionValidator.validate() with fail-fast pipeline in src/question_progression/validators.py
- [X] T036 [US3] Add unit tests for all 5 validation checks in tests/spec6/unit/test_validation.py
- [X] T037 [US3] Add test cases for constitutional constraint keywords in tests/spec6/unit/test_validation.py
- [X] T038 [US3] Add integration test for host-defined question rejection in tests/spec6/integration/test_host_defined_flow.py

**Checkpoint**: All questions validated against constitutional constraints before use

---

## Phase 5: User Story 2 - Auto-Generated Question Flow (Priority: P2)

**Goal**: After each round, system autonomously generates next question based on Sankey patterns. Host still controls when next round begins.

**Independent Test**: Create discussion with 1 initial question → complete Round 1 → verify autonomous question generation after Sankey → confirm Round 2 begins with auto-generated question

### Implementation for User Story 2

- [X] T039 [P] [US2] Create LLM prompt template for question generation in src/question_progression/prompts.py (constitutional principles 15%, Sankey context 60%, question history 25%)
- [X] T040 [P] [US2] Create QuestionGenerationService with Claude API integration in src/question_progression/services/generation.py
- [X] T041 [P] [US2] Implement QuestionGenerationService.generate_from_sankey() in src/question_progression/services/generation.py (prompt construction, LLM call)
- [X] T042 [P] [US2] Implement retry logic with exponential backoff in src/question_progression/services/generation.py (max 3 retries)
- [X] T043 [P] [US2] Implement validation retry loop in src/question_progression/services/generation.py (regenerate if validation fails, max 3 attempts)
- [X] T044 [US2] Implement ProvenanceTracker.record() in src/question_progression/services/provenance.py (Sankey hash, LLM model, latency, retry count)
- [X] T045 [US2] Create event handler for sankey.complete event in src/question_progression/event_handlers.py (subscribe to Spec 5 event)
- [X] T046 [US2] Integrate QuestionGenerationService with sankey.complete handler in src/question_progression/event_handlers.py
- [X] T047 [US2] Add QUESTION_READY state to Round entity in src/discussion_protocol/models.py (question generated, awaiting host advancement)
- [X] T048 [US2] Implement QUESTION_GENERATION_FAILED fallback state in src/discussion_protocol/models.py (notify host to provide manual question)
- [X] T049 [US2] Create background worker for async generation in src/question_progression/workers/generation_worker.py
- [X] T050 [US2] Implement POST /auto-generation/generate endpoint in src/question_progression/api/auto_generation.py (trigger generation manually for testing)
- [X] T051 [US2] Implement GET /auto-generation/status/{discussion_id} endpoint in src/question_progression/api/auto_generation.py (check generation status)
- [X] T052 [US2] Add auto-generation timeout handling in src/question_progression/services/generation.py (30-second timeout, fallback to manual entry)
- [X] T053 [US2] Add provenance metadata to Question entity response in src/question_progression/api/questions.py
- [X] T054 [US2] Add logging for auto-generation lifecycle in src/question_progression/services/generation.py (start, success, retry, failure)
- [X] T055 [US2] Add integration test for auto-generation workflow in tests/spec6/integration/test_auto_generated_flow.py (mocked LLM)
- [X] T056 [US2] Add contract test for sankey.complete event in tests/spec6/contract/test_event_contract.py (AsyncAPI schema validation)

**Checkpoint**: Auto-generated mode fully functional - questions generated autonomously from Sankey patterns

---

## Phase 6: User Story 4 - Round Advancement Control (Priority: P2)

**Goal**: Host maintains synchronous control over round advancement in both modes. In auto-mode, host controls timing after question generation completes.

**Independent Test**: Create discussions in both modes → verify host can pause before advancement → confirm termination works at any stage

### Implementation for User Story 4

- [X] T057 [P] [US4] Implement Round.can_advance() check in src/discussion_protocol/models.py (Sankey complete + question ready)
- [X] T058 [P] [US4] Implement POST /discussions/{id}/advance endpoint in src/discussion_protocol/api/discussions.py (host triggers advancement)
- [X] T059 [P] [US4] Add blocking logic for advancement in src/discussion_protocol/services/round_service.py (wait for Sankey + question)
- [X] T060 [US4] Add "Ready for Next Round" indicator to Discussion state in src/discussion_protocol/models.py
- [X] T061 [US4] Implement host control validation in src/discussion_protocol/services/round_service.py (only host can advance)
- [X] T062 [US4] Add advancement status to GET /discussions/{id} response in src/discussion_protocol/api/discussions.py (ready, blocked, waiting_generation)
- [X] T063 [US4] Add integration test for host advancement control in tests/spec6/integration/test_host_defined_flow.py
- [X] T064 [US4] Add integration test for auto-mode advancement control in tests/spec6/integration/test_auto_generated_flow.py

**Checkpoint**: Host controls advancement timing in both modes with clear status indicators

---

## Phase 7: User Story 5 - Discussion Completion and Termination (Priority: P3)

**Goal**: When all questions exhausted (host-defined) or host manually terminates (either mode), discussion enters completed state with final report.

**Independent Test**: Complete all rounds of host-defined discussion → verify status changes to "completed" with no further input accepted

### Implementation for User Story 5

- [X] T065 [P] [US5] Add COMPLETED status to Discussion entity in src/discussion_protocol/models.py
- [X] T066 [P] [US5] Add TERMINATED status to Discussion entity in src/discussion_protocol/models.py
- [X] T067 [P] [US5] Implement automatic completion for host-defined mode in src/discussion_protocol/services/discussion_service.py (all questions used)
- [X] T068 [US5] Implement POST /discussions/{id}/terminate endpoint in src/discussion_protocol/api/discussions.py (host manual termination)
- [X] T069 [US5] Add termination blocking during active input collection in src/discussion_protocol/services/discussion_service.py (wait for window to close)
- [X] T070 [US5] Add partial round termination support in src/discussion_protocol/services/discussion_service.py (after collection, before Sankey)
- [X] T071 [US5] Implement final report generation on termination in src/discussion_protocol/services/report_service.py (last completed Sankey)
- [X] T072 [US5] Add participant input blocking for completed/terminated discussions in src/input_collection/services/submission_service.py
- [X] T073 [US5] Add "Discussion has ended" message to participant interface in src/input_collection/api/submissions.py
- [X] T074 [US5] Add integration test for automatic completion in tests/spec6/integration/test_host_defined_flow.py
- [X] T075 [US5] Add integration test for manual termination in tests/spec6/integration/test_auto_generated_flow.py

**Checkpoint**: Discussions complete/terminate correctly with final reports generated

---

## Phase 8: Integration & Event Handling

**Purpose**: Complete Spec 5 → Spec 6 event integration and cross-spec coordination

- [X] T076 [P] Implement event payload validation for sankey.complete in src/question_progression/event_handlers.py
- [X] T077 [P] Implement question.ready event emission in src/question_progression/event_handlers.py (notify host UI)
- [X] T078 [P] Implement question.generation_failed event emission in src/question_progression/event_handlers.py (trigger fallback)
- [X] T079 [P] Add retry logic for event handler failures in src/question_progression/event_handlers.py
- [X] T080 [P] Add event handler monitoring/logging in src/question_progression/event_handlers.py
- [X] T081 Add contract test for question-api.yaml in tests/spec6/contract/test_question_api_contract.py
- [X] T082 Add contract test for spec5-to-spec6-events.yaml in tests/spec6/contract/test_event_contract.py
- [X] T083 Add integration test for Spec 5 → Spec 6 handoff in tests/spec6/integration/test_event_integration.py

---

## Phase 9: Error Handling & Edge Cases

**Purpose**: Robust error handling for LLM failures, validation edge cases, and fallback scenarios

- [X] T084 [P] Implement LLM API error handling in src/question_progression/services/generation.py (timeout, rate limit, service unavailable)
- [X] T085 [P] Implement fallback to manual question entry in src/question_progression/services/generation.py (after max retries)
- [X] T086 [P] Add host notification for generation failures in src/question_progression/api/auto_generation.py
- [X] T087 [P] Add question immutability enforcement at API level in src/question_progression/api/questions.py (reject edits after round starts)
- [X] T088 [P] Add linear sequence validation in src/question_progression/services/sequence.py (no gaps, no skips)
- [X] T089 [P] Add discussion stall detection in src/discussion_protocol/services/discussion_service.py (mark stalled after 7 days inactivity)
- [X] T090 [P] Add unit tests for LLM error handling in tests/spec6/unit/test_generation.py
- [X] T091 [P] Add unit tests for fallback scenarios in tests/spec6/unit/test_generation.py
- [X] T092 Add integration test for generation failure recovery in tests/spec6/integration/test_auto_generated_flow.py

---

## Phase 10: End-to-End Testing & Performance

**Purpose**: Real LLM integration tests and performance validation

- [X] T093 [P] Add e2e test with real Claude API in tests/spec6/e2e/test_real_generation.py (--e2e flag)
- [X] T094 [P] Add e2e test for complete host-defined discussion in tests/spec6/e2e/test_real_generation.py
- [X] T095 [P] Add e2e test for complete auto-generated discussion in tests/spec6/e2e/test_real_generation.py
- [X] T096 [P] Add performance test for auto-generation latency in tests/spec6/e2e/test_real_generation.py (verify p95 < 10s)
- [X] T097 [P] Add performance test for validation speed in tests/spec6/unit/test_validation.py (verify < 10ms)
- [X] T098 [P] Add performance test for question query speed in tests/spec6/integration/test_sequence_api.py (verify < 5ms)

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T099 [P] Add database indexes for (discussion_id, order) in Question table
- [X] T100 [P] Add database indexes for (question_id) in QuestionProvenance table
- [X] T101 [P] Add comprehensive error messages for all validation failures in src/question_progression/validators.py
- [X] T102 [P] Add monitoring metrics for auto-generation success rate in src/question_progression/services/generation.py
- [X] T103 [P] Add monitoring metrics for validation rejection rate in src/question_progression/validators.py
- [X] T104 [P] Add API rate limiting for question generation in src/question_progression/api/auto_generation.py
- [X] T105 [P] Add caching for question sequences in src/question_progression/services/sequence.py
- [X] T106 [P] Update quickstart.md with example commands and troubleshooting
- [X] T107 Code cleanup and refactoring across all services
- [X] T108 Security hardening (input sanitization, injection prevention)
- [X] T109 Documentation updates in specs/006-question-progression/

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (P1) can start immediately after foundational
  - US3 (validation) should complete before US2 (auto-generation needs validation)
  - US2 (auto-generation) extends US1
  - US4 (advancement control) integrates with US1 and US2
  - US5 (completion/termination) extends US1 and US2
- **Integration (Phase 8)**: Can proceed in parallel with user stories
- **Error Handling (Phase 9)**: Depends on US2 completion
- **E2E Testing (Phase 10)**: Depends on all user stories complete
- **Polish (Phase 11)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Independent validation logic
- **User Story 2 (P2)**: Depends on US3 completion (needs validation) - Extends US1
- **User Story 4 (P2)**: Depends on US1 and US2 - Integrates with both modes
- **User Story 5 (P3)**: Depends on US1 and US2 - Completion logic for both modes

### Within Each User Story

- Models before services
- Services before endpoints
- Backend implementation before API integration
- Core implementation before error handling/logging
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T002-T006)
- All Foundational tasks marked [P] can run in parallel (T011-T015)
- Once Foundational phase completes:
  - US1 models/services (T018-T021) can run in parallel
  - US3 validation checks (T029-T033) can run in parallel with US1
- Within US2: LLM integration tasks (T039-T042) can run in parallel
- Phase 8 event handling tasks (T076-T080) can run in parallel
- Phase 9 error handling tasks (T084-T092) can run in parallel
- Phase 10 e2e tests (T093-T098) can run in parallel
- Phase 11 polish tasks (T099-T109) can run in parallel

---

## Parallel Example: User Story 2 (Auto-Generation)

```bash
# Launch all foundational tasks for auto-generation together:
Task T039: "Create LLM prompt template in src/question_progression/prompts.py"
Task T040: "Create QuestionGenerationService in src/question_progression/services/generation.py"
Task T041: "Implement generate_from_sankey()"
Task T042: "Implement retry logic with exponential backoff"
Task T043: "Implement validation retry loop"

# After services complete, launch API and event handlers:
Task T045: "Create sankey.complete event handler"
Task T050: "Implement POST /auto-generation/generate endpoint"
Task T051: "Implement GET /auto-generation/status endpoint"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (T018-T028) - Host-defined mode
4. Complete Phase 4: User Story 3 (T029-T038) - Validation
5. **STOP and VALIDATE**: Test host-defined mode independently
   - Create discussion with 3 questions
   - Verify questions appear in sequence
   - Verify validation blocks invalid questions
   - Verify immutability after round starts
6. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP! Host-defined mode working)
3. Add User Story 3 → Test independently → Deploy/Demo (Validation enforced)
4. Add User Story 2 → Test independently → Deploy/Demo (Auto-generation enabled)
5. Add User Story 4 → Test independently → Deploy/Demo (Advancement control refined)
6. Add User Story 5 → Test independently → Deploy/Demo (Completion/termination working)
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (P1) - Host-defined mode
   - Developer B: User Story 3 (P3) - Validation (can run parallel with US1)
3. After US1/US3 complete:
   - Developer A: User Story 2 (P2) - Auto-generation (needs validation)
   - Developer B: User Story 4 (P2) - Advancement control (integrates with US1/US2)
4. After US2/US4 complete:
   - Developer A: User Story 5 (P3) - Completion/termination
   - Developer B: Phase 8 (Integration) + Phase 9 (Error handling)
5. Stories integrate without blocking each other

---

## Task Summary

- **Total Tasks**: 109
- **Phase 1 (Setup)**: 6 tasks
- **Phase 2 (Foundational)**: 11 tasks (BLOCKS all stories)
- **Phase 3 (US1 - MVP)**: 11 tasks
- **Phase 4 (US3 - Validation)**: 10 tasks
- **Phase 5 (US2 - Auto-generation)**: 18 tasks
- **Phase 6 (US4 - Advancement)**: 8 tasks
- **Phase 7 (US5 - Completion)**: 11 tasks
- **Phase 8 (Integration)**: 8 tasks
- **Phase 9 (Error Handling)**: 9 tasks
- **Phase 10 (E2E Testing)**: 6 tasks
- **Phase 11 (Polish)**: 11 tasks

**Parallel Tasks**: 51 tasks marked [P] can run in parallel with other tasks in their phase

**MVP Scope**: Phase 1 + Phase 2 + Phase 3 + Phase 4 = 38 tasks for host-defined mode with validation

**Success Criteria**:
- Auto-generation latency p95 < 10 seconds
- Validation < 10ms per question
- 100% constitutional constraint enforcement
- Host synchronous control preserved

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- MVP = US1 + US3 (host-defined mode with validation)
- US2 (auto-generation) is core feature but can be added after MVP validation
- US3 implemented before US2 because validation is foundational for auto-generation

---

**Last Updated**: 2026-01-29
**Next Action**: Begin implementation with Phase 1 (Setup)
