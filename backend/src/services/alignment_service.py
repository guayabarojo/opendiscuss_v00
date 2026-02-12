"""
Alignment service for cross-round cluster alignment.

This service computes similarity between clusters across adjacent rounds
and assigns display groups for visual continuity in Sankey diagrams.
Alignment is presentation-only and does NOT affect cluster membership.
"""

import logging
from typing import List, Dict, Tuple, Optional
from uuid import UUID, uuid4
from datetime import datetime
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text, insert

from src.services.centroid_service import (
    load_centroids,
    cosine_similarity,
    CentroidServiceError,
)

logger = logging.getLogger(__name__)


class AlignmentServiceError(Exception):
    """Raised when alignment service operations fail."""
    pass


class AlignmentResult:
    """Result of cross-round alignment."""

    def __init__(
        self,
        discussion_id: UUID,
        round_r: int,
        round_r1: int,
        alignments: List[Dict],
        match_count: int,
        processing_time_ms: int,
        display_group_count: int,
    ):
        self.discussion_id = discussion_id
        self.round_r = round_r
        self.round_r1 = round_r1
        self.alignments = alignments
        self.match_count = match_count
        self.processing_time_ms = processing_time_ms
        self.display_group_count = display_group_count


async def compute_similarity_matrix(
    centroids_r: Dict[UUID, np.ndarray],
    centroids_r1: Dict[UUID, np.ndarray],
) -> Dict[Tuple[UUID, UUID], float]:
    """
    Compute cosine similarity matrix between all centroid pairs from rounds r and r+1.

    Args:
        centroids_r: Dictionary mapping cluster_id -> centroid for round r
        centroids_r1: Dictionary mapping cluster_id -> centroid for round r+1

    Returns:
        Dictionary mapping (cluster_r_id, cluster_r1_id) -> similarity_score

    Raises:
        AlignmentServiceError: If computation fails

    Requirements:
        - T050: Compute similarity matrix
        - FR-030: Compute similarity matrix between all pairs
        - FR-031: Use cosine similarity

    Example:
        >>> centroids_r = {cluster_a: vec_a, cluster_b: vec_b}
        >>> centroids_r1 = {cluster_c: vec_c, cluster_d: vec_d}
        >>> matrix = await compute_similarity_matrix(centroids_r, centroids_r1)
        >>> matrix[(cluster_a, cluster_c)]
        0.85  # High similarity
        >>> matrix[(cluster_b, cluster_d)]
        0.45  # Low similarity
    """
    try:
        logger.info(
            f"Computing similarity matrix: {len(centroids_r)} x {len(centroids_r1)} = "
            f"{len(centroids_r) * len(centroids_r1)} pairs"
        )

        similarity_matrix = {}

        # Compute cosine similarity for all pairs
        for cluster_r_id, centroid_r in centroids_r.items():
            for cluster_r1_id, centroid_r1 in centroids_r1.items():
                similarity = cosine_similarity(centroid_r, centroid_r1)
                similarity_matrix[(cluster_r_id, cluster_r1_id)] = similarity

        logger.info(f"Computed {len(similarity_matrix)} similarity scores")

        return similarity_matrix

    except Exception as e:
        error_msg = f"Failed to compute similarity matrix: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise AlignmentServiceError(error_msg) from e


async def greedy_matching(
    similarity_matrix: Dict[Tuple[UUID, UUID], float],
    threshold: float = 0.7,
) -> List[Tuple[UUID, UUID, float]]:
    """
    Find best-match alignment using greedy algorithm with similarity threshold.

    Greedily selects the highest similarity pair, then removes both clusters
    from consideration. Continues until no more pairs exceed threshold.

    Produces 1-to-1, 1-to-many, or many-to-1 alignments depending on similarity.

    Args:
        similarity_matrix: Dictionary mapping (cluster_r_id, cluster_r1_id) -> similarity
        threshold: Minimum similarity for alignment (default: 0.7)

    Returns:
        List of (cluster_r_id, cluster_r1_id, similarity) tuples

    Raises:
        AlignmentServiceError: If matching fails

    Requirements:
        - T051: Greedy matching algorithm
        - FR-032: Use configurable ALIGN_THRESHOLD
        - FR-033: Only align pairs with similarity >= threshold
        - FR-034: Greedy matching algorithm

    Example:
        >>> matrix = {
        ...     (a, c): 0.85,  # Best match
        ...     (a, d): 0.50,  # Below threshold
        ...     (b, c): 0.60,  # Below threshold
        ...     (b, d): 0.75,  # Second best
        ... }
        >>> matches = await greedy_matching(matrix, threshold=0.7)
        >>> matches
        [(a, c, 0.85), (b, d, 0.75)]
    """
    try:
        logger.info(
            f"Running greedy matching with threshold={threshold} "
            f"({len(similarity_matrix)} candidate pairs)"
        )

        # Filter pairs by threshold
        valid_pairs = [
            (cluster_r, cluster_r1, sim)
            for (cluster_r, cluster_r1), sim in similarity_matrix.items()
            if sim >= threshold
        ]

        # Sort by similarity (descending)
        valid_pairs.sort(key=lambda x: x[2], reverse=True)

        logger.info(f"{len(valid_pairs)} pairs exceed threshold")

        # Greedy matching: select best pairs without reusing clusters
        # Note: This allows 1-to-many and many-to-1 alignments
        # We DON'T enforce 1-to-1 constraint to support splits/merges
        matches = []
        for cluster_r, cluster_r1, sim in valid_pairs:
            # Add all high-similarity pairs (allows multiple matches per cluster)
            matches.append((cluster_r, cluster_r1, sim))
            logger.debug(
                f"Aligned {cluster_r} -> {cluster_r1} (similarity={sim:.3f})"
            )

        logger.info(f"Greedy matching produced {len(matches)} alignments")

        return matches

    except Exception as e:
        error_msg = f"Failed to perform greedy matching: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise AlignmentServiceError(error_msg) from e


async def assign_display_groups(
    matches: List[Tuple[UUID, UUID, float]],
) -> Dict[UUID, UUID]:
    """
    Assign display_group_id for aligned cluster pairs.

    Clusters with the same display_group_id are visually grouped
    for color continuity and label families in Sankey diagrams.

    Handles 1-to-1, 1-to-many (split), and many-to-1 (merge) alignments.

    Args:
        matches: List of (cluster_r_id, cluster_r1_id, similarity) tuples

    Returns:
        Dictionary mapping cluster_id -> display_group_id for all aligned clusters

    Raises:
        AlignmentServiceError: If assignment fails

    Requirements:
        - T052: Assign display groups
        - FR-035: Support 1-to-1, 1-to-many, many-to-1 mappings
        - FR-036: Assign display_group_ids for visual continuity

    Example:
        >>> matches = [(a, c, 0.85), (b, c, 0.75)]  # Many-to-1 (merge)
        >>> groups = await assign_display_groups(matches)
        >>> groups[a] == groups[b] == groups[c]
        True  # All get same display_group_id
    """
    try:
        logger.info(f"Assigning display groups for {len(matches)} alignments")

        display_groups = {}

        # Group clusters by connectivity
        # Clusters that share alignment partners get the same display group
        for cluster_r, cluster_r1, _ in matches:
            # Check if either cluster already has a group
            group_r = display_groups.get(cluster_r)
            group_r1 = display_groups.get(cluster_r1)

            if group_r and group_r1:
                # Both have groups - merge groups
                if group_r != group_r1:
                    # Replace all occurrences of group_r1 with group_r
                    for cluster_id in list(display_groups.keys()):
                        if display_groups[cluster_id] == group_r1:
                            display_groups[cluster_id] = group_r
            elif group_r:
                # Only r has group - assign to r1
                display_groups[cluster_r1] = group_r
            elif group_r1:
                # Only r1 has group - assign to r
                display_groups[cluster_r] = group_r1
            else:
                # Neither has group - create new group
                new_group_id = uuid4()
                display_groups[cluster_r] = new_group_id
                display_groups[cluster_r1] = new_group_id

        unique_groups = len(set(display_groups.values()))
        logger.info(
            f"Assigned {len(display_groups)} clusters to {unique_groups} display groups"
        )

        return display_groups

    except Exception as e:
        error_msg = f"Failed to assign display groups: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise AlignmentServiceError(error_msg) from e


async def persist_alignment(
    session: AsyncSession,
    discussion_id: UUID,
    round_r: int,
    round_r1: int,
    matches: List[Tuple[UUID, UUID, float]],
    display_groups: Dict[UUID, UUID],
) -> None:
    """
    Persist alignment maps and display group IDs to database.

    Args:
        session: Database session
        discussion_id: Discussion UUID
        round_r: Earlier round number
        round_r1: Later round number (r+1)
        matches: List of (cluster_r_id, cluster_r1_id, similarity) tuples
        display_groups: Dictionary mapping cluster_id -> display_group_id

    Raises:
        AlignmentServiceError: If persistence fails

    Requirements:
        - T053: Persist alignment to database
        - FR-036: Store alignment maps with display_group_id
        - Data model: alignment_maps table

    Example:
        >>> await persist_alignment(
        ...     session, discussion_id, 1, 2,
        ...     [(a, c, 0.85), (b, d, 0.75)],
        ...     {a: g1, c: g1, b: g2, d: g2}
        ... )
        # Creates 2 alignment_map records in database
    """
    try:
        logger.info(
            f"Persisting {len(matches)} alignments for discussion {discussion_id}, "
            f"rounds {round_r}->{round_r1}"
        )

        # Insert alignment maps
        alignment_records = []
        for cluster_r_id, cluster_r1_id, similarity in matches:
            display_group_id = display_groups.get(cluster_r_id) or display_groups.get(cluster_r1_id)

            alignment_records.append({
                "alignment_id": uuid4(),
                "discussion_id": discussion_id,
                "round_r": round_r,
                "round_r1": round_r1,
                "cluster_r_id": cluster_r_id,
                "cluster_r1_id": cluster_r1_id,
                "similarity_score": float(similarity),
                "display_group_id": display_group_id,
                "created_at": datetime.utcnow(),
            })

        if alignment_records:
            await session.execute(
                text("""
                    INSERT INTO alignment_maps
                    (alignment_id, discussion_id, round_r, round_r1,
                     cluster_r_id, cluster_r1_id, similarity_score,
                     display_group_id, created_at)
                    VALUES
                    (:alignment_id, :discussion_id, :round_r, :round_r1,
                     :cluster_r_id, :cluster_r1_id, :similarity_score,
                     :display_group_id, :created_at)
                """),
                alignment_records
            )

            logger.info(f"Inserted {len(alignment_records)} alignment_maps records")

    except Exception as e:
        error_msg = f"Failed to persist alignment: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise AlignmentServiceError(error_msg) from e


async def update_cluster_display_groups(
    session: AsyncSession,
    display_groups: Dict[UUID, UUID],
) -> None:
    """
    Update display_group_id field in clusters table without modifying membership.

    CRITICAL: This function MUST NOT change cluster membership or user assignments.
    It only updates the display_group_id field for presentation purposes.

    Args:
        session: Database session
        display_groups: Dictionary mapping cluster_id -> display_group_id

    Raises:
        AlignmentServiceError: If update fails

    Requirements:
        - T054: Update display groups in clusters table
        - FR-037: Alignment does NOT change cluster membership
        - FR-038: Alignment does NOT affect flow calculations
        - FR-039: Alignment affects presentation only

    Example:
        >>> await update_cluster_display_groups(
        ...     session,
        ...     {cluster_a: group_1, cluster_b: group_1, cluster_c: group_2}
        ... )
        # Updates display_group_id for clusters a, b, c (NO membership changes)
    """
    try:
        logger.info(f"Updating display_group_id for {len(display_groups)} clusters")

        # Update each cluster's display_group_id
        # Note: We update one at a time to avoid complex SQL
        for cluster_id, display_group_id in display_groups.items():
            await session.execute(
                text("""
                    UPDATE clusters
                    SET display_group_id = :display_group_id
                    WHERE cluster_id = :cluster_id
                """),
                {
                    "cluster_id": cluster_id,
                    "display_group_id": display_group_id,
                }
            )

        await session.commit()

        logger.info("Display groups updated successfully")

    except Exception as e:
        await session.rollback()
        error_msg = f"Failed to update cluster display groups: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise AlignmentServiceError(error_msg) from e


async def validate_alignment_invariance(
    session: AsyncSession,
    round_ids: List[UUID],
    member_counts_before: Dict[UUID, int],
) -> bool:
    """
    Validate that alignment did NOT change cluster membership counts.

    This is a critical invariant to ensure alignment affects presentation only.

    Args:
        session: Database session
        round_ids: List of round UUIDs to validate
        member_counts_before: Dictionary mapping cluster_id -> member_count before alignment

    Returns:
        True if invariant holds, False otherwise

    Raises:
        AlignmentServiceError: If validation fails

    Requirements:
        - T060: Alignment invariance validation
        - FR-037: Alignment does NOT change cluster membership
        - SC-009: Verify alignment does NOT change membership (100% accuracy)

    Example:
        >>> # Before alignment
        >>> before = {cluster_a: 10, cluster_b: 5}
        >>> # Run alignment...
        >>> # After alignment
        >>> valid = await validate_alignment_invariance(session, [round_id], before)
        >>> valid
        True  # Member counts unchanged
    """
    try:
        logger.info(f"Validating alignment invariance for {len(round_ids)} rounds")

        # Query current member counts
        query = text("""
            SELECT c.cluster_id, COUNT(cm.summary_id) as member_count
            FROM clusters c
            LEFT JOIN cluster_members cm ON c.cluster_id = cm.cluster_id
            WHERE c.round_id = ANY(:round_ids)
            GROUP BY c.cluster_id
        """)

        result = await session.execute(
            query,
            {"round_ids": [str(rid) for rid in round_ids]}
        )

        # Compare counts
        invariant_holds = True
        for row in result:
            cluster_id = UUID(row.cluster_id) if isinstance(row.cluster_id, str) else row.cluster_id
            current_count = row.member_count

            expected_count = member_counts_before.get(cluster_id)

            if expected_count is None:
                logger.warning(
                    f"Cluster {cluster_id} not found in before counts "
                    "(may be newly created)"
                )
                continue

            if current_count != expected_count:
                logger.error(
                    f"Alignment invariance violated for cluster {cluster_id}: "
                    f"before={expected_count}, after={current_count}"
                )
                invariant_holds = False

        if invariant_holds:
            logger.info("Alignment invariance validated successfully")
        else:
            logger.error("Alignment invariance validation FAILED")

        return invariant_holds

    except Exception as e:
        error_msg = f"Failed to validate alignment invariance: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise AlignmentServiceError(error_msg) from e


async def get_cluster_member_counts(
    session: AsyncSession,
    round_ids: List[UUID],
) -> Dict[UUID, int]:
    """
    Get current member counts for all clusters in specified rounds.

    Args:
        session: Database session
        round_ids: List of round UUIDs

    Returns:
        Dictionary mapping cluster_id -> member_count

    Example:
        >>> counts = await get_cluster_member_counts(session, [round_id])
        >>> counts[cluster_a]
        10
    """
    try:
        query = text("""
            SELECT c.cluster_id, COUNT(cm.summary_id) as member_count
            FROM clusters c
            LEFT JOIN cluster_members cm ON c.cluster_id = cm.cluster_id
            WHERE c.round_id = ANY(:round_ids)
            GROUP BY c.cluster_id
        """)

        result = await session.execute(
            query,
            {"round_ids": [str(rid) for rid in round_ids]}
        )

        counts = {}
        for row in result:
            cluster_id = UUID(row.cluster_id) if isinstance(row.cluster_id, str) else row.cluster_id
            counts[cluster_id] = row.member_count

        return counts

    except Exception as e:
        logger.error(f"Failed to get cluster member counts: {str(e)}")
        raise AlignmentServiceError(str(e)) from e
