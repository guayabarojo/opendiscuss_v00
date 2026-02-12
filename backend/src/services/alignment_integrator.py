"""
Alignment Integrator Service - Integrates display_group_id for visual continuity

This module provides functions for fetching alignment metadata from Spec 004
and integrating display_group_ids into Sankey nodes for stable colors and
labels across rounds.

Constitutional Compliance:
- Representation Not Adjudication: Alignment is for visual aid only, not computation
- Semantic Accuracy: Alignment metadata does not affect edge computation (SC-006)
- Intent Fidelity: Display groups preserve semantic relationships for clarity
"""

from typing import Dict, Optional
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.alignment import Alignment

logger = logging.getLogger(__name__)


async def fetch_alignment_metadata(
    discussion_id: UUID,
    session: AsyncSession
) -> Dict[UUID, UUID]:
    """
    Retrieve display_group_id mappings from Spec 004 alignment data.

    This function fetches alignment metadata that maps cluster_ids to
    display_group_ids. Clusters with the same display_group_id across rounds
    are semantically related (aligned) and should be rendered with the same
    color and visual treatment.

    Args:
        discussion_id: Discussion UUID
        session: Database session for querying alignment data

    Returns:
        Dict mapping cluster_id to display_group_id for aligned clusters
        Empty dict if no alignment data available (not an error)

    Validates:
        FR-024: Alignment metadata fetched from Spec 004
        SC-006: Alignment does not affect edge computation

    Constitutional Compliance:
        - Representation Not Adjudication: Alignment for visualization only
        - Semantic Accuracy: Optional metadata, doesn't change participant data

    Performance:
        Target <50ms for 100 clusters (single database query)

    Example:
        alignment_metadata = await fetch_alignment_metadata(discussion_id, session)
        # Returns: {cluster_a: group_1, cluster_b: group_1, cluster_c: group_2, ...}
        # Clusters A and B are aligned (same group), C is different group
    """
    if not discussion_id:
        raise ValueError("discussion_id cannot be None")

    logger.info(
        f"Fetching alignment metadata for discussion {discussion_id}"
    )

    try:
        # Query alignment table for this discussion
        # Note: The actual schema depends on Spec 004 implementation
        # This is a template that should be adjusted based on actual Alignment model
        stmt = (
            select(Alignment)
            .where(Alignment.discussion_id == discussion_id)
            .order_by(Alignment.created_at.desc())
        )

        result = await session.execute(stmt)
        alignments = result.scalars().all()

        if not alignments:
            logger.info(
                f"No alignment data found for discussion {discussion_id} "
                f"(this is normal if alignment hasn't run yet)"
            )
            return {}

        # Build mapping: cluster_id -> display_group_id
        alignment_map: Dict[UUID, UUID] = {}

        for alignment in alignments:
            # Spec 004 alignment may have different structures:
            # Option 1: cluster_id and display_group_id fields directly
            if hasattr(alignment, 'cluster_id') and hasattr(alignment, 'display_group_id'):
                if alignment.display_group_id:  # Only include if not null
                    alignment_map[alignment.cluster_id] = alignment.display_group_id

            # Option 2: cluster_groups field with nested structure
            elif hasattr(alignment, 'cluster_groups'):
                # cluster_groups might be: {group_id: [cluster_id1, cluster_id2, ...]}
                for group_id, cluster_ids in alignment.cluster_groups.items():
                    for cluster_id in cluster_ids:
                        alignment_map[UUID(cluster_id)] = UUID(group_id)

        logger.info(
            f"Loaded alignment metadata: {len(alignment_map)} cluster-to-group mappings"
        )

        return alignment_map

    except Exception as e:
        # Alignment is optional - if fetch fails, log warning but continue
        logger.warning(
            f"Failed to fetch alignment metadata for discussion {discussion_id}: {e}. "
            f"Continuing without alignment (nodes will use default colors)."
        )
        return {}


def integrate_alignment(
    cluster_id: UUID,
    alignment_metadata: Optional[Dict[UUID, UUID]]
) -> Optional[UUID]:
    """
    Get display_group_id for a cluster from alignment metadata.

    This is a simple lookup function that returns the display_group_id for
    a given cluster, or None if no alignment exists. Used during node creation.

    Args:
        cluster_id: Cluster UUID to look up
        alignment_metadata: Dict mapping cluster_id to display_group_id (optional)

    Returns:
        display_group_id if cluster is aligned, None otherwise

    Validates:
        FR-025: Display group assignment from alignment metadata
        SC-006: Alignment does not affect node user_count or edge computation

    Constitutional Compliance:
        - Representation Not Adjudication: Alignment metadata is optional visual aid
        - Semantic Accuracy: Alignment lookup is pure function, no side effects

    Example:
        display_group_id = integrate_alignment(cluster_a_id, alignment_map)
        # Returns: group_1 UUID if cluster_a is in group_1
        # Returns: None if cluster_a is not aligned
    """
    if not alignment_metadata:
        return None

    if cluster_id not in alignment_metadata:
        logger.debug(
            f"Cluster {cluster_id} not found in alignment metadata "
            f"(will use default color)"
        )
        return None

    display_group_id = alignment_metadata[cluster_id]

    logger.debug(
        f"Cluster {cluster_id} mapped to display_group {display_group_id}"
    )

    return display_group_id


def validate_alignment_metadata_structure(
    alignment_metadata: Dict[UUID, UUID]
) -> bool:
    """
    Validate that alignment metadata has correct structure.

    This function performs basic structural validation on alignment metadata
    to catch data corruption or schema mismatches early.

    Args:
        alignment_metadata: Dict to validate

    Returns:
        True if valid, False otherwise

    Validates:
        - Dict keys are valid UUIDs (cluster_ids)
        - Dict values are valid UUIDs (display_group_ids)
        - No None values in dict

    Example:
        is_valid = validate_alignment_metadata_structure(alignment_map)
        # Returns: True if structure is correct
        # Returns: False if any UUIDs are invalid or None
    """
    if not isinstance(alignment_metadata, dict):
        logger.error(
            f"Alignment metadata must be dict, got {type(alignment_metadata)}"
        )
        return False

    for cluster_id, display_group_id in alignment_metadata.items():
        # Check cluster_id is valid UUID
        if not isinstance(cluster_id, UUID):
            logger.error(
                f"Invalid cluster_id in alignment metadata: {cluster_id} "
                f"(type: {type(cluster_id)})"
            )
            return False

        # Check display_group_id is valid UUID
        if not isinstance(display_group_id, UUID):
            logger.error(
                f"Invalid display_group_id in alignment metadata: {display_group_id} "
                f"(type: {type(display_group_id)})"
            )
            return False

        # Check for None values
        if cluster_id is None or display_group_id is None:
            logger.error("Alignment metadata contains None values")
            return False

    logger.debug(
        f"Alignment metadata structure validated: {len(alignment_metadata)} mappings"
    )
    return True
