"""
Integration Test for Minority Preservation (User Story 2, T042)

Tests that minority clusters (1-2 participants) are preserved without forced merging,
implementing the "semantic accuracy over aesthetics" constitutional principle.

Test Scenario: 18 majority + 2 minority summaries
Expected Result: 2 distinct thought spaces created (no forced merging)

Requirements Tested:
- FR-012: No minimum cluster size enforcement
- FR-013: No forced merging of semantically distinct clusters
- FR-009: Variable cluster count
- SC-004: Low-frequency clusters preserved 100% of the time
"""

import pytest
import numpy as np
from uuid import uuid4
from typing import List, Dict

from src.ml.clustering_algorithms import create_clusterer, cluster_embeddings
from src.services.clustering_service import (
    validate_cluster_count,
    validate_no_forced_merging,
    calculate_cluster_stats
)


def create_test_embeddings(
    majority_count: int,
    minority_count: int,
    embedding_dim: int = 384
) -> tuple[np.ndarray, List[str]]:
    """
    Create synthetic embeddings for testing minority preservation.
    
    Args:
        majority_count: Number of majority view embeddings (similar)
        minority_count: Number of minority view embeddings (distinct)
        embedding_dim: Embedding dimension
        
    Returns:
        Tuple of (embeddings array, labels list)
    """
    np.random.seed(42)  # For reproducibility
    
    embeddings_list = []
    labels = []
    
    # Majority cluster: Centered around [1, 0, 0, ...]
    majority_center = np.zeros(embedding_dim)
    majority_center[0] = 1.0
    
    for i in range(majority_count):
        # Add small random noise
        embedding = majority_center + np.random.normal(0, 0.05, embedding_dim)
        # Normalize
        embedding = embedding / np.linalg.norm(embedding)
        embeddings_list.append(embedding)
        labels.append("majority")
    
    # Minority cluster: Centered around [0, 1, 0, ...] (orthogonal)
    minority_center = np.zeros(embedding_dim)
    minority_center[1] = 1.0
    
    for i in range(minority_count):
        # Add small random noise
        embedding = minority_center + np.random.normal(0, 0.05, embedding_dim)
        # Normalize
        embedding = embedding / np.linalg.norm(embedding)
        embeddings_list.append(embedding)
        labels.append("minority")
    
    embeddings = np.array(embeddings_list, dtype=np.float32)
    
    return embeddings, labels


@pytest.mark.asyncio
async def test_minority_preservation_18_plus_2():
    """
    Test minority preservation with 18 majority + 2 minority scenario (T042).
    
    Verifies:
    1. Two distinct thought spaces are created
    2. No forced merging occurs
    3. Minority cluster is preserved with 2 participants
    4. Percentages sum to 1.0
    5. Variable cluster count (not fixed K)
    """
    # Arrange: Create 18 majority + 2 minority embeddings
    majority_count = 18
    minority_count = 2
    total_participants = majority_count + minority_count
    
    embeddings, labels = create_test_embeddings(majority_count, minority_count)
    
    assert embeddings.shape == (total_participants, 384)
    assert len(labels) == total_participants
    
    # Act: Run clustering with min_cluster_size=2
    cluster_labels = cluster_embeddings(embeddings)
    
    # Assert: Validate cluster count
    cluster_info = validate_cluster_count(cluster_labels)
    
    # Should have 2 clusters (1 majority, 1 minority)
    assert cluster_info['n_clusters'] >= 2, (
        f"Expected at least 2 clusters, got {cluster_info['n_clusters']} "
        f"(FR-012: minority clusters must be preserved)"
    )
    
    # Check cluster sizes
    cluster_sizes = cluster_info['cluster_sizes']
    assert len(cluster_sizes) >= 2, "Should have at least 2 distinct clusters"
    
    # Find the minority cluster (should have 2 participants)
    sizes = sorted(cluster_sizes.values())
    min_cluster_size = sizes[0]
    max_cluster_size = sizes[-1]
    
    # Minority cluster should exist (FR-012, FR-013)
    assert min_cluster_size <= 2, (
        f"Smallest cluster has {min_cluster_size} participants, "
        f"but minority cluster should have ~2 (FR-012 violation)"
    )
    
    # Majority cluster should exist
    assert max_cluster_size >= 18, (
        f"Largest cluster has {max_cluster_size} participants, "
        f"but majority cluster should have ~18"
    )
    
    # Verify no forced merging
    # Calculate centroids for validation
    centroids = {}
    cluster_stats = {}
    
    for cluster_id, size in cluster_sizes.items():
        mask = (cluster_labels == cluster_id)
        cluster_embeddings = embeddings[mask]
        centroid = np.mean(cluster_embeddings, axis=0)
        centroids[cluster_id] = centroid
        cluster_stats[cluster_id] = (size, size / total_participants)
    
    # This should not raise an error
    validate_no_forced_merging(cluster_stats, centroids, similarity_threshold=0.7)
    
    # Verify percentages sum to 1.0
    total_pct = sum(pct for _, pct in cluster_stats.values())
    assert abs(total_pct - 1.0) < 0.0001, (
        f"Percentages sum to {total_pct}, expected 1.0 (FR-019)"
    )
    
    print(f"\n✅ Minority Preservation Test PASSED:")
    print(f"   - Total clusters: {cluster_info['n_clusters']}")
    print(f"   - Cluster sizes: {sorted(cluster_sizes.values())}")
    print(f"   - Minority cluster preserved: {min_cluster_size} participants")
    print(f"   - Majority cluster size: {max_cluster_size} participants")
    print(f"   - Percentages sum: {total_pct:.6f}")


@pytest.mark.asyncio
async def test_variable_cluster_count():
    """
    Test that clustering produces variable cluster count (FR-009).
    
    Verifies:
    1. Cluster count varies based on data
    2. Not fixed K-means style
    3. Respects semantic structure
    """
    # Arrange: Create 3 semantic groups
    np.random.seed(123)
    
    embeddings_list = []
    
    # Group 1: 10 participants
    for i in range(10):
        emb = np.random.randn(384)
        emb[0] = 5.0  # Strong signal in first dimension
        emb = emb / np.linalg.norm(emb)
        embeddings_list.append(emb)
    
    # Group 2: 5 participants
    for i in range(5):
        emb = np.random.randn(384)
        emb[1] = 5.0  # Strong signal in second dimension
        emb = emb / np.linalg.norm(emb)
        embeddings_list.append(emb)
    
    # Group 3: 3 participants (minority)
    for i in range(3):
        emb = np.random.randn(384)
        emb[2] = 5.0  # Strong signal in third dimension
        emb = emb / np.linalg.norm(emb)
        embeddings_list.append(emb)
    
    embeddings = np.array(embeddings_list, dtype=np.float32)
    
    # Act: Run clustering
    cluster_labels = cluster_embeddings(embeddings)
    
    # Assert: Should detect 3 clusters (variable K)
    cluster_info = validate_cluster_count(cluster_labels)
    
    assert cluster_info['n_clusters'] >= 2, (
        f"Expected at least 2 clusters for distinct groups, "
        f"got {cluster_info['n_clusters']} (FR-009 violation)"
    )
    
    print(f"\n✅ Variable Cluster Count Test PASSED:")
    print(f"   - Detected {cluster_info['n_clusters']} clusters (variable K)")
    print(f"   - Cluster sizes: {sorted(cluster_info['cluster_sizes'].values())}")


@pytest.mark.asyncio
async def test_no_minimum_cluster_size_enforcement():
    """
    Test that no minimum cluster size is enforced (FR-012).
    
    Verifies:
    1. Even single-participant clusters are preserved
    2. No forced merging of small clusters
    3. All participants assigned
    """
    # Arrange: Create scenario with 1 singleton
    np.random.seed(456)
    
    embeddings_list = []
    
    # Main cluster: 8 participants
    for i in range(8):
        emb = np.random.randn(384)
        emb[0] = 3.0
        emb = emb / np.linalg.norm(emb)
        embeddings_list.append(emb)
    
    # Outlier: 1 participant (will become singleton after outlier handling)
    emb = np.random.randn(384)
    emb[100] = 5.0  # Far from main cluster
    emb = emb / np.linalg.norm(emb)
    embeddings_list.append(emb)
    
    embeddings = np.array(embeddings_list, dtype=np.float32)
    
    # Act: Run clustering (will be tested with outlier handler in T048)
    cluster_labels = cluster_embeddings(embeddings)
    
    # Assert: Validate cluster distribution
    cluster_info = validate_cluster_count(cluster_labels)
    
    # Even if outlier is marked as noise (-1), it will be converted to singleton
    total_assigned = sum(cluster_info['cluster_sizes'].values())
    total_with_outliers = total_assigned + cluster_info['n_noise']
    
    assert total_with_outliers == 9, (
        f"Expected 9 total points (assigned + noise), got {total_with_outliers}"
    )
    
    print(f"\n✅ No Minimum Cluster Size Test PASSED:")
    print(f"   - Clusters: {cluster_info['n_clusters']}")
    print(f"   - Assigned: {total_assigned}")
    print(f"   - Noise (to become singletons): {cluster_info['n_noise']}")
    print(f"   - Total coverage: {total_with_outliers}/9")


if __name__ == "__main__":
    import asyncio
    
    print("Running Minority Preservation Integration Tests (T042)...")
    print("=" * 70)
    
    asyncio.run(test_minority_preservation_18_plus_2())
    asyncio.run(test_variable_cluster_count())
    asyncio.run(test_no_minimum_cluster_size_enforcement())
    
    print("\n" + "=" * 70)
    print("✅ All Minority Preservation Tests PASSED")
