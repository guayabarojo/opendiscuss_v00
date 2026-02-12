# Data Model: Temporal Sankey Construction Protocol

**Phase**: 1 (Design)
**Date**: 2026-01-29
**Status**: Complete

## Overview

This document defines the canonical data entities for the Sankey Construction Protocol. All entities are designed to be serializable to JSON for API responses and storage. The model prioritizes clarity, type safety (via Pydantic), and direct mapping to the spec's functional requirements.

---

## Core Entities

### 1. SankeyGraph

The complete multi-column Sankey diagram representation for a discussion.

**Purpose**: Top-level container for all Sankey visualization data. Immutable once constructed.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `discussion_id` | `str` | Yes | Unique identifier for the discussion |
| `rounds` | `List[int]` | Yes | Ordered list of round indices (e.g., [1, 2, 3]) |
| `columns` | `List[Column]` | Yes | Ordered list of columns (one per round) |
| `edges` | `List[Edge]` | Yes | List of all flows between adjacent columns |
| `created_at` | `datetime` | Yes | Timestamp when Sankey was constructed |
| `metadata` | `Dict[str, Any]` | No | Optional metadata (e.g., construction time, version) |

**Relationships**:
- Has many `Column` (one per round with clusters)
- Has many `Edge` (flows between columns)
- Belongs to one `Discussion` (from Spec 1)

**Invariants**:
- `len(columns)` must equal `len(rounds)`
- Each `column.round_index` must be in `rounds` list
- All edges reference valid column round indices
- Immutable after construction (no updates allowed)

**Example JSON**:
```json
{
  "discussion_id": "disc_abc123",
  "rounds": [1, 2, 3],
  "columns": [
    {
      "round_index": 1,
      "nodes": [...]
    },
    {
      "round_index": 2,
      "nodes": [...]
    },
    {
      "round_index": 3,
      "nodes": [...]
    }
  ],
  "edges": [...],
  "created_at": "2026-01-29T15:30:00Z",
  "metadata": {
    "construction_time_ms": 250,
    "total_participants": 50
  }
}
```

---

### 2. Column

A vertical section of the Sankey representing one round's thought spaces.

**Purpose**: Groups all nodes (thought spaces) for a single round. Provides round-level metadata.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `round_index` | `int` | Yes | 1-based round number (1, 2, 3, ...) |
| `nodes` | `List[Node]` | Yes | All thought space nodes for this round |
| `total_participants` | `int` | No | Derived: sum of node user_counts |

**Relationships**:
- Belongs to one `SankeyGraph`
- Has many `Node` (thought spaces in this round)
- Corresponds to one `Round` (from Spec 1)

**Invariants**:
- `sum(node.user_pct for node in nodes)` must equal 1.0 (±0.0001 rounding tolerance)
- All `node.cluster_id` values must be unique within the column
- `total_participants` must match sum of `node.user_count` values

**Example JSON**:
```json
{
  "round_index": 2,
  "nodes": [
    {
      "node_id": "n_r2_c8",
      "cluster_id": "cluster_8",
      "label_summary": "Hybrid work model with 2-3 days in office",
      "user_count": 15,
      "user_pct": 0.50,
      "display_group_id": "dg_12"
    },
    {
      "node_id": "n_r2_c9",
      "cluster_id": "cluster_9",
      "label_summary": "Full remote work for all roles",
      "user_count": 10,
      "user_pct": 0.33,
      "display_group_id": "dg_15"
    },
    {
      "node_id": "n_r2_c10",
      "cluster_id": "cluster_10",
      "label_summary": "Office-first policy with remote exceptions",
      "user_count": 5,
      "user_pct": 0.17,
      "display_group_id": null
    }
  ],
  "total_participants": 30
}
```

---

### 3. Node

A visual element representing a thought space (cluster) in a column.

**Purpose**: Represents one cluster from Spec 4 as a Sankey node. Carries participant count and label for visualization.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `node_id` | `str` | Yes | Unique node identifier (e.g., "n_r2_c8" = round 2, cluster 8) |
| `cluster_id` | `str` | Yes | Cluster ID from Spec 4 (maps to ThoughtSpace) |
| `label_summary` | `str` | Yes | Exact label from Spec 4 (medoid summary text) |
| `user_count` | `int` | Yes | Number of participants in this thought space |
| `user_pct` | `float` | Yes | Percentage of round's total participants (0.0 to 1.0) |
| `display_group_id` | `str` | No | Optional alignment group ID from Spec 4 (for color continuity) |

**Relationships**:
- Belongs to one `Column`
- Corresponds to one `ThoughtSpace` (from Spec 4)
- Source or target of many `Edge` (flows in/out)

**Invariants**:
- `user_count` must be ≥ 1 (at least one participant)
- `user_pct` must be in range (0.0, 1.0]
- `label_summary` must not be empty or null
- `node_id` must be unique across all columns in the SankeyGraph

**Derived Values**:
- Visual width proportional to `user_pct`
- Node color derived from `display_group_id` (if present) or `cluster_id` (fallback)

**Example JSON**:
```json
{
  "node_id": "n_r2_c8",
  "cluster_id": "cluster_8",
  "label_summary": "Hybrid work model with 2-3 days in office",
  "user_count": 15,
  "user_pct": 0.50,
  "display_group_id": "dg_12"
}
```

---

### 4. Edge (Flow)

A connection between nodes in adjacent columns representing participant movement.

**Purpose**: Represents the transition of participants from one thought space to another across rounds. Width reflects participant count.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_round_index` | `int` | Yes | Source round (e.g., 1) |
| `to_round_index` | `int` | Yes | Target round (e.g., 2) |
| `from_cluster_id` | `str` | Yes | Source cluster ID |
| `to_cluster_id` | `str` | Yes | Target cluster ID |
| `user_count` | `int` | Yes | Number of participants making this transition |
| `pct_of_from` | `float` | No | Optional: percentage of source cluster (user_count / from_node.user_count) |
| `pct_of_to` | `float` | No | Optional: percentage of target cluster (user_count / to_node.user_count) |

**Relationships**:
- Connects two `Node` entities (from and to)
- Source node is in `Column` with `round_index = from_round_index`
- Target node is in `Column` with `round_index = to_round_index`

**Invariants**:
- `to_round_index` must equal `from_round_index + 1` (adjacent rounds only)
- `user_count` must be ≥ 1 (at least one participant moved)
- `user_count` must be ≤ source node's `user_count`
- `user_count` must be ≤ target node's `user_count`
- For any round transition, `sum(edge.user_count for all edges from r to r+1)` must equal user intersection size

**Derived Values**:
- Visual flow width proportional to `user_count`
- Flow path curvature determined by node positions

**Example JSON**:
```json
{
  "from_round_index": 1,
  "to_round_index": 2,
  "from_cluster_id": "cluster_5",
  "to_cluster_id": "cluster_8",
  "user_count": 10,
  "pct_of_from": 0.67,
  "pct_of_to": 0.67
}
```

---

### 5. DiscussionReport

A comprehensive summary of the discussion including Sankey and statistics.

**Purpose**: Final deliverable artifact for participants. Combines Sankey visualization with interpretive statistics.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `discussion_id` | `str` | Yes | Unique identifier for the discussion |
| `sankey_graph` | `SankeyGraph` | Yes | Complete Sankey diagram data |
| `cluster_summaries` | `List[RoundClusterSummary]` | Yes | Per-round cluster summaries |
| `dropout_curve` | `List[DropoutPoint]` | Yes | Participant counts per round |
| `top_movements` | `List[TopMovement]` | Yes | Largest flows per round transition |
| `generated_at` | `datetime` | Yes | Timestamp when report was generated |
| `export_format` | `str` | Yes | Format version (e.g., "json-v1") |

**Relationships**:
- Belongs to one `Discussion` (from Spec 1)
- Contains one `SankeyGraph`
- Aggregates data from multiple `ThoughtSpace` entities (from Spec 4)

**Example JSON**:
```json
{
  "discussion_id": "disc_abc123",
  "sankey_graph": {
    "discussion_id": "disc_abc123",
    "rounds": [1, 2, 3],
    "columns": [...],
    "edges": [...]
  },
  "cluster_summaries": [
    {
      "round_index": 1,
      "clusters": [
        {"label": "Remote work flexibility", "user_count": 20},
        {"label": "Office-first culture", "user_count": 10}
      ]
    }
  ],
  "dropout_curve": [
    {"round_index": 1, "participant_count": 30},
    {"round_index": 2, "participant_count": 28},
    {"round_index": 3, "participant_count": 25}
  ],
  "top_movements": [
    {
      "from_round": 1,
      "to_round": 2,
      "movements": [
        {
          "from_label": "Remote work flexibility",
          "to_label": "Hybrid work model",
          "user_count": 12
        }
      ]
    }
  ],
  "generated_at": "2026-01-29T15:35:00Z",
  "export_format": "json-v1"
}
```

---

## Supporting Entities

### RoundClusterSummary

Summary of thought spaces for a single round.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `round_index` | `int` | Yes | Round number |
| `clusters` | `List[ClusterInfo]` | Yes | List of cluster labels and counts |

**Example JSON**:
```json
{
  "round_index": 2,
  "clusters": [
    {"label": "Hybrid work model", "user_count": 15},
    {"label": "Full remote work", "user_count": 10},
    {"label": "Office-first policy", "user_count": 5}
  ]
}
```

---

### ClusterInfo

Minimal cluster information for report summaries.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `label` | `str` | Yes | Cluster label summary |
| `user_count` | `int` | Yes | Number of participants |

---

### DropoutPoint

Participant count at a single round (for dropout curve).

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `round_index` | `int` | Yes | Round number |
| `participant_count` | `int` | Yes | Total participants in round |

**Example JSON**:
```json
{"round_index": 2, "participant_count": 28}
```

---

### TopMovement

Top movement edges for a round transition.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_round` | `int` | Yes | Source round |
| `to_round` | `int` | Yes | Target round |
| `movements` | `List[MovementDetail]` | Yes | Top N movements (default 5) |

**Example JSON**:
```json
{
  "from_round": 1,
  "to_round": 2,
  "movements": [
    {
      "from_label": "Remote work flexibility",
      "to_label": "Hybrid work model",
      "user_count": 12
    },
    {
      "from_label": "Office-first culture",
      "to_label": "Hybrid work model",
      "user_count": 8
    }
  ]
}
```

---

### MovementDetail

Details of a single movement flow.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_label` | `str` | Yes | Source cluster label |
| `to_label` | `str` | Yes | Target cluster label |
| `user_count` | `int` | Yes | Number of participants |

---

## Data Flow

```text
Input (from Spec 4):
  - Cluster assignments per round
  - Display group IDs (optional)
  - Participant assignments

Processing:
  1. NodeBuilder → Creates Node entities from clusters
  2. MovementTracker → Computes participant transitions
  3. EdgeBuilder → Creates Edge entities from transitions
  4. SankeyBuilder → Assembles SankeyGraph
  5. SankeyInvariantsValidator → Validates graph correctness
  6. ReportGenerator → Creates DiscussionReport

Output:
  - SankeyGraph (for visualization)
  - DiscussionReport (for export)
```

---

## Database Schema Notes

**Storage Approach**: Store `SankeyGraph` as JSONB in PostgreSQL for fast retrieval. No need to normalize into separate tables for MVP.

**Table**: `sankey_graphs`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `discussion_id` | UUID | Foreign key to discussions table |
| `graph_data` | JSONB | Complete SankeyGraph JSON |
| `created_at` | TIMESTAMP | Construction timestamp |
| `metadata` | JSONB | Optional metadata |

**Indexes**:
- `discussion_id` (unique) - Fast lookup by discussion
- `created_at` - Sorting by recency

**Rationale**: SankeyGraph is immutable and read-heavy. JSONB storage avoids complex joins and provides fast single-query retrieval. Normalization offers no benefit for this use case.

---

## Validation Rules

**Implemented in `SankeyInvariantsValidator`**:

1. **Percentage Sum Check**: For each column, `sum(node.user_pct) ≈ 1.0` (tolerance: 0.0001)

2. **Edge Total Check**: For each round transition (r, r+1), `sum(edge.user_count) == len(continuing_users)`

3. **Coverage Check**: Every participant in a round is assigned to exactly one node

4. **Determinism Check**: Same cluster assignments produce identical SankeyGraph (test-only)

---

## Pydantic Model Definitions

**Location**: `backend/src/models/`

**Key Models**:
- `SankeyGraph` (pydantic.BaseModel)
- `Column` (pydantic.BaseModel)
- `Node` (pydantic.BaseModel)
- `Edge` (pydantic.BaseModel)
- `DiscussionReport` (pydantic.BaseModel)

**Benefits**:
- Automatic validation on construction
- JSON serialization/deserialization
- Type hints for IDE support
- OpenAPI schema generation

---

## Next Steps

1. Implement Pydantic models in `backend/src/models/`
2. Define OpenAPI contracts in `contracts/` directory
3. Create example JSON fixtures for testing
4. Write unit tests for model validation rules
