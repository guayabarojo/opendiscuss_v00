# OpenDiscuss v00 - Priority TODO List

**Last Updated**: 2026-02-05
**Branch**: 004-clustering-alignment

---

## 🔴 CRITICAL - Must Complete for MVP

### 1. Implement Spec 005: Sankey Construction (84 tasks)
**Status**: NOT STARTED
**Estimated Effort**: 4-5 weeks
**Blocking**: Discussion rounds cannot complete without Sankey visualization

**Why This is Critical:**
- Discussion Protocol expects `sankey.complete` event to advance rounds
- Question Progression listens for `sankey.complete` to trigger auto-generation
- Core value proposition: visualizing participant movement across rounds
- Frontend has SankeyDiagram component stub waiting for backend data

**Recommended Approach - MVP First (42 tasks in 3 weeks):**

#### Week 1: Setup & Foundation (18 tasks)
```bash
# Backend Structure
- Create backend/src/services/sankey/ directory
  - sankey_builder.py
  - node_builder.py
  - edge_builder.py
  - movement_tracker.py
  - dropout_handler.py
  - alignment_integrator.py
  - report_generator.py

# Models
- Create backend/src/models/sankey_node.py
- Create backend/src/models/sankey_edge.py
- Create backend/src/models/sankey_column.py
- Create backend/src/models/sankey_graph.py
- Create backend/src/models/discussion_report.py

# Validators
- Create backend/src/validators/sankey_invariants.py
- Create backend/src/validators/graph_validator.py

# Database
- Create migration for sankey_graphs table (JSONB storage)
- Add indexes on discussion_id, created_at

# Dependencies
- Add to requirements.txt: networkx, d3 (if using Python D3)
```

#### Week 2: User Story 1 - Multi-Column Sankey (14 tasks)
```bash
# Backend Services
- Implement load_cluster_data() - fetch from Spec 4
- Implement create_node_from_cluster() - convert cluster to Node
- Implement build_column() - create Column with percentage validation
- Implement build_sankey_graph() - assemble full SankeyGraph
- Implement validate_percentage_sum() - ensure 1.0 ± 0.0001

# API Endpoints
- POST /api/v1/sankey/construct
  - Trigger Sankey construction workflow
  - Persist to sankey_graphs table
  - Emit sankey.complete event
- GET /api/v1/sankey/{discussion_id}
  - Retrieve SankeyGraph from database

# Frontend Components
- Implement SankeyDiagram.tsx with D3.js
  - Multi-column layout
  - Node rendering with proportional widths
  - Column labels and round indicators
- Implement SankeyNode.tsx
  - Node box with label
  - Width based on user_pct
  - Hover tooltip
```

#### Week 3: User Story 2 - Movement-Based Edges (10 tasks)
```bash
# Backend Services
- Implement get_participant_assignments() - fetch from Spec 4
- Implement track_movement() - compute transitions
- Implement aggregate_movements() - count participants per flow
- Implement create_edge() - convert movement to Edge entity
- Implement validate_edge_totals() - verify counts

# Frontend Components
- Implement SankeyEdge.tsx
  - Flow path rendering with Bézier curves
  - Width proportional to user_count
  - Color from source cluster
- Update SankeyDiagram.tsx
  - Render edges between columns
  - Positioning and curvature
```

#### Week 4: User Stories 3-5 + Integration
```bash
# US3: Dropout Handling (6 tasks)
- Implement compute_user_intersection()
- Update track_movement() to filter continuing users only
- Add validation: no synthetic "dropout" nodes

# US4: Alignment Metadata (7 tasks)
- Implement fetch_alignment_metadata()
- Integrate display_group_id into nodes
- Frontend: use display_group_id for stable colors

# US5: Discussion Reports (12 tasks)
- Implement generate_cluster_summaries()
- Implement generate_dropout_curve()
- Implement generate_top_movements()
- Create DiscussionReport component
- Add JSON export functionality

# Event Integration
- Subscribe to clustering.complete event
- Emit sankey.complete event
- Test event flow: Spec 4 → Spec 5 → Spec 6
```

#### Week 5: Testing & Polish
```bash
# Tests
- Unit tests for percentage validation
- Unit tests for edge computation
- Integration test: multi-round Sankey construction
- Integration test: dropout natural shrinkage
- Contract test: Spec 4 → Spec 5 data format
- Performance test: <3s for 100 participants

# Documentation
- API documentation
- Integration guide with Spec 4
- Frontend usage examples
```

**Files to Create:**
```
backend/src/models/
  - sankey_node.py
  - sankey_edge.py
  - sankey_column.py
  - sankey_graph.py
  - discussion_report.py

backend/src/services/sankey/
  - __init__.py
  - sankey_builder.py
  - node_builder.py
  - edge_builder.py
  - movement_tracker.py
  - dropout_handler.py
  - alignment_integrator.py
  - report_generator.py

backend/src/validators/
  - sankey_invariants.py
  - graph_validator.py

backend/src/api/routes/
  - sankey_routes.py
  - report_routes.py

backend/alembic/versions/
  - 014_create_sankey_graphs.py

frontend/src/components/SankeyDiagram/
  - SankeyDiagram.tsx (complete implementation)
  - SankeyNode.tsx
  - SankeyEdge.tsx
  - SankeyColumn.tsx
  - styles.css

frontend/src/components/DiscussionReport/
  - DiscussionReport.tsx
  - ClusterSummaries.tsx
  - DropoutCurve.tsx
  - TopMovements.tsx

frontend/src/services/
  - sankeyApi.ts
  - reportApi.ts

backend/tests/unit/
  - test_sankey_invariants.py
  - test_graph_validator.py

backend/tests/integration/
  - test_sankey_construction.py
  - test_dropout_natural_shrinkage.py

backend/tests/contract/
  - test_cluster_to_sankey.py

backend/tests/performance/
  - test_sankey_performance.py
```

---

## 🟡 HIGH - Complete Before Production

### 2. Finish Spec 002: Input Collection (3 tasks)
**Status**: 87/90 complete (97%)
**Estimated Effort**: 2-3 days

#### T044: Implement thread-safe rate limiter
```python
# File: backend/src/services/rate_limiter.py
import threading
from collections import defaultdict

class RateLimiter:
    def __init__(self):
        self._locks = defaultdict(threading.Lock)
        self._counts = defaultdict(int)

    def check_and_increment_rate_limit(
        self, participant_id: str, round_id: str, max_allowed: int
    ) -> bool:
        key = f"{participant_id}:{round_id}"
        with self._locks[key]:
            if self._counts[key] >= max_allowed:
                return False
            self._counts[key] += 1
            return True
```

#### T063: Enhanced window violation errors
```python
# File: backend/src/api/routes/submissions.py
# Add to window violation error response:
{
    "error": "OUTSIDE_WINDOW",
    "message": "Submission window has closed",
    "window_start": "2026-02-05T14:00:00Z",
    "window_end": "2026-02-05T14:05:00Z",
    "current_time": "2026-02-05T14:06:23Z",
    "status": "AFTER_WINDOW"
}
```

#### T064: Participant submission history endpoint
```python
# File: backend/src/api/routes/submissions.py
@router.get("/participants/{participant_id}/submissions")
async def get_participant_submissions(
    participant_id: str,
    db: Session = Depends(get_db)
):
    submissions = (
        db.query(SubmissionMetadata)
        .filter(SubmissionMetadata.participant_id == participant_id)
        .order_by(SubmissionMetadata.timestamp.desc())
        .all()
    )
    return {"submissions": submissions, "total_count": len(submissions)}
```

### 3. Finish Spec 004: Clustering & Alignment (3 tasks)
**Status**: 79/82 complete (96%)
**Estimated Effort**: 2-3 days

#### T077: Run quickstart validation scenarios
```bash
# Execute from specs/004-clustering-alignment/quickstart.md

# Scenario 1: Basic clustering
curl -X POST http://localhost:8000/api/v1/clusters/trigger \
  -H "Content-Type: application/json" \
  -d '{"round_id": "test-round-1", "force_recluster": false}'

# Scenario 2: Minority preservation
# Create test data with 18 majority + 2 minority summaries
# Verify 2 distinct thought spaces created

# Scenario 3: Cross-round alignment
# Cluster two rounds, run alignment
# Verify display_group_id assigned without changing membership
```

#### T081: Fix Pydantic deprecations (14 files)
```bash
# Find and replace across backend/src/
# .dict() → .model_dump()
# .parse_obj() → .model_validate()
# .schema() → .model_json_schema()

# Files to update:
backend/src/models/alignment.py
backend/src/models/cluster.py
backend/src/models/cluster_member.py
backend/src/models/embedding.py
backend/src/services/clustering_service.py
backend/src/services/alignment_service.py
# ... (14 files total)
```

#### T082: Final validation checklist
```bash
# Run full test suite
pytest backend/tests/ -v

# Validate success criteria SC-001 through SC-013
# Document results in VERIFICATION_CHECKLIST.md
```

---

## 🟢 MEDIUM - Production Readiness

### 4. Security Hardening (1 week)

#### JWT Authentication
```python
# Currently stubbed in api-spec.yaml securitySchemes
# Implement actual JWT validation

# File: backend/src/middleware/auth.py
- Add JWT token validation
- Add bearer token extraction
- Add role-based access control (host vs participant)
```

#### Input Sanitization
```python
# Review all API endpoints for:
- SQL injection prevention (already using SQLAlchemy ORM ✓)
- XSS prevention in text fields
- Path traversal prevention
- Command injection prevention
```

#### Rate Limiting
```python
# Add API-level rate limiting
# File: backend/src/middleware/rate_limit.py
- Per-IP rate limiting
- Per-user rate limiting
- Sliding window algorithm
```

### 5. Documentation (3-4 days)

#### API Documentation
```bash
# File: backend/docs/api_documentation.md
- Document all 50+ endpoints
- Add curl examples
- Add response schemas
- Add error codes reference
```

#### Deployment Guide
```bash
# File: DEPLOYMENT.md
- Docker Compose setup
- Environment variables
- Database migrations
- Monitoring setup
- Backup strategy
```

#### User Guides
```bash
# File: docs/user-guide-host.md
- Creating discussions
- Managing rounds
- Reviewing results

# File: docs/user-guide-participant.md
- Joining discussions
- Submitting input (text/voice)
- Approving summaries
```

### 6. Observability (3-4 days)

#### Metrics Export
```python
# File: backend/src/telemetry.py
- Add Prometheus metrics export
- Track: request latency, error rates, LLM call latency
- Track: clustering time, participant counts
```

#### Dashboards
```yaml
# File: monitoring/grafana-dashboards.json
- System health dashboard
- Discussion metrics dashboard
- Performance metrics dashboard
```

#### Error Tracking
```python
# File: backend/src/logging_config.py
- Add Sentry integration
- Add error fingerprinting
- Add breadcrumb tracking
```

---

## 🔵 LOW - Nice-to-Have

### 7. Performance Optimization

- Database query optimization with EXPLAIN ANALYZE
- Connection pooling tuning
- Redis caching strategy review
- Frontend bundle size optimization (currently ~2MB)

### 8. Testing Improvements

- Increase test coverage to >80% (currently ~70%)
- Add load testing scripts (100+ concurrent participants)
- Add chaos engineering tests
- Add visual regression testing for Sankey diagrams

### 9. Developer Experience

- Hot reload for backend development
- Docker Compose for local development (partially exists)
- CI/CD pipeline setup (GitHub Actions)
- Pre-commit hooks for linting

---

## Quick Reference: Implementation Priorities

1. **Weeks 1-5**: Implement Spec 005 (Sankey Construction) - CRITICAL BLOCKER
2. **Week 6**: Complete Spec 002 and Spec 004 remaining tasks - HIGH PRIORITY
3. **Weeks 7-8**: Security hardening and documentation - MEDIUM PRIORITY
4. **Weeks 9-10**: Observability and performance optimization - LOW PRIORITY

**Total Time to Production-Ready**: 8-10 weeks

---

## Daily Checklist for Spec 005 Implementation

### Day 1-2: Setup
- [ ] Create backend/src/services/sankey/ directory structure
- [ ] Create Pydantic models (Node, Edge, Column, SankeyGraph)
- [ ] Create database migration for sankey_graphs table
- [ ] Add NetworkX to requirements.txt

### Day 3-4: Foundation
- [ ] Implement sankey_invariants.py validators
- [ ] Implement graph_validator.py
- [ ] Create API client for Spec 4 cluster data
- [ ] Write unit tests for validators

### Day 5-7: User Story 1 (Nodes)
- [ ] Implement load_cluster_data()
- [ ] Implement create_node_from_cluster()
- [ ] Implement build_column()
- [ ] Implement build_sankey_graph()
- [ ] Implement POST /api/v1/sankey/construct

### Day 8-9: User Story 1 (Frontend)
- [ ] Implement SankeyDiagram.tsx with D3.js
- [ ] Implement SankeyNode.tsx
- [ ] Test multi-column rendering

### Day 10-12: User Story 2 (Edges)
- [ ] Implement get_participant_assignments()
- [ ] Implement track_movement()
- [ ] Implement aggregate_movements()
- [ ] Implement create_edge()
- [ ] Implement SankeyEdge.tsx

### Day 13-15: User Stories 3-5
- [ ] Implement dropout handling
- [ ] Integrate alignment metadata
- [ ] Implement report generation
- [ ] Create DiscussionReport component

### Day 16-20: Testing & Integration
- [ ] Write integration tests
- [ ] Write contract tests
- [ ] Performance testing
- [ ] Event bus integration (sankey.complete)
- [ ] End-to-end testing

---

## Contact & Support

For questions about implementation:
- See `CLAUDE.md` for development guidelines
- See `IMPLEMENTATION_STATUS_REPORT.md` for detailed status
- See spec files in `specs/` for detailed requirements

---

*Last Updated: 2026-02-05*
*Priority: Spec 005 (Sankey Construction) is CRITICAL PATH*
