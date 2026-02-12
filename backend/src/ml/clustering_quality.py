"""
Clustering Quality Metrics Module

Provides comprehensive quality measurement infrastructure for semantic clustering validation.
Addresses the observation that clusters within rounds are too similar to each other.

Metrics Provided:
- Silhouette Score: Measures intra-cluster cohesion vs inter-cluster separation
- Davies-Bouldin Index: Measures cluster separation quality
- Within-Cluster Cohesion: Average pairwise similarity per cluster
- Near-Duplicate Detection: Identifies high-similarity cluster pairs

Constitutional Compliance:
- FR-012 (Minority Preservation): Metrics are measurement-only, no enforcement
- FR-013 (No Forced Merging): Near-duplicate detection returns suggestions, not automatic merging
- SC-003 (Semantic Accuracy): Quality metrics validate semantic coherence
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from uuid import UUID

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import silhouette_score, davies_bouldin_score
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class ClusterQualityMetrics:
    """
    Quality metrics for a clustering result.

    Attributes:
        round_id: UUID of the round being analyzed
        silhouette_score: [-1, 1], higher = better (>0.5 good, <0.3 poor)
        davies_bouldin_index: [0, ∞], lower = better (<1.0 good, >2.0 poor)
        near_duplicate_count: Count of cluster pairs with >threshold similarity
        near_duplicate_pairs: List of (label_i, label_j, similarity, text_i, text_j)
        within_cluster_cohesion: Dict mapping cluster label to avg pairwise similarity
        singleton_count: Number of clusters with size=1
        avg_cluster_size: Average participants per cluster
        min_within_cohesion: Minimum cohesion across all clusters
        max_within_cohesion: Maximum cohesion across all clusters
        avg_within_cohesion: Average cohesion across all clusters
    """

    round_id: UUID
    silhouette_score: float
    davies_bouldin_index: float
    near_duplicate_count: int
    near_duplicate_pairs: List[Tuple[int, int, float, str, str]]
    within_cluster_cohesion: Dict[int, float]
    singleton_count: int
    avg_cluster_size: float
    min_within_cohesion: float
    max_within_cohesion: float
    avg_within_cohesion: float


def compute_silhouette_score(
    embeddings: NDArray[np.float32],
    cluster_labels: NDArray[np.int32]
) -> float:
    """
    Compute Silhouette Score using cosine metric.

    The Silhouette Score measures how similar an object is to its own cluster
    compared to other clusters. Higher values indicate better-defined clusters.

    Range: [-1, 1]
    - >0.7: Strong, well-separated clusters
    - 0.5-0.7: Reasonable cluster structure
    - 0.25-0.5: Weak/overlapping clusters
    - <0.25: Poor clustering, arbitrary assignment

    Args:
        embeddings: Array of shape (n_samples, n_features)
        cluster_labels: Array of shape (n_samples,) with cluster assignments

    Returns:
        float: Silhouette score

    Raises:
        ValueError: If less than 2 clusters or all samples in one cluster
    """
    # Filter out noise points (label=-1) if any
    valid_mask = cluster_labels != -1
    valid_embeddings = embeddings[valid_mask]
    valid_labels = cluster_labels[valid_mask]

    # Need at least 2 clusters for silhouette score
    unique_labels = np.unique(valid_labels)
    if len(unique_labels) < 2:
        raise ValueError(
            f"Silhouette score requires at least 2 clusters, got {len(unique_labels)}"
        )

    # Check if most clusters are singletons (silhouette score not meaningful)
    # Count points per cluster
    cluster_sizes = np.bincount(valid_labels)
    non_singleton_clusters = np.sum(cluster_sizes > 1)

    if non_singleton_clusters < 2:
        # Most/all clusters are singletons - silhouette score not meaningful
        # Return 0.0 to indicate poor clustering quality
        return 0.0

    return float(silhouette_score(valid_embeddings, valid_labels, metric='cosine'))


def compute_davies_bouldin_index(
    embeddings: NDArray[np.float32],
    cluster_labels: NDArray[np.int32]
) -> float:
    """
    Compute Davies-Bouldin Index (lower is better).

    The Davies-Bouldin Index measures the average similarity between each cluster
    and its most similar cluster. Lower values indicate better cluster separation.

    Range: [0, ∞]
    - <1.0: Excellent separation
    - 1.0-2.0: Good separation
    - >2.0: Poor separation (clusters overlap)

    Args:
        embeddings: Array of shape (n_samples, n_features)
        cluster_labels: Array of shape (n_samples,) with cluster assignments

    Returns:
        float: Davies-Bouldin index

    Raises:
        ValueError: If less than 2 clusters
    """
    # Filter out noise points (label=-1) if any
    valid_mask = cluster_labels != -1
    valid_embeddings = embeddings[valid_mask]
    valid_labels = cluster_labels[valid_mask]

    # Need at least 2 clusters
    unique_labels = np.unique(valid_labels)
    if len(unique_labels) < 2:
        raise ValueError(
            f"Davies-Bouldin index requires at least 2 clusters, got {len(unique_labels)}"
        )

    # Check if most clusters are singletons (DB index not meaningful)
    cluster_sizes = np.bincount(valid_labels)
    non_singleton_clusters = np.sum(cluster_sizes > 1)

    if non_singleton_clusters < 2:
        # Most/all clusters are singletons - DB index not meaningful
        # Return high value to indicate poor clustering quality
        return 999.0

    # Use euclidean distance (sklearn's davies_bouldin_score uses euclidean)
    return float(davies_bouldin_score(valid_embeddings, valid_labels))


def compute_within_cluster_cohesion(
    cluster_assignments: Dict[UUID, int],
    embeddings: Dict[UUID, NDArray[np.float32]]
) -> Dict[int, float]:
    """
    Compute average pairwise cosine similarity within each cluster.

    Within-cluster cohesion measures how semantically similar cluster members are.
    Higher values indicate tighter, more coherent clusters.

    Use Case: Validate that minority clusters (size=1-2) are semantically coherent,
    not arbitrary noise assignments.

    Args:
        cluster_assignments: Mapping from summary_id to cluster label
        embeddings: Mapping from summary_id to embedding vector

    Returns:
        Dict mapping cluster label to average pairwise cosine similarity

    Example:
        {
            0: 0.92,  # Tight cluster
            1: 0.78,  # Moderate cohesion
            2: 1.0,   # Singleton (perfect cohesion)
        }
    """
    cohesion = {}

    # Group summaries by cluster
    cluster_to_summaries: Dict[int, List[UUID]] = {}
    for summary_id, cluster_label in cluster_assignments.items():
        if cluster_label not in cluster_to_summaries:
            cluster_to_summaries[cluster_label] = []
        cluster_to_summaries[cluster_label].append(summary_id)

    # Compute cohesion for each cluster
    for cluster_label, summary_ids in cluster_to_summaries.items():
        if len(summary_ids) == 1:
            # Singleton: perfect cohesion
            cohesion[cluster_label] = 1.0
        else:
            # Get embeddings for this cluster
            cluster_embeddings = np.array([embeddings[sid] for sid in summary_ids])

            # Compute pairwise cosine similarities
            similarities = cosine_similarity(cluster_embeddings)

            # Get upper triangle (excluding diagonal) for pairwise similarities
            n = len(similarities)
            upper_tri = similarities[np.triu_indices(n, k=1)]

            # Average pairwise similarity
            cohesion[cluster_label] = float(upper_tri.mean()) if len(upper_tri) > 0 else 1.0

    return cohesion


def identify_near_duplicate_clusters(
    centroids: Dict[int, NDArray[np.float32]],
    cluster_labels: Dict[int, str],
    cluster_sizes: Dict[int, int],
    similarity_threshold: float = 0.8
) -> List[Tuple[int, int, float, str, str]]:
    """
    Identify cluster pairs with high centroid similarity (above threshold).

    Near-duplicate clusters suggest over-fragmentation: semantically similar
    submissions are being split into separate clusters instead of grouped together.

    Constitutional Note: This function returns SUGGESTIONS only, does NOT merge
    automatically. Human review required (FR-013: No Forced Merging).

    Args:
        centroids: Mapping from cluster label to centroid vector
        cluster_labels: Mapping from cluster label to label text
        cluster_sizes: Mapping from cluster label to member count
        similarity_threshold: Minimum similarity to flag as near-duplicate (default: 0.8)

    Returns:
        List of tuples: (label_i, label_j, similarity, text_i, text_j)
        Sorted by similarity descending (most similar pairs first)

    Example:
        [
            (0, 5, 0.95, "transparency is essential", "transparency must be the foundation"),
            (1, 3, 0.87, "safety research needed", "extensive safety research required"),
        ]
    """
    near_duplicates = []
    labels = sorted(centroids.keys())

    # Compare all pairs of clusters
    for i, label_i in enumerate(labels):
        for label_j in labels[i + 1:]:
            centroid_i = centroids[label_i]
            centroid_j = centroids[label_j]

            # Compute cosine similarity between centroids
            similarity = float(cosine_similarity(
                centroid_i.reshape(1, -1),
                centroid_j.reshape(1, -1)
            )[0, 0])

            # Flag if above threshold
            if similarity >= similarity_threshold:
                near_duplicates.append((
                    label_i,
                    label_j,
                    similarity,
                    cluster_labels.get(label_i, "Unknown"),
                    cluster_labels.get(label_j, "Unknown")
                ))

    # Sort by similarity descending (highest similarity first)
    near_duplicates.sort(key=lambda x: x[2], reverse=True)

    return near_duplicates


def compute_cluster_centroids(
    embeddings: NDArray[np.float32],
    cluster_labels: NDArray[np.int32]
) -> Dict[int, NDArray[np.float32]]:
    """
    Compute centroid (mean embedding) for each cluster.

    Args:
        embeddings: Array of shape (n_samples, n_features)
        cluster_labels: Array of shape (n_samples,) with cluster assignments

    Returns:
        Dict mapping cluster label to centroid vector
    """
    centroids = {}
    unique_labels = set(cluster_labels)

    for label in unique_labels:
        if label == -1:  # Skip noise
            continue
        mask = cluster_labels == label
        cluster_embeddings = embeddings[mask]
        centroids[label] = cluster_embeddings.mean(axis=0)

    return centroids


def compute_cluster_quality_metrics(
    embeddings: NDArray[np.float32],
    cluster_labels: NDArray[np.int32],
    cluster_assignments: Dict[UUID, int],
    embeddings_dict: Dict[UUID, NDArray[np.float32]],
    cluster_info: Dict[int, Dict],
    round_id: UUID,
    near_duplicate_threshold: float = 0.8
) -> ClusterQualityMetrics:
    """
    Compute all quality metrics in one pass.

    Main entry point for clustering quality analysis. Computes comprehensive
    metrics to identify over-fragmentation, poor separation, and near-duplicates.

    Args:
        embeddings: Array of all embeddings (n_samples, n_features)
        cluster_labels: Array of cluster assignments (n_samples,)
        cluster_assignments: Mapping from summary_id to cluster label
        embeddings_dict: Mapping from summary_id to embedding vector
        cluster_info: Dict with keys: {label: {'label': str, 'size': int, ...}}
        round_id: UUID of the round being analyzed
        near_duplicate_threshold: Similarity threshold for flagging duplicates

    Returns:
        ClusterQualityMetrics: Comprehensive quality metrics object

    Raises:
        ValueError: If insufficient data for metrics computation
    """
    # Filter out noise (if any)
    valid_mask = cluster_labels != -1
    valid_embeddings = embeddings[valid_mask]
    valid_labels = cluster_labels[valid_mask]

    if len(valid_embeddings) < 2:
        raise ValueError("Insufficient data: need at least 2 samples for quality metrics")

    # 1. Silhouette Score
    num_clusters = len(np.unique(valid_labels))
    if num_clusters >= 2:
        silhouette = compute_silhouette_score(embeddings, cluster_labels)
        db_index = compute_davies_bouldin_index(embeddings, cluster_labels)
    else:
        # Single cluster: metrics not applicable
        silhouette = 0.0
        db_index = 0.0

    # 2. Within-cluster cohesion
    cohesion = compute_within_cluster_cohesion(cluster_assignments, embeddings_dict)

    # 3. Centroids for near-duplicate detection
    centroids = compute_cluster_centroids(valid_embeddings, valid_labels)

    # 4. Near-duplicate detection
    cluster_labels_text = {
        label: info['label']
        for label, info in cluster_info.items()
    }
    cluster_sizes = {
        label: info['size']
        for label, info in cluster_info.items()
    }

    near_duplicates = identify_near_duplicate_clusters(
        centroids,
        cluster_labels_text,
        cluster_sizes,
        similarity_threshold=near_duplicate_threshold
    )

    # 5. Cluster size statistics
    singleton_count = sum(1 for info in cluster_info.values() if info['size'] == 1)
    avg_cluster_size = np.mean([info['size'] for info in cluster_info.values()])

    # 6. Cohesion statistics
    cohesion_values = list(cohesion.values())
    min_cohesion = float(np.min(cohesion_values)) if cohesion_values else 0.0
    max_cohesion = float(np.max(cohesion_values)) if cohesion_values else 0.0
    avg_cohesion = float(np.mean(cohesion_values)) if cohesion_values else 0.0

    return ClusterQualityMetrics(
        round_id=round_id,
        silhouette_score=silhouette,
        davies_bouldin_index=db_index,
        near_duplicate_count=len(near_duplicates),
        near_duplicate_pairs=near_duplicates,
        within_cluster_cohesion=cohesion,
        singleton_count=singleton_count,
        avg_cluster_size=avg_cluster_size,
        min_within_cohesion=min_cohesion,
        max_within_cohesion=max_cohesion,
        avg_within_cohesion=avg_cohesion
    )
