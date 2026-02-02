# Tasks: Semantic Clustering & Hybrid Alignment Protocol

**Input**: Design documents from `/specs/004-clustering-alignment/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Constitution Compliance**: Tasks MUST align with `.specify/memory/constitution.md` principles.
Parallel tasks support Parallel-First Architecture; independent user stories enable incremental delivery.

**Tests**: Tests are NOT explicitly requested in spec.md, so test tasks are MINIMAL (contract validation only for critical paths).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Per plan.md, this is a backend-only service with structure:
- `backend/src/` for source code
- `backend/tests/` for tests

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create backend project structure per plan.md with backend/src/{models,services,api,ml} directories
- [x] T002 Initialize Python 3.11+ project with requirements.txt including sentence-transformers==2.2+, hdbscan==0.8.33, numpy==1.24+, scipy==1.10+, scikit-learn==1.3+, psycopg2-binary, asyncpg, fastapi, uvicorn
- [x] T003 [P] Configure pytest 7.4+ with pytest.ini and test directory structure
- [x] T004 [P] Setup PostgreSQL 15+ with pgvector extension enabled (CREATE EXTENSION vector)
- [x] T005 [P] Configure environment variables in .env for DATABASE_URL, EMBEDDING_MODEL_VERSION, ALIGN_THRESHOLD, REDIS_URL

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create database schema for embeddings table with pgvector in backend/alembic/versions/013_create_spec004_clustering_tables.py (summary_id UUID PRIMARY KEY, embedding_vector vector(384), model_version VARCHAR, created_at TIMESTAMP)
- [x] T007 [P] Create database schema for clusters table in backend/alembic/versions/013_create_spec004_clustering_tables.py (cluster_id UUID, round_id UUID, user_count INT, user_pct FLOAT, label_summary_id UUID, centroid_vector vector(384), created_at TIMESTAMP)
- [x] T008 [P] Create database schema for cluster_members table in backend/alembic/versions/013_create_spec004_clustering_tables.py (membership_id UUID, cluster_id UUID, summary_id UUID, user_id UUID)
- [x] T009 [P] Create database schema for alignment_maps table in backend/alembic/versions/013_create_spec004_clustering_tables.py (alignment_id UUID, round_r INT, round_r1 INT, cluster_r_id UUID, cluster_r1_id UUID, similarity_score FLOAT, display_group_id UUID, created_at TIMESTAMP)
- [x] T010 Run database migrations to create all tables with pgvector support
- [x] T011 [P] Create Embedding entity model in backend/src/models/embedding.py with fields (summary_id, embedding_vector, model_version) and save/load methods
- [x] T012 [P] Create Cluster entity model in backend/src/models/cluster.py with fields (cluster_id, round_id, user_count, user_pct, label_summary_id, centroid_vector, display_group_id) and validation for user_pct sum constraint
- [x] T013 [P] Create ClusterMember entity model in backend/src/models/cluster_member.py with fields (membership_id, cluster_id, summary_id, user_id)
- [x] T014 [P] Create AlignmentMap entity model in backend/src/models/alignment.py with fields (alignment_id, round_r, round_r1, cluster_r_id, cluster_r1_id, similarity_score, display_group_id, alignment_type)
- [x] T015 [P] Setup Redis client for event pub/sub in backend/src/services/event_service.py with publish and subscribe methods
- [x] T016 [P] Implement event subscriber for summaries.approved_for_round event from Spec 3 in backend/src/services/event_service.py with onSummariesApprovedForRound handler
- [x] T017 [P] Setup FastAPI app structure in backend/src/main.py with routers, middleware, and error handlers
- [x] T018 [P] Configure CORS, logging, and error handling middleware in backend/src/main.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Cluster Approved Summaries into Thought Spaces (Priority: P1) 🎯 MVP

**Goal**: Cluster semantically similar approved summaries into thought spaces with deterministic embedding and density-based clustering

**Independent Test**: Provide 10 approved summaries with clear thematic groups (3 about cost, 4 about speed, 3 about fairness), run clustering, verify distinct thought spaces are created with correct member assignments and percentages summing to 1.0

### Implementation for User Story 1

- [x] T019 [P] [US1] Load SBERT all-MiniLM-L6-v2 model in backend/src/ml/embedding_models.py with deterministic seed and model versioning
- [x] T020 [P] [US1] Implement generate_embeddings function in backend/src/services/embedding_service.py to generate 384-dim embeddings from summary_text with determinism guarantee (FR-007)
- [x] T021 [P] [US1] Implement persist_embeddings function in backend/src/services/embedding_service.py to save embeddings to database with model_version tracking
- [x] T022 [P] [US1] Configure HDBSCAN in backend/src/ml/clustering_algorithms.py with min_cluster_size=2, allow_single_cluster=True, cluster_selection_method='eom', no fixed K (FR-009, FR-012)
- [x] T023 [US1] Implement cluster_embeddings function in backend/src/services/clustering_service.py to run HDBSCAN on embedding vectors and return cluster labels
- [x] T024 [US1] Implement convert_outliers_to_singletons function in backend/src/services/outlier_handler.py to identify noise points (label=-1) and assign unique cluster IDs (FR-014, FR-015)
- [x] T025 [US1] Implement compute_centroids function in backend/src/services/centroid_service.py to calculate mean embedding vector for each cluster (FR-026, FR-027)
- [x] T026 [US1] Implement persist_centroids function in backend/src/services/centroid_service.py to save centroid vectors to clusters table
- [x] T027 [US1] Implement calculate_cluster_stats function in backend/src/services/clustering_service.py to compute user_count and user_pct for each cluster with sum validation (FR-019, SC-005)
- [x] T028 [US1] Implement persist_clusters function in backend/src/services/clustering_service.py to save Cluster entities with all members to database
- [x] T029 [US1] Implement POST /api/v1/clusters/trigger endpoint in backend/src/api/routes/clustering.py to trigger clustering workflow (fetch approved summaries from Spec 3, generate embeddings, run HDBSCAN, handle outliers, compute centroids, persist clusters)
- [x] T030 [US1] Add input validation in POST /api/v1/clusters/trigger to enforce approved summaries only (FR-001, FR-003) and reject if no approved summaries exist (400 error)
- [x] T031 [US1] Add idempotency check in POST /api/v1/clusters/trigger to return 409 error if clustering already exists for round_id unless force_recluster=true
- [x] T032 [US1] Implement GET /api/v1/clusters endpoint in backend/src/api/routes/clustering.py to fetch thought spaces for a round_id with cluster details (cluster_id, user_count, user_pct, label_summary, centroid_vector, display_group_id)
- [x] T033 [US1] Implement GET /api/v1/clusters/{cluster_id} endpoint in backend/src/api/routes/clustering.py to fetch specific thought space details including all members (summary_id, user_id, summary_text)
- [x] T034 [US1] Implement clustering.completed event publisher in backend/src/services/event_service.py to publish event with payload (round_id, cluster_count, total_participants, singleton_count, processing_time_ms) to Redis channel opendiscuss.clustering.completed
- [x] T035 [US1] Add logging for clustering workflow in backend/src/services/clustering_service.py with timestamps for each step (embedding, clustering, outlier handling, centroid computation, persistence)
- [x] T036 [US1] Add error handling for embedding service failures in backend/src/services/embedding_service.py with descriptive error messages
- [x] T037 [US1] Contract validation test in backend/tests/contract/test_clustering_api.py to verify GET /api/v1/clusters returns ClusterList schema per api-spec.yaml (cluster_id, user_count, user_pct, label_summary, centroid_vector, percentage_sum=1.0)

**Checkpoint**: At this point, User Story 1 should be fully functional - clustering runs, thought spaces are created, all participants are assigned, percentages sum to 1.0

---

## Phase 4: User Story 2 - Preserve Minority Clusters Without Forced Merging (Priority: P2)

**Goal**: Preserve low-frequency clusters (1-2 participants) without forced merging, enforcing "semantic accuracy over aesthetics" constitutional principle

**Independent Test**: Cluster 20 summaries where 18 support one position and 2 express a distinct minority view, verify 2 separate thought spaces are created (no forced merging)

### Implementation for User Story 2

- [ ] T038 [P] [US2] Add min_cluster_size validation in backend/src/ml/clustering_algorithms.py to verify HDBSCAN is configured with min_cluster_size=2 (not higher) to allow minority clusters (FR-012)
- [ ] T039 [P] [US2] Add cluster count validation in backend/src/services/clustering_service.py to ensure variable cluster count (not fixed K) and log cluster distribution (FR-009)
- [ ] T040 [US2] Implement validate_no_forced_merging in backend/src/services/clustering_service.py to check that no semantically distinct clusters (cosine similarity < 0.7) are merged post-clustering (FR-013)
- [ ] T041 [US2] Add minority_cluster_count metric to clustering.completed event payload in backend/src/services/event_service.py to track preservation of low-frequency clusters
- [ ] T042 [US2] Integration test in backend/tests/integration/test_minority_preservation.py to cluster 18 majority + 2 minority summaries and assert 2 distinct thought spaces are created

**Checkpoint**: At this point, minority clusters are guaranteed to be preserved - no forced merging occurs

---

## Phase 5: User Story 3 - Handle Outliers as Singleton Clusters (Priority: P3)

**Goal**: Convert noise points identified by HDBSCAN into singleton clusters to ensure 100% participant coverage

**Independent Test**: Provide 10 summaries where 8 form a tight cluster and 2 are outliers, verify 3 thought spaces are created (1 main + 2 singletons) with 100% participant coverage

### Implementation for User Story 3

- [x] T043 [P] [US3] Implement identify_outliers function in backend/src/services/outlier_handler.py to detect HDBSCAN noise points (cluster_label == -1)
- [x] T044 [US3] Implement assign_singleton_cluster_ids function in backend/src/services/outlier_handler.py to generate unique cluster_id for each noise point and update cluster assignment
- [x] T045 [US3] Add 100% coverage validation in backend/src/services/clustering_service.py to verify every summary_id has a cluster assignment before persistence (FR-016, SC-003)
- [x] T046 [US3] Update calculate_cluster_stats in backend/src/services/clustering_service.py to include singleton clusters in user_pct calculation
- [x] T047 [US3] Add singleton_count to clustering.completed event payload in backend/src/services/event_service.py
- [x] T048 [US3] Integration test in backend/tests/integration/test_outlier_handling.py to cluster 8 tight + 2 outlier summaries and assert 3 thought spaces created with all 10 participants assigned

**Checkpoint**: At this point, outliers are guaranteed to become singleton clusters - 100% participant coverage is enforced

---

## Phase 6: User Story 4 - Cross-Round Alignment for Visual Continuity (Priority: P4)

**Goal**: Align semantically similar thought spaces across adjacent rounds using centroid similarity, assign display group IDs for visual continuity without changing cluster membership

**Independent Test**: Cluster two rounds with semantically similar thought spaces, run alignment, verify display group IDs are assigned without changing cluster membership or flow calculations

### Implementation for User Story 4

- [x] T049 [P] [US4] Implement load_centroids function in backend/src/services/centroid_service.py to fetch centroid vectors for rounds r and r+1 from database
- [x] T050 [P] [US4] Implement compute_similarity_matrix function in backend/src/services/alignment_service.py to calculate cosine similarity between all centroid pairs (round_r × round_r+1) using scipy.spatial.distance.cosine
- [x] T051 [US4] Implement greedy_matching function in backend/src/services/alignment_service.py to find best-match alignment using greedy algorithm (FR-034) with ALIGN_THRESHOLD (default 0.7) filter (FR-032, FR-033)
- [x] T052 [US4] Implement assign_display_groups function in backend/src/services/alignment_service.py to assign display_group_id for aligned cluster pairs (1-to-1, 1-to-many, many-to-1) based on similarity matches
- [x] T053 [US4] Implement persist_alignment function in backend/src/services/alignment_service.py to save AlignmentMap entities with alignment_id, similarity_score, display_group_id, alignment_type
- [x] T054 [US4] Implement update_cluster_display_groups function in backend/src/services/alignment_service.py to update display_group_id field in clusters table without modifying cluster membership or user assignments (FR-037, FR-038)
- [x] T055 [US4] Implement POST /api/v1/alignments/trigger endpoint in backend/src/api/routes/alignment.py to trigger cross-round alignment workflow (load centroids, compute similarity, greedy matching, assign display groups, persist alignment)
- [x] T056 [US4] Add validation in POST /api/v1/alignments/trigger to enforce adjacent rounds (round_r1 == round_r + 1) and return 400 error for non-adjacent rounds
- [x] T057 [US4] Add validation in POST /api/v1/alignments/trigger to verify both rounds are already clustered before alignment, return 400 error if rounds not clustered
- [x] T058 [US4] Implement GET /api/v1/alignments endpoint in backend/src/api/routes/alignment.py to fetch alignment maps for a discussion_id with optional round_r filter
- [x] T059 [US4] Implement alignment.completed event publisher in backend/src/services/event_service.py to publish event with payload (discussion_id, round_r, round_r1, match_count, similarity_threshold, processing_time_ms, display_group_count) to Redis channel opendiscuss.alignment.completed
- [x] T060 [US4] Add alignment_invariance validation in backend/src/services/alignment_service.py to verify cluster membership counts remain unchanged after alignment (FR-037, SC-009)
- [x] T061 [US4] Integration test in backend/tests/integration/test_alignment_accuracy.py to cluster two rounds, run alignment, and assert display_group_id assigned without changing cluster membership

**Checkpoint**: At this point, cross-round alignment is functional - display groups are assigned for visual continuity, cluster membership remains unchanged

---

## Phase 7: User Story 5 - Generate Deterministic Cluster Labels Using Medoid (Priority: P5)

**Goal**: Generate thought space labels using medoid method (summary closest to centroid) with deterministic tie-breaking, ensuring labels use actual participant language

**Independent Test**: Cluster summaries, compute centroids, verify the label is the actual member summary closest to the centroid with deterministic results across multiple runs

### Implementation for User Story 5

- [x] T062 [P] [US5] Implement compute_medoid function in backend/src/services/medoid_labeling.py to find the member summary with smallest cosine distance to cluster centroid (FR-022, FR-023)
- [x] T063 [US5] Implement deterministic_tiebreaker function in backend/src/services/medoid_labeling.py to use lexicographic order of summary_id when multiple summaries are equidistant from centroid (FR-044)
- [x] T064 [US5] Implement assign_medoid_labels function in backend/src/services/medoid_labeling.py to set label_summary_id for each cluster to the medoid summary_id (FR-024)
- [x] T065 [US5] Add medoid labeling step to clustering workflow in backend/src/api/routes/clustering.py (execute_full_clustering_workflow) after centroid computation and before persistence
- [x] T066 [US5] Add label_summary field to GET /api/v1/clusters response in backend/src/api/routes/clustering.py to return actual medoid summary text (FR-024)
- [x] T067 [US5] Unit test in backend/tests/unit/test_medoid_selection.py to verify determinism - run medoid selection 10 times with same input, assert same label_summary_id every time (SC-006)

**Checkpoint**: At this point, medoid-based labeling is functional - labels use actual participant language, deterministic across runs

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T068 [P] Add embedding determinism test in backend/tests/unit/test_embedding_determinism.py to generate embeddings 10 times with same text, assert identical vectors (SC-007)
- [ ] T069 [P] Add centroid computation test in backend/tests/unit/test_centroid_computation.py to verify mean calculation accuracy
- [ ] T070 [P] Add alignment matching test in backend/tests/unit/test_alignment_matching.py to verify greedy algorithm correctness with known similarity matrices
- [ ] T071 [P] Add clustering flow integration test in backend/tests/integration/test_clustering_flow.py to test end-to-end workflow from approved summaries to persisted clusters
- [ ] T072 [P] Add performance test in backend/tests/performance/test_clustering_performance.py to verify clustering completes in < 5s for 100 participants (SC-001)
- [ ] T073 [P] Add contract validation for events in backend/tests/contract/test_events_schema.py to verify clustering.completed and alignment.completed events match events.yaml schema
- [ ] T074 [P] Document API endpoints in backend/docs/api_documentation.md with curl examples from quickstart.md
- [ ] T075 [P] Document integration with Spec 3 in backend/docs/integration_spec3.md (receiving summaries.approved_for_round event)
- [ ] T076 [P] Document integration with Spec 5 in backend/docs/integration_spec5.md (publishing clustering.completed and alignment.completed events)
- [ ] T077 Run quickstart.md validation scenarios (Scenario 1: basic clustering, Scenario 2: minority preservation, Scenario 3: cross-round alignment)
- [ ] T078 [P] Add monitoring and observability logging for clustering latency, cluster distribution, singleton count, alignment match rate
- [ ] T079 [P] Add configuration management for ALIGN_THRESHOLD, HDBSCAN parameters (min_cluster_size, cluster_selection_method) in backend/src/config.py
- [ ] T080 [P] Security review for API authentication using bearerAuth (JWT) per api-spec.yaml securitySchemes
- [ ] T081 Code cleanup and refactoring - remove unused imports, add type hints, improve variable naming
- [ ] T082 Final validation: Run all tests, verify all success criteria (SC-001 through SC-013) are met

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User Story 1 (P1): Can start after Foundational - No dependencies on other stories
  - User Story 2 (P2): Can start after Foundational - Integrates with US1 clustering logic but independently testable
  - User Story 3 (P3): Can start after Foundational - Integrates with US1 clustering logic but independently testable
  - User Story 4 (P4): Depends on US1 completion (requires clustering to be functional) - Can run after US1 is complete
  - User Story 5 (P5): Depends on US1 completion (requires centroids from clustering) - Can run in parallel with US4
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: FOUNDATIONAL FOR ALL OTHER STORIES - Core clustering must work first
- **User Story 2 (P2)**: Depends on US1 (enhances clustering logic to preserve minority clusters)
- **User Story 3 (P3)**: Depends on US1 (enhances clustering logic to handle outliers)
- **User Story 4 (P4)**: Depends on US1 (requires clustering to generate centroids for alignment)
- **User Story 5 (P5)**: Depends on US1 (requires centroids to compute medoid labels)

**CRITICAL PATH**: Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4-7 can proceed in parallel after US1

### Within Each User Story

- Models before services (database entities must exist)
- Services before endpoints (business logic before API)
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1 (Setup)**: T003, T004, T005 can run in parallel
- **Phase 2 (Foundational)**: T007-T009 (schema), T011-T014 (models), T015-T018 (API setup) can run in parallel
- **Phase 3 (US1)**: T019-T022 (embedding/clustering setup) can run in parallel before workflow implementation
- **Phase 4 (US2)**: T038-T039 can run in parallel
- **Phase 5 (US3)**: T043-T044 can run in parallel
- **Phase 6 (US4)**: T049-T050 can run in parallel before matching implementation
- **Phase 7 (US5)**: T062-T063 can run in parallel
- **Phase 8 (Polish)**: T068-T080 are all parallel (different test files, documentation)

---

## Parallel Example: User Story 1 (Core Clustering)

```bash
# Launch embedding and clustering setup together:
Task: "Load SBERT all-MiniLM-L6-v2 model in backend/src/ml/embedding_models.py"
Task: "Implement generate_embeddings function in backend/src/services/embedding_service.py"
Task: "Implement persist_embeddings function in backend/src/services/embedding_service.py"
Task: "Configure HDBSCAN in backend/src/ml/clustering_algorithms.py"

# After embedding service is ready, implement clustering workflow:
Task: "Implement cluster_embeddings function in backend/src/services/clustering_service.py"
Task: "Implement convert_outliers_to_singletons function in backend/src/services/outlier_handler.py"
Task: "Implement compute_centroids function in backend/src/services/centroid_service.py"
```

---

## Parallel Example: Phase 8 (Polish)

```bash
# All polish tasks are independent and can run in parallel:
Task: "Add embedding determinism test in backend/tests/unit/test_embedding_determinism.py"
Task: "Add centroid computation test in backend/tests/unit/test_centroid_computation.py"
Task: "Add alignment matching test in backend/tests/unit/test_alignment_matching.py"
Task: "Document API endpoints in backend/docs/api_documentation.md"
Task: "Document integration with Spec 3 in backend/docs/integration_spec3.md"
Task: "Add monitoring and observability logging"
Task: "Add configuration management in backend/src/config.py"
Task: "Security review for API authentication"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T018) - CRITICAL - blocks all stories
3. Complete Phase 3: User Story 1 (T019-T037)
4. **STOP and VALIDATE**: Test User Story 1 independently with 10 approved summaries, verify clustering creates distinct thought spaces, percentages sum to 1.0, all participants assigned
5. Deploy/demo if ready - THIS IS MVP (clustering works, thought spaces are created)

**MVP = Phase 1 + Phase 2 + Phase 3 (User Story 1) = 37 tasks**

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (18 tasks)
2. Add User Story 1 → Test independently → Deploy/Demo (MVP! - 37 total tasks)
3. Add User Story 2 → Test independently → Minority preservation guaranteed (42 total tasks)
4. Add User Story 3 → Test independently → Outlier handling complete (48 total tasks)
5. Add User Story 4 → Test independently → Cross-round alignment functional (61 total tasks)
6. Add User Story 5 → Test independently → Medoid labeling complete (67 total tasks)
7. Add Polish → All tests, docs, monitoring complete (82 total tasks)

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (Phase 1-2)
2. Once Foundational is done:
   - Developer A: User Story 1 (MUST complete first - blocks others)
3. After User Story 1 completes:
   - Developer A: User Story 4 (alignment)
   - Developer B: User Story 2 (minority preservation)
   - Developer C: User Story 3 (outlier handling)
   - Developer D: User Story 5 (medoid labeling)
4. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently testable (see "Independent Test" for each phase)
- User Story 1 is foundational - all other stories depend on it
- Tests are MINIMAL (contract validation only) since spec.md does not explicitly request TDD
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitutional compliance: Semantic Accuracy Over Aesthetics (US2), Intent Fidelity (US5), Temporal Transparency (US1, US4)

---

## Total Task Summary

- **Total Tasks**: 82
- **MVP Tasks** (Phase 1 + 2 + 3): 37 tasks
- **Parallel Tasks**: 41 tasks marked [P]
- **User Story Breakdown**:
  - Setup (Phase 1): 5 tasks
  - Foundational (Phase 2): 13 tasks
  - User Story 1 (Phase 3): 19 tasks 🎯 MVP
  - User Story 2 (Phase 4): 5 tasks
  - User Story 3 (Phase 5): 6 tasks
  - User Story 4 (Phase 6): 13 tasks
  - User Story 5 (Phase 7): 6 tasks
  - Polish (Phase 8): 15 tasks
