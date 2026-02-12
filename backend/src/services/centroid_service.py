"""
Centroid service for computing and managing cluster centroids.

This service handles centroid computation (mean embedding vectors) and persistence
for semantic clustering and cross-round alignment.
"""

import logging
from typing import List, Dict, Tuple
from uuid import UUID
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

logger = logging.getLogger(__name__)


class CentroidServiceError(Exception):
    """Raised when centroid service operations fail."""
    pass


async def load_centroids(
    session: AsyncSession,
    round_ids: List[UUID],
) -> Dict[UUID, Dict[UUID, np.ndarray]]:
    """
    Load centroid vectors for specified rounds from database.

    Args:
        session: Database session
        round_ids: List of round UUIDs to load centroids for

    Returns:
        Dictionary mapping round_id -> {cluster_id: centroid_vector}

    Raises:
        CentroidServiceError: If loading fails

    Requirements:
        - T049: Load centroids for rounds r and r+1
        - Data model: Read from clusters.centroid_vector

    Example:
        >>> centroids = await load_centroids(session, [round_1_id, round_2_id])
        >>> centroids[round_1_id][cluster_a_id]
        array([0.123, -0.456, ...])  # 384-dim vector
    """
    try:
        logger.info(f"Loading centroids for {len(round_ids)} rounds")

        # Query clusters and their centroids for the specified rounds
        query = text("""
            SELECT cluster_id, round_id, centroid_vector
            FROM clusters
            WHERE round_id = ANY(:round_ids)
        """)

        result = await session.execute(
            query,
            {"round_ids": [str(rid) for rid in round_ids]}
        )

        # Organize results by round_id -> cluster_id -> centroid
        centroids = {rid: {} for rid in round_ids}

        for row in result:
            cluster_id = UUID(row.cluster_id) if isinstance(row.cluster_id, str) else row.cluster_id
            round_id = UUID(row.round_id) if isinstance(row.round_id, str) else row.round_id

            # Convert pgvector format to numpy array
            if isinstance(row.centroid_vector, str):
                # Parse string format: "[0.1, 0.2, ...]"
                vector_str = row.centroid_vector.strip('[]')
                centroid = np.array([float(x) for x in vector_str.split(',')])
            elif isinstance(row.centroid_vector, (list, tuple)):
                centroid = np.array(row.centroid_vector, dtype=np.float32)
            else:
                centroid = np.array(row.centroid_vector, dtype=np.float32)

            centroids[round_id][cluster_id] = centroid

        # Log statistics
        for round_id in round_ids:
            count = len(centroids[round_id])
            logger.info(f"Loaded {count} centroids for round {round_id}")

        return centroids

    except Exception as e:
        error_msg = f"Failed to load centroids: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise CentroidServiceError(error_msg) from e


async def compute_centroid(
    embeddings: np.ndarray,
    normalize: bool = True,
) -> np.ndarray:
    """
    Compute centroid (mean) of embedding vectors.

    Args:
        embeddings: Array of embeddings with shape (n_members, embedding_dim)
        normalize: Whether to L2-normalize the centroid (default: True)

    Returns:
        Centroid vector with shape (embedding_dim,)

    Raises:
        ValueError: If embeddings is empty
        CentroidServiceError: If computation fails

    Requirements:
        - FR-026: Compute cluster centroids
        - FR-027: Centroids are mean of member embeddings
        - Data model: Centroid normalization for cosine similarity

    Example:
        >>> embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        >>> centroid = await compute_centroid(embeddings)
        >>> centroid
        array([0.2, 0.3])  # Mean of embeddings
    """
    if len(embeddings) == 0:
        raise ValueError("embeddings cannot be empty")

    try:
        # Compute mean along axis 0
        centroid = np.mean(embeddings, axis=0)

        # Normalize for cosine similarity optimization
        if normalize:
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm
            else:
                logger.warning("Centroid has zero norm, skipping normalization")

        return centroid

    except Exception as e:
        error_msg = f"Failed to compute centroid: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise CentroidServiceError(error_msg) from e


async def verify_centroid_accuracy(
    embeddings: np.ndarray,
    expected_centroid: np.ndarray,
    tolerance: float = 1e-6,
) -> bool:
    """
    Verify that a centroid is the correct mean of embeddings.

    Args:
        embeddings: Array of member embeddings
        expected_centroid: Centroid to verify
        tolerance: Numerical tolerance for comparison

    Returns:
        True if centroid is accurate, False otherwise

    Requirements:
        - T069: Centroid computation test
        - FR-027: Verify mean calculation accuracy

    Example:
        >>> embeddings = np.array([[1, 0], [0, 1]])
        >>> centroid = await compute_centroid(embeddings, normalize=False)
        >>> await verify_centroid_accuracy(embeddings, centroid)
        True
    """
    try:
        # Compute expected centroid (without normalization)
        actual_mean = np.mean(embeddings, axis=0)

        # Check if expected_centroid is normalized version
        norm = np.linalg.norm(actual_mean)
        if norm > 0:
            expected_normalized = actual_mean / norm

            # Check both normalized and unnormalized
            is_equal_unnormalized = np.allclose(actual_mean, expected_centroid, atol=tolerance)
            is_equal_normalized = np.allclose(expected_normalized, expected_centroid, atol=tolerance)

            return is_equal_unnormalized or is_equal_normalized
        else:
            return np.allclose(actual_mean, expected_centroid, atol=tolerance)

    except Exception as e:
        logger.error(f"Failed to verify centroid accuracy: {str(e)}")
        return False


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity in range [-1, 1] (typically [0, 1] for normalized vectors)

    Requirements:
        - FR-031: Cosine similarity for alignment
        - Data model: Optimized for normalized vectors

    Example:
        >>> vec1 = np.array([1, 0, 0])
        >>> vec2 = np.array([1, 0, 0])
        >>> cosine_similarity(vec1, vec2)
        1.0
        >>> vec3 = np.array([0, 1, 0])
        >>> cosine_similarity(vec1, vec3)
        0.0
    """
    # If vectors are normalized (L2 norm = 1), cosine similarity = dot product
    # Otherwise, use standard formula
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    # Cosine similarity = dot(v1, v2) / (||v1|| * ||v2||)
    similarity = np.dot(vec1, vec2) / (norm1 * norm2)

    # Clamp to [-1, 1] to handle numerical errors
    return float(np.clip(similarity, -1.0, 1.0))


# ============================================================================
# T025 & T026: Compute and Persist Centroids for Clustering Workflow
# ============================================================================


def compute_centroids(
    cluster_assignments: Dict[UUID, int],
    embeddings: Dict[UUID, np.ndarray]
) -> Dict[int, np.ndarray]:
    """
    Compute centroid vectors for each cluster as mean of member embeddings.

    Implements T025: Calculate mean embedding vector for each cluster.

    The centroid is the arithmetic mean (centroid) of all member embedding vectors
    in a cluster. This represents the semantic "center" of the thought space.

    Args:
        cluster_assignments: Dict mapping summary_id to cluster_label
        embeddings: Dict mapping summary_id to embedding vector (384-dim)

    Returns:
        Dict mapping cluster_label to centroid vector (384-dim numpy array)

    Computation:
        centroid = (1/N) * sum(embedding_i) for all members i in cluster

    Requirements:
        - FR-026: Compute and persist cluster centroids
        - FR-027: Centroids calculated as mean of member embeddings
        - FR-028: Centroids persisted for cross-round alignment

    Raises:
        ValueError: If embeddings missing for cluster members
        RuntimeError: If centroid computation fails
    """
    logger.info(
        f"Computing centroids for {len(set(cluster_assignments.values()))} clusters"
    )

    # Group summaries by cluster
    cluster_members: Dict[int, List[UUID]] = {}
    for summary_id, cluster_label in cluster_assignments.items():
        if cluster_label not in cluster_members:
            cluster_members[cluster_label] = []
        cluster_members[cluster_label].append(summary_id)

    # Compute centroid for each cluster
    centroids: Dict[int, np.ndarray] = {}

    for cluster_label, member_ids in cluster_members.items():
        # Collect embeddings for all members
        member_embeddings = []

        for summary_id in member_ids:
            if summary_id not in embeddings:
                raise ValueError(
                    f"Missing embedding for summary {summary_id} "
                    f"in cluster {cluster_label}"
                )
            member_embeddings.append(embeddings[summary_id])

        if not member_embeddings:
            raise RuntimeError(
                f"No embeddings found for cluster {cluster_label}"
            )

        # Compute mean of all member embeddings
        member_embeddings_array = np.array(member_embeddings)
        centroid = np.mean(member_embeddings_array, axis=0)

        # Validate centroid shape (must be 384-dim for SBERT MiniLM)
        if centroid.shape[0] != 384:
            raise RuntimeError(
                f"Invalid centroid dimensions for cluster {cluster_label}: "
                f"{centroid.shape[0]} (expected 384)"
            )

        centroids[cluster_label] = centroid

        logger.debug(
            f"Computed centroid for cluster {cluster_label}: "
            f"{len(member_ids)} members, centroid norm={np.linalg.norm(centroid):.4f}"
        )

    logger.info(
        f"Successfully computed {len(centroids)} centroids"
    )

    return centroids


async def persist_centroids(
    centroids: Dict[int, np.ndarray],
    cluster_id_map: Dict[int, UUID]
) -> None:
    """
    Persist centroid vectors to clusters table.

    Implements T026: Save centroid vectors to database.

    Note: In the current implementation, centroids are persisted as part of the
    Cluster (ThoughtSpace) entity creation in persist_clusters(). This function
    is provided for completeness and can be used for updating centroids if needed.

    Args:
        centroids: Dict mapping cluster_label to centroid vector
        cluster_id_map: Dict mapping cluster_label to cluster_id (UUID)

    Requirements:
        - FR-026: Persist centroids for alignment
        - FR-028: Centroids available for cross-round alignment

    Note:
        Actual persistence happens in clustering_service.persist_clusters()
        where centroids are included in the ThoughtSpace entity creation.
        This function validates the centroid data structure.
    """
    logger.info(
        f"Validating {len(centroids)} centroids for persistence"
    )

    # Validate centroids match cluster_id_map
    for cluster_label in centroids.keys():
        if cluster_label not in cluster_id_map:
            raise ValueError(
                f"Centroid for cluster {cluster_label} has no corresponding cluster_id"
            )

    # Validate centroid dimensions
    for cluster_label, centroid in centroids.items():
        if centroid.shape[0] != 384:
            raise ValueError(
                f"Invalid centroid dimensions for cluster {cluster_label}: "
                f"{centroid.shape[0]} (expected 384)"
            )

    logger.info(
        "Centroid validation complete - ready for persistence in Cluster entities"
    )
