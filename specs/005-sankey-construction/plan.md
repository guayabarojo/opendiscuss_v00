# Implementation Plan: Temporal Sankey Construction Protocol

**Branch**: `005-sankey-construction` | **Date**: 2026-01-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-sankey-construction/spec.md`

## Summary

The Temporal Sankey Construction Protocol transforms cluster data from Spec 4 into a multi-column visual representation showing participant movement across rounds. It constructs nodes from thought spaces, computes edges from actual participant transitions, and handles dropout naturally through flow mass shrinkage (Option A). The implementation requires graph construction algorithms, participant tracking across rounds, and integration with alignment metadata for visual continuity.

## Technical Context

**Language/Version**: Python 3.11+ (async computation for parallel edge processing)
**Primary Dependencies**: FastAPI (API layer), PostgreSQL (cluster data queries), Pydantic (SankeyGraph validation), NetworkX (graph structure validation)
**Storage**: PostgreSQL for cluster assignments, participant movements, generated SankeyGraph artifacts; read-only access to Spec 4 cluster data
**Testing**: pytest with property-based testing for invariants (edge totals, percentage sums), synthetic round datasets for movement accuracy
**Target Platform**: Linux server (containerized deployment)
**Project Type**: Web application (backend graph construction + frontend Sankey rendering)
**Performance Goals**: Complete Sankey construction for 100 participants across 5 rounds in <3 seconds; discussion report generation <5 seconds
**Constraints**: <200ms p95 for Sankey data retrieval; 100% edge accuracy (matches participant movement); deterministic construction (same input = same output)
**Scale/Scope**: Support up to 100 participants per discussion, 10 rounds max per discussion, 1000 edges max per discussion

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Validate compliance with `.specify/memory/constitution.md`:

- [x] **Parallel-First Architecture**: Sankey visualizes output of parallel rounds; no threading/replies introduced
- [x] **Intent Fidelity**: Uses only approved summaries via Spec 4 cluster data; no additional interpretation
- [x] **Semantic Accuracy Over Aesthetics**: Preserves all clusters as nodes (no merging); minority clusters fully visible
- [x] **Temporal Transparency**: Edges computed strictly from participant movement; natural dropout via flow mass shrinkage (Option A)
- [x] **Community-Bounded Context**: Sankey scoped to single discussion within community; no cross-community flows
- [x] **Synchronous Deliberation**: Visualizes synchronous round progression; no async constructs
- [x] **Representation Not Adjudication**: Pure visualization artifact; no voting/ranking/convergence signals
- [x] **MVP Boundaries**: Discussion reports only; no historical comparison, no decision mechanisms, no private spaces
- [x] **Complexity Justified**: Graph construction complexity required for movement-based edge computation and alignment integration

**Violations**: None

## Project Structure

### Documentation (this feature)

```text
specs/005-sankey-construction/
├── plan.md              # This file
├── research.md          # Phase 0 output: Graph algorithms, dropout handling, alignment integration
├── data-model.md        # Phase 1 output: SankeyGraph, Column, Node, Edge entities
├── quickstart.md        # Phase 1 output: Developer setup guide for Sankey construction
├── contracts/           # Phase 1 output: OpenAPI specs for Sankey endpoints
│   ├── sankey-api.yaml          # Sankey construction and retrieval
│   ├── report-api.yaml          # Discussion report generation
│   └── sankey-data-contract.yaml # SankeyGraph JSON schema
└── tasks.md             # Phase 2 output: Implementation task breakdown
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── sankey_graph.py       # SankeyGraph entity (columns, nodes, edges)
│   │   ├── sankey_column.py      # Column entity (round representation)
│   │   ├── sankey_node.py        # Node entity (thought space representation)
│   │   ├── sankey_edge.py        # Edge entity (movement flow)
│   │   └── discussion_report.py  # DiscussionReport entity (Sankey + statistics)
│   ├── services/
│   │   ├── sankey_builder.py     # Core graph construction logic
│   │   ├── node_builder.py       # Node creation from cluster data
│   │   ├── edge_builder.py       # Edge computation from participant movement
│   │   ├── movement_tracker.py   # Participant assignment tracking across rounds
│   │   ├── dropout_handler.py    # Option A dropout behavior (natural shrinkage)
│   │   ├── alignment_integrator.py # Display group metadata integration
│   │   └── report_generator.py   # Discussion report assembly
│   ├── api/
│   │   ├── sankey_routes.py      # Sankey construction and retrieval endpoints
│   │   └── report_routes.py      # Discussion report generation endpoints
│   └── validators/
│       ├── sankey_invariants.py  # Percentage sums, edge totals, coverage validation
│       └── graph_validator.py    # Graph structure correctness checks
├── tests/
│   ├── contract/                 # Integration with Spec 4 cluster data
│   │   ├── test_cluster_to_node_conversion.py
│   │   ├── test_alignment_metadata_integration.py
│   │   └── test_sankey_to_report_handoff.py
│   ├── integration/              # End-to-end Sankey construction tests
│   │   ├── test_single_round_sankey.py
│   │   ├── test_multi_round_movement.py
│   │   ├── test_dropout_natural_shrinkage.py
│   │   └── test_report_generation.py
│   └── unit/                     # Node/edge builder, movement tracker tests
│       ├── test_node_builder.py
│       ├── test_edge_builder.py
│       ├── test_movement_tracker.py
│       ├── test_dropout_handler.py
│       └── test_sankey_invariants.py

frontend/
├── src/
│   ├── components/
│   │   ├── SankeyDiagram/        # Sankey visualization component (D3.js or similar)
│   │   ├── SankeyNode/           # Node rendering (width, label, color)
│   │   ├── SankeyEdge/           # Edge rendering (flow paths, widths)
│   │   └── DiscussionReport/     # Full report display (Sankey + stats)
│   ├── pages/
│   │   ├── SankeyView.tsx        # Standalone Sankey viewer
│   │   └── ReportView.tsx        # Discussion report page
│   └── services/
│       ├── sankeyApi.ts          # API client for Sankey endpoints
│       └── reportApi.ts          # API client for report endpoints
└── tests/
    └── e2e/                      # Cypress end-to-end visualization tests
        ├── sankey_rendering.cy.ts
        └── report_export.cy.ts
```

**Structure Decision**: Web application structure (Option 2) selected because Sankey construction requires both backend graph algorithms (node/edge computation, movement tracking, invariant validation) and frontend visualization (rendering the Sankey diagram with proportional widths, colors, labels). Backend handles all graph logic; frontend provides interactive Sankey display and report export.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| None | N/A | N/A |
