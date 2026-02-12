# Spec 005 - Sankey Construction Protocol: Implementation Status

**Date**: 2026-02-06
**Branch**: 004-clustering-alignment
**Status**: Partially Implemented - Core Services Complete, Missing Frontend & Tests

## Executive Summary

The backend services for Sankey diagram construction are **substantially complete**. The core infrastructure (models, services, API endpoints) exists and follows the architecture defined in spec.md and plan.md. However, significant work remains in:

1. **Frontend components** (React/TypeScript visualization)
2. **Report generation services** (User Story 5)
3. **Comprehensive test coverage** (Phase 8 polish tasks)
4. **Dropout handling refinements** (User Story 3)
5. **Alignment integration** (User Story 4)

## Completed Implementation

### Phase 1: Setup ✓ COMPLETE
All foundational project structure exists:
- ✓ Backend structure: `backend/src/{models,services,api,validators}`
- ✓ Python environment with FastAPI, Pydantic, PostgreSQL, NetworkX
- ✓ Database schema for `sankey_graphs` table
- ✓ Environment configuration

### Phase 2: Foundational ✓ MOSTLY COMPLETE  
Core models and infrastructure:
- ✓ **T010**: `SankeyNode` model (`backend/src/models/sankey_node.py`)
- ✓ **T011**: `SankeyEdge` model (`backend/src/models/sankey_edge.py`)
- ✓ **T012**: `SankeyColumn` model (`backend/src/models/sankey_column.py`)
- ✓ **T013**: `SankeyGraph` model (`backend/src/models/sankey_graph.py`)
- ⚠️ **T014**: Discussion report models - PARTIAL (old report_service.py exists but needs update)
- ✓ **T015**: FastAPI app structure (`backend/src/main.py` with routers)
- ✓ **T016**: Cluster API client (`backend/src/services/cluster_api_client.py`)
- ✓ **T017**: Invariants validator (`backend/src/validators/sankey_invariants.py`)
- ✓ **T018**: Graph structure validator (`backend/src/validators/graph_validator.py`)

### Phase 3: User Story 1 - Core Sankey Construction ✓ MOSTLY COMPLETE
Multi-column Sankey with nodes:
- ✓ **T019**: Load cluster data (`cluster_api_client.py::get_clusters_for_round`)
- ✓ **T020**: Create node from cluster (`node_builder.py::create_node_from_cluster`)
- ✓ **T021**: Build column (`node_builder.py::build_column`)
- ✓ **T022**: Build sankey graph (`sankey_builder.py::build_sankey_graph`)
- ✓ **T023**: POST /api/v1/sankey/construct endpoint (`api/routes/sankey.py`)
- ✓ **T024**: GET /api/v1/sankey/{discussion_id} endpoint (`api/routes/sankey.py`)
- ✓ **T025**: Database persistence (`sankey_builder.py::save_to_database`)
- ✓ **T026**: Idempotency check (`sankey_builder.py::load_from_database`)
- ✓ **T027**: Logging (`sankey_builder.py` with timing metrics)
- ❌ **T028**: Contract validation test - MISSING
- ⚠️ **T029**: SankeyDiagram React component - EXISTS but needs verification
- ⚠️ **T030**: SankeyNode React component - EXISTS but needs verification  
- ❌ **T031**: SankeyView page - MISSING
- ❌ **T032**: fetchSankeyGraph service - MISSING

**Status**: Backend COMPLETE (T019-T027), Frontend INCOMPLETE (T028-T032)

### Phase 4: User Story 2 - Movement-Based Edges ✓ COMPLETE
Participant movement computation:
- ✓ **T033**: Get participant assignments (`cluster_api_client.py::get_participant_assignments`)
- ✓ **T034**: Track movement (`movement_tracker.py::track_user_movements`)
- ✓ **T035**: Aggregate movements (`movement_tracker.py::compute_movements_for_rounds`)
- ✓ **T036**: Create edge (`edge_builder.py::create_edge_from_movement`)
- ✓ **T037**: Compute derived metrics (`edge_builder.py` - pct_of_from/pct_of_to)
- ✓ **T038**: Update build_sankey_graph with edges (`sankey_builder.py` lines 184-231)
- ✓ **T039**: Edge total validation (`sankey_invariants.py::validate_edge_totals`)
- ⚠️ **T040**: SankeyEdge React component - EXISTS but needs verification
- ⚠️ **T041**: Update SankeyDiagram for edges - EXISTS but needs verification
- ❌ **T042**: Integration test for multi-round movement - MISSING

**Status**: Backend COMPLETE (T033-T039), Frontend PARTIAL (T040-T041), Tests MISSING (T042)

### Phase 5: User Story 3 - Natural Dropout ⚠️ PARTIAL
Option A dropout behavior:
- ❌ **T043**: compute_user_intersection in dropout_handler.py - MISSING
  - Note: `dropout_detection.py` exists but is for a different purpose (real-time dropout detection)
- ⚠️ **T044**: Update track_movement to filter continuing users - NEEDS VERIFICATION
- ⚠️ **T045**: Dropout tracking - PARTIAL (some logic exists)
- ❌ **T046**: Validate no synthetic nodes - MISSING
- ❌ **T047**: Validate natural shrinkage - MISSING
- ❌ **T048**: Integration test for dropout - MISSING

**Status**: INCOMPLETE - Needs dedicated dropout_handler.py service

### Phase 6: User Story 4 - Alignment Integration ⚠️ PARTIAL
Display metadata for visual continuity:
- ⚠️ **T049**: fetch_alignment_metadata - EXISTS in cluster_api_client.py but needs verification
- ⚠️ **T050**: integrate_alignment - PARTIAL (alignment_service.py exists but may be for Spec 4)
- ⚠️ **T051**: Update build_column for display_group_id - PARTIAL (parameter exists in node_builder.py)
- ❌ **T052**: Invariant check for alignment - MISSING
- ⚠️ **T053**: Update SankeyNode for colors - EXISTS but needs verification
- ⚠️ **T054**: Color continuity in SankeyDiagram - EXISTS but needs verification
- ❌ **T055**: Contract test for alignment - MISSING

**Status**: PARTIAL - Core logic exists but needs refinement and testing

### Phase 7: User Story 5 - Discussion Reports ❌ INCOMPLETE
Comprehensive report generation:
- ❌ **T056-T059**: Report generation functions - MISSING (report_service.py exists but outdated)
- ❌ **T060-T061**: Report API endpoints - MISSING
- ❌ **T062**: Export to JSON - MISSING
- ❌ **T063-T066**: Frontend report components - MISSING
- ❌ **T067**: Integration test for reports - MISSING

**Status**: INCOMPLETE - Needs complete rewrite of report_generator.py service

### Phase 8: Polish & Testing ❌ MOSTLY INCOMPLETE
- ❌ **T068-T073**: Unit and integration tests - MISSING (some test files exist but incomplete)
- ❌ **T074**: Performance test - EXISTS (`test_sankey_performance.py`) but needs verification
- ❌ **T075-T076**: Documentation - MISSING
- ❌ **T077-T078**: E2E tests - MISSING
- ❌ **T079**: Quickstart validation - MISSING
- ❌ **T080-T082**: Monitoring, config, security - PARTIAL
- ❌ **T083-T084**: Cleanup and final validation - MISSING

**Status**: INCOMPLETE - Comprehensive testing suite needed

## Files Implemented

### Backend Models (Complete)
```
backend/src/models/
├── sankey_node.py         ✓ Complete with validation
├── sankey_edge.py         ✓ Complete with validation
├── sankey_column.py       ✓ Complete with validation
├── sankey_graph.py        ✓ Complete with validation
└── sankey_graph_db.py     ✓ SQLAlchemy model for persistence
```

### Backend Services (Mostly Complete)
```
backend/src/services/
├── sankey_builder.py      ✓ Main orchestration service
├── node_builder.py        ✓ Node creation from clusters
├── edge_builder.py        ✓ Edge creation from movements
├── movement_tracker.py    ✓ Participant movement tracking
├── cluster_api_client.py  ✓ Fetch cluster data from Spec 4
├── alignment_service.py   ⚠️ Exists but needs verification for Spec 5
├── dropout_detection.py   ⚠️ Wrong purpose (real-time detection, not Option A)
└── report_service.py      ❌ Outdated - needs rewrite
```

### Backend Validators (Complete)
```
backend/src/validators/
├── sankey_invariants.py   ✓ Percentage sums, edge totals, coverage
└── graph_validator.py     ✓ Column ordering, edge references
```

### Backend API (Complete)
```
backend/src/api/routes/
└── sankey.py              ✓ construct, get, delete endpoints
```

### Frontend Components (Partial)
```
frontend/src/components/
├── SankeyDiagram/         ⚠️ Exists but needs verification
│   ├── SankeyDiagram.tsx
│   ├── FlowRenderer.tsx
│   └── SankeyDiagram.css
└── SankeyNode/            ⚠️ Exists but needs verification
    └── index.ts
```

### Tests (Incomplete)
```
backend/tests/
├── contract/
│   ├── test_clustering_to_sankey.py    ⚠️ Exists but may be outdated
│   └── test_sankey_to_question.py      ⚠️ Exists but may be outdated
├── performance/
│   └── test_sankey_performance.py      ⚠️ Exists but needs verification
└── unit/
    └── test_sankey_models.py           ⚠️ Exists but incomplete
```

## Missing Critical Components

### 1. Dropout Handler Service (Priority: HIGH)
**File**: `backend/src/services/dropout_handler.py`

Need to implement Option A dropout behavior:
```python
async def compute_user_intersection(
    from_round_id: UUID,
    to_round_id: UUID,
    cluster_client: ClusterAPIClient
) -> Set[UUID]:
    """Compute users present in BOTH rounds (continuing participants)."""
    # FR-017: User intersection for dropout handling
    pass

async def filter_continuing_users(
    movements: List[Movement],
    continuing_users: Set[UUID]
) -> List[Movement]:
    """Filter movements to only include continuing participants."""
    # FR-019: Exclude dropouts from edge computation
    pass
```

### 2. Report Generator Service (Priority: MEDIUM)
**File**: `backend/src/services/report_generator.py`

Complete rewrite needed for User Story 5:
```python
async def generate_cluster_summaries(sankey: SankeyGraph) -> List[RoundClusterSummary]
async def generate_dropout_curve(sankey: SankeyGraph) -> List[DropoutPoint]
async def generate_top_movements(sankey: SankeyGraph, top_n: int = 5) -> List[TopMovement]
async def assemble_discussion_report(sankey: SankeyGraph) -> DiscussionReport
```

### 3. Report API Endpoints (Priority: MEDIUM)
**File**: `backend/src/api/routes/report.py`

New router for report generation:
```python
POST /api/v1/reports/generate
GET /api/v1/reports/{discussion_id}
GET /api/v1/reports/{discussion_id}/export
```

### 4. Frontend Pages (Priority: HIGH)
**Files**:
- `frontend/src/pages/SankeyView.tsx` - Main Sankey visualization page
- `frontend/src/pages/ReportView.tsx` - Discussion report page
- `frontend/src/services/sankeyApi.ts` - API client for Sankey endpoints
- `frontend/src/services/reportApi.ts` - API client for report endpoints

### 5. Frontend Report Components (Priority: MEDIUM)
**Files**:
- `frontend/src/components/DiscussionReport/DiscussionReport.tsx`
- `frontend/src/components/DropoutCurve/DropoutCurve.tsx`
- `frontend/src/components/TopMovements/TopMovements.tsx`

### 6. Comprehensive Test Suite (Priority: HIGH)
**Missing tests**:
- Contract tests for cluster-to-node conversion (T028)
- Integration test for multi-round movement (T042)
- Integration test for dropout natural shrinkage (T048)
- Contract test for alignment metadata integration (T055)
- Integration test for report generation (T067)
- Unit tests for all validators (T068-T071)
- E2E tests for Sankey rendering (T077-T078)

## Implementation Recommendations

### Immediate Next Steps (MVP Completion)

**Goal**: Complete User Story 1 + User Story 2 (MVP = 42 tasks)**

1. **Fix Frontend Integration** (2-4 hours)
   - Verify SankeyDiagram and SankeyNode components work with new API
   - Create SankeyView page
   - Implement sankeyApi.ts service
   - Test end-to-end: API → Component → Rendering

2. **Complete Dropout Handling** (2-3 hours)
   - Create `dropout_handler.py` service
   - Implement user intersection computation
   - Update `movement_tracker.py` to filter continuing users
   - Add validation for no synthetic nodes

3. **Verify Alignment Integration** (1-2 hours)
   - Test `fetch_alignment_metadata` in cluster_api_client.py
   - Verify `display_group_id` flows through to frontend
   - Add invariant check that alignment doesn't change edge counts

4. **Add Critical Tests** (3-4 hours)
   - T028: Contract test for cluster-to-node conversion
   - T042: Integration test for movement edges
   - T048: Integration test for dropout shrinkage
   - Basic smoke tests for API endpoints

**Total Estimate**: 8-13 hours to complete MVP

### Post-MVP: Reports & Polish (User Stories 3-5 + Phase 8)

5. **Implement Report Generation** (4-6 hours)
   - Rewrite `report_generator.py`
   - Create report API endpoints
   - Add report models to `discussion_report.py`

6. **Build Report UI** (4-6 hours)
   - Create DiscussionReport component
   - Create ReportView page
   - Add export functionality

7. **Comprehensive Testing** (6-8 hours)
   - Complete unit test suite (T068-T071)
   - Add integration tests (T072-T073)
   - Add performance tests (T074)
   - Add E2E tests (T077-T078)

8. **Documentation & Polish** (3-4 hours)
   - API documentation (T075)
   - Integration documentation (T076)
   - Quickstart validation (T079)
   - Code cleanup (T083)
   - Final validation (T084)

**Total Estimate**: 17-24 hours for complete implementation

## Success Criteria Status

| Criteria | Target | Status | Notes |
|----------|--------|--------|-------|
| SC-001: Performance (<3s) | <3s for 100 users, 5 rounds | ⚠️ UNTESTED | Logging exists, needs verification |
| SC-002: Cluster coverage | 100% of clusters as nodes | ✓ PASS | Validated in build_column |
| SC-003: Edge accuracy | 100% match participant movement | ⚠️ PARTIAL | Logic exists, needs testing |
| SC-004: Dropout accuracy | 100% natural (no synthetic nodes) | ❌ INCOMPLETE | Needs dropout_handler.py |
| SC-005: Percentage sum | 1.0 ± 0.0001 per column | ✓ PASS | Validated in SankeyColumn model |
| SC-006: Alignment invariant | Alignment doesn't change edges | ⚠️ PARTIAL | Logic exists, needs validation |
| SC-007: Schema compliance | 100% conform to data contract | ✓ PASS | Pydantic models enforce schema |
| SC-008: Report completeness | 100% include all sections | ❌ INCOMPLETE | Report generator missing |
| SC-009: Determinism | 100% reproducibility | ⚠️ UNTESTED | No explicit test |
| SC-010: Edge correctness | 100% on synthetic datasets | ❌ INCOMPLETE | Need integration tests |
| SC-011: Invariants verifiable | All automated tests | ❌ INCOMPLETE | Many tests missing |
| SC-012: Integration tests | Synthetic rounds pass | ❌ INCOMPLETE | Few tests exist |
| SC-013: End-to-end tests | Spec 3 → Spec 5 → Spec 6 | ❌ INCOMPLETE | E2E tests missing |

## Conclusion

**Backend Progress**: ~70% complete
- Core services and models are solid
- API endpoints functional
- Validation infrastructure complete
- Missing: dropout refinement, report generation, comprehensive tests

**Frontend Progress**: ~30% complete
- Basic components exist
- Missing: pages, API services, report components

**Overall Progress**: ~55% complete (46/84 tasks substantially done)

**Recommended Path**: 
1. Focus on MVP (US1 + US2) first - complete frontend integration and basic tests
2. Then tackle US3 (dropout), US4 (alignment), US5 (reports) sequentially
3. Finally add comprehensive test suite (Phase 8)

**Estimated Time to Complete**: 25-37 hours total
- MVP: 8-13 hours
- Full Feature Set: 17-24 additional hours
