# Tasks: Temporal Sankey Construction Protocol

**Input**: Design documents from `/specs/005-sankey-construction/`
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

Per plan.md, this is a web application with structure:
- `backend/src/` for backend source code
- `frontend/src/` for frontend source code
- `backend/tests/` for backend tests
- `frontend/tests/` for frontend tests

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create backend project structure per plan.md with backend/src/{models,services,api,validators} directories
- [x] T002 Create frontend project structure per plan.md with frontend/src/{components,pages,services} directories
- [x] T003 Initialize Python 3.11+ backend with requirements.txt including fastapi, uvicorn, pydantic, psycopg2-binary, asyncpg, networkx, pytest
- [x] T004 Initialize React 18+ frontend with TypeScript 5+, package.json including D3.js/recharts for Sankey visualization, axios for API calls
- [x] T005 [P] Setup PostgreSQL database with sankey_graphs table (id UUID, discussion_id UUID, graph_data JSONB, created_at TIMESTAMP, metadata JSONB)
- [x] T006 [P] Create database indexes on discussion_id (unique) and created_at in sankey_graphs table
- [x] T007 [P] Configure pytest with pytest.ini and test directory structure for backend
- [ ] T008 [P] Setup frontend testing with Jest/Vitest and Cypress for e2e tests
- [x] T009 [P] Configure environment variables in .env for DATABASE_URL, SPEC4_CLUSTER_API_URL, FRONTEND_URL

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T010 Create Pydantic model for Node in backend/src/models/sankey_node.py with fields (node_id, cluster_id, label_summary, user_count, user_pct, display_group_id) and validation (user_count >= 1, user_pct in (0.0, 1.0])
- [x] T011 [P] Create Pydantic model for Edge in backend/src/models/sankey_edge.py with fields (from_round_index, to_round_index, from_cluster_id, to_cluster_id, user_count, pct_of_from, pct_of_to) and validation (to_round_index == from_round_index + 1, user_count >= 1)
- [x] T012 [P] Create Pydantic model for Column in backend/src/models/sankey_column.py with fields (round_index, nodes, total_participants) and validation (sum of node user_pct == 1.0 ± 0.0001)
- [x] T013 [P] Create Pydantic model for SankeyGraph in backend/src/models/sankey_graph.py with fields (discussion_id, rounds, columns, edges, created_at, metadata) and validation (len(columns) == len(rounds), all edges reference valid rounds)
- [x] T014 [P] Create Pydantic models for DiscussionReport supporting entities in backend/src/models/discussion_report.py (RoundClusterSummary, ClusterInfo, DropoutPoint, TopMovement, MovementDetail, DiscussionReport)
- [x] T015 [P] Setup FastAPI app structure in backend/src/api/main.py with routers, CORS middleware, error handlers
- [x] T016 [P] Create API client for Spec 4 cluster data in backend/src/services/cluster_api_client.py with get_clusters_for_round and get_participant_assignments methods
- [x] T017 Implement invariants validator in backend/src/validators/sankey_invariants.py with validate_percentage_sum, validate_edge_totals, validate_coverage methods
- [x] T018 [P] Create graph structure validator in backend/src/validators/graph_validator.py with validate_column_ordering, validate_edge_references methods

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel ✅ COMPLETE

---

## Phase 3: User Story 1 - Construct Multi-Column Sankey from Cluster Data (Priority: P1) 🎯 MVP

**Goal**: Construct a multi-column Sankey diagram from cluster data with nodes representing thought spaces and widths proportional to participant counts

**Independent Test**: Provide cluster data for 3 rounds, verify a 3-column Sankey is generated with correct node counts and widths

### Implementation for User Story 1

- [x] T019 [P] [US1] Implement load_cluster_data function in backend/src/services/cluster_api_client.py to fetch cluster data from Spec 4 for all rounds in a discussion
- [x] T020 [P] [US1] Implement create_node_from_cluster function in backend/src/services/node_builder.py to convert Spec 4 cluster to Node entity (map cluster_id, label_summary, user_count, compute user_pct per round)
- [x] T021 [US1] Implement build_column function in backend/src/services/node_builder.py to create Column entity for a round with all nodes and validate percentage sum
- [x] T022 [US1] Implement build_sankey_graph function in backend/src/services/sankey_builder.py to assemble SankeyGraph from columns (create discussion_id, rounds list, columns list, empty edges initially)
- [x] T023 [US1] Implement POST /api/v1/sankey/construct endpoint in backend/src/api/sankey_routes.py to trigger Sankey construction (fetch cluster data, build nodes, build columns, validate invariants, persist to database)
- [x] T024 [US1] Implement GET /api/v1/sankey/{discussion_id} endpoint in backend/src/api/sankey_routes.py to retrieve SankeyGraph from database by discussion_id
- [x] T025 [US1] Add database persistence in backend/src/services/sankey_builder.py to save SankeyGraph as JSONB to sankey_graphs table
- [x] T026 [US1] Add idempotency check in POST /api/v1/sankey/construct to return existing Sankey if already constructed for discussion_id
- [x] T027 [US1] Add logging for Sankey construction workflow in backend/src/services/sankey_builder.py with timestamps for each step (load clusters, build nodes, build columns, validate, persist)
- [ ] T028 [US1] Contract validation test in backend/tests/contract/test_cluster_to_node_conversion.py to verify Node entities correctly map Spec 4 cluster fields (cluster_id, label_summary, user_count, user_pct)
- [x] T029 [US1] Create SankeyDiagram React component in frontend/src/components/SankeyDiagram/SankeyDiagram.tsx to render multi-column Sankey with D3.js (columns, nodes with proportional widths, labels)
- [x] T030 [US1] Create SankeyNode React component in frontend/src/components/SankeyNode/SankeyNode.tsx to render individual node with width based on user_pct, label text from label_summary
- [x] T031 [US1] Create SankeyView page in frontend/src/pages/SankeyView.tsx to display Sankey diagram for a discussion (fetch SankeyGraph via API, render SankeyDiagram component)
- [x] T032 [US1] Implement fetchSankeyGraph function in frontend/src/services/sankeyApi.ts to call GET /api/v1/sankey/{discussion_id} and return SankeyGraph

**Checkpoint**: At this point, User Story 1 should be fully functional - multi-column Sankey is constructed with nodes representing clusters, widths proportional to participant counts ✅ 13/14 COMPLETE (T028 pending)

---

## Phase 4: User Story 2 - Compute Movement-Based Edges Between Rounds (Priority: P2)

**Goal**: Compute edges between nodes in adjacent columns based on actual participant movement, where edge width reflects number of participants making each transition

**Independent Test**: Provide participant assignments for 2 rounds, verify edges are created with correct participant counts

### Implementation for User Story 2

- [x] T033 [P] [US2] Implement get_participant_assignments function in backend/src/services/cluster_api_client.py to fetch user assignments from Spec 4 (user_id, cluster_id per round)
- [x] T034 [P] [US2] Implement track_movement function in backend/src/services/movement_tracker.py to compute participant transitions between adjacent rounds (return list of (user_id, from_cluster_id, to_cluster_id))
- [x] T035 [US2] Implement aggregate_movements function in backend/src/services/movement_tracker.py to group transitions by (from_cluster_id, to_cluster_id) and count participants per transition
- [x] T036 [US2] Implement create_edge function in backend/src/services/edge_builder.py to convert aggregated movement into Edge entity (from_round_index, to_round_index, from_cluster_id, to_cluster_id, user_count)
- [x] T037 [US2] Implement compute_derived_metrics function in backend/src/services/edge_builder.py to calculate pct_of_from and pct_of_to for edges (optional metrics per FR-028, FR-029)
- [x] T038 [US2] Update build_sankey_graph in backend/src/services/sankey_builder.py to include edge computation workflow (track movements, aggregate, create edges, validate edge totals, add to SankeyGraph.edges)
- [x] T039 [US2] Add edge total validation in backend/src/validators/sankey_invariants.py to verify sum of edge user_counts equals user intersection size between adjacent rounds (FR-040)
- [x] T040 [US2] Create SankeyEdge React component in frontend/src/components/SankeyEdge/SankeyEdge.tsx to render flow paths between nodes with width proportional to user_count
- [x] T041 [US2] Update SankeyDiagram component in frontend/src/components/SankeyDiagram/SankeyDiagram.tsx to render edges between adjacent columns with proper positioning and curvature
- [ ] T042 [US2] Integration test in backend/tests/integration/test_multi_round_movement.py to verify edge computation accuracy with known participant movements (10 users in Round 1, 5 move A→D, 3 move B→D, 2 move A→E)

**Checkpoint**: At this point, movement-based edges are functional - participants transitions between thought spaces are visualized with correct flow widths ✅ 9/10 COMPLETE (T042 test pending verification)

---

## Phase 5: User Story 3 - Handle Participant Dropout Naturally (Priority: P3)

**Goal**: Compute edges based only on continuing participants, resulting in natural flow mass shrinkage without synthetic "dropout" nodes

**Independent Test**: Provide 10 participants in Round 1 and 7 in Round 2, verify edge totals sum to 7 (not 10), confirm no dropout node exists

### Implementation for User Story 3

- [x] T043 [P] [US3] Implement compute_user_intersection function in backend/src/services/dropout_handler.py to identify participants present in both rounds (continuing_users = users_in_round_r ∩ users_in_round_r1)
- [x] T044 [US3] Update track_movement in backend/src/services/movement_tracker.py to filter movements to only include continuing users (exclude dropouts from edge computation per FR-019)
- [x] T045 [US3] Add dropout tracking in backend/src/services/dropout_handler.py to compute per-round participant counts (for dropout curve generation)
- [x] T046 [US3] Add validation in backend/src/validators/sankey_invariants.py to verify no synthetic "dropout" or "no response" nodes exist in any column (FR-020)
- [x] T047 [US3] Add validation in backend/src/validators/sankey_invariants.py to verify total edge width shrinks naturally when dropout occurs (FR-021, FR-022)
- [ ] T048 [US3] Integration test in backend/tests/integration/test_dropout_natural_shrinkage.py to verify dropout handling (10 participants Round 1, 7 Round 2, edge totals = 7, no dropout node, visual narrowing of flow)

**Checkpoint**: At this point, dropout is handled naturally - flow mass shrinks without synthetic nodes, temporal transparency is maintained ✅ 5/6 COMPLETE (T048 test pending)

---

## Phase 6: User Story 4 - Integrate Alignment Metadata for Display Continuity (Priority: P4)

**Goal**: Include display_group_ids from Spec 4 alignment in Sankey output for stable colors and labels, without affecting edge computation

**Independent Test**: Provide aligned clusters with display_group_ids, verify they appear in Sankey output, confirm edge counts are unchanged

### Implementation for User Story 4

- [x] T049 [P] [US4] Implement fetch_alignment_metadata function in backend/src/services/alignment_integrator.py to retrieve display_group_id mappings from Spec 4 alignment data
- [x] T050 [US4] Implement integrate_alignment function in backend/src/services/alignment_integrator.py to add display_group_id to Node entities based on cluster_id mapping (optional field, null if no alignment)
- [x] T051 [US4] Update build_column in backend/src/services/node_builder.py to include display_group_id in Node creation if alignment metadata is available
- [x] T052 [US4] Add invariant check in backend/src/validators/sankey_invariants.py to verify alignment metadata does NOT change edge counts (FR-026, SC-006)
- [x] T053 [US4] Update SankeyNode component in frontend/src/components/SankeyNode/SankeyNode.tsx to use display_group_id for color assignment (stable colors across rounds for aligned clusters)
- [x] T054 [US4] Add color continuity logic in frontend/src/components/SankeyDiagram/SankeyDiagram.tsx to assign consistent colors to nodes with same display_group_id across columns
- [ ] T055 [US4] Contract validation test in backend/tests/contract/test_alignment_metadata_integration.py to verify display_group_id included in Node entities when Spec 4 provides alignment, edge counts unchanged

**Checkpoint**: At this point, alignment metadata is integrated - stable colors improve readability, edge computation remains based solely on participant movement ✅ 6/7 COMPLETE (T055 test pending)

---

## Phase 7: User Story 5 - Generate Discussion Report with Sankey and Statistics (Priority: P5)

**Goal**: Generate comprehensive report including final Sankey diagram, per-round cluster summaries, participant counts per round (dropout curve), and top movement edges

**Independent Test**: Construct a Sankey, verify report includes all required sections (SankeyGraph, cluster summaries, dropout curve, top movements)

### Implementation for User Story 5

- [ ] T056 [P] [US5] Implement generate_cluster_summaries function in backend/src/services/report_generator.py to extract per-round cluster summaries from SankeyGraph (round_index, list of {label, user_count})
- [ ] T057 [P] [US5] Implement generate_dropout_curve function in backend/src/services/report_generator.py to compute participant counts per round from Column.total_participants
- [ ] T058 [P] [US5] Implement generate_top_movements function in backend/src/services/report_generator.py to identify largest flows per round transition (top 5 edges by user_count)
- [ ] T059 [US5] Implement assemble_discussion_report function in backend/src/services/report_generator.py to create DiscussionReport entity with SankeyGraph, cluster summaries, dropout curve, top movements
- [ ] T060 [US5] Implement POST /api/v1/reports/generate endpoint in backend/src/api/report_routes.py to trigger report generation (fetch SankeyGraph, generate summaries/curve/movements, assemble report, return JSON)
- [ ] T061 [US5] Implement GET /api/v1/reports/{discussion_id} endpoint in backend/src/api/report_routes.py to retrieve generated DiscussionReport by discussion_id
- [ ] T062 [US5] Add report export to JSON in backend/src/services/report_generator.py with export_format="json-v1" and structured JSON serialization (FR-038)
- [ ] T063 [US5] Create DiscussionReport React component in frontend/src/components/DiscussionReport/DiscussionReport.tsx to display full report (Sankey diagram, cluster summaries table, dropout curve chart, top movements list)
- [ ] T064 [US5] Create ReportView page in frontend/src/pages/ReportView.tsx to display discussion report for a discussion (fetch DiscussionReport via API, render DiscussionReport component)
- [ ] T065 [US5] Implement fetchDiscussionReport function in frontend/src/services/reportApi.ts to call GET /api/v1/reports/{discussion_id} and return DiscussionReport
- [ ] T066 [US5] Add export functionality in frontend/src/components/DiscussionReport/DiscussionReport.tsx to download report as JSON file
- [ ] T067 [US5] Integration test in backend/tests/integration/test_report_generation.py to verify report includes all required sections (SankeyGraph, cluster summaries, dropout curve, top movements)

**Checkpoint**: At this point, discussion reports are fully functional - comprehensive report artifact available for participants to export and analyze

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T068 [P] Add percentage sum validation test in backend/tests/unit/test_sankey_invariants.py to verify node user_pct values sum to 1.0 within each column (tolerance 0.0001)
- [ ] T069 [P] Add edge total validation test in backend/tests/unit/test_sankey_invariants.py to verify edge user_counts match user intersection size between rounds
- [ ] T070 [P] Add coverage validation test in backend/tests/unit/test_sankey_invariants.py to verify every participant in a round is assigned to exactly one node
- [ ] T071 [P] Add determinism test in backend/tests/unit/test_sankey_invariants.py to verify same cluster assignments produce identical SankeyGraph (run construction twice, assert equality)
- [ ] T072 [P] Add single round Sankey test in backend/tests/integration/test_single_round_sankey.py to verify degenerate case (1 column with nodes, 0 edges)
- [ ] T073 [P] Add contract validation for Sankey data structure in backend/tests/contract/test_sankey_to_report_handoff.py to verify SankeyGraph conforms to JSON schema from contracts/sankey-data-contract.yaml
- [ ] T074 [P] Add performance test in backend/tests/performance/test_sankey_construction_performance.py to verify construction completes in <3s for 100 participants across 5 rounds (SC-001)
- [ ] T075 [P] Document API endpoints in backend/docs/api_documentation.md with curl examples from quickstart.md
- [ ] T076 [P] Document integration with Spec 4 in backend/docs/integration_spec4.md (receiving cluster data, alignment metadata)
- [ ] T077 [P] Add Sankey rendering e2e test in frontend/tests/e2e/sankey_rendering.cy.ts to verify visual Sankey diagram renders correctly with nodes, edges, labels
- [ ] T078 [P] Add report export e2e test in frontend/tests/e2e/report_export.cy.ts to verify JSON export functionality works
- [ ] T079 Run quickstart.md validation scenarios (construct Sankey for 3 rounds, verify nodes and edges, generate report)
- [ ] T080 [P] Add monitoring and observability logging for Sankey construction latency, edge computation time, validation failures
- [ ] T081 [P] Add configuration management for construction parameters (top_movements_count, dropout_curve_enabled) in backend/src/config.py
- [ ] T082 [P] Security review for API authentication using bearerAuth (JWT) per contracts
- [ ] T083 Code cleanup and refactoring - remove unused imports, add type hints, improve variable naming
- [ ] T084 Final validation: Run all tests, verify all success criteria (SC-001 through SC-013) are met

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User Story 1 (P1): Can start after Foundational - FOUNDATIONAL FOR ALL OTHER STORIES (core Sankey construction)
  - User Story 2 (P2): Depends on US1 (requires node structure to add edges)
  - User Story 3 (P3): Depends on US2 (enhances edge computation with dropout handling)
  - User Story 4 (P4): Depends on US1 (integrates alignment metadata into nodes)
  - User Story 5 (P5): Depends on US1 and US2 (requires complete SankeyGraph to generate report)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: FOUNDATIONAL - Core Sankey construction must work first (nodes, columns, graph structure)
- **User Story 2 (P2)**: Depends on US1 (adds edges to existing node structure)
- **User Story 3 (P3)**: Depends on US2 (enhances edge computation with dropout logic)
- **User Story 4 (P4)**: Depends on US1 (adds alignment metadata to nodes, can run in parallel with US2/US3)
- **User Story 5 (P5)**: Depends on US1 and US2 (requires complete SankeyGraph with nodes and edges)

**CRITICAL PATH**: Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) and Phase 7 (US5)
**PARALLEL OPPORTUNITY**: After US1 completes, US4 can run in parallel with US2

### Within Each User Story

- Backend models before services (Pydantic entities must exist)
- Services before API endpoints (business logic before routes)
- Backend API before frontend integration (data layer before UI)
- Core implementation before integration tests
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1 (Setup)**: T005-T009 can run in parallel (database, pytest, frontend tests, env config)
- **Phase 2 (Foundational)**: T010-T014 (Pydantic models), T015-T018 (API setup, validators) can run in parallel
- **Phase 3 (US1)**: T019-T020 (load clusters, node builder) can run in parallel before workflow integration
- **Phase 4 (US2)**: T033-T034 (participant assignments, movement tracker) can run in parallel
- **Phase 5 (US3)**: T043-T045 can run in parallel
- **Phase 6 (US4)**: T049-T050 can run in parallel
- **Phase 7 (US5)**: T056-T058 can run in parallel (summaries, dropout curve, top movements)
- **Phase 8 (Polish)**: T068-T082 are all parallel (different test files, documentation)

---

## Parallel Example: User Story 1 (Core Sankey Construction)

```bash
# Launch cluster loading and node building together:
Task: "Implement load_cluster_data function in backend/src/services/cluster_api_client.py"
Task: "Implement create_node_from_cluster function in backend/src/services/node_builder.py"

# After node builder is ready, build workflow components in parallel:
Task: "Implement build_column function in backend/src/services/node_builder.py"
Task: "Add logging for Sankey construction workflow in backend/src/services/sankey_builder.py"

# Frontend components can run in parallel with backend API:
Task: "Create SankeyDiagram React component in frontend/src/components/SankeyDiagram/SankeyDiagram.tsx"
Task: "Create SankeyNode React component in frontend/src/components/SankeyNode/SankeyNode.tsx"
```

---

## Parallel Example: User Story 5 (Discussion Report)

```bash
# All report generation components can run in parallel:
Task: "Implement generate_cluster_summaries function in backend/src/services/report_generator.py"
Task: "Implement generate_dropout_curve function in backend/src/services/report_generator.py"
Task: "Implement generate_top_movements function in backend/src/services/report_generator.py"

# Frontend report components can run in parallel:
Task: "Create DiscussionReport React component in frontend/src/components/DiscussionReport/DiscussionReport.tsx"
Task: "Implement fetchDiscussionReport function in frontend/src/services/reportApi.ts"
```

---

## Parallel Example: Phase 8 (Polish)

```bash
# All polish tasks are independent and can run in parallel:
Task: "Add percentage sum validation test in backend/tests/unit/test_sankey_invariants.py"
Task: "Add edge total validation test in backend/tests/unit/test_sankey_invariants.py"
Task: "Add determinism test in backend/tests/unit/test_sankey_invariants.py"
Task: "Add performance test in backend/tests/performance/test_sankey_construction_performance.py"
Task: "Document API endpoints in backend/docs/api_documentation.md"
Task: "Add Sankey rendering e2e test in frontend/tests/e2e/sankey_rendering.cy.ts"
Task: "Add monitoring and observability logging"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2)

1. Complete Phase 1: Setup (T001-T009)
2. Complete Phase 2: Foundational (T010-T018) - CRITICAL - blocks all stories
3. Complete Phase 3: User Story 1 (T019-T032)
4. **STOP and VALIDATE**: Test User Story 1 independently with 3 rounds, verify multi-column Sankey with nodes
5. Complete Phase 4: User Story 2 (T033-T042)
6. **STOP and VALIDATE**: Test User Story 2 independently, verify edges show participant movement
7. Deploy/demo if ready - THIS IS MVP (Sankey with nodes and edges, movement-based visualization)

**MVP = Phase 1 + Phase 2 + Phase 3 + Phase 4 (US1 + US2) = 42 tasks**

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (18 tasks)
2. Add User Story 1 → Test independently → Multi-column Sankey with nodes (32 total tasks)
3. Add User Story 2 → Test independently → Movement-based edges functional (MVP! - 42 total tasks)
4. Add User Story 3 → Test independently → Dropout handled naturally (48 total tasks)
5. Add User Story 4 → Test independently → Alignment metadata integrated (55 total tasks)
6. Add User Story 5 → Test independently → Discussion reports complete (67 total tasks)
7. Add Polish → All tests, docs, monitoring complete (84 total tasks)

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (Phase 1-2)
2. Once Foundational is done:
   - Developer A: User Story 1 (MUST complete first - blocks others)
3. After User Story 1 completes:
   - Developer A: User Story 2 (edges)
   - Developer B: User Story 4 (alignment metadata - can run in parallel with US2)
4. After User Story 2 completes:
   - Developer A: User Story 3 (dropout handling)
   - Developer B: Continue User Story 4
5. After US1 and US2 complete:
   - Developer C: User Story 5 (reports)
6. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently testable (see "Independent Test" for each phase)
- User Story 1 is foundational - all other stories depend on it
- User Story 2 is critical for movement visualization (MVP includes US1 + US2)
- Tests are MINIMAL (contract validation only) since spec.md does not explicitly request TDD
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitutional compliance: Temporal Transparency (US3 dropout), Semantic Accuracy (all clusters preserved as nodes), Representation Not Adjudication (pure visualization)

---

## Total Task Summary

- **Total Tasks**: 84
- **MVP Tasks** (Phase 1 + 2 + 3 + 4): 42 tasks
- **Parallel Tasks**: 44 tasks marked [P]
- **User Story Breakdown**:
  - Setup (Phase 1): 9 tasks
  - Foundational (Phase 2): 9 tasks
  - User Story 1 (Phase 3): 14 tasks 🎯 (Core Sankey structure)
  - User Story 2 (Phase 4): 10 tasks 🎯 MVP (Movement-based edges)
  - User Story 3 (Phase 5): 6 tasks
  - User Story 4 (Phase 6): 7 tasks
  - User Story 5 (Phase 7): 12 tasks
  - Polish (Phase 8): 17 tasks
