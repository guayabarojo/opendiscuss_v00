"""
Clustering algorithm configuration for semantic clustering.

Implements HDBSCAN-based density clustering with deterministic configuration
and validation to ensure minority cluster preservation (FR-012, FR-013).
"""

import logging
from typing import Optional
import hdbscan
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


def compute_adaptive_parameters(n_participants: int) -> dict:
    """
    Compute HDBSCAN parameters scaled to participant count.

    Targets 7±2 clusters per Miller's Law by adaptively scaling min_cluster_size
    and min_samples based on the number of participants.

    Args:
        n_participants: Number of participants in the discussion

    Returns:
        dict with 'min_cluster_size', 'min_samples', and 'n_participants'

    Scaling Formula:
        - min_cluster_size: ~8% of N, floor at 2 (FR-012 compliance)
        - min_samples: ~4% of N, floor at 2
        - For very small N (<10), use fixed values

    Constitutional Compliance:
        - FR-012: min_cluster_size never goes below 2 (minority preservation)
        - Miller's Law: Targets 7±2 clusters for cognitive load management

    Example:
        - 10 participants: min_cluster_size=2, min_samples=2
        - 50 participants: min_cluster_size=4, min_samples=2
        - 100 participants: min_cluster_size=8, min_samples=4
    """
    # For very small discussions, use fixed minimum values
    if n_participants < 10:
        min_cluster_size = 2
        min_samples = 2
    else:
        # Scale with participant count (8% and 4% respectively)
        min_cluster_size = max(2, int(n_participants * 0.08))
        min_samples = max(2, int(n_participants * 0.04))

    logger.info(
        f"Adaptive parameters for {n_participants} participants: "
        f"min_cluster_size={min_cluster_size}, min_samples={min_samples}"
    )

    return {
        'min_cluster_size': min_cluster_size,
        'min_samples': min_samples,
        'n_participants': n_participants
    }


class ClusteringConfig:
    """Configuration for HDBSCAN clustering algorithm."""

    # Constitutional requirement: Preserve minority clusters
    MIN_CLUSTER_SIZE = 2  # FR-012: Must not be higher to allow minority clusters
    ALLOW_SINGLE_CLUSTER = True  # Allow all summaries in one cluster if semantically identical
    CLUSTER_SELECTION_METHOD = 'eom'  # Excess of Mass (EOM) for better minority preservation
    METRIC = 'euclidean'  # Distance metric (cosine handled via normalized embeddings)

    # Quality tuning parameters (added to reduce near-duplicate clusters)
    MIN_SAMPLES = 3  # Requires higher point density before forming clusters (was None)
                     # Higher value reduces over-fragmentation while preserving minorities
                     # Recommended: 3-5 (baseline showed 73.3 near-duplicates/round with min_samples=2)

    CLUSTER_SELECTION_EPSILON = 0.0  # Merge clusters within epsilon distance (0.0 = no merging)
                                     # Non-zero values reduce semantic near-duplicates
                                     # Recommended: 0.05-0.15 for additional near-duplicate reduction

    @classmethod
    def validate_config(cls) -> None:
        """
        Validate clustering configuration meets constitutional requirements.

        Validates:
        - FR-012: min_cluster_size=2 (not higher) to allow minority clusters
        - FR-009: Variable cluster count (not fixed K)

        Raises:
            ValueError: If configuration violates requirements
        """
        if cls.MIN_CLUSTER_SIZE > 2:
            raise ValueError(
                f"Constitutional violation (FR-012): min_cluster_size={cls.MIN_CLUSTER_SIZE} "
                f"would prevent minority clusters. Must be 2 or less."
            )

        logger.info(
            f"Clustering configuration validated: min_cluster_size={cls.MIN_CLUSTER_SIZE}, "
            f"allow_single_cluster={cls.ALLOW_SINGLE_CLUSTER}, "
            f"method={cls.CLUSTER_SELECTION_METHOD}"
        )


def create_clusterer(
    min_cluster_size: Optional[int] = None,
    min_samples: Optional[int] = None,
    cluster_selection_epsilon: Optional[float] = None,
    allow_single_cluster: Optional[bool] = None
) -> hdbscan.HDBSCAN:
    """
    Create configured HDBSCAN clusterer with quality tuning parameters.

    Args:
        min_cluster_size: Minimum cluster size (default: 2 per FR-012)
        min_samples: Minimum samples in neighborhood (default: 3, reduces over-fragmentation)
        cluster_selection_epsilon: Merge threshold for similar clusters (default: 0.0, no merging)
        allow_single_cluster: Allow all points in one cluster (default: True)

    Returns:
        Configured HDBSCAN clusterer

    Raises:
        ValueError: If min_cluster_size > 2 (violates FR-012)

    Quality Tuning (Phase 2):
        - min_samples=3: Requires higher point density, reduces near-duplicates
        - cluster_selection_epsilon: Merges very similar clusters algorithmically
        - Both parameters are constitutionally compliant (FR-012, FR-013)
    """
    # Use defaults from config if not specified
    if min_cluster_size is None:
        min_cluster_size = ClusteringConfig.MIN_CLUSTER_SIZE
    if min_samples is None:
        min_samples = ClusteringConfig.MIN_SAMPLES
    if cluster_selection_epsilon is None:
        cluster_selection_epsilon = ClusteringConfig.CLUSTER_SELECTION_EPSILON
    if allow_single_cluster is None:
        allow_single_cluster = ClusteringConfig.ALLOW_SINGLE_CLUSTER

    # Validate min_cluster_size doesn't violate minority preservation
    if min_cluster_size > 2:
        raise ValueError(
            f"min_cluster_size={min_cluster_size} violates FR-012 (minority preservation). "
            f"Must be 2 or less to preserve low-frequency clusters."
        )

    logger.info(
        f"Creating HDBSCAN clusterer: min_cluster_size={min_cluster_size}, "
        f"min_samples={min_samples}, cluster_selection_epsilon={cluster_selection_epsilon}, "
        f"allow_single_cluster={allow_single_cluster}"
    )

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        cluster_selection_epsilon=cluster_selection_epsilon,
        metric=ClusteringConfig.METRIC,
        cluster_selection_method=ClusteringConfig.CLUSTER_SELECTION_METHOD,
        allow_single_cluster=allow_single_cluster,
        prediction_data=True,  # Enable downstream noise assignment capabilities
        core_dist_n_jobs=-1  # Use all CPU cores for performance
    )

    return clusterer


def cluster_embeddings(
    embeddings: NDArray[np.float32],
    min_samples: Optional[int] = None,
    cluster_selection_epsilon: Optional[float] = None,
    use_adaptive_parameters: bool = True
) -> NDArray[np.int32]:
    """
    Cluster embedding vectors using HDBSCAN with quality tuning parameters.

    Args:
        embeddings: Array of embedding vectors (N x D)
        min_samples: Minimum samples in neighborhood (default: from config or adaptive)
        cluster_selection_epsilon: Merge threshold for similar clusters (default: from config)
        use_adaptive_parameters: Use Miller's Law adaptive parameter scaling (default: True)

    Returns:
        Array of cluster labels (N,). Label -1 indicates noise/outlier.

    Raises:
        ValueError: If embeddings are empty or invalid

    Quality Tuning:
        - Adaptive parameters: Scale min_cluster_size and min_samples for Miller's Law (7±2 clusters)
        - min_samples: Reduces near-duplicate clusters while preserving minorities
        - cluster_selection_epsilon: Merges very similar clusters
    """
    if embeddings.size == 0:
        raise ValueError("Cannot cluster empty embeddings array")

    if len(embeddings.shape) != 2:
        raise ValueError(
            f"Embeddings must be 2D array (N x D), got shape {embeddings.shape}"
        )

    n_points, n_dims = embeddings.shape
    logger.info(f"Clustering {n_points} embeddings with {n_dims} dimensions")

    # Compute adaptive parameters if enabled
    min_cluster_size = None
    if use_adaptive_parameters:
        adaptive_params = compute_adaptive_parameters(n_points)
        min_cluster_size = adaptive_params['min_cluster_size']
        if min_samples is None:
            min_samples = adaptive_params['min_samples']
        logger.info(f"Using adaptive parameters: min_cluster_size={min_cluster_size}, min_samples={min_samples}")

    # Create and fit clusterer with quality parameters
    clusterer = create_clusterer(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        cluster_selection_epsilon=cluster_selection_epsilon
    )
    cluster_labels = clusterer.fit_predict(embeddings)

    # Count clusters (excluding noise label -1)
    unique_labels = np.unique(cluster_labels)
    n_clusters = len(unique_labels[unique_labels >= 0])
    n_noise = np.sum(cluster_labels == -1)

    logger.info(
        f"Clustering complete: {n_clusters} clusters, {n_noise} noise points "
        f"(variable K per FR-009)"
    )

    return cluster_labels


def cluster_with_hdbscan(
    embeddings: np.ndarray,
    min_cluster_size: int = 2,
    min_samples: Optional[int] = None,
    cluster_selection_epsilon: float = 0.0,
    metric: str = "euclidean",
    cluster_selection_method: str = "eom",
    allow_single_cluster: bool = True
) -> np.ndarray:
    """
    Cluster embeddings using HDBSCAN (Hierarchical Density-Based Spatial Clustering).

    This is an alias/wrapper for cluster_embeddings() that provides a more explicit
    function name and additional parameter flexibility for T023 implementation.

    HDBSCAN is chosen for:
    - Variable cluster count (no need to specify K)
    - Automatic outlier detection (noise points labeled as -1)
    - Density-based clustering (finds clusters of varying density)
    - No forced merging of semantically distinct clusters

    Args:
        embeddings: numpy array of shape (n_samples, n_features)
        min_cluster_size: Minimum cluster size (default: 2, preserves minority clusters)
        min_samples: Min samples in neighborhood (default: 3, reduces over-fragmentation)
        cluster_selection_epsilon: Merge clusters within epsilon distance (default: 0.0, no merging)
        metric: Distance metric (default: "euclidean", can use "cosine")
        cluster_selection_method: How to select clusters from hierarchy (default: "eom")
        allow_single_cluster: Allow all points in single cluster if appropriate (default: True)

    Returns:
        numpy array of cluster labels (shape: n_samples)
        - Labels: 0, 1, 2, ... for valid clusters
        - Noise: -1 for outliers

    Configuration (T022):
        - min_cluster_size=2: Preserve low-frequency clusters (FR-012)
        - allow_single_cluster=True: Handle cases where all summaries are similar
        - cluster_selection_method='eom' (Excess of Mass): Stable selection

    Requirements:
        - FR-009: Variable cluster count (not fixed K)
        - FR-010: Non-LLM based clustering
        - FR-011: Handle outliers without dropping
        - FR-012: No minimum cluster size threshold enforcement

    Raises:
        ValueError: If embeddings array is invalid
        RuntimeError: If clustering fails
    """
    if embeddings.shape[0] == 0:
        raise ValueError("Cannot cluster empty embeddings array")

    if min_cluster_size < 2:
        logger.warning(
            f"min_cluster_size={min_cluster_size} < 2 may produce unstable results"
        )

    if min_samples is None:
        min_samples = ClusteringConfig.MIN_SAMPLES if ClusteringConfig.MIN_SAMPLES else min_cluster_size

    logger.info(
        f"Running HDBSCAN clustering: "
        f"{embeddings.shape[0]} samples, "
        f"min_cluster_size={min_cluster_size}, "
        f"min_samples={min_samples}, "
        f"cluster_selection_epsilon={cluster_selection_epsilon}, "
        f"metric={metric}"
    )

    try:
        # Initialize HDBSCAN clusterer with quality parameters
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            cluster_selection_epsilon=cluster_selection_epsilon,
            metric=metric,
            cluster_selection_method=cluster_selection_method,
            allow_single_cluster=allow_single_cluster,
            prediction_data=True,  # Enable downstream noise assignment capabilities
            core_dist_n_jobs=-1  # Use all CPU cores
        )

        # Fit and predict cluster labels
        cluster_labels = clusterer.fit_predict(embeddings)

        # Log clustering results
        unique_labels = np.unique(cluster_labels)
        n_clusters = len(unique_labels[unique_labels >= 0])
        n_noise = np.sum(cluster_labels == -1)

        logger.info(
            f"HDBSCAN clustering complete: "
            f"{n_clusters} clusters, {n_noise} noise points"
        )

        # Log cluster sizes
        for label in unique_labels:
            if label >= 0:
                cluster_size = np.sum(cluster_labels == label)
                logger.debug(f"Cluster {label}: {cluster_size} members")

        return cluster_labels

    except Exception as e:
        logger.error(f"HDBSCAN clustering failed: {e}", exc_info=True)
        raise RuntimeError(f"Clustering failed: {e}") from e


# Validate configuration on module import
ClusteringConfig.validate_config()
