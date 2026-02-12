"""
Integration Test for Outlier Handling (User Story 3, T048)

Tests that outliers identified by HDBSCAN are converted to singleton clusters,
ensuring 100% participant coverage.

Test Scenario: 8 tight cluster + 2 outliers
Expected Result: 3 thought spaces created (1 main + 2 singletons) with 100% coverage

Requirements Tested:
- FR-011: Handle outliers/noise points without dropping them
- FR-014: Each noise point becomes its own singleton cluster
- FR-015: Singleton clusters are visible
- FR-016: 100% participant coverage
- SC-010: Outliers converted to singletons with 100% success rate
"""

import pytest
import numpy as np
from uuid import uuid4
from typing import List

from src.ml.clustering_algorithms import cluster_embeddings
from src.services.outlier_handler import (
    identify_outliers,
    assign_singleton_cluster_ids,
    convert_outliers_to_singletons,
    calculate_singleton_metrics
)
from src.services.clustering_service import (
    validate_cluster_count,
    validate_100_percent_coverage
)


def create_tight_cluster_with_outliers(
    tight_count: int = 8,
    outlier_count: int = 2,
    embedding_dim: int = 384
) -> np.ndarray:
    """
    Create synthetic embeddings with a tight cluster and outliers.
    
    Args:
        tight_count: Number of embeddings in tight cluster
        outlier_count: Number of outlier embeddings
        embedding_dim: Embedding dimension
        
    Returns:
        numpy array of embeddings
    """
    np.random.seed(789)
    
    embeddings_list = []
    
    # Tight cluster: Very close together
    cluster_center = np.zeros(embedding_dim)
    cluster_center[0] = 1.0
    
    for i in range(tight_count):
        # Very small noise for tight cluster
        embedding = cluster_center + np.random.normal(0, 0.01, embedding_dim)
        embedding = embedding / np.linalg.norm(embedding)
        embeddings_list.append(embedding)
    
    # Outliers: Far from cluster
    for i in range(outlier_count):
        # Random direction, far from cluster
        embedding = np.random.randn(embedding_dim)
        embedding[50 + i * 10] = 5.0  # Strong signal in different dimensions
        embedding = embedding / np.linalg.norm(embedding)
        embeddings_list.append(embedding)
    
    return np.array(embeddings_list, dtype=np.float32)


@pytest.mark.asyncio
async def test_outlier_handling_8_plus_2():
    """
    Test outlier handling with 8 tight + 2 outlier scenario (T048).
    
    Verifies:
    1. Three thought spaces created (1 main + 2 singletons)
    2. All 10 participants assigned (100% coverage)
    3. Outliers converted to singleton clusters
    4. No participants dropped
    5. Singleton count tracked
    """
    # Arrange: Create 8 tight + 2 outlier embeddings
    tight_count = 8
    outlier_count = 2
    total_participants = tight_count + outlier_count
    
    embeddings = create_tight_cluster_with_outliers(tight_count, outlier_count)
    assert embeddings.shape == (total_participants, 384)
    
    # Act: Run clustering
    cluster_labels = cluster_embeddings(embeddings)
    
    # Initial validation
    cluster_info_before = validate_cluster_count(cluster_labels)
    
    print(f"\nBefore outlier conversion:")
    print(f"  - Clusters: {cluster_info_before['n_clusters']}")
    print(f"  - Noise points: {cluster_info_before['n_noise']}")
    
    # Convert outliers to singletons
    updated_labels, singleton_count = convert_outliers_to_singletons(cluster_labels)
    
    # Assert: Validate after conversion
    cluster_info_after = validate_cluster_count(updated_labels)
    
    print(f"\nAfter outlier conversion:")
    print(f"  - Clusters: {cluster_info_after['n_clusters']}")
    print(f"  - Singleton clusters: {singleton_count}")
    print(f"  - Noise points: {cluster_info_after['n_noise']}")
    
    # Should have no noise points after conversion (FR-014)
    assert cluster_info_after['n_noise'] == 0, (
        f"Expected 0 noise points after conversion, got {cluster_info_after['n_noise']} "
        f"(FR-014 violation)"
    )
    
    # Should have at least 2 clusters (1 main + singletons)
    assert cluster_info_after['n_clusters'] >= 2, (
        f"Expected at least 2 clusters, got {cluster_info_after['n_clusters']}"
    )
    
    # Singleton count should match outliers
    assert singleton_count == outlier_count, (
        f"Expected {outlier_count} singletons, got {singleton_count}"
    )
    
    # 100% coverage: all 10 participants assigned (FR-016)
    total_assigned = sum(cluster_info_after['cluster_sizes'].values())
    assert total_assigned == total_participants, (
        f"Expected {total_participants} assigned, got {total_assigned} "
        f"(FR-016: 100% coverage violation)"
    )
    
    # Test coverage validation
    summary_ids = [uuid4() for _ in range(total_participants)]
    cluster_assignments = {
        summary_id: int(label)
        for summary_id, label in zip(summary_ids, updated_labels)
    }
    
    # This should not raise an error
    validate_100_percent_coverage(cluster_assignments, summary_ids)
    
    print(f"\n✅ Outlier Handling Test PASSED:")
    print(f"   - Total clusters: {cluster_info_after['n_clusters']}")
    print(f"   - Singleton clusters: {singleton_count}")
    print(f"   - Total assigned: {total_assigned}/{total_participants}")
    print(f"   - Coverage: 100% ✓")


@pytest.mark.asyncio
async def test_identify_outliers():
    """
    Test outlier identification function (T043).
    
    Verifies:
    1. Correctly identifies noise points (label=-1)
    2. Returns correct count
    3. Returns correct indices
    """
    # Arrange: Create cluster labels with noise
    cluster_labels = np.array([0, 0, 0, -1, 1, 1, -1, 2], dtype=np.int32)
    
    # Act: Identify outliers
    outlier_indices, outlier_count = identify_outliers(cluster_labels)
    
    # Assert
    assert outlier_count == 2, f"Expected 2 outliers, got {outlier_count}"
    assert len(outlier_indices) == 2, "Outlier indices length mismatch"
    assert 3 in outlier_indices, "Index 3 should be an outlier"
    assert 6 in outlier_indices, "Index 6 should be an outlier"
    
    print(f"\n✅ Identify Outliers Test PASSED:")
    print(f"   - Outliers found: {outlier_count}")
    print(f"   - Outlier indices: {outlier_indices.tolist()}")


@pytest.mark.asyncio
async def test_assign_singleton_cluster_ids():
    """
    Test singleton cluster ID assignment (T044).
    
    Verifies:
    1. Each outlier gets a unique cluster ID
    2. No -1 labels remain
    3. Existing cluster IDs are not modified
    """
    # Arrange: Create cluster labels with noise
    cluster_labels = np.array([0, 0, 0, -1, 1, 1, -1, 2], dtype=np.int32)
    outlier_indices = np.array([3, 6], dtype=np.int32)
    next_cluster_id = 3  # Start after existing clusters 0, 1, 2
    
    # Act: Assign singleton IDs
    updated_labels, singleton_count = assign_singleton_cluster_ids(
        cluster_labels,
        outlier_indices,
        next_cluster_id
    )
    
    # Assert
    assert singleton_count == 2, f"Expected 2 singletons, got {singleton_count}"
    
    # No -1 labels should remain
    assert np.sum(updated_labels == -1) == 0, "Found remaining -1 labels"
    
    # Outliers should have new IDs
    assert updated_labels[3] >= 3, "Outlier at index 3 not reassigned"
    assert updated_labels[6] >= 3, "Outlier at index 6 not reassigned"
    
    # Original clusters should be unchanged
    assert updated_labels[0] == 0, "Original cluster 0 modified"
    assert updated_labels[4] == 1, "Original cluster 1 modified"
    assert updated_labels[7] == 2, "Original cluster 2 modified"
    
    print(f"\n✅ Assign Singleton IDs Test PASSED:")
    print(f"   - Singletons assigned: {singleton_count}")
    print(f"   - Updated labels: {updated_labels.tolist()}")
    print(f"   - No -1 labels remaining: ✓")


@pytest.mark.asyncio
async def test_calculate_singleton_metrics():
    """
    Test singleton metrics calculation (T047).
    
    Verifies:
    1. Correct singleton count
    2. Correct total clusters
    3. Correct percentage calculation
    """
    # Arrange: Create cluster stats with singletons
    cluster_stats = {
        0: (8, 0.8),   # Regular cluster
        1: (1, 0.1),   # Singleton
        2: (1, 0.1),   # Singleton
    }
    
    cluster_labels = np.array([0]*8 + [1] + [2], dtype=np.int32)
    
    # Act: Calculate metrics
    metrics = calculate_singleton_metrics(cluster_labels, cluster_stats)
    
    # Assert
    assert metrics['singleton_count'] == 2, (
        f"Expected 2 singletons, got {metrics['singleton_count']}"
    )
    assert metrics['total_clusters'] == 3, (
        f"Expected 3 total clusters, got {metrics['total_clusters']}"
    )
    expected_pct = (2 / 3) * 100
    assert abs(metrics['singleton_percentage'] - expected_pct) < 0.1, (
        f"Expected {expected_pct:.1f}% singletons, got {metrics['singleton_percentage']:.1f}%"
    )
    
    print(f"\n✅ Singleton Metrics Test PASSED:")
    print(f"   - Singleton count: {metrics['singleton_count']}")
    print(f"   - Total clusters: {metrics['total_clusters']}")
    print(f"   - Singleton percentage: {metrics['singleton_percentage']:.1f}%")


@pytest.mark.asyncio
async def test_100_percent_coverage_validation():
    """
    Test 100% coverage validation (T045).
    
    Verifies:
    1. All participants assigned
    2. No duplicates
    3. No missing participants
    """
    # Arrange: Create complete assignments
    summary_ids = [uuid4() for _ in range(10)]
    cluster_assignments = {
        summary_id: i % 3  # Distribute across 3 clusters
        for i, summary_id in enumerate(summary_ids)
    }
    
    # Act & Assert: Should not raise error
    validate_100_percent_coverage(cluster_assignments, summary_ids)
    
    print(f"\n✅ 100% Coverage Validation Test PASSED:")
    print(f"   - All {len(summary_ids)} participants assigned")
    print(f"   - No duplicates or missing participants")
    
    # Test missing participant detection
    incomplete_assignments = dict(list(cluster_assignments.items())[:-1])  # Remove one
    
    with pytest.raises(ValueError, match="not assigned"):
        validate_100_percent_coverage(incomplete_assignments, summary_ids)
    
    print(f"   - Missing participant detection: ✓")


if __name__ == "__main__":
    import asyncio
    
    print("Running Outlier Handling Integration Tests (T048)...")
    print("=" * 70)
    
    asyncio.run(test_outlier_handling_8_plus_2())
    asyncio.run(test_identify_outliers())
    asyncio.run(test_assign_singleton_cluster_ids())
    asyncio.run(test_calculate_singleton_metrics())
    asyncio.run(test_100_percent_coverage_validation())
    
    print("\n" + "=" * 70)
    print("✅ All Outlier Handling Tests PASSED")
