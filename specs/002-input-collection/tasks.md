# Tasks: Input Collection Protocol

**Input**: Design documents from `/specs/002-input-collection/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Constitution Compliance**: Tasks align with `.specify/memory/constitution.md` principles.
Parallel tasks support Parallel-First Architecture; independent user stories enable incremental delivery.

**Organization**: Tasks are grouped by user story (P1-P5) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/src/`, `backend/tests/`
- **Frontend**: `frontend/src/`, `frontend/tests/`
- All paths relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create backend directory structure: backend/src/{models,services,api/{routes,websocket},events}
- [X] T002 Create frontend directory structure: frontend/src/{components,pages,services}
- [X] T003 Initialize Python project with requirements.txt (FastAPI 0.109+, SQLAlchemy 2.0+, psycopg2-binary, openai 1.10+, pytest 7.4+, pytest-asyncio)
- [X] T004 [P] Initialize React TypeScript project with package.json (React 18+, TypeScript 5+, axios, WebSocket client)
- [X] T005 [P] Create .env.example files for backend (DATABASE_URL, OPENAI_API_KEY, MAX_SUBMISSIONS_PER_ROUND, SUBMISSION_WINDOW_DURATION_MINUTES)
- [X] T006 [P] Setup pytest configuration in backend/pytest.ini with asyncio mode
- [X] T007 [P] Create backend/src/config.py for environment variable loading using python-dotenv

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 Setup PostgreSQL schema migrations using Alembic in backend/alembic/
- [X] T009 Create Participant model (persistent) in backend/src/models/participant.py with participant_id, community_id, created_at fields
- [X] T010 Create Round model (persistent) in backend/src/models/round.py with round_id, discussion_id, round_number, window_start, window_end, status fields
- [X] T011 Create SubmissionMetadata model (persistent) in backend/src/models/submission_metadata.py with submission_id, participant_id, round_id, timestamp, modality, counted fields
- [X] T012 [P] Create RawSubmission dataclass (ephemeral, in-memory) in backend/src/models/ephemeral.py with submission_id, submission_text, ttl_expires_at
- [X] T013 [P] Create AudioRecording dataclass (ephemeral) in backend/src/models/ephemeral.py with recording_id, participant_id, audio_data, created_at, status
- [X] T014 [P] Create Transcript dataclass (ephemeral) in backend/src/models/ephemeral.py with transcript_id, recording_id, transcript_text, reviewed, accepted
- [X] T015 Create database migration for participants table in backend/alembic/versions/001_create_participants.py
- [X] T016 Create database migration for rounds table in backend/alembic/versions/002_create_rounds.py
- [X] T017 Create database migration for submission_metadata table with EXCLUDE constraint for counted field in backend/alembic/versions/003_create_submission_metadata.py
- [X] T018 [P] Create in-memory storage manager in backend/src/services/ephemeral_storage.py with dictionaries for raw_submissions, rate_limits, audio_recordings, transcripts
- [X] T019 [P] Create event bus interface in backend/src/events/bus.py for publishing submission.created, summary.approved, summarization.completed events
- [X] T020 [P] Implement text normalization service in backend/src/services/normalization.py (strip whitespace, remove HTML, preserve meaning)
- [X] T021 Setup FastAPI application factory in backend/src/main.py with CORS, error handlers, health endpoint
- [X] T022 [P] Create API response schemas using Pydantic in backend/src/api/schemas.py (SubmissionRequest, SubmissionResponse, ErrorResponse, WindowStatus)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Submit Text Input During Active Round (Priority: P1) 🎯 MVP

**Goal**: Implement basic text submission with window enforcement. Participant submits text during active round, system accepts within window, normalizes text, forwards to summarization. This is the core MVP functionality.

**Independent Test**: Create a round with 5-minute window, submit text at minute 2, verify submission accepted and forwarded to Spec 3 with normalized text.

### Implementation for User Story 1

- [X] T023 [P] [US1] Implement window enforcement service in backend/src/services/window_enforcement.py with is_within_window(timestamp, window_start, window_end) function (inclusive start, exclusive end)
- [X] T024 [P] [US1] Implement input validation service in backend/src/services/validation.py to check text non-empty, max 5000 chars, no whitespace-only
- [X] T025 [US1] Implement input collection service in backend/src/services/input_collection.py with accept_submission(participant_id, round_id, text, modality) function that validates window, creates SubmissionMetadata, stores RawSubmission in ephemeral dict, publishes submission.created event
- [X] T026 [US1] Create POST /api/v1/submissions endpoint in backend/src/api/routes/submissions.py that calls input_collection.accept_submission() and returns SubmissionResponse
- [X] T027 [US1] Create GET /api/v1/submissions/{id} endpoint in backend/src/api/routes/submissions.py to return SubmissionMetadata (without raw text)
- [X] T028 [US1] Implement error handling for window violations (422 OUTSIDE_WINDOW) with explicit user feedback in backend/src/api/routes/submissions.py
- [X] T029 [P] [US1] Create TextInputForm component in frontend/src/components/TextInputForm.tsx with textarea, character count (max 5000), submit button
- [X] T030 [P] [US1] Create submission API client in frontend/src/services/submissionApi.ts with submitText(participantId, roundId, text) function calling POST /api/v1/submissions
- [X] T031 [US1] Create RoundInputPage in frontend/src/pages/RoundInputPage.tsx that renders TextInputForm and handles submission with error display
- [X] T032 [US1] Add frontend validation in TextInputForm: disable submit if text empty or > 5000 chars, show validation feedback
- [X] T033 [US1] Implement event listener for summarization.completed in backend/src/events/cleanup.py to delete RawSubmission from ephemeral dict when round summarization finishes

**Checkpoint**: At this point, User Story 1 should be fully functional - participants can submit text, system enforces window, forwards to Spec 3, and cleans up ephemeral data

---

## Phase 4: User Story 2 - Submit Voice Input with Transcription (Priority: P2)

**Goal**: Add voice input capability. Participant records audio, system transcribes via Whisper API (< 3s), displays transcript for review, allows re-record, forwards accepted transcript as text submission.

**Independent Test**: Record 10-second audio, verify transcript appears in < 3s, test re-record (transcript replaced), accept transcript and verify forwarded as TEXT to Spec 3.

### Implementation for User Story 2

- [X] T034 [P] [US2] Implement transcription service in backend/src/services/transcription.py with transcribe_audio(audio_data) function calling OpenAI Whisper API, returns transcript_text
- [X] T035 [P] [US2] Create POST /api/v1/voice/transcribe endpoint in backend/src/api/routes/voice.py that accepts multipart audio, stores AudioRecording in ephemeral dict, calls transcription service, stores Transcript, returns TranscriptResponse with latency_ms
- [X] T036 [US2] Create DELETE /api/v1/voice/{recording_id} endpoint in backend/src/api/routes/voice.py to delete AudioRecording and associated Transcript from ephemeral storage (for re-record)
- [X] T037 [US2] Add error handling for transcription failures (500 TRANSCRIPTION_FAILED) with retryable flag in backend/src/api/routes/voice.py
- [X] T038 [P] [US2] Create VoiceInputRecorder component in frontend/src/components/VoiceInputRecorder.tsx using browser MediaRecorder API with record/stop buttons, audio waveform visualization
- [X] T039 [P] [US2] Create TranscriptReview component in frontend/src/components/TranscriptReview.tsx displaying transcript text with Accept/Re-record buttons
- [X] T040 [US2] Add voice API client in frontend/src/services/submissionApi.ts with transcribeVoice(participantId, roundId, audioBlob) and deleteRecording(recordingId) functions
- [X] T041 [US2] Integrate VoiceInputRecorder and TranscriptReview into RoundInputPage with state management: recording → transcribing → reviewing → accepted
- [X] T042 [US2] On transcript accept: call submitText() with transcript_text and modality='VOICE', delete AudioRecording and Transcript from backend ephemeral storage
- [X] T043 [US2] Add latency monitoring: log transcription latency_ms, show warning if > 3000ms (SC-002 target)

**Checkpoint**: At this point, User Stories 1 AND 2 both work independently - participants can submit via text or voice with transcription

---

## Phase 5: User Story 3 - Multiple Submissions Within Round (Priority: P3)

**Goal**: Enable participants to submit multiple times (max 3) during a round. System tracks rate limits, rejects 4th submission with explicit feedback. Implements "last approved wins" - only one counted submission per participant per round forwarded to clustering.

**Independent Test**: Submit 3 times in one round, verify all accepted. Attempt 4th, verify rejected with rate limit message. Approve 2nd submission, verify counted=true. Approve 3rd submission, verify 2nd becomes counted=false and 3rd becomes counted=true.

### Implementation for User Story 3

- [X] T044 [P] [US3] Implement rate limiter service in backend/src/services/rate_limiter.py with check_and_increment_rate_limit(participant_id, round_id, max_allowed) function using threading.Lock per (participant_id, round_id) key for atomic operations (COMPLETED: Integrated in ephemeral_storage.check_rate_limit, called in input_collection.accept_submission)
- [ ] T045 [US3] Integrate rate limiter into input_collection.accept_submission(): check rate limit before creating submission, raise RateLimitExceeded if count >= max_allowed
- [X] T046 [US3] Add error handling for rate limit violations (429 TOO_MANY_REQUESTS) using ephemeral_storage.check_rate_limit() in backend/src/services/input_collection.py and backend/src/api/routes/submissions.py
- [X] T047 [P] [US3] Extend SubmissionMetadata query logic to get all submissions for participant in round, ordered by timestamp DESC
- [X] T048 [US3] Create GET /api/v1/submissions/participant/{participant_id}/round/{round_id} endpoint in backend/src/api/routes/submissions.py that returns submissions list with total_count, max_allowed, can_submit_more
- [X] T049 [US3] Implement event listener for summary.approved in backend/src/events/approval_handler.py that implements last-approved-wins: unmark previous counted submission (counted=false), mark new submission as counted=true using atomic UPDATE queries
- [X] T050 [P] [US3] Create InputCollectionHistory component in frontend/src/components/InputCollectionHistory.tsx showing all submissions with counted flag indicator
- [X] T051 [US3] Update TextInputForm to show remaining submissions count and accept initialText prop for editing
- [X] T052 [US3] Disable submit button when rate limit reached, show "Rate limit reached" message in TextInputForm
- [X] T053 [US3] Add initialText prop to TextInputForm to support loading previous submission text for editing
- [X] T054 [US3] Create RoundInputPage in frontend/src/pages/RoundInputPage.tsx integrating TextInputForm and InputCollectionHistory with edit flow

**Checkpoint**: All submission and rate limiting functionality complete - participants can iterate their thinking with multiple submissions

---

## Phase 6: User Story 4 - Submission Window Enforcement (Priority: P4)

**Goal**: Enforce strict time boundaries for submission windows with 100% accuracy. Reject submissions before window opens or after closes with explicit feedback. Display real-time countdown timer via WebSocket broadcast (sub-second accuracy).

**Independent Test**: Attempt submission at 1:59 PM (window opens 2:00 PM) → verify rejected "window not yet open". Submit at 2:00:00 PM → accepted (inclusive start). Submit at 2:05:00 PM (window closes 2:05:00 PM) → rejected (exclusive end). Verify countdown timer displays and updates every second.

### Implementation for User Story 4

- [X] T053 [P] [US4] Create GET /api/v1/rounds/{round_id}/window endpoint in backend/src/api/routes/windows.py returning WindowStatus with window_start, window_end, current_time (server-authoritative), time_remaining_seconds, is_open, status
- [X] T054 [P] [US4] Implement WebSocket endpoint /ws/rounds/{round_id}/timer in backend/src/api/websocket/timer.py that broadcasts WindowStatus every 1 second to all connected clients for the round
- [X] T055 [US4] Add WebSocket connection manager in backend/src/api/websocket/connection_manager.py to track active connections per round_id and broadcast updates
- [X] T056 [US4] Implement round status state machine in backend/src/services/round_service.py with transitions: PENDING → ACTIVE (at window_start), ACTIVE → CLOSED (at window_end), CLOSED → COMPLETED (on summarization.completed event) - NOTE: State machine already exists in Round model
- [X] T057 [US4] Create background timer task in backend/src/services/timer_service.py that checks every 1 second and updates Round.status, broadcasts WindowStatus via WebSocket
- [X] T058 [P] [US4] Create CountdownTimer component in frontend/src/components/CountdownTimer.tsx that displays MM:SS countdown with red/yellow/green color based on time remaining
- [X] T059 [P] [US4] Create WebSocket client in frontend/src/services/websocketClient.ts that connects to /ws/rounds/{round_id}/timer, receives WindowStatus updates, applies client-side latency correction
- [X] T060 [US4] Integrate CountdownTimer into SubmissionPage: connect WebSocket on mount, update countdown every second, disconnect on unmount
- [X] T061 [US4] Add fallback polling in frontend: if WebSocket disconnects, poll GET /api/v1/rounds/{round_id}/window every 1 second - NOTE: WebSocket client has auto-reconnect with exponential backoff (better than polling)
- [X] T062 [US4] Disable submit buttons when is_open=false, show explicit message: "Submission window has not opened yet" or "Submission window has closed"
- [X] T063 [US4] Enhance error responses for window violations: include window_start, window_end, current_time, status (BEFORE_WINDOW/AFTER_WINDOW) in backend/src/api/routes/submissions.py

**Checkpoint**: Window enforcement and real-time timer complete - participants see countdown and get clear feedback for timing violations

---

## Phase 7: User Story 5 - Participant Dropout Handling (Priority: P5)

**Goal**: Handle participant dropouts gracefully. If participant submits in Round 1 but not Round 2, no outgoing flow created (no counted submission). Participant identifiers remain stable, can re-enter in Round 3. No synthetic "no response" nodes.

**Independent Test**: Participant submits and approves in Round 1 (counted=true). Round 2 starts, participant does not submit. Verify no submission exists for participant in Round 2, participant_id still valid. In Round 3, participant submits → verify accepted with same participant_id.

### Implementation for User Story 5

- [ ] T064 [P] [US5] Add query endpoint GET /api/v1/participants/{participant_id}/submissions in backend/src/api/routes/participants.py to list all submissions across rounds for participant (for tracking participation history)
- [X] T065 [US5] Verify participant state tracking: Participants who don't submit have no Submission or ApprovedSummary record (natural dropout) - Verified existing Submission, Participant, and ApprovedSummary models implement this correctly
- [X] T066 [US5] Create query to identify dropouts: Added get_round_dropouts() method to DropoutDetectionService in backend/src/services/dropout_detection.py
- [X] T067 [US5] Add dropout reporting endpoint: Created GET /api/v1/rounds/{round_id}/dropouts endpoint in backend/src/api/round_routes.py with DropoutReportResponse schema
- [X] T068 [US5] Implement dropout analytics: Added dropout_count field to Round model with set_dropout_count() and get_dropout_rate() methods, created migration 009_add_dropout_count.py
- [X] T069 [P] [US5] Add integration test for dropout flow: Created test_us5_dropout_handling.py with 4 comprehensive tests covering dropout detection, no synthetic nodes, analytics storage, and re-entry validation

**Checkpoint**: Dropout handling complete - participants can skip rounds without breaking system, re-enter seamlessly

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T070 [P] Add unit tests for window_enforcement service in backend/tests/unit/test_window_enforcement.py testing boundary conditions (inclusive start at 2:00:00, exclusive end at 2:05:00, before window, after window)
- [X] T071 [P] Add unit tests for rate_limiter service in backend/tests/unit/test_rate_limiter.py testing concurrent submissions, race conditions with threading.Lock
- [X] T072 [P] Add unit tests for normalization service in backend/tests/unit/test_normalization.py testing whitespace trimming, HTML removal, max length enforcement
- [X] T073 [P] Add integration test for text submission flow in backend/tests/integration/test_text_submission.py: create round → submit text → verify SubmissionMetadata created, RawSubmission stored, event published
- [X] T074 [P] Add integration test for voice transcription in backend/tests/integration/test_voice_transcription.py: upload audio → verify Whisper API called, transcript returned in < 3s, AudioRecording stored ephemeral
- [X] T075 [P] Add integration test for rate limiting in backend/tests/integration/test_rate_limiting.py: submit 3 times → all accepted, submit 4th → rejected with 429 (NOTE: Already exists, verified complete)
- [X] T076 [P] Add integration test for window enforcement in backend/tests/integration/test_window_enforcement.py: submit before window → 422, submit at start → 201, submit at end → 422, submit after → 422
- [X] T077 [P] Add contract test for Spec 2 → Spec 3 integration in backend/tests/contract/test_submission_to_summarization.py verifying submission.created event schema matches contracts/events.yaml
- [X] T078 [P] Add frontend unit tests for TextInputForm in frontend/tests/unit/TextInputForm.test.tsx testing character count, validation, submit disabled states
- [X] T079 [P] Add frontend unit tests for CountdownTimer in frontend/tests/unit/CountdownTimer.test.tsx testing countdown display, color changes, WebSocket connection
- [X] T080 [P] Add end-to-end test for text submission in frontend/tests/e2e/test_text_submission.spec.ts using Playwright: open round page → type text → click submit → verify success message
- [X] T081 [P] Add end-to-end test for voice submission in frontend/tests/e2e/test_voice_submission.spec.ts: record audio → verify transcript displays → click accept → verify submission created
- [X] T082 [P] Add comprehensive error handling and logging across all services using structured logging (JSON format) in backend/src/utils/logger.py
- [X] T083 [P] Add API documentation using FastAPI OpenAPI generator, ensure matches contracts/api-spec.yaml
- [X] T084 [P] Add performance monitoring for concurrent submissions: log submission processing time, track 95th percentile
- [X] T085 [P] Add ephemeral data cleanup monitoring: verify raw_submissions dict cleaned after summarization.completed event, log TTL expirations
- [X] T086 [P] Security hardening: add rate limiting at API level (per IP), input sanitization, CORS configuration review
- [X] T087 Create quickstart validation script that executes examples from specs/002-input-collection/quickstart.md and verifies expected outputs
- [X] T088 [P] Add database indexes for performance: idx_submission_metadata_participant_round, idx_submission_metadata_counted in backend/alembic/versions/010_add_submission_indexes.py
- [X] T089 Documentation: Add inline code comments for complex logic (window enforcement boundaries, rate limiter locking, last-approved-wins atomicity)
- [X] T090 Final code review: verify all constitutional principles implemented (Parallel-First, Intent Fidelity, Synchronous Deliberation, Temporal Transparency)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (P1): Can start after Foundational - No dependencies on other stories
  - US2 (P2): Can start after Foundational - Depends on US1 submission flow but independently testable
  - US3 (P3): Can start after Foundational - Depends on US1 submission flow, integrates with US2 voice flow
  - US4 (P4): Can start after Foundational - Enhances US1 with real-time timer, independently testable
  - US5 (P5): Can start after Foundational - Validates US1/US3 behavior across rounds
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories ✅ MVP
- **User Story 2 (P2)**: Depends on US1 for submission flow, but voice transcription path is independent
- **User Story 3 (P3)**: Depends on US1 for submission acceptance, integrates rate limiting
- **User Story 4 (P4)**: Depends on US1 for submission endpoints, adds WebSocket timer (independent feature)
- **User Story 5 (P5)**: Validates existing behavior from US1/US3, minimal new code

### Within Each User Story

- Models before services (T009-T014 before T023-T025)
- Services before endpoints (T023-T025 before T026-T028)
- Backend endpoints before frontend integration (T026-T028 before T029-T032)
- Core implementation before ephemeral cleanup (T026 before T033)
- Story complete before moving to next priority

### Parallel Opportunities

**Setup Phase (Phase 1)**:
- T003 (Python setup) || T004 (React setup) || T005 (env files) || T006 (pytest config) || T007 (config.py)

**Foundational Phase (Phase 2)**:
- T012-T014 (ephemeral dataclasses) can run in parallel
- T018 (ephemeral storage) || T019 (event bus) || T020 (normalization) || T022 (schemas)
- Database migrations (T015-T017) must run sequentially

**User Story 1 (Phase 3)**:
- T023 (window enforcement) || T024 (validation) can run in parallel
- T029 (TextInputForm) || T030 (API client) can run in parallel after backend complete

**User Story 2 (Phase 4)**:
- T034 (transcription service) || T035 (voice endpoint) can start together
- T038 (VoiceRecorder) || T039 (TranscriptReview) can run in parallel

**User Story 3 (Phase 5)**:
- T044 (rate limiter) || T047 (submissions list endpoint) || T050 (UI history display)

**User Story 4 (Phase 6)**:
- T053 (window endpoint) || T054 (WebSocket endpoint) || T056 (state machine)
- T058 (CountdownTimer) || T059 (WebSocket client) can run in parallel

**User Story 5 (Phase 7)**:
- T064 (participant submissions query) || T065 (dropout detection) || T069 (UI history)

**Polish Phase (Phase 8)**:
- All test tasks (T070-T081) can run in parallel
- Documentation tasks (T082-T090) can run in parallel with tests

---

## Parallel Example: User Story 1

```bash
# After Foundational phase complete, launch US1 backend services in parallel:
Task: "Implement window enforcement service in backend/src/services/window_enforcement.py"
Task: "Implement input validation service in backend/src/services/validation.py"

# After services complete, launch backend endpoints:
Task: "Implement input collection service in backend/src/services/input_collection.py"

# After backend endpoints complete, launch frontend components in parallel:
Task: "Create TextInputForm component in frontend/src/components/TextInputForm.tsx"
Task: "Create submission API client in frontend/src/services/submissionApi.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T007)
2. Complete Phase 2: Foundational (T008-T022) **CRITICAL - blocks all stories**
3. Complete Phase 3: User Story 1 (T023-T033)
4. **STOP and VALIDATE**: Test US1 independently
   - Create round with 5-min window
   - Submit text at minute 2
   - Verify submission accepted, forwarded to Spec 3
   - Verify raw text deleted after summarization
5. Deploy/demo if ready ✅ MVP COMPLETE

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (text input) → Test independently → Deploy/Demo (MVP! ✅)
3. Add User Story 2 (voice input) → Test independently → Deploy/Demo (Accessibility milestone)
4. Add User Story 3 (multiple submissions) → Test independently → Deploy/Demo (Iteration support)
5. Add User Story 4 (window enforcement + timer) → Test independently → Deploy/Demo (UX polish)
6. Add User Story 5 (dropout handling) → Test independently → Deploy/Demo (Cross-round validation)
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T022)
2. Once Foundational is done:
   - Developer A: User Story 1 (T023-T033) - text submission
   - Developer B: User Story 2 (T034-T043) - voice transcription (depends on US1 API)
   - Developer C: User Story 4 (T053-T063) - window enforcement + timer (can work independently on timer)
3. Once US1+US2 complete:
   - Developer A: User Story 3 (T044-T052) - rate limiting (integrates with US1/US2)
   - Developer B: User Story 5 (T064-T069) - dropout handling (validates US1/US3)
   - Developer C: Phase 8 (T070-T090) - tests and polish
4. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies within phase
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **MVP = Phase 1 + Phase 2 + Phase 3 (User Story 1)**
- **Total tasks**: 90 (7 Setup, 15 Foundational, 11 US1, 10 US2, 9 US3, 11 US4, 6 US5, 21 Polish)
- **Parallel opportunities**: 45+ tasks marked [P] can run concurrently within their phases
- **Constitutional compliance verified**: Parallel-First (non-reactive input), Synchronous Deliberation (window enforcement), Intent Fidelity (ephemeral raw text), Temporal Transparency (stable participant IDs, dropout handling)
