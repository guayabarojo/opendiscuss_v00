"""
Sankey Builder Service - Assembles complete SankeyGraph from columns and edges

This module provides the main orchestration service for constructing Sankey diagrams.
It coordinates cluster data fetching, node building, column assembly, edge computation,
validation, and persistence.

Constitutional Compliance:
- Temporal Transparency: Preserves temporal ordering of rounds
- Semantic Accuracy: 100% participant coverage validation
- Representation Not Adjudication: Pure visualization artifact
"""

from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session_factory
from ..models.sankey_graph import SankeyGraph
from ..models.sankey_column import SankeyColumn
from ..models.sankey_edge import SankeyEdge
from ..services.cluster_api_client import ClusterAPIClient
from ..services.node_builder import build_columns_for_discussion
from ..services.movement_tracker import compute_movements_for_rounds
from ..services.edge_builder import build_edges_from_aggregated_movements
from ..validators.sankey_invariants import SankeyInvariantValidator
from ..validators.graph_validator import GraphStructureValidator

logger = logging.getLogger(__name__)


class SankeyBuilder:
    """
    Orchestrates Sankey diagram construction from cluster data.

    This service coordinates the entire construction pipeline:
    1. Fetch cluster data from Spec 004
    2. Build nodes and columns
    3. Compute edges (if multi-round)
    4. Validate all invariants
    5. Persist to database

    Methods:
        build_sankey_graph: Construct SankeyGraph for a discussion
        save_to_database: Persist SankeyGraph as JSONB
        load_from_database: Retrieve cached SankeyGraph
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize Sankey builder.

        Args:
            session: Database session for querying and persisting
        """
        self.session = session
        self.cluster_client = ClusterAPIClient(session)

    async def load_cluster_data(
        self,
        discussion_id: UUID,
        rounds: List[UUID]
    ) -> Dict[UUID, List]:
        """
        Fetch all cluster data for a discussion.

        Args:
            discussion_id: Discussion UUID
            rounds: List of round UUIDs in temporal order

        Returns:
            Dict mapping round_id to list of clusters with loaded relationships

        Raises:
            ValueError: If any round has no clusters

        Validates:
            FR-013: Every round has at least one cluster
        """
        logger.info(
            f"Loading cluster data for discussion {discussion_id}: {len(rounds)} rounds"
        )

        clusters_by_round = {}

        for round_id in rounds:
            clusters = await self.cluster_client.get_clusters_for_round(round_id)

            if not clusters:
                raise ValueError(
                    f"No clusters found for round {round_id} in discussion {discussion_id}"
                )

            clusters_by_round[round_id] = clusters

            logger.debug(
                f"Loaded {len(clusters)} clusters for round {round_id}"
            )

        total_clusters = sum(len(clusters) for clusters in clusters_by_round.values())
        logger.info(
            f"Cluster data loaded: {total_clusters} total clusters across {len(rounds)} rounds"
        )

        return clusters_by_round

    async def build_sankey_graph(
        self,
        discussion_id: UUID,
        rounds: List[UUID],
        include_alignment: bool = True
    ) -> SankeyGraph:
        """
        Build complete SankeyGraph for a discussion.

        Args:
            discussion_id: Discussion UUID from Spec 001
            rounds: List of round UUIDs in temporal order
            include_alignment: Include alignment metadata for visual continuity

        Returns:
            Complete SankeyGraph with columns, nodes, and edges (if multi-round)

        Raises:
            ValueError: If cluster data invalid or validation fails

        Validates:
            All success criteria (SC-001 through SC-013)

        Performance:
            Target <3s for 100 participants across 5 rounds (SC-001)

        Constitutional Compliance:
            - Temporal Transparency: Edges computed from actual movement
            - Semantic Accuracy: 100% participant coverage
            - Representation Not Adjudication: No filtering or ranking
        """
        start_time = time.time()

        logger.info(
            f"Starting Sankey construction for discussion {discussion_id}: "
            f"{len(rounds)} rounds, alignment={include_alignment}"
        )

        # Step 1: Load cluster data
        step_start = time.time()
        clusters_by_round = await self.load_cluster_data(discussion_id, rounds)
        load_time_ms = int((time.time() - step_start) * 1000)
        logger.info(f"Cluster data loaded in {load_time_ms}ms")

        # Step 2: Get alignment metadata if requested
        alignment_metadata = None
        if include_alignment:
            step_start = time.time()
            alignment_metadata = await self.cluster_client.get_alignment_metadata(
                discussion_id
            )
            alignment_time_ms = int((time.time() - step_start) * 1000)
            logger.info(
                f"Alignment metadata fetched in {alignment_time_ms}ms: "
                f"{len(alignment_metadata)} aligned clusters"
            )

        # Step 3: Build columns
        step_start = time.time()
        columns = await build_columns_for_discussion(
            discussion_id=discussion_id,
            rounds=rounds,
            clusters_by_round=clusters_by_round,
            alignment_metadata=alignment_metadata
        )
        build_columns_time_ms = int((time.time() - step_start) * 1000)
        logger.info(f"Columns built in {build_columns_time_ms}ms")

        # Step 4: Compute edges for multi-round discussions
        edges: List[SankeyEdge] = []
        compute_edges_time_ms = 0

        if len(rounds) > 1:
            step_start = time.time()
            logger.info(f"Computing edges for {len(rounds) - 1} round transitions")

            # Build node lookup by cluster_id for all columns
            nodes_by_cluster_id = {}
            for column in columns:
                for node in column.nodes:
                    nodes_by_cluster_id[node.cluster_id] = node

            # Compute edges for each adjacent round pair
            for i in range(len(rounds) - 1):
                from_round_id = rounds[i]
                to_round_id = rounds[i + 1]

                logger.debug(
                    f"Computing edges for round transition {i} → {i + 1} "
                    f"({from_round_id} → {to_round_id})"
                )

                # Track and aggregate participant movements
                aggregated_movements = await compute_movements_for_rounds(
                    from_round_id=from_round_id,
                    to_round_id=to_round_id,
                    cluster_client=self.cluster_client
                )

                # Build edges from aggregated movements
                round_edges = build_edges_from_aggregated_movements(
                    aggregated_movements=aggregated_movements,
                    from_round_index=i,
                    to_round_index=i + 1,
                    nodes_by_cluster_id=nodes_by_cluster_id,
                    compute_percentages=True
                )

                edges.extend(round_edges)

                logger.info(
                    f"Created {len(round_edges)} edges for round {i} → {i + 1}, "
                    f"total flow = {sum(e.user_count for e in round_edges)} participants"
                )

            compute_edges_time_ms = int((time.time() - step_start) * 1000)
            logger.info(
                f"Edge computation completed in {compute_edges_time_ms}ms: "
                f"{len(edges)} total edges"
            )
        else:
            logger.info("Single-round discussion, no edges to compute")

        # Step 5: Assemble SankeyGraph
        sankey_graph = SankeyGraph(
            discussion_id=discussion_id,
            rounds=rounds,
            columns=columns,
            edges=edges,
            created_at=datetime.utcnow(),
            metadata={
                "construction_time_ms": str(int((time.time() - start_time) * 1000)),
                "load_clusters_ms": str(load_time_ms),
                "build_columns_ms": str(build_columns_time_ms),
                "compute_edges_ms": str(compute_edges_time_ms),
                "alignment_included": str(include_alignment),
                "algorithm_version": "1.0",
                "phase": "US2_edges_added"
            }
        )

        logger.info(
            f"SankeyGraph assembled: {len(columns)} columns, "
            f"{sankey_graph.get_total_node_count()} total nodes, "
            f"{len(edges)} edges, "
            f"{sankey_graph.get_total_participants()} max participants"
        )

        # Step 6: Validate invariants
        step_start = time.time()
        await self.validate_sankey_graph(sankey_graph)
        validation_time_ms = int((time.time() - step_start) * 1000)
        logger.info(f"Validation completed in {validation_time_ms}ms")

        # Step 7: Update total construction time
        total_time_ms = int((time.time() - start_time) * 1000)
        sankey_graph.metadata["construction_time_ms"] = str(total_time_ms)

        logger.info(
            f"Sankey construction completed in {total_time_ms}ms "
            f"for discussion {discussion_id}"
        )

        # Check performance target (SC-001: <3s)
        if total_time_ms > 3000:
            logger.warning(
                f"Construction time {total_time_ms}ms exceeds 3s target (SC-001)"
            )

        return sankey_graph

    async def validate_sankey_graph(self, sankey_graph: SankeyGraph) -> None:
        """
        Validate all invariants for a SankeyGraph.

        Args:
            sankey_graph: SankeyGraph to validate

        Raises:
            ValueError: If any validation fails

        Validates:
            - All mathematical invariants (SankeyInvariantValidator)
            - All structural invariants (GraphStructureValidator)
        """
        logger.debug("Running invariant validation...")

        # Run invariant validations
        is_valid, invariant_errors = SankeyInvariantValidator.validate_all(
            sankey_graph
        )

        if not is_valid:
            error_summary = "\n".join(f"  - {err}" for err in invariant_errors)
            raise ValueError(
                f"Sankey invariant validation failed:\n{error_summary}"
            )

        # Run structural validations
        is_valid, structural_errors = GraphStructureValidator.validate_all(
            sankey_graph
        )

        if not is_valid:
            error_summary = "\n".join(f"  - {err}" for err in structural_errors)
            raise ValueError(
                f"Sankey structural validation failed:\n{error_summary}"
            )

        logger.info("All validations passed")

    async def save_to_database(self, sankey_graph: SankeyGraph) -> None:
        """
        Persist SankeyGraph to database as JSONB.

        Args:
            sankey_graph: SankeyGraph to persist

        Raises:
            Exception: If database operation fails

        Implementation:
            - Stores graph_data as JSONB for fast retrieval
            - Uses UPSERT for idempotency (same discussion_id)
            - Creates indexes on discussion_id and created_at
        """
        from ..models.sankey_graph_db import SankeyGraphDB

        logger.info(f"Persisting SankeyGraph for discussion {sankey_graph.discussion_id}")

        # Convert Pydantic model to JSON
        graph_json = sankey_graph.model_dump(mode='json')

        # Create or update database record
        stmt = select(SankeyGraphDB).where(
            SankeyGraphDB.discussion_id == sankey_graph.discussion_id
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing record
            existing.graph_data = graph_json
            existing.created_at = sankey_graph.created_at
            existing.graph_metadata = sankey_graph.metadata
            logger.info(
                f"Updated existing SankeyGraph for discussion {sankey_graph.discussion_id}"
            )
        else:
            # Create new record
            db_graph = SankeyGraphDB(
                discussion_id=sankey_graph.discussion_id,
                graph_data=graph_json,
                created_at=sankey_graph.created_at,
                graph_metadata=sankey_graph.metadata
            )
            self.session.add(db_graph)
            logger.info(
                f"Created new SankeyGraph for discussion {sankey_graph.discussion_id}"
            )

        await self.session.commit()
        logger.info("SankeyGraph persisted successfully")

    async def load_from_database(self, discussion_id: UUID) -> Optional[SankeyGraph]:
        """
        Retrieve cached SankeyGraph from database.

        Args:
            discussion_id: Discussion UUID

        Returns:
            SankeyGraph if found, None otherwise

        Performance:
            Target <100ms for retrieval (single database query)
        """
        from ..models.sankey_graph_db import SankeyGraphDB

        logger.debug(f"Loading SankeyGraph for discussion {discussion_id}")

        stmt = select(SankeyGraphDB).where(
            SankeyGraphDB.discussion_id == discussion_id
        )
        result = await self.session.execute(stmt)
        db_graph = result.scalar_one_or_none()

        if not db_graph:
            logger.info(f"No SankeyGraph found for discussion {discussion_id}")
            return None

        # Convert JSONB to Pydantic model
        sankey_graph = SankeyGraph(**db_graph.graph_data)

        logger.info(
            f"SankeyGraph loaded from database: {len(sankey_graph.columns)} columns, "
            f"{len(sankey_graph.edges)} edges"
        )

        return sankey_graph


async def get_sankey_builder() -> SankeyBuilder:
    """
    Factory function for SankeyBuilder.

    Returns:
        SankeyBuilder instance with database session

    Usage:
        ```python
        builder = await get_sankey_builder()
        graph = await builder.build_sankey_graph(discussion_id, rounds)
        ```
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        return SankeyBuilder(session)
