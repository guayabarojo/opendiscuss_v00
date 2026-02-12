"""
Medoid-based cluster labeling service.

This module implements medoid selection for cluster labels using the centroid-closest
member method with deterministic tie-breaking (FR-044). Labels use actual participant
language (FR-024) rather than AI-generated text.

Tasks:
- T062: compute_medoid function (find closest to centroid)
- T063: deterministic_tiebreaker function (lexicographic order)
- T064: assign_medoid_labels function
"""

import logging
from typing import List, Tuple, Optional
from uuid import UUID
import numpy as np
from scipy.spatial.distance import cosine

logger = logging.getLogger(__name__)


class MedoidLabelingError(Exception):
    """Raised when medoid labeling operations fail."""
    pass


def compute_medoid(
    cluster_id: UUID,
    centroid_vector: np.ndarray,
    member_embeddings: List[Tuple[UUID, np.ndarray]]
) -> UUID:
    """
    Compute medoid: the cluster member closest to the centroid.

    The medoid is the cluster member whose embedding has the smallest cosine
    distance to the cluster centroid. This ensures the label is representative
    of the cluster's semantic center while using actual participant language.

    Args:
        cluster_id: Cluster ID for logging purposes
        centroid_vector: Cluster centroid embedding (384-dim normalized vector)
        member_embeddings: List of (summary_id, embedding_vector) tuples for cluster members

    Returns:
        summary_id of the medoid (cluster member closest to centroid)

    Raises:
        MedoidLabelingError: If no members provided or computation fails

    Requirements:
        - FR-022: Medoid method (centroid-closest member)
        - FR-023: Use cosine distance (same metric as clustering)
        - FR-024: Label is actual participant text (no AI generation)
        - FR-044: Deterministic tie-breaking with lexicographic order

    Example:
        >>> centroid = np.array([0.5, 0.5, 0.0, ...])  # 384-dim
        >>> members = [
        ...     (UUID('a...'), np.array([0.4, 0.6, 0.0, ...])),
        ...     (UUID('b...'), np.array([0.6, 0.4, 0.0, ...]))
        ... ]
        >>> medoid_id = compute_medoid(cluster_id, centroid, members)
    """
    if not member_embeddings:
        raise MedoidLabelingError(
            f"Cannot compute medoid for cluster {cluster_id}: no members provided"
        )

    # Validate centroid vector
    if centroid_vector is None or len(centroid_vector) != 384:
        raise MedoidLabelingError(
            f"Invalid centroid vector for cluster {cluster_id}: "
            f"expected 384-dim array, got {type(centroid_vector)}"
        )

    logger.debug(
        f"Computing medoid for cluster {cluster_id} with {len(member_embeddings)} members"
    )

    # Compute cosine distances from each member to centroid
    distances: List[Tuple[float, UUID]] = []

    for summary_id, embedding in member_embeddings:
        if embedding is None or len(embedding) != 384:
            logger.warning(
                f"Skipping member {summary_id} with invalid embedding "
                f"(expected 384-dim, got {len(embedding) if embedding is not None else 'None'})"
            )
            continue

        try:
            # Compute cosine distance (1 - cosine_similarity)
            # scipy.spatial.distance.cosine computes 1 - dot(A, B) / (norm(A) * norm(B))
            distance = cosine(embedding, centroid_vector)

            # Handle NaN or infinite distances (shouldn't happen with normalized vectors)
            if np.isnan(distance) or np.isinf(distance):
                logger.warning(
                    f"Invalid distance computed for member {summary_id}: {distance}"
                )
                continue

            distances.append((distance, summary_id))

        except Exception as e:
            logger.warning(
                f"Failed to compute distance for member {summary_id}: {e}"
            )
            continue

    if not distances:
        raise MedoidLabelingError(
            f"Failed to compute valid distances for any member in cluster {cluster_id}"
        )

    # Find minimum distance
    min_distance = min(d[0] for d in distances)

    # Find all members with minimum distance (for tie-breaking)
    closest_members = [
        summary_id for distance, summary_id in distances
        if distance == min_distance
    ]

    # Apply deterministic tie-breaking if multiple members have same distance
    if len(closest_members) > 1:
        logger.debug(
            f"Cluster {cluster_id}: {len(closest_members)} members equidistant "
            f"from centroid (distance={min_distance:.6f}), applying tie-breaker"
        )
        medoid_id = deterministic_tiebreaker(closest_members)
    else:
        medoid_id = closest_members[0]

    logger.info(
        f"Cluster {cluster_id}: Selected medoid {medoid_id} "
        f"(distance to centroid: {min_distance:.6f})"
    )

    return medoid_id


def deterministic_tiebreaker(candidate_summary_ids: List[UUID]) -> UUID:
    """
    Apply deterministic tie-breaking using lexicographic order of summary_id.

    When multiple cluster members are equidistant from the centroid, this function
    selects the medoid deterministically by choosing the summary_id that comes first
    in lexicographic (alphabetical) order.

    Args:
        candidate_summary_ids: List of summary UUIDs with equal distance to centroid

    Returns:
        summary_id selected as medoid (lexicographically first)

    Raises:
        MedoidLabelingError: If candidate list is empty

    Requirements:
        - FR-044: Deterministic tie-breaking with lexicographic order
        - SC-006: Same cluster → same medoid across multiple runs

    Example:
        >>> candidates = [
        ...     UUID('aaaaaaaa-1234-5678-90ab-cdef12345678'),
        ...     UUID('bbbbbbbb-1234-5678-90ab-cdef12345678'),
        ...     UUID('cccccccc-1234-5678-90ab-cdef12345678')
        ... ]
        >>> medoid = deterministic_tiebreaker(candidates)
        >>> medoid == UUID('aaaaaaaa-1234-5678-90ab-cdef12345678')
        True
    """
    if not candidate_summary_ids:
        raise MedoidLabelingError("Cannot apply tie-breaker: no candidates provided")

    # Sort by string representation of UUID (lexicographic order)
    # This ensures deterministic selection across different runs
    sorted_candidates = sorted(candidate_summary_ids, key=lambda uid: str(uid))

    selected = sorted_candidates[0]

    logger.debug(
        f"Tie-breaker: Selected {selected} from {len(candidate_summary_ids)} "
        f"equidistant candidates (lexicographic order)"
    )

    return selected


def assign_medoid_labels(
    clusters_data: List[dict]
) -> List[Tuple[UUID, UUID]]:
    """
    Assign medoid labels to all clusters.

    For each cluster, computes the medoid (centroid-closest member) and returns
    the mapping of cluster_id to label_summary_id.

    Args:
        clusters_data: List of cluster dictionaries with keys:
            - cluster_id: UUID
            - centroid_vector: np.ndarray (384-dim)
            - members: List of (summary_id, embedding_vector) tuples

    Returns:
        List of (cluster_id, label_summary_id) tuples

    Raises:
        MedoidLabelingError: If label assignment fails for any cluster

    Requirements:
        - FR-021: Every cluster has a label (medoid)
        - FR-024: Labels use actual participant language
        - FR-025: Deterministic labeling (SC-006)

    Example:
        >>> clusters = [
        ...     {
        ...         'cluster_id': UUID('...'),
        ...         'centroid_vector': np.array([...]),
        ...         'members': [(UUID('...'), np.array([...]))]
        ...     }
        ... ]
        >>> labels = assign_medoid_labels(clusters)
        >>> # labels = [(cluster_id_1, medoid_id_1), (cluster_id_2, medoid_id_2), ...]
    """
    if not clusters_data:
        logger.warning("No clusters provided for medoid label assignment")
        return []

    logger.info(f"Assigning medoid labels to {len(clusters_data)} clusters")

    labels: List[Tuple[UUID, UUID]] = []
    failed_clusters: List[UUID] = []

    for cluster in clusters_data:
        cluster_id = cluster.get('cluster_id')
        centroid_vector = cluster.get('centroid_vector')
        members = cluster.get('members', [])

        if cluster_id is None:
            logger.error("Cluster missing cluster_id, skipping")
            continue

        try:
            # Compute medoid for this cluster
            medoid_id = compute_medoid(
                cluster_id=cluster_id,
                centroid_vector=centroid_vector,
                member_embeddings=members
            )

            labels.append((cluster_id, medoid_id))

        except MedoidLabelingError as e:
            logger.error(f"Failed to assign medoid label to cluster {cluster_id}: {e}")
            failed_clusters.append(cluster_id)
        except Exception as e:
            logger.error(
                f"Unexpected error assigning medoid label to cluster {cluster_id}: {e}",
                exc_info=True
            )
            failed_clusters.append(cluster_id)

    # Report results
    success_count = len(labels)
    failure_count = len(failed_clusters)

    logger.info(
        f"Medoid label assignment complete: {success_count} successful, "
        f"{failure_count} failed"
    )

    if failed_clusters:
        raise MedoidLabelingError(
            f"Failed to assign medoid labels to {failure_count} cluster(s): "
            f"{failed_clusters}"
        )

    return labels


def validate_medoid_is_member(
    cluster_id: UUID,
    label_summary_id: UUID,
    member_summary_ids: List[UUID]
) -> bool:
    """
    Validate that the medoid label is actually a member of the cluster.

    This is a safety check to ensure the medoid selection algorithm correctly
    chooses from the cluster's member set.

    Args:
        cluster_id: Cluster ID
        label_summary_id: Selected medoid summary ID
        member_summary_ids: List of summary IDs in the cluster

    Returns:
        True if validation passes

    Raises:
        MedoidLabelingError: If medoid is not a cluster member

    Requirements:
        - Data model validation: "Medoid Validation" section
        - Label must be a cluster member
    """
    if label_summary_id not in member_summary_ids:
        raise MedoidLabelingError(
            f"Medoid validation failed for cluster {cluster_id}: "
            f"label {label_summary_id} is not a cluster member"
        )

    logger.debug(f"Cluster {cluster_id}: Medoid validation passed")
    return True
