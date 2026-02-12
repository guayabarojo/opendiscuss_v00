"""
Flow computation service for tracking participant movement across rounds.

Implements the constitutional guarantee of Temporal Transparency (Principle IV):
flows represent actual participant movement, not semantic similarity.
"""

import logging
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Flow, ApprovedSummary, Cluster, Round

logger = logging.getLogger(__name__)


class FlowService:
    """
    Service for computing participant flows between consecutive rounds.

    Constitutional Guarantees:
    - Flows computed ONLY from participant movement (not semantic similarity)
    - Edge widths = actual participant counts (intersection of participant_ids)
    - display_group_id alignment does NOT inflate flow counts
    - All participants accounted for (no silent data loss)
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize FlowService with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session

    async def compute_flows(
        self,
        source_round_id: UUID,
        target_round_id: UUID
    ) -> List[Flow]:
        """
        Compute participant flows from Round N to Round N+1.

        This is the core implementation of flow computation per data-model.md:
        - Query ApprovedSummaries for both rounds to get participant→cluster mappings
        - For each source cluster → target cluster pair:
          - Compute intersection: participants in BOTH source AND target
          - Create Flow entity with participant_count and participant_ids
        - Validate counts <= min(source.member_count, target.member_count)
        - Return list of Flow entities (not yet persisted)

        Constitutional Guarantee:
        Flow weights represent ACTUAL participant movement, never semantic similarity.
        Participants who drop out have zero outgoing flows (mass shrinks naturally).

        Args:
            source_round_id: UUID of source round (Round N)
            target_round_id: UUID of target round (Round N+1)

        Returns:
            List of Flow entities (uncommitted, caller must persist)

        Raises:
            ValueError: If rounds not consecutive or not found
            RuntimeError: If data validation fails (e.g., impossible counts)
        """
        logger.info(
            f"Computing flows from round {source_round_id} to {target_round_id}"
        )

        # Validate rounds exist and are consecutive
        source_round = await self._get_round(source_round_id)
        target_round = await self._get_round(target_round_id)

        if not source_round or not target_round:
            raise ValueError(
                f"Rounds not found: source={source_round_id}, target={target_round_id}"
            )

        if target_round.round_num != source_round.round_num + 1:
            raise ValueError(
                f"Rounds must be consecutive. "
                f"Source round_num={source_round.round_num}, "
                f"Target round_num={target_round.round_num}"
            )

        logger.debug(
            f"Validated consecutive rounds: "
            f"Round {source_round.round_num} → Round {target_round.round_num}"
        )

        # Get all thought spaces for both rounds
        source_clusters = await self._get_clusters(source_round_id)
        target_clusters = await self._get_clusters(target_round_id)

        if not source_clusters:
            logger.warning(
                f"No thought spaces found for source round {source_round_id}"
            )
            return []

        if not target_clusters:
            logger.warning(
                f"No thought spaces found for target round {target_round_id}"
            )
            return []

        logger.debug(
            f"Found {len(source_clusters)} source clusters, "
            f"{len(target_clusters)} target clusters"
        )

        # Build participant→cluster maps for O(1) lookups
        source_participant_map = await self._build_participant_to_cluster_map(
            source_round_id
        )
        target_participant_map = await self._build_participant_to_cluster_map(
            target_round_id
        )

        logger.debug(
            f"Source round has {len(source_participant_map)} participants, "
            f"Target round has {len(target_participant_map)} participants"
        )

        # Compute flows between every source-target cluster pair
        flows: List[Flow] = []
        total_source_participants = len(source_participant_map)
        total_participants_with_flows = set()

        for source_ts in source_clusters:
            # Get participants in this source cluster
            source_pids = await self._get_participants_in_cluster(
                source_ts.cluster_id
            )

            for target_ts in target_clusters:
                # Get participants in this target cluster
                target_pids = await self._get_participants_in_cluster(
                    target_ts.cluster_id
                )

                # Compute intersection: participants in BOTH clusters
                intersection = source_pids & target_pids

                if len(intersection) > 0:
                    # Validate flow count within bounds
                    max_possible = min(source_ts.member_count, target_ts.member_count)
                    if len(intersection) > max_possible:
                        raise RuntimeError(
                            f"Flow validation failed: intersection count "
                            f"({len(intersection)}) exceeds bounds "
                            f"(max={max_possible}, source={source_ts.member_count}, "
                            f"target={target_ts.member_count})"
                        )

                    # Create flow entity
                    flow = Flow(
                        source_cluster_id=source_ts.cluster_id,
                        target_cluster_id=target_ts.cluster_id,
                        participant_count=len(intersection),
                        participant_ids=list(intersection)
                    )

                    flows.append(flow)
                    total_participants_with_flows.update(intersection)

                    logger.debug(
                        f"Flow created: {source_ts.cluster_id} → {target_ts.cluster_id}, "
                        f"count={len(intersection)}"
                    )

        # Validate all source participants are accounted for
        # (they either have flows OR dropped out)
        participants_with_flows_count = len(total_participants_with_flows)
        dropout_count = total_source_participants - participants_with_flows_count

        logger.info(
            f"Flow computation complete: "
            f"{len(flows)} flows created, "
            f"{participants_with_flows_count} participants with flows, "
            f"{dropout_count} dropouts detected "
            f"(total source participants: {total_source_participants})"
        )

        # Validate conservation: source participants = flows + dropouts
        if participants_with_flows_count > total_source_participants:
            raise RuntimeError(
                f"Flow validation failed: more participants with flows "
                f"({participants_with_flows_count}) than source participants "
                f"({total_source_participants}). This indicates data corruption."
            )

        return flows

    async def _get_round(self, round_id: UUID) -> Round:
        """
        Fetch Round entity by ID.

        Args:
            round_id: UUID of round

        Returns:
            Round entity or None if not found
        """
        result = await self.session.execute(
            select(Round).where(Round.round_id == round_id)
        )
        return result.scalar_one_or_none()

    async def _get_clusters(self, round_id: UUID) -> List[Cluster]:
        """
        Fetch all Clusters for a round.

        Args:
            round_id: UUID of round

        Returns:
            List of Cluster entities
        """
        result = await self.session.execute(
            select(Cluster).where(Cluster.round_id == round_id)
        )
        return list(result.scalars().all())

    async def _build_participant_to_cluster_map(
        self,
        round_id: UUID
    ) -> dict[UUID, UUID]:
        """
        Build participant_id → cluster_id mapping for a round.

        Args:
            round_id: UUID of round

        Returns:
            Dictionary mapping participant_id to cluster_id
        """
        result = await self.session.execute(
            select(
                ApprovedSummary.participant_id,
                ApprovedSummary.cluster_id
            ).where(ApprovedSummary.round_id == round_id)
        )

        participant_map = {}
        for participant_id, cluster_id in result.all():
            if cluster_id is None:
                logger.warning(
                    f"ApprovedSummary has NULL cluster_id for participant "
                    f"{participant_id} in round {round_id}. "
                    f"This violates 100% participant coverage guarantee."
                )
            else:
                participant_map[participant_id] = cluster_id

        return participant_map

    async def _get_participants_in_cluster(
        self,
        cluster_id: UUID
    ) -> set[UUID]:
        """
        Get all participant_ids in a specific cluster.

        Args:
            cluster_id: UUID of Cluster

        Returns:
            Set of participant UUIDs
        """
        result = await self.session.execute(
            select(ApprovedSummary.participant_id).where(
                ApprovedSummary.cluster_id == cluster_id
            )
        )
        return set(result.scalars().all())


async def get_flow_service(session: AsyncSession) -> FlowService:
    """
    Factory function to create FlowService instance.

    Args:
        session: Async SQLAlchemy session

    Returns:
        FlowService instance
    """
    return FlowService(session)
