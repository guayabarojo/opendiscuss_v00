"""
Cluster API Client - Access Spec 004 cluster and alignment data

This module provides a client for fetching cluster data, participant assignments,
and alignment metadata from Spec 004 (Clustering & Alignment). Used by Spec 005
(Sankey Construction) to build visualization from actual cluster assignments.

Constitutional Compliance:
- Semantic Accuracy: Fetches real cluster data without modification
- Intent Fidelity: Uses actual participant assignments for movement tracking
- Temporal Transparency: Preserves temporal ordering across rounds
"""

from typing import Dict, List, Set, Tuple
from uuid import UUID
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session_factory
from ..models.cluster import Cluster
from ..models.thought_space import ThoughtSpace
from ..models.cluster_member import ClusterMember
from ..models.alignment import AlignmentMap

logger = logging.getLogger(__name__)


class ClusterAPIClient:
    """
    Client for accessing Spec 004 cluster data for Sankey construction.

    This client provides read-only access to:
    - Clusters: Thought spaces identified by HDBSCAN
    - Cluster members: Participant assignments to clusters
    - Alignment groups: Cross-round cluster alignment metadata

    Methods:
        get_clusters_for_round: Fetch all clusters for a specific round
        get_participant_assignments: Get participant-to-cluster mappings for a round
        get_participant_movements: Track participant movement between adjacent rounds
        get_alignment_metadata: Fetch display_group_id mappings for aligned clusters
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize cluster API client.

        Args:
            session: Async database session for querying Spec 004 data
        """
        self.session = session

    async def get_clusters_for_round(
        self,
        round_id: UUID
    ) -> List[Cluster]:
        """
        Fetch all clusters for a specific round.

        Args:
            round_id: Round UUID from Spec 001

        Returns:
            List of Cluster entities with cluster_id, round_id, medoid_summary_id,
            and member counts

        Raises:
            ValueError: If round_id is invalid or no clusters found

        Validates:
            FR-013: Every round with submissions has at least one cluster
        """
        if not round_id:
            raise ValueError("round_id cannot be None")

        # Try thought_spaces table first (production table)
        stmt = select(ThoughtSpace).where(ThoughtSpace.round_id == round_id)
        result = await self.session.execute(stmt)
        thought_spaces = result.scalars().all()

        if thought_spaces:
            # Convert ThoughtSpace to Cluster-like objects for compatibility
            clusters = []
            for ts in thought_spaces:
                # Create a pseudo-Cluster object with the data we need
                cluster = type('Cluster', (), {
                    'cluster_id': ts.cluster_id,
                    'round_id': ts.round_id,
                    'user_count': ts.member_count,
                    'user_pct': ts.member_pct,
                    'member_count': ts.member_count,  # Add this for node_builder
                    'label_summary': ts.label_summary,
                    'centroid_vector': ts.centroid_vector,
                    'display_group_id': ts.display_group_id,
                })()
                clusters.append(cluster)

            logger.info(
                f"Fetched {len(clusters)} thought spaces for round {round_id}"
            )
            return list(clusters)

        # Fallback to clusters table (legacy)
        stmt = select(Cluster).where(Cluster.round_id == round_id)
        result = await self.session.execute(stmt)
        clusters = result.scalars().all()

        if not clusters:
            logger.warning(f"No clusters or thought spaces found for round {round_id}")
            raise ValueError(f"No clusters found for round {round_id}")

        logger.info(
            f"Fetched {len(clusters)} clusters for round {round_id}"
        )
        return list(clusters)

    async def get_participant_assignments(
        self,
        round_id: UUID
    ) -> Dict[UUID, UUID]:
        """
        Get participant-to-cluster mappings for a round.

        Args:
            round_id: Round UUID from Spec 001

        Returns:
            Dict mapping participant_id (user_id) to cluster_id

        Validates:
            SC-003: 100% participant coverage (every participant assigned to one cluster)
            FR-016: Each participant assigned to exactly one cluster per round
        """
        if not round_id:
            raise ValueError("round_id cannot be None")

        # Try approved_summaries first (production approach)
        from ..models.approved_summary import ApprovedSummary
        from ..models.participant import Participant

        stmt = (
            select(Participant.user_id, ApprovedSummary.cluster_id)
            .join(ApprovedSummary, ApprovedSummary.participant_id == Participant.participant_id)
            .where(ApprovedSummary.round_id == round_id)
            .where(ApprovedSummary.cluster_id.isnot(None))
        )
        result = await self.session.execute(stmt)
        assignments = {row.user_id: row.cluster_id for row in result}

        if assignments:
            logger.debug(
                f"Fetched {len(assignments)} participant assignments for round {round_id} from approved_summaries"
            )
            return assignments

        # Fallback to cluster_members table (legacy)
        stmt = (
            select(ClusterMember.user_id, ClusterMember.cluster_id)
            .join(Cluster, ClusterMember.cluster_id == Cluster.cluster_id)
            .where(Cluster.round_id == round_id)
        )
        result = await self.session.execute(stmt)
        assignments = {row.user_id: row.cluster_id for row in result}

        logger.debug(
            f"Fetched {len(assignments)} participant assignments for round {round_id}"
        )
        return assignments

    async def get_participant_movements(
        self,
        from_round_id: UUID,
        to_round_id: UUID
    ) -> Dict[UUID, Tuple[UUID, UUID]]:
        """
        Track participant movement between adjacent rounds.

        Args:
            from_round_id: Source round UUID
            to_round_id: Destination round UUID

        Returns:
            Dict mapping user_id to (from_cluster_id, to_cluster_id) for participants
            who submitted in BOTH rounds (continuing participants only)

        Validates:
            FR-019: Edges computed only for continuing participants (intersection)
            SC-002: 100% edge accuracy (matches actual participant movement)

        Note:
            This method implements dropout handling by computing the intersection
            of participants across rounds. Only users present in both rounds are
            included in movement tracking (FR-019).
        """
        if not from_round_id or not to_round_id:
            raise ValueError("round_id parameters cannot be None")

        # Get assignments for both rounds
        from_assignments = await self.get_participant_assignments(from_round_id)
        to_assignments = await self.get_participant_assignments(to_round_id)

        # Compute intersection (continuing participants)
        continuing_users = set(from_assignments.keys()) & set(to_assignments.keys())

        # Track movements for continuing users only
        movements = {
            user_id: (from_assignments[user_id], to_assignments[user_id])
            for user_id in continuing_users
        }

        dropout_count = len(from_assignments) - len(continuing_users)
        logger.info(
            f"Tracked {len(movements)} participant movements from round "
            f"{from_round_id} to {to_round_id} ({dropout_count} dropouts)"
        )

        return movements

    async def get_alignment_metadata(
        self,
        discussion_id: UUID
    ) -> Dict[UUID, UUID]:
        """
        Fetch display_group_id mappings for aligned clusters.

        Args:
            discussion_id: Discussion UUID from Spec 001

        Returns:
            Dict mapping cluster_id to display_group_id for all aligned clusters
            in this discussion. Clusters without alignment are not included in the dict.

        Validates:
            FR-024: Alignment metadata is optional (dict may be empty)
            FR-025: display_group_id provides stable visual identity across rounds

        Note:
            This is used for visual continuity (stable colors/labels) and does NOT
            affect edge computation (FR-026, SC-006).
        """
        if not discussion_id:
            raise ValueError("discussion_id cannot be None")

        # Query alignment_maps table for this discussion
        # We need to get the display_group_id for each cluster
        # AlignmentMap stores mappings between clusters in adjacent rounds
        # For now, return empty dict as alignment is optional (FR-024)
        # TODO: Implement proper alignment metadata fetching when alignment service is ready

        # For now, return empty dict (alignment is optional per FR-024)
        alignment_map = {}

        logger.debug(
            f"Alignment metadata not yet implemented, returning empty dict for discussion {discussion_id}"
        )
        return alignment_map

    async def get_all_participants_for_round(
        self,
        round_id: UUID
    ) -> Set[UUID]:
        """
        Get set of all participant UUIDs who submitted in a round.

        Args:
            round_id: Round UUID from Spec 001

        Returns:
            Set of participant UUIDs who have cluster assignments in this round

        Validates:
            SC-003: 100% coverage validation (used for invariant checking)
        """
        if not round_id:
            raise ValueError("round_id cannot be None")

        assignments = await self.get_participant_assignments(round_id)
        return set(assignments.keys())


async def get_cluster_api_client() -> ClusterAPIClient:
    """
    Factory function for ClusterAPIClient.

    Returns:
        ClusterAPIClient instance with database session

    Usage:
        ```python
        client = await get_cluster_api_client()
        clusters = await client.get_clusters_for_round(round_id)
        ```
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        return ClusterAPIClient(session)
