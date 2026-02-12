"""
Outlier Handler for Semantic Clustering (Spec 004)

Handles noise points identified by HDBSCAN, converting them to singleton clusters
to ensure 100% participant coverage.

Tasks Implemented:
- T043: identify_outliers function
- T044: assign_singleton_cluster_ids function
- T047: singleton_count in events
"""

import logging
from typing import Dict, List, Tuple, Optional
from uuid import UUID
import numpy as np
from scipy.spatial.distance import cosine as cosine_distance

logger = logging.getLogger(__name__)


def identify_outliers(cluster_labels: np.ndarray) -> Tuple[np.ndarray, int]:
    """
    Identify HDBSCAN noise points (cluster_label == -1).

    Implements T043: Detect noise points identified by HDBSCAN for conversion
    to singleton clusters.

    Args:
        cluster_labels: Array of cluster assignments where -1 indicates noise/outliers

    Returns:
        Tuple of (outlier_indices, outlier_count):
        - outlier_indices: numpy array of indices where cluster_label == -1
        - outlier_count: number of outliers detected

    Requirements:
        - FR-011: Handle outliers/noise points without dropping them
        - FR-014: Each noise point must become its own singleton cluster
        - FR-015: Singleton clusters must be visible
    """
    if cluster_labels.size == 0:
        logger.warning("identify_outliers: Empty cluster_labels array")
        return np.array([], dtype=int), 0

    # Find indices where cluster label is -1 (noise/outlier)
    outlier_indices = np.where(cluster_labels == -1)[0]
    outlier_count = len(outlier_indices)

    if outlier_count > 0:
        logger.info(
            f"Identified {outlier_count} outliers (FR-011, FR-014) "
            f"at indices: {outlier_indices.tolist()[:10]}..."  # Log first 10
        )
    else:
        logger.info("No outliers detected - all points assigned to clusters")

    return outlier_indices, outlier_count


def assign_singleton_cluster_ids(
    cluster_labels: np.ndarray,
    outlier_indices: np.ndarray,
    next_cluster_id: int
) -> Tuple[np.ndarray, int]:
    """
    Generate unique cluster IDs for each noise point (outlier).

    Implements T044: Assign unique cluster_id for each noise point and update
    cluster assignment to ensure 100% coverage.

    Args:
        cluster_labels: Array of cluster assignments (will be modified in place)
        outlier_indices: Indices of noise points (-1 labels)
        next_cluster_id: Next available cluster ID to use for singletons

    Returns:
        Tuple of (updated_cluster_labels, singleton_count):
        - updated_cluster_labels: Modified cluster_labels with singletons assigned
        - singleton_count: Number of singleton clusters created

    Side Effects:
        - Modifies cluster_labels array in place

    Requirements:
        - FR-014: Each noise point becomes its own singleton cluster
        - FR-015: Singleton clusters must be visible
        - FR-016: 100% coverage - every participant assigned
        - SC-010: Outliers converted to singletons with 100% success rate
    """
    if outlier_indices.size == 0:
        logger.info("assign_singleton_cluster_ids: No outliers to assign")
        return cluster_labels, 0

    singleton_count = len(outlier_indices)

    logger.info(
        f"Assigning {singleton_count} singleton cluster IDs "
        f"starting from cluster_id={next_cluster_id} (FR-014, FR-016)"
    )

    # Assign unique cluster ID to each outlier
    for i, outlier_idx in enumerate(outlier_indices):
        singleton_cluster_id = next_cluster_id + i
        cluster_labels[outlier_idx] = singleton_cluster_id

        if i < 10:  # Log first 10 for debugging
            logger.debug(
                f"Outlier at index {outlier_idx} assigned to singleton cluster {singleton_cluster_id}"
            )

    # Verify no -1 labels remain
    remaining_outliers = np.sum(cluster_labels == -1)
    if remaining_outliers > 0:
        error_msg = (
            f"Singleton assignment failed: {remaining_outliers} outliers "
            f"still have cluster_label=-1 (FR-016 violation)"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info(
        f"Successfully assigned {singleton_count} singleton clusters (FR-014, SC-010). "
        f"100% coverage achieved (FR-016)."
    )

    return cluster_labels, singleton_count


def smart_noise_reassignment(
    cluster_labels: np.ndarray,
    embeddings: Dict[UUID, np.ndarray],
    centroids: Dict[int, np.ndarray],
    summary_ids: List[UUID],
    similarity_threshold: float = 0.4
) -> Tuple[np.ndarray, int, int]:
    """
    Reassign noise points to nearest cluster if similarity >= threshold.
    Otherwise promote to "Distinct Voice" singleton.

    This implements Miller's Law optimization by reducing unnecessary singletons
    while preserving truly distinct minority views.

    Args:
        cluster_labels: Array of cluster assignments where -1 indicates noise
        embeddings: Dict mapping summary_id to embedding vector
        centroids: Dict mapping cluster_id to centroid vector
        summary_ids: List of summary UUIDs corresponding to cluster_labels indices
        similarity_threshold: Minimum cosine similarity to reassign (default: 0.4)

    Returns:
        Tuple of (updated_labels, reassigned_count, distinct_voice_count):
        - updated_labels: Modified cluster_labels with reassignments
        - reassigned_count: Number of noise points reassigned to clusters
        - distinct_voice_count: Number promoted to "Distinct Voice" singletons

    Constitutional Compliance:
        - FR-011: All noise points handled (no dropping)
        - FR-016: 100% coverage maintained
        - Threshold 0.4 ensures only related points reassign
        - Distinct voices preserved as singletons (minority preservation)

    Example:
        - Noise point with 0.55 similarity to Cluster 3 -> reassigned to Cluster 3
        - Noise point with 0.25 similarity to all clusters -> "Distinct Voice" singleton
    """
    outlier_indices, outlier_count = identify_outliers(cluster_labels)

    if outlier_count == 0:
        logger.info("smart_noise_reassignment: No noise points to process")
        return cluster_labels, 0, 0

    logger.info(
        f"Processing {outlier_count} noise points with similarity threshold {similarity_threshold}"
    )

    reassigned_count = 0
    distinct_voice_count = 0

    # Calculate next available singleton ID
    non_noise_labels = cluster_labels[cluster_labels >= 0]
    if len(non_noise_labels) > 0:
        next_singleton_id = int(np.max(non_noise_labels)) + 1
    else:
        # All points are noise - start singleton IDs from 0
        next_singleton_id = 0

    for idx in outlier_indices:
        summary_id = summary_ids[idx]
        embedding = embeddings[summary_id]

        # Find best matching cluster
        best_similarity = -1.0
        best_cluster = None

        for cluster_id, centroid in centroids.items():
            # Compute cosine similarity (1 - cosine distance)
            similarity = 1.0 - cosine_distance(embedding, centroid)

            if similarity > best_similarity:
                best_similarity = similarity
                best_cluster = cluster_id

        # Reassign or promote based on similarity
        if best_similarity >= similarity_threshold and best_cluster is not None:
            # Reassign to nearest cluster
            cluster_labels[idx] = best_cluster
            reassigned_count += 1
            logger.debug(
                f"Noise point {idx} reassigned to cluster {best_cluster} "
                f"(similarity: {best_similarity:.3f})"
            )
        else:
            # Promote to "Distinct Voice" singleton
            cluster_labels[idx] = next_singleton_id
            distinct_voice_count += 1
            next_singleton_id += 1
            logger.debug(
                f"Noise point {idx} promoted to Distinct Voice singleton "
                f"(best similarity: {best_similarity:.3f})"
            )

    # Verify no -1 labels remain (safety check)
    remaining_noise = np.sum(cluster_labels == -1)
    if remaining_noise > 0:
        logger.warning(
            f"Smart noise reassignment: {remaining_noise} noise points "
            f"still have cluster_label=-1. Converting to singletons as fallback."
        )
        # Fallback: convert any remaining -1 labels to singletons
        remaining_indices = np.where(cluster_labels == -1)[0]
        for idx in remaining_indices:
            cluster_labels[idx] = next_singleton_id
            distinct_voice_count += 1
            next_singleton_id += 1

    logger.info(
        f"Smart noise reassignment complete: {reassigned_count} reassigned, "
        f"{distinct_voice_count} promoted to Distinct Voice singletons "
        f"(FR-011, FR-016 compliant)"
    )

    return cluster_labels, reassigned_count, distinct_voice_count


def convert_outliers_to_singletons(
    cluster_labels: np.ndarray,
    embeddings: Optional[Dict[UUID, np.ndarray]] = None,
    centroids: Optional[Dict[int, np.ndarray]] = None,
    summary_ids: Optional[List[UUID]] = None,
    similarity_threshold: Optional[float] = None,
    use_smart_reassignment: bool = True
) -> Tuple[np.ndarray, int]:
    """
    Convert HDBSCAN noise points to singleton clusters.

    Optionally uses smart reassignment to reduce unnecessary singletons while
    preserving truly distinct minority views (Miller's Law optimization).

    Args:
        cluster_labels: Array of cluster assignments where -1 indicates noise/outliers
        embeddings: Optional dict mapping summary_id to embedding (for smart reassignment)
        centroids: Optional dict mapping cluster_id to centroid (for smart reassignment)
        summary_ids: Optional list of summary UUIDs (for smart reassignment)
        similarity_threshold: Minimum similarity to reassign (default: 0.4, for smart reassignment)
        use_smart_reassignment: Use smart noise reassignment if embeddings available (default: True)

    Returns:
        Tuple of (updated_cluster_labels, singleton_count):
        - updated_cluster_labels: Modified cluster_labels with singletons assigned
        - singleton_count: Number of singleton clusters created

    Requirements:
        - FR-011: Handle outliers/noise points
        - FR-014: Each noise point becomes its own singleton cluster (or reassigned)
        - FR-015: Singleton clusters must be visible
        - FR-016: 100% coverage
        - SC-010: 100% success rate for outlier conversion

    Note:
        If use_smart_reassignment=True and embeddings/centroids/summary_ids are provided,
        uses smart_noise_reassignment(). Otherwise falls back to simple singleton conversion.
    """
    # Use smart reassignment if enabled and data available
    if use_smart_reassignment and embeddings is not None and centroids is not None and summary_ids is not None:
        logger.info("Using smart noise reassignment (Miller's Law optimization)")

        if similarity_threshold is None:
            similarity_threshold = 0.4

        updated_labels, reassigned_count, distinct_voice_count = smart_noise_reassignment(
            cluster_labels=cluster_labels,
            embeddings=embeddings,
            centroids=centroids,
            summary_ids=summary_ids,
            similarity_threshold=similarity_threshold
        )

        # Return total singleton count (only distinct voices)
        return updated_labels, distinct_voice_count

    # Fall back to simple singleton conversion
    logger.info("Converting outliers to singleton clusters (simple mode, FR-014)")

    # Identify outliers
    outlier_indices, outlier_count = identify_outliers(cluster_labels)

    if outlier_count == 0:
        logger.info("No outliers to convert")
        return cluster_labels, 0

    # Find next available cluster ID (max existing + 1)
    max_cluster_id = int(np.max(cluster_labels[cluster_labels >= 0]))
    next_cluster_id = max_cluster_id + 1

    # Assign singleton cluster IDs
    updated_labels, singleton_count = assign_singleton_cluster_ids(
        cluster_labels=cluster_labels,
        outlier_indices=outlier_indices,
        next_cluster_id=next_cluster_id
    )

    return updated_labels, singleton_count


def calculate_singleton_metrics(
    cluster_labels: np.ndarray,
    cluster_stats: Dict[int, Tuple[int, float]]
) -> Dict[str, int]:
    """
    Calculate singleton cluster metrics for event publishing.

    Implements T047: Add singleton_count to clustering.completed event payload.

    Args:
        cluster_labels: Array of cluster assignments (after outlier conversion)
        cluster_stats: Dict mapping cluster_id to (user_count, user_pct)

    Returns:
        Dictionary with singleton metrics:
        - singleton_count: Number of singleton clusters (user_count == 1)
        - total_clusters: Total number of clusters
        - singleton_percentage: Percentage of clusters that are singletons

    Requirements:
        - T047: singleton_count in clustering.completed event
        - FR-015: Singleton clusters must be visible (counted separately)
    """
    # Count singletons from cluster_stats
    singleton_clusters = [
        cluster_id for cluster_id, (user_count, _) in cluster_stats.items()
        if user_count == 1
    ]
    singleton_count = len(singleton_clusters)

    total_clusters = len(cluster_stats)
    singleton_percentage = (
        (singleton_count / total_clusters * 100) if total_clusters > 0 else 0.0
    )

    logger.info(
        f"Singleton metrics (T047): {singleton_count}/{total_clusters} clusters "
        f"are singletons ({singleton_percentage:.1f}%)"
    )

    return {
        'singleton_count': singleton_count,
        'total_clusters': total_clusters,
        'singleton_percentage': singleton_percentage
    }
