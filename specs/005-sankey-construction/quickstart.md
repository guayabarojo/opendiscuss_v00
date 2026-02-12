# Quickstart: Temporal Sankey Construction Protocol

**Spec**: 005-sankey-construction
**Date**: 2026-01-29
**Audience**: Backend developers implementing Sankey construction

## Overview

This guide walks through setting up the Sankey construction service, understanding the data flow from Spec 4 cluster data to rendered Sankey diagram, and running your first Sankey construction.

---

## Prerequisites

1. **Cluster Data Available**: Spec 4 (Clustering & Alignment) must be implemented and have generated cluster data for at least one discussion
2. **Development Environment**: Python 3.11+, PostgreSQL, Redis running locally
3. **Dependencies**: FastAPI, Pydantic, SQLAlchemy, pytest

---

## Installation

```bash
# From repository root
cd backend

# Install dependencies (assuming pyproject.toml or requirements.txt exists)
pip install -r requirements.txt

# Run migrations to create sankey_graphs table
alembic upgrade head

# Verify setup
pytest tests/contract/test_cluster_to_node_conversion.py -v
```

---

## Data Flow

```text
1. Input: Cluster Data from Spec 4
   - Per-round cluster assignments (user_id → cluster_id)
   - Cluster metadata (label_summary, user_count, display_group_id)

2. Node Construction (NodeBuilder)
   - Creates Node entity for each cluster
   - Computes user_pct relative to round total
   - Includes display_group_id if present

3. Movement Tracking (MovementTracker)
   - Computes user intersection between adjacent rounds
   - Builds dictionaries: user_id → cluster_id per round
   - Tracks transitions: (from_cluster, to_cluster) → user_count

4. Edge Construction (EdgeBuilder)
   - Creates Edge entity for each transition
   - Computes optional derived metrics (pct_of_from, pct_of_to)

5. Graph Assembly (SankeyBuilder)
   - Assembles SankeyGraph with columns and edges
   - Runs SankeyInvariantsValidator
   - Persists to database as JSONB

6. Report Generation (ReportGenerator)
   - Derives cluster summaries, dropout curve, top movements
   - Assembles DiscussionReport
   - Exports to JSON
```

---

## Quick Example: Constructing a Sankey

### Step 1: Fetch Cluster Data

```python
from backend.src.services.sankey_builder import SankeyBuilder

# Assume discussion_id is known
discussion_id = "550e8400-e29b-41d4-a716-446655440000"

# Fetch cluster data from Spec 4 (example pseudocode)
cluster_data = fetch_cluster_data(discussion_id)

# cluster_data structure:
# {
#   "rounds": [1, 2, 3],
#   "cluster_assignments": {
#     1: [
#       {"user_id": "u1", "cluster_id": "cluster_1", "label_summary": "Remote work", ...},
#       {"user_id": "u2", "cluster_id": "cluster_1", ...},
#       {"user_id": "u3", "cluster_id": "cluster_2", "label_summary": "Office-first", ...}
#     ],
#     2: [...],
#     3: [...]
#   }
# }
```

### Step 2: Construct Sankey

```python
from backend.src.services.sankey_builder import SankeyBuilder

builder = SankeyBuilder()

# Build Sankey graph
sankey_graph = builder.build(
    discussion_id=discussion_id,
    cluster_data=cluster_data,
    include_alignment=True,  # Include display_group_id metadata
    include_derived_metrics=True  # Compute pct_of_from, pct_of_to
)

# sankey_graph is a SankeyGraph Pydantic model
print(f"Constructed Sankey with {len(sankey_graph.columns)} columns and {len(sankey_graph.edges)} edges")
```

### Step 3: Validate Invariants

```python
from backend.src.validators.sankey_invariants import SankeyInvariantsValidator

validator = SankeyInvariantsValidator()

# Validate (raises exception if any invariant violated)
try:
    validator.validate(sankey_graph)
    print("✓ All invariants passed")
except ValidationError as e:
    print(f"✗ Validation failed: {e.violations}")
```

### Step 4: Persist to Database

```python
from backend.src.models.sankey_graph import SankeyGraph
from backend.src.database import session

# Serialize to JSON
sankey_json = sankey_graph.model_dump_json()

# Store in database (JSONB column)
db_record = SankeyGraphRecord(
    id=uuid.uuid4(),
    discussion_id=discussion_id,
    graph_data=sankey_json,
    created_at=datetime.utcnow()
)
session.add(db_record)
session.commit()

print(f"✓ Sankey persisted: {db_record.id}")
```

### Step 5: Generate Report

```python
from backend.src.services.report_generator import ReportGenerator

report_gen = ReportGenerator()

# Generate discussion report
report = report_gen.generate(
    sankey_graph=sankey_graph,
    top_movements_count=5  # Top 5 movements per round transition
)

# report is a DiscussionReport Pydantic model
print(f"✓ Report generated with {len(report.cluster_summaries)} round summaries")

# Export to JSON
report_json = report.model_dump_json(indent=2)
with open(f"report_{discussion_id}.json", "w") as f:
    f.write(report_json)
```

---

## API Usage

### Construct Sankey via API

```bash
# POST to construct Sankey
curl -X POST http://localhost:8000/api/v1/discussions/550e8400-e29b-41d4-a716-446655440000/sankey \
  -H "Content-Type: application/json" \
  -d '{
    "include_alignment": true,
    "include_derived_metrics": true
  }'

# Response: 201 Created with SankeyGraph JSON
```

### Retrieve Sankey

```bash
# GET to retrieve existing Sankey
curl http://localhost:8000/api/v1/discussions/550e8400-e29b-41d4-a716-446655440000/sankey

# Response: 200 OK with SankeyGraph JSON
```

### Generate Report

```bash
# POST to generate report
curl -X POST http://localhost:8000/api/v1/discussions/550e8400-e29b-41d4-a716-446655440000/report \
  -H "Content-Type: application/json" \
  -d '{
    "top_movements_count": 5
  }'

# Response: 201 Created with DiscussionReport JSON
```

### Export Report

```bash
# GET to export report
curl http://localhost:8000/api/v1/discussions/550e8400-e29b-41d4-a716-446655440000/report/export?format=json \
  -o report.json

# Response: 200 OK with JSON file download
```

---

## Testing Strategy

### Unit Tests

Test individual components in isolation:

```python
# tests/unit/test_node_builder.py
def test_node_builder_creates_nodes_from_clusters():
    clusters = [
        {"cluster_id": "c1", "label_summary": "Remote work", "user_count": 15, ...},
        {"cluster_id": "c2", "label_summary": "Office-first", "user_count": 10, ...}
    ]

    node_builder = NodeBuilder()
    nodes = node_builder.build_nodes(round_index=1, clusters=clusters)

    assert len(nodes) == 2
    assert nodes[0].node_id == "n_r1_c1"
    assert nodes[0].user_pct == 0.60  # 15 / 25
    assert nodes[1].user_pct == 0.40  # 10 / 25
```

### Contract Tests

Validate integration with Spec 4:

```python
# tests/contract/test_cluster_to_node_conversion.py
def test_cluster_data_converts_to_nodes_correctly():
    # Fetch real cluster data from Spec 4 implementation
    cluster_data = spec4_client.fetch_cluster_data(discussion_id)

    # Build Sankey
    sankey_graph = builder.build(discussion_id, cluster_data)

    # Verify all clusters become nodes
    for round_idx in cluster_data["rounds"]:
        spec4_clusters = cluster_data["cluster_assignments"][round_idx]
        sankey_nodes = [col.nodes for col in sankey_graph.columns if col.round_index == round_idx][0]

        assert len(sankey_nodes) == len(spec4_clusters)
```

### Integration Tests

End-to-end Sankey construction:

```python
# tests/integration/test_multi_round_movement.py
def test_three_round_sankey_with_dropout():
    # Create synthetic discussion with known movements
    discussion = create_test_discussion(rounds=3, participants=30)

    # Round 1: 30 users in 3 clusters (10, 15, 5)
    # Round 2: 28 users in 2 clusters (18, 10) - 2 dropouts
    # Round 3: 25 users in 2 clusters (15, 10) - 3 more dropouts

    # Build Sankey
    sankey_graph = builder.build(discussion.id, cluster_data)

    # Validate edge totals match dropout behavior
    r1_to_r2_edges = [e for e in sankey_graph.edges if e.from_round_index == 1]
    assert sum(e.user_count for e in r1_to_r2_edges) == 28  # 30 - 2 dropouts

    r2_to_r3_edges = [e for e in sankey_graph.edges if e.from_round_index == 2]
    assert sum(e.user_count for e in r2_to_r3_edges) == 25  # 28 - 3 dropouts
```

### Property-Based Tests

Use Hypothesis to validate invariants:

```python
# tests/unit/test_sankey_invariants.py
from hypothesis import given, strategies as st

@given(st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=10))
def test_percentage_sum_invariant(user_pcts):
    # Normalize to sum to 1.0
    total = sum(user_pcts)
    normalized = [pct / total for pct in user_pcts]

    # Create nodes with normalized percentages
    nodes = [Node(..., user_pct=pct) for pct in normalized]
    column = Column(round_index=1, nodes=nodes)

    # Validate
    validator = SankeyInvariantsValidator()
    assert validator.check_percentage_sum(column)  # Should pass
```

---

## Debugging Common Issues

### Issue 1: Percentage Sum Doesn't Equal 1.0

**Symptom**: ValidationError with "PercentageSum" invariant violation

**Cause**: Floating-point rounding errors in user_pct calculation

**Solution**: Use tolerance check (±0.0001) instead of exact equality:

```python
def check_percentage_sum(column: Column) -> bool:
    total = sum(node.user_pct for node in column.nodes)
    return abs(total - 1.0) < 0.0001  # Tolerance: 0.01%
```

### Issue 2: Edge Totals Exceed User Intersection

**Symptom**: ValidationError with "EdgeTotal" invariant violation

**Cause**: Double-counting users or incorrect intersection computation

**Solution**: Verify user intersection logic:

```python
def compute_user_intersection(round_r_users: Set[str], round_r1_users: Set[str]) -> Set[str]:
    return round_r_users & round_r1_users  # Set intersection

# Edge totals must match intersection size
continuing_users = compute_user_intersection(r1_users, r2_users)
edge_total = sum(e.user_count for e in r1_to_r2_edges)
assert edge_total == len(continuing_users)
```

### Issue 3: Missing Alignment Metadata

**Symptom**: display_group_id is null for all nodes

**Cause**: Spec 4 alignment not run, or include_alignment=False

**Solution**: Verify Spec 4 alignment was executed and pass include_alignment=True:

```python
sankey_graph = builder.build(
    discussion_id=discussion_id,
    cluster_data=cluster_data,
    include_alignment=True  # Enable alignment metadata
)
```

### Issue 4: Dropout Not Visible in Sankey

**Symptom**: Flow mass doesn't shrink across rounds despite dropouts

**Cause**: Incorrect per-round normalization (cross-round normalization applied)

**Solution**: Ensure user_pct is computed relative to round total, not global total:

```python
# CORRECT: Per-round normalization
round_total = sum(c.user_count for c in round_clusters)
for cluster in round_clusters:
    node.user_pct = cluster.user_count / round_total

# INCORRECT: Cross-round normalization (hides dropout)
global_total = max(sum(...) for round in all_rounds)  # DO NOT USE
```

---

## Next Steps

1. **Implement Frontend Visualization**: Use D3.js or similar to render Sankey diagram
2. **Add Real-Time Updates**: Stream Sankey updates as rounds complete (post-MVP)
3. **Export to PDF**: Generate PDF reports with embedded Sankey visualization (post-MVP)
4. **Performance Optimization**: Profile edge computation for discussions with 100+ participants

---

## Resources

- **Spec Document**: [spec.md](./spec.md)
- **Data Model**: [data-model.md](./data-model.md)
- **OpenAPI Contracts**: [contracts/](./contracts/)
- **Research Decisions**: [research.md](./research.md)
- **Spec 4 (Clustering)**: [../004-clustering-alignment/](../004-clustering-alignment/)

---

## Support

For questions or issues:
1. Check [data-model.md](./data-model.md) for entity definitions
2. Review [research.md](./research.md) for design rationale
3. Run contract tests to validate Spec 4 integration
4. Check invariant violations in ValidationError details
