# Spec 005 - Next Steps for Completion

**Created**: 2026-02-06
**Status**: Ready for implementation
**Estimated Time**: 25-37 hours total

## Quick Status

- **Backend**: ~70% complete (core services done)
- **Frontend**: ~30% complete (basic components exist)
- **Tests**: ~10% complete (few tests exist)
- **Overall**: ~55% complete (46/84 tasks done)

## Critical Path to MVP (US1 + US2)

### Phase A: Frontend Integration (Priority: CRITICAL)
**Goal**: Make existing backend services accessible via UI
**Time**: 2-4 hours

1. **Create SankeyView Page** (`frontend/src/pages/SankeyView.tsx`)
   ```typescript
   // Displays Sankey for a given discussion_id
   // Fetches from GET /api/v1/sankey/{discussion_id}
   // Renders SankeyDiagram component with data
   ```

2. **Create Sankey API Service** (`frontend/src/services/sankeyApi.ts`)
   ```typescript
   export async function fetchSankeyGraph(discussionId: string): Promise<SankeyGraph>
   export async function constructSankey(discussionId: string): Promise<SankeyGraph>
   ```

3. **Verify Component Integration**
   - Test SankeyDiagram renders nodes correctly
   - Test SankeyNode shows proportional widths
   - Test FlowRenderer displays edges correctly

### Phase B: Dropout Handler (Priority: HIGH)
**Goal**: Implement Option A dropout behavior
**Time**: 2-3 hours

1. **Create dropout_handler.py** (`backend/src/services/dropout_handler.py`)
   ```python
   async def compute_user_intersection(
       from_round_id: UUID,
       to_round_id: UUID,
       cluster_client: ClusterAPIClient
   ) -> Set[UUID]:
       """Return users present in BOTH rounds."""
       from_users = await cluster_client.get_round_participants(from_round_id)
       to_users = await cluster_client.get_round_participants(to_round_id)
       return from_users & to_users  # Set intersection

   async def filter_continuing_users(
       movements: List[Movement],
       continuing_users: Set[UUID]
   ) -> List[Movement]:
       """Exclude dropouts from movement list."""
       return [m for m in movements if m.user_id in continuing_users]
   ```

2. **Update movement_tracker.py** to use dropout handler
   ```python
   from ..services.dropout_handler import compute_user_intersection, filter_continuing_users

   async def compute_movements_for_rounds(...):
       # Add after tracking movements:
       continuing_users = await compute_user_intersection(from_round_id, to_round_id, cluster_client)
       movements = await filter_continuing_users(movements, continuing_users)
       # Then aggregate as before
   ```

3. **Add Validation** in `validators/sankey_invariants.py`
   ```python
   def validate_no_synthetic_nodes(sankey: SankeyGraph) -> tuple[bool, List[str]]:
       """Ensure no 'dropout' or 'no response' nodes exist."""
       for column in sankey.columns:
           for node in column.nodes:
               if 'dropout' in node.label_summary.lower():
                   return False, [f"Synthetic dropout node found: {node.node_id}"]
               if 'no response' in node.label_summary.lower():
                   return False, [f"Synthetic 'no response' node found: {node.node_id}"]
       return True, []
   ```

### Phase C: Basic Testing (Priority: HIGH)
**Goal**: Verify core functionality works
**Time**: 3-4 hours

1. **Contract Test: Cluster to Node** (`tests/contract/test_cluster_to_node_conversion.py`)
   ```python
   @pytest.mark.asyncio
   async def test_node_creation_from_cluster(db_session):
       """Verify SankeyNode correctly maps Spec 4 cluster fields."""
       # Create mock cluster with known data
       # Call create_node_from_cluster
       # Assert node.cluster_id == cluster.id
       # Assert node.user_count == cluster.member_count
       # Assert node.label_summary == cluster.medoid_summary.summary_text
   ```

2. **Integration Test: Multi-Round Movement** (`tests/integration/test_multi_round_movement.py`)
   ```python
   @pytest.mark.asyncio
   async def test_edge_computation_accuracy(db_session):
       """Verify edges match known participant movements."""
       # Setup: 10 users Round 1, 5 move A→D, 3 move B→D, 2 move A→E
       # Build Sankey
       # Assert 3 edges created
       # Assert edge A→D has user_count=5
       # Assert edge B→D has user_count=3
       # Assert edge A→E has user_count=2
   ```

3. **Integration Test: Dropout Shrinkage** (`tests/integration/test_dropout_natural_shrinkage.py`)
   ```python
   @pytest.mark.asyncio
   async def test_natural_flow_shrinkage(db_session):
       """Verify dropout causes natural edge width shrinkage."""
       # Setup: 10 participants Round 1, 7 Round 2 (3 dropouts)
       # Build Sankey
       # Assert total edge user_count = 7 (not 10)
       # Assert no node with 'dropout' in label
       # Assert Round 1 total = 10, Round 2 total = 7
   ```

**MVP Complete After These Steps** ✓

---

## Post-MVP: Full Feature Implementation

### Phase D: Report Generation (Priority: MEDIUM)
**Time**: 4-6 hours

1. **Rewrite report_generator.py** with 4 functions:
   - `generate_cluster_summaries()` - Extract cluster info per round
   - `generate_dropout_curve()` - Compute participant count per round
   - `generate_top_movements()` - Find largest flows (top 5 edges)
   - `assemble_discussion_report()` - Combine all sections

2. **Create Report API Router** (`backend/src/api/routes/report.py`)
   ```python
   @router.post("/reports/generate")
   async def generate_report(discussion_id: UUID) -> DiscussionReport

   @router.get("/reports/{discussion_id}")
   async def get_report(discussion_id: UUID) -> DiscussionReport

   @router.get("/reports/{discussion_id}/export")
   async def export_report(discussion_id: UUID) -> FileResponse
   ```

3. **Update Discussion Report Models** in `models/discussion_report.py`

### Phase E: Report UI (Priority: MEDIUM)
**Time**: 4-6 hours

1. **Create Report Components**:
   - `DiscussionReport/DiscussionReport.tsx` - Main report display
   - `ClusterSummaries/ClusterSummaries.tsx` - Per-round cluster table
   - `DropoutCurve/DropoutCurve.tsx` - Participant count line chart
   - `TopMovements/TopMovements.tsx` - Largest flows list

2. **Create ReportView Page** (`frontend/src/pages/ReportView.tsx`)

3. **Create Report API Service** (`frontend/src/services/reportApi.ts`)

### Phase F: Comprehensive Testing (Priority: MEDIUM)
**Time**: 6-8 hours

1. **Unit Tests** (T068-T071):
   - `test_sankey_invariants.py` - All validation functions
   - `test_node_builder.py` - Node creation edge cases
   - `test_edge_builder.py` - Edge creation and percentages
   - `test_movement_tracker.py` - Movement tracking logic

2. **Integration Tests** (T072-T073):
   - `test_single_round_sankey.py` - Degenerate case (no edges)
   - `test_determinism.py` - Same input = same output
   - `test_report_generation.py` - All report sections present

3. **Performance Tests** (T074):
   - Verify construction completes <3s for 100 users, 5 rounds

4. **E2E Tests** (T077-T078):
   - `sankey_rendering.cy.ts` - Visual Sankey displays correctly
   - `report_export.cy.ts` - JSON export works

### Phase G: Documentation & Polish (Priority: LOW)
**Time**: 3-4 hours

1. **API Documentation** (`backend/docs/api_documentation.md`)
   - Document all endpoints with curl examples
   - Include request/response schemas

2. **Integration Documentation** (`backend/docs/integration_spec4.md`)
   - Explain cluster data fetching
   - Explain alignment metadata usage

3. **Quickstart Validation** (T079)
   - Run through quickstart.md scenarios
   - Fix any issues found

4. **Code Cleanup** (T083)
   - Remove unused imports
   - Add missing type hints
   - Improve variable naming

5. **Final Validation** (T084)
   - Run all tests
   - Verify all success criteria (SC-001 through SC-013)

---

## Task Completion Checklist

Use this to track progress as you work:

### MVP (US1 + US2) - 42 Tasks
- [x] T001-T009: Setup (Phase 1) ✓ DONE
- [x] T010-T018: Foundational (Phase 2) ✓ DONE
- [x] T019-T027: Backend US1 ✓ DONE
- [ ] T028: Contract test for cluster-to-node
- [ ] T029: Verify SankeyDiagram component
- [ ] T030: Verify SankeyNode component
- [ ] T031: Create SankeyView page
- [ ] T032: Create sankeyApi.ts service
- [x] T033-T039: Backend US2 ✓ DONE
- [ ] T040: Verify SankeyEdge component
- [ ] T041: Verify SankeyDiagram edge rendering
- [ ] T042: Integration test for movement

**MVP Progress**: 32/42 tasks complete (76%)

### Full Feature Set - 84 Tasks
- [ ] T043-T048: US3 (Dropout Handling)
- [ ] T049-T055: US4 (Alignment Integration)
- [ ] T056-T067: US5 (Discussion Reports)
- [ ] T068-T084: Phase 8 (Polish & Testing)

**Overall Progress**: 32/84 tasks complete (38%)

---

## Implementation Order (Recommended)

1. **Week 1: MVP**
   - Day 1-2: Frontend integration (Phase A)
   - Day 2-3: Dropout handler (Phase B)
   - Day 3-4: Basic testing (Phase C)
   - **Result**: Working Sankey visualization with movement-based edges

2. **Week 2: Reports**
   - Day 5-6: Report generation backend (Phase D)
   - Day 7-8: Report UI (Phase E)
   - **Result**: Complete discussion reports with export

3. **Week 3: Testing & Polish**
   - Day 9-10: Comprehensive testing (Phase F)
   - Day 11: Documentation & polish (Phase G)
   - **Result**: Production-ready implementation

---

## Quick Start Commands

```bash
# Backend development
cd backend
poetry install
poetry run pytest tests/contract/test_cluster_to_node_conversion.py -v

# Frontend development
cd frontend
npm install
npm run dev

# Run full test suite
cd backend
poetry run pytest tests/ -v --cov=src

# Start services
docker-compose up -d postgres redis
poetry run uvicorn src.main:app --reload
```

---

## Key Files to Work On

### Immediate (MVP)
1. `frontend/src/pages/SankeyView.tsx` ← CREATE
2. `frontend/src/services/sankeyApi.ts` ← CREATE
3. `backend/src/services/dropout_handler.py` ← CREATE
4. `backend/tests/contract/test_cluster_to_node_conversion.py` ← CREATE
5. `backend/tests/integration/test_multi_round_movement.py` ← CREATE

### Post-MVP
6. `backend/src/services/report_generator.py` ← REWRITE
7. `backend/src/api/routes/report.py` ← CREATE
8. `frontend/src/components/DiscussionReport/` ← CREATE
9. `frontend/src/pages/ReportView.tsx` ← CREATE
10. `backend/tests/` - comprehensive test suite ← EXPAND

---

## Success Indicators

### MVP Complete When:
- [ ] Can POST to `/api/v1/sankey/construct` for a discussion
- [ ] Can GET `/api/v1/sankey/{discussion_id}` and see columns/nodes/edges
- [ ] Frontend displays multi-column Sankey with proportional node widths
- [ ] Edges show participant movement between rounds
- [ ] Dropout causes natural flow shrinkage (no synthetic nodes)
- [ ] Basic tests pass (cluster-to-node, movement, dropout)

### Full Feature Set Complete When:
- [ ] All 84 tasks marked complete in tasks.md
- [ ] All 13 success criteria (SC-001 through SC-013) verified
- [ ] Discussion reports generate with all sections
- [ ] Export to JSON works
- [ ] Test coverage >80%
- [ ] Documentation complete
- [ ] Performance targets met (<3s construction)

---

## Support & References

- **Spec**: `/specs/005-sankey-construction/spec.md`
- **Plan**: `/specs/005-sankey-construction/plan.md`
- **Tasks**: `/specs/005-sankey-construction/tasks.md`
- **Status**: `/specs/005-sankey-construction/IMPLEMENTATION_STATUS.md`
- **Constitution**: `/.specify/memory/constitution.md`

**Note**: This spec is part of the OpenDiscuss system. All implementation must comply with constitutional principles (Temporal Transparency, Semantic Accuracy, Intent Fidelity, Representation Not Adjudication).
