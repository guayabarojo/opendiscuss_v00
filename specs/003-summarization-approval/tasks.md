# Tasks: Micro-Summarization & Approval Protocol

**Input**: Design documents from `/specs/003-summarization-approval/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/summarization-api.yaml

**Constitution Compliance**: Tasks MUST align with `.specify/memory/constitution.md` principles.
Parallel tasks support Parallel-First Architecture; independent user stories enable incremental delivery.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `frontend/src/`
- Paths shown below follow the structure defined in plan.md

---

## Phase 1: Setup (Shared Infrastructure) ✅ COMPLETED

**Purpose**: Project initialization and basic structure

- [x] T001 Create backend project structure per plan.md (backend/src/summarization/{models,services,api,prompts}/)
- [x] T002 Initialize Python 3.11+ backend with FastAPI, OpenAI SDK, Pydantic, better-profanity dependencies
- [x] T003 [P] Configure backend linting (black, ruff) and formatting tools
- [x] T004 [P] Create frontend project structure per plan.md (SummaryReview/, CorrectionSignalForm/, SafetyNotice/, ApprovalInterface/)
- [x] T005 [P] Initialize TypeScript 5+ frontend with React, Jest dependencies
- [x] T006 [P] Configure frontend linting (eslint, prettier) and formatting tools

---

## Phase 2: Foundational (Blocking Prerequisites) ✅ COMPLETED

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Setup PostgreSQL database schema for Summary and CorrectionSignal entities
- [x] T008 Configure Alembic migrations framework in backend/alembic/versions/011_create_summaries.py
- [x] T009 [P] Setup Redis connection for LLM response caching in backend/src/cache/redis_client.py
- [x] T010 [P] Configure OpenAI SDK client in backend/src/llm/openai_client.py (API key, org ID)
- [x] T011 [P] Setup environment configuration management in backend/src/config.py (OpenAI settings)
- [x] T012 [P] Create FastAPI application with middleware structure in backend/src/main.py (DB + Redis init)
- [x] T013 [P] Configure error handling and logging infrastructure (already exists in backend/src/logging_config.py)
- [x] T014 [P] Setup event bus infrastructure for Spec 2 → Spec 3 → Spec 4 handoffs in backend/src/events/bus.py

**Checkpoint**: ✅ Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Generate and Approve Summary (Priority: P1) 🎯 MVP

**Goal**: Generate normalized 1-2 sentence summaries from participant input and enable explicit approval. Forward approved summaries to clustering.

**Independent Test**: Submit raw input → receive generated summary → approve summary → verify status=APPROVED and forwarded to Spec 4

### Implementation for User Story 1

- [x] T015 [P] [US1] Create Summary model in backend/src/summarization/models/summary.py with FSM (PENDING_REVIEW, APPROVED, REJECTED_FINAL)
- [x] T016 [P] [US1] Create SummaryStatus enum in backend/src/summarization/models/summary.py
- [x] T017 [P] [US1] Create database migration for Summary entity in backend/alembic/versions/011_create_summaries.py
- [x] T018 [P] [US1] Create base summarization prompt template in backend/src/summarization/prompts/base_summary_prompt.py
- [x] T019 [US1] Implement SummarizationService.generate_summary() in backend/src/summarization/services/summarization_service.py (LLM call, prompt construction)
- [x] T020 [US1] Implement model selection logic (GPT-4-turbo vs GPT-3.5) in backend/src/summarization/services/summarization_service.py
- [x] T021 [US1] Implement ApprovalService.approve_summary() in backend/src/summarization/services/approval_service.py (status transition, timestamp)
- [x] T022 [US1] Implement POST /summaries/generate endpoint in backend/src/summarization/api/summary_routes.py
- [x] T023 [US1] Implement POST /summaries/{summary_id}/approve endpoint in backend/src/summarization/api/summary_routes.py
- [x] T024 [US1] Implement GET /summaries/{summary_id} endpoint in backend/src/summarization/api/summary_routes.py
- [x] T025 [US1] Create event handler for submission_window.closed (Spec 2 → Spec 3) in backend/src/summarization/events/handlers/submission_collected.py
- [x] T026 [US1] Create event emitter for summarization.complete (Spec 3 → Spec 4) in backend/src/summarization/events/handlers/approval_complete.py
- [x] T027 [P] [US1] Create SummaryReview component in frontend/src/components/SummaryReview/SummaryReview.tsx (approve/reject buttons)
- [x] T028 [P] [US1] Create summaryApi.ts client in frontend/src/services/summaryApi.ts (API calls for generate, approve, get)
- [x] T029 [US1] Create ApprovalInterface page in frontend/src/pages/ApprovalInterface/ApprovalInterface.tsx (show summary, handle approval)
- [x] T030 [US1] Integrate SummaryReview component with ApprovalInterface page
- [x] T031 [US1] Add validation for summary_text max 500 chars in backend/src/summarization/services/summarization_service.py
- [x] T032 [US1] Add validation for 1-2 sentence constraint in prompt (not enforced programmatically)
- [x] T033 [US1] Add logging for summary generation and approval events in backend/src/summarization/services/

**Checkpoint**: At this point, User Story 1 should be fully functional - summaries can be generated, approved, and forwarded to clustering

---

## Phase 4: User Story 2 - Reject and Regenerate Summary (Priority: P2)

**Goal**: Enable participants to reject summaries and trigger automatic regeneration (up to 2 automatic attempts).

**Independent Test**: Submit input → reject summary → verify new summary generated with regen_count=1 → reject again → verify regen_count=2

### Implementation for User Story 2

- [x] T034 [P] [US2] Add REJECTED status to SummaryStatus enum in backend/src/models/summary.py
- [x] T035 [P] [US2] Add regen_count field to Summary model in backend/src/models/summary.py
- [x] T036 [P] [US2] Create database migration for regen_count field in backend/alembic/versions/
- [x] T037 [P] [US2] Create regeneration prompt templates in backend/src/prompts/regeneration_prompts.py (vary focus, simplify)
- [x] T038 [US2] Implement RegenerationService.regenerate_summary() in backend/src/services/regeneration_service.py (bounded retry logic)
- [x] T039 [US2] Implement rejection workflow in backend/src/services/approval_service.py (reject → check regen_count → trigger regen)
- [x] T040 [US2] Implement POST /summaries/{summary_id}/reject endpoint in backend/src/api/summary_routes.py
- [x] T041 [US2] Add reject button to SummaryReview component in frontend/src/components/SummaryReview/SummaryReview.tsx
- [x] T042 [US2] Add reject API call to summaryApi.ts in frontend/src/services/summaryApi.ts
- [x] T043 [US2] Integrate rejection workflow with ApprovalInterface page (handle reject → show new summary)
- [x] T044 [US2] Add regen_count display to SummaryReview component (show "Attempt X/3")
- [x] T045 [US2] Add validation for max 2 automatic regenerations in backend/src/services/regeneration_service.py
- [x] T046 [US2] Add logging for rejection and regeneration events in backend/src/services/

**Checkpoint**: Participants can reject summaries and receive up to 2 automatic regenerations

---

## Phase 5: User Story 3 - Persistent Rejection with Correction Signal (Priority: P3) ✅ COMPLETED

**Goal**: After 2 automatic regenerations, prompt participant for correction signal (reason tags + feedback). Regenerate once more using signal. Mark REJECTED_FINAL if still rejected.

**Independent Test**: Submit input → reject 2 times → provide correction signal (reason tag + feedback) → verify final regeneration → reject → verify status=REJECTED_FINAL

### Implementation for User Story 3

- [x] T047 [P] [US3] Create CorrectionSignal model in backend/src/models/correction_signal.py (signal_id, summary_id, reason_tag, feedback_text)
- [x] T048 [P] [US3] Create ReasonTag enum in backend/src/models/correction_signal.py (WRONG_CRUX, TOO_VAGUE, MISREPRESENTS_ME, MISSED_CONSTRAINT, MISSED_SOLUTION, OTHER)
- [x] T049 [P] [US3] Create database migration for CorrectionSignal entity in backend/alembic/versions/
- [x] T050 [P] [US3] Add REJECTED_FINAL status to SummaryStatus enum in backend/src/models/summary.py
- [x] T051 [P] [US3] Create correction signal prompt templates in backend/src/prompts/correction_prompts.py (incorporate reason tags)
- [x] T052 [US3] Implement correction signal handling in backend/src/services/regeneration_service.py (regenerate with correction)
- [x] T053 [US3] Implement POST /summaries/{summary_id}/correction endpoint in backend/src/api/correction_routes.py
- [x] T054 [US3] Add REJECTED_FINAL transition logic in backend/src/services/approval_service.py (after regen_count=3)
- [x] T055 [P] [US3] Create CorrectionSignalForm component in frontend/src/components/CorrectionSignalForm/CorrectionSignalForm.tsx (reason tags, feedback input)
- [x] T056 [US3] Integrate CorrectionSignalForm with ApprovalInterface page (show after 2 rejections)
- [x] T057 [US3] Add correction signal API call to summaryApi.ts in frontend/src/services/summaryApi.ts
- [x] T058 [US3] Add REJECTED_FINAL notification to ApprovalInterface page (show "may resubmit input" message)
- [x] T059 [US3] Add validation for feedback_text max 240 chars in backend/src/api/correction_routes.py
- [x] T060 [US3] Add validation for reason_tag required field in backend/src/api/correction_routes.py
- [x] T061 [US3] Add logging for correction signal and REJECTED_FINAL events in backend/src/services/

**Checkpoint**: ✅ Participants can provide correction signals after 2 rejections, and summaries are marked REJECTED_FINAL if still rejected

---

## Phase 6: User Story 4 - Safety and Profanity Filtering (Priority: P4)

**Goal**: Detect and neutralize profanity, slurs, and illegal threats during summarization. Block disallowed content and notify participants.

**Independent Test**: Submit input with profanity → verify profanity neutralized in summary → submit input with threats → verify status=DISALLOWED_CONTENT and approval blocked

### Implementation for User Story 4

- [x] T062 [P] [US4] Install better-profanity library for profanity detection
- [x] T063 [P] [US4] Add DISALLOWED_CONTENT status to SummaryStatus enum in backend/src/models/summary.py
- [x] T064 [P] [US4] Add safety_flags field to Summary model in backend/src/models/summary.py (ARRAY of strings)
- [x] T065 [P] [US4] Create database migration for safety_flags field in backend/alembic/versions/
- [x] T066 [P] [US4] Implement SafetyFilterService.filter_submission() in backend/src/services/safety_filter_service.py (profanity detection)
- [x] T067 [P] [US4] Implement profanity neutralization logic in backend/src/services/safety_filter_service.py (strip/replace)
- [x] T068 [P] [US4] Implement threat detection logic in backend/src/services/safety_filter_service.py (keywords + OpenAI Moderation API)
- [x] T069 [US4] Integrate safety filtering into SummarizationService.generate_summary() (filter before LLM call)
- [x] T070 [US4] Add disallowed content handling in backend/src/services/summarization_service.py (block approval, set safety_flags)
- [x] T071 [P] [US4] Create SafetyNotice component in frontend/src/components/SafetyNotice/SafetyNotice.tsx (display warnings)
- [x] T072 [US4] Integrate SafetyNotice with ApprovalInterface page (show if safety_flags present)
- [x] T073 [US4] Add disallowed content notification to ApprovalInterface page (show "resubmit appropriate content" message)
- [x] T074 [US4] Add safety_flags to Summary response schema in backend/src/api/summary_routes.py
- [x] T075 [US4] Add logging for safety filtering events in backend/src/services/safety_filter_service.py

**Checkpoint**: ✅ Profanity is neutralized in summaries, and illegal threats prevent approval

---

## Phase 7: User Story 5 - Multiple Submissions with Last-Approved-Wins (Priority: P5) ✅ COMPLETED

**Goal**: Support multiple submissions per participant per round (Spec 1 integration). Ensure exactly one summary (last approved) is forwarded to clustering.

**Independent Test**: Submit 3 times → approve summary from submission #1 → approve summary from submission #2 → verify only submission #2 summary forwarded (latest approved_at)

### Implementation for User Story 5

- [x] T076 [P] [US5] Add SUPERSEDED status to SummaryStatus enum in backend/src/models/summary.py
- [x] T077 [P] [US5] Create database migration for SUPERSEDED status in backend/alembic/versions/
- [x] T078 [US5] Implement last-approved-wins selection logic in backend/src/services/approval_service.py (query by approved_at DESC)
- [x] T079 [US5] Implement SUPERSEDED status transition in backend/src/services/approval_service.py (mark previous approved summaries)
- [x] T080 [US5] Add last-approved-wins logic to approval_complete event handler in backend/src/events/handlers/approval_complete.py
- [x] T081 [US5] Add validation for exactly one summary per participant in event payload in backend/src/events/handlers/approval_complete.py
- [x] T082 [US5] Add approved_at timestamp to Summary response schema in backend/src/api/summary_routes.py
- [x] T083 [US5] Add multiple submissions support to ApprovalInterface page (show list of submissions)
- [x] T084 [US5] Add latest approved indicator to SummaryReview component (highlight last approved)
- [x] T085 [US5] Add logging for last-approved-wins selection in backend/src/services/approval_service.py

**Checkpoint**: ✅ Multiple approved summaries are handled correctly, with only the last approved forwarded to clustering

---

## Phase 8: Additional Features & Integration ✅ COMPLETED

**Purpose**: LLM caching, approval deadline, ephemeral data cleanup

- [x] T086 [P] Implement LLM response caching in backend/src/summarization/services/llm_cache_service.py (Redis, TTL=3600)
- [x] T087 [P] Integrate caching into SummarizationService.generate_summary() (check cache before LLM call)
- [x] T088 [P] Add approval deadline enforcement in backend/src/summarization/services/approval_service.py (check round.approval_deadline)
- [x] T089 [P] Add APPROVAL_TIMEOUT status to SummaryStatus enum (already exists in model)
- [x] T090 [P] Create database migration for APPROVAL_TIMEOUT status (already in enum migration)
- [x] T091 [P] Implement approval deadline timeout handler in backend/src/summarization/events/handlers/approval_deadline.py (mark APPROVAL_TIMEOUT)
- [x] T092 [P] Implement ephemeral data cleanup in backend/src/summarization/services/cleanup_service.py (delete raw submissions 5 min after approval)
- [x] T093 [P] Add retry logic for LLM failures in backend/src/summarization/services/generation_retry.py (fallback to GPT-3.5)
- [x] T094 Add integration tests for Spec 2 → Spec 3 contract in backend/tests/contract/test_spec2_to_spec3.py
- [x] T095 Add integration tests for Spec 3 → Spec 4 contract in backend/tests/contract/test_spec3_to_spec4.py
- [x] T096 Add integration tests for approval workflow in backend/tests/integration/test_approve_workflow.py
- [x] T097 Add integration tests for regeneration workflow in backend/tests/integration/test_regeneration_workflow.py
- [x] T098 Add integration tests for last-approved-wins logic in backend/tests/integration/test_last_approved_wins.py
- [x] T099 Add integration tests for safety filtering in backend/tests/integration/test_safety_filtering.py

---

## Phase 9: Polish & Cross-Cutting Concerns ✅ COMPLETED

**Purpose**: Improvements that affect multiple user stories

- [x] T100 [P] Add comprehensive error handling for all API endpoints (already implemented in summary_routes.py)
- [x] T101 [P] Add rate limiting for LLM calls in backend/src/summarization/services/rate_limiter.py
- [x] T102 [P] Add performance monitoring for summary generation in backend/src/summarization/services/performance_monitor.py (track p95 latency <3s)
- [x] T103 [P] Add analytics for approval rates, rejection rates, correction signal usage in backend/src/summarization/services/analytics_service.py
- [x] T104 [P] Add database indexes for (participant_id, round_id, status) in backend/alembic/versions/012_add_summary_performance_indexes.py
- [x] T105 [P] Add database indexes for (approved_at) in Summary table in backend/alembic/versions/012_add_summary_performance_indexes.py
- [x] T106 [P] Add unit tests for summarization service in backend/tests/unit/test_summarization_service.py
- [x] T107 [P] Add unit tests for approval service in backend/tests/unit/test_approval_service.py
- [x] T108 [P] Add unit tests for safety filters in backend/tests/unit/test_safety_filters.py
- [x] T109 [P] Add frontend integration tests for approval flow in frontend/tests/integration/approval_flow.test.tsx
- [x] T110 [P] Update quickstart.md with example commands and test scenarios
- [x] T111 Code cleanup and refactoring across all services (services are well-structured)
- [x] T112 Security hardening (input validation in Pydantic models, SQLAlchemy ORM prevents SQL injection)
- [x] T113 Documentation updates in specs/003-summarization-approval/ (quickstart.md updated)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4 → P5)
- **Additional Features (Phase 8)**: Can be done in parallel with user stories or after
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Extends US1 (rejection workflow)
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Extends US2 (correction signal)
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Integrates with US1 (safety filtering)
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) - Extends US1 (multiple approvals)

### Within Each User Story

- Models before services
- Services before endpoints
- Backend implementation before frontend integration
- Core implementation before validation/logging
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003, T004, T005, T006)
- All Foundational tasks marked [P] can run in parallel (T009-T014)
- Once Foundational phase completes, multiple user stories can start in parallel:
  - US1 models (T015-T017) can run parallel
  - US1 prompts (T018) parallel with models
  - US1 frontend (T027-T028) parallel with backend services
- Within US2: T034-T037 can run in parallel
- Within US3: T047-T051 can run in parallel
- Within US4: T062-T068 can run in parallel
- Within US5: T076-T077 can run in parallel
- Phase 8 tasks are largely independent (T086-T093 parallel)
- Phase 9 polish tasks (T100-T113) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all models for User Story 1 together:
Task T015: "Create Summary model in backend/src/models/summary.py"
Task T016: "Create SummaryStatus enum in backend/src/models/summary.py"
Task T017: "Create database migration for Summary entity"
Task T018: "Create base summarization prompt template"

# After models complete, launch services:
Task T019: "Implement SummarizationService.generate_summary()"
Task T020: "Implement model selection logic"
Task T021: "Implement ApprovalService.approve_summary()"

# Launch frontend components in parallel with API endpoints:
Task T022: "Implement POST /summaries/generate endpoint"
Task T023: "Implement POST /summaries/{summary_id}/approve endpoint"
Task T024: "Implement GET /summaries/{summary_id} endpoint"
Task T027: "Create SummaryReview component" (parallel)
Task T028: "Create summaryApi.ts client" (parallel)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (T015-T033)
4. **STOP and VALIDATE**: Test User Story 1 independently
   - Submit input → generate summary → approve → verify forwarded to Spec 4
   - Verify summary constraints (1-2 sentences, neutral, max 500 chars)
   - Verify only approved summaries forwarded (Intent Fidelity enforcer)
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP! Core approval gate working)
3. Add User Story 2 → Test independently → Deploy/Demo (Regeneration enabled)
4. Add User Story 3 → Test independently → Deploy/Demo (Correction signals working)
5. Add User Story 4 → Test independently → Deploy/Demo (Safety filtering active)
6. Add User Story 5 → Test independently → Deploy/Demo (Multiple submissions supported)
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (P1) - Core approval gate
   - Developer B: User Story 2 (P2) - Regeneration workflow
   - Developer C: User Story 4 (P4) - Safety filtering (independent)
3. After P1/P2 complete:
   - Developer A: User Story 3 (P3) - Correction signals (extends US2)
   - Developer B: User Story 5 (P5) - Multiple submissions (extends US1)
4. Stories integrate without blocking each other

---

## Task Summary

- **Total Tasks**: 113
- **Phase 1 (Setup)**: 6 tasks
- **Phase 2 (Foundational)**: 8 tasks (BLOCKS all stories)
- **Phase 3 (US1 - MVP)**: 19 tasks
- **Phase 4 (US2)**: 13 tasks
- **Phase 5 (US3)**: 15 tasks
- **Phase 6 (US4)**: 14 tasks
- **Phase 7 (US5)**: 10 tasks
- **Phase 8 (Integration)**: 14 tasks
- **Phase 9 (Polish)**: 14 tasks

**Parallel Tasks**: 44 tasks marked [P] can run in parallel with other tasks in their phase

**MVP Scope**: Phase 1 + Phase 2 + Phase 3 (User Story 1) = 33 tasks for core approval gate

**Success Criteria**:
- Summary generation <3 seconds (p95)
- 80% approval on first attempt (intent fidelity)
- Zero unapproved summaries enter clustering (strict invariant)
- Last-approved-wins 100% accuracy

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- MVP = US1 only (core trust gate validation)
- All user stories extend US1 without breaking existing functionality

---

**Last Updated**: 2026-01-29
**Next Action**: Begin implementation with Phase 1 (Setup)
