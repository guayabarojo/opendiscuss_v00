"""
Unit tests for clustering quality metrics module.

Tests:
- Silhouette score computation
- Davies-Bouldin index computation
- Within-cluster cohesion calculation
- Near-duplicate cluster detection
- Edge cases and error handling
"""

import pytest
import numpy as np
from uuid import uuid4

from src.ml.clustering_quality import (
    compute_silhouette_score,
    compute_davies_bouldin_index,
    compute_within_cluster_cohesion,
    identify_near_duplicate_clusters,
    compute_cluster_centroids,
    compute_cluster_quality_metrics,
    ClusterQualityMetrics
)


class TestSilhouetteScore:
    """Tests for Silhouette score computation."""

    def test_perfect_clustering(self):
        """Test Silhouette score with well-separated clusters."""
        # Create 3 tight, well-separated clusters
        cluster1 = np.random.randn(10, 5) + np.array([0, 0, 0, 0, 0])
        cluster2 = np.random.randn(10, 5) + np.array([10, 10, 10, 10, 10])
        cluster3 = np.random.randn(10, 5) + np.array([-10, -10, -10, -10, -10])

        embeddings = np.vstack([cluster1, cluster2, cluster3])
        labels = np.array([0]*10 + [1]*10 + [2]*10)

        score = compute_silhouette_score(embeddings, labels)

        # Well-separated clusters should have high Silhouette score
        assert score > 0.5, f"Expected score > 0.5 for well-separated clusters, got {score}"

    def test_overlapping_clusters(self):
        """Test Silhouette score with overlapping clusters."""
        # Create overlapping clusters
        cluster1 = np.random.randn(20, 5) + np.array([0, 0, 0, 0, 0])
        cluster2 = np.random.randn(20, 5) + np.array([1, 1, 1, 1, 1])  # Close to cluster1

        embeddings = np.vstack([cluster1, cluster2])
        labels = np.array([0]*20 + [1]*20)

        score = compute_silhouette_score(embeddings, labels)

        # Overlapping clusters should have lower score
        assert 0 < score < 0.7, f"Expected moderate score for overlapping clusters, got {score}"

    def test_filters_noise_points(self):
        """Test that noise points (label=-1) are filtered out."""
        embeddings = np.random.randn(30, 5)
        labels = np.array([0]*10 + [1]*10 + [-1]*10)  # 10 noise points

        # Should only use the 20 non-noise points
        score = compute_silhouette_score(embeddings, labels)

        assert isinstance(score, float)
        assert -1 <= score <= 1

    def test_single_cluster_raises_error(self):
        """Test that single cluster raises ValueError."""
        embeddings = np.random.randn(20, 5)
        labels = np.zeros(20, dtype=int)

        with pytest.raises(ValueError, match="at least 2 clusters"):
            compute_silhouette_score(embeddings, labels)


class TestDaviesBouldinIndex:
    """Tests for Davies-Bouldin index computation."""

    def test_well_separated_clusters(self):
        """Test DB index with well-separated clusters."""
        # Create well-separated clusters
        cluster1 = np.random.randn(10, 5) + np.array([0, 0, 0, 0, 0])
        cluster2 = np.random.randn(10, 5) + np.array([20, 20, 20, 20, 20])

        embeddings = np.vstack([cluster1, cluster2])
        labels = np.array([0]*10 + [1]*10)

        db_index = compute_davies_bouldin_index(embeddings, labels)

        # Well-separated clusters should have low DB index
        assert db_index < 1.0, f"Expected DB index < 1.0 for well-separated clusters, got {db_index}"

    def test_overlapping_clusters(self):
        """Test DB index with poorly separated clusters."""
        # Create overlapping clusters
        cluster1 = np.random.randn(15, 5)
        cluster2 = np.random.randn(15, 5) + 0.5  # Slight offset

        embeddings = np.vstack([cluster1, cluster2])
        labels = np.array([0]*15 + [1]*15)

        db_index = compute_davies_bouldin_index(embeddings, labels)

        # Overlapping clusters should have higher DB index
        assert db_index > 0.5, f"Expected DB index > 0.5 for overlapping clusters, got {db_index}"

    def test_filters_noise_points(self):
        """Test that noise points are filtered out."""
        embeddings = np.random.randn(25, 5)
        labels = np.array([0]*10 + [1]*10 + [-1]*5)

        db_index = compute_davies_bouldin_index(embeddings, labels)

        assert isinstance(db_index, float)
        assert db_index >= 0

    def test_single_cluster_raises_error(self):
        """Test that single cluster raises ValueError."""
        embeddings = np.random.randn(15, 5)
        labels = np.zeros(15, dtype=int)

        with pytest.raises(ValueError, match="at least 2 clusters"):
            compute_davies_bouldin_index(embeddings, labels)


class TestWithinClusterCohesion:
    """Tests for within-cluster cohesion calculation."""

    def test_singleton_cluster_perfect_cohesion(self):
        """Test that singleton clusters have cohesion of 1.0."""
        cluster_assignments = {uuid4(): 0}
        embeddings_dict = {list(cluster_assignments.keys())[0]: np.random.randn(5)}

        cohesion = compute_within_cluster_cohesion(cluster_assignments, embeddings_dict)

        assert cohesion[0] == 1.0, "Singleton cluster should have perfect cohesion"

    def test_tight_cluster_high_cohesion(self):
        """Test that tight clusters have high cohesion."""
        # Create 5 very similar embeddings
        base_embedding = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        cluster_assignments = {}
        embeddings_dict = {}

        for i in range(5):
            sid = uuid4()
            cluster_assignments[sid] = 0
            # Add tiny random noise
            embeddings_dict[sid] = base_embedding + np.random.randn(5) * 0.01

        cohesion = compute_within_cluster_cohesion(cluster_assignments, embeddings_dict)

        assert cohesion[0] > 0.95, f"Tight cluster should have high cohesion, got {cohesion[0]}"

    def test_loose_cluster_lower_cohesion(self):
        """Test that loose clusters have lower cohesion."""
        cluster_assignments = {}
        embeddings_dict = {}

        # Create diverse embeddings
        for i in range(5):
            sid = uuid4()
            cluster_assignments[sid] = 0
            embeddings_dict[sid] = np.random.randn(5) * 3  # High variance

        cohesion = compute_within_cluster_cohesion(cluster_assignments, embeddings_dict)

        # Diverse embeddings should have lower cohesion
        assert 0 <= cohesion[0] < 1.0, f"Expected cohesion in [0, 1), got {cohesion[0]}"

    def test_multiple_clusters(self):
        """Test cohesion computation for multiple clusters."""
        cluster_assignments = {}
        embeddings_dict = {}

        # Cluster 0: tight
        for i in range(3):
            sid = uuid4()
            cluster_assignments[sid] = 0
            embeddings_dict[sid] = np.array([1.0, 1.0, 1.0]) + np.random.randn(3) * 0.01

        # Cluster 1: loose
        for i in range(3):
            sid = uuid4()
            cluster_assignments[sid] = 1
            embeddings_dict[sid] = np.random.randn(3) * 5

        cohesion = compute_within_cluster_cohesion(cluster_assignments, embeddings_dict)

        assert len(cohesion) == 2
        assert 0 in cohesion
        assert 1 in cohesion
        # Tight cluster should have higher cohesion than loose cluster
        assert cohesion[0] > cohesion[1]


class TestNearDuplicateDetection:
    """Tests for near-duplicate cluster detection."""

    def test_identifies_perfect_duplicates(self):
        """Test detection of clusters with identical centroids."""
        centroids = {
            0: np.array([1.0, 2.0, 3.0]),
            1: np.array([1.0, 2.0, 3.0]),  # Identical to cluster 0
            2: np.array([10.0, 20.0, 30.0])
        }
        labels = {0: "Label A", 1: "Label A", 2: "Label B"}
        sizes = {0: 5, 1: 3, 2: 4}

        near_dups = identify_near_duplicate_clusters(centroids, labels, sizes, similarity_threshold=0.99)

        assert len(near_dups) >= 1
        # Should find pair (0, 1) with similarity ~1.0
        found = False
        for label_i, label_j, sim, text_i, text_j in near_dups:
            if (label_i == 0 and label_j == 1) or (label_i == 1 and label_j == 0):
                assert sim > 0.99
                found = True
        assert found, "Should detect perfect duplicate clusters"

    def test_identifies_high_similarity(self):
        """Test detection of high-similarity clusters."""
        centroids = {
            0: np.array([1.0, 0.0, 0.0]),
            1: np.array([0.9, 0.1, 0.1]),  # Very similar to cluster 0
            2: np.array([0.0, 1.0, 0.0])   # Different
        }
        labels = {0: "A", 1: "A-like", 2: "B"}
        sizes = {0: 10, 1: 8, 2: 5}

        near_dups = identify_near_duplicate_clusters(centroids, labels, sizes, similarity_threshold=0.8)

        # Should find pair (0, 1)
        assert len(near_dups) >= 1
        assert near_dups[0][2] > 0.8  # High similarity

    def test_no_duplicates_below_threshold(self):
        """Test that dissimilar clusters are not flagged."""
        centroids = {
            0: np.array([1.0, 0.0, 0.0]),
            1: np.array([0.0, 1.0, 0.0]),
            2: np.array([0.0, 0.0, 1.0])
        }
        labels = {0: "A", 1: "B", 2: "C"}
        sizes = {0: 5, 1: 5, 2: 5}

        near_dups = identify_near_duplicate_clusters(centroids, labels, sizes, similarity_threshold=0.9)

        assert len(near_dups) == 0, "Should not flag dissimilar clusters"

    def test_sorted_by_similarity(self):
        """Test that results are sorted by similarity descending."""
        centroids = {
            0: np.array([1.0, 0.0, 0.0]),
            1: np.array([0.99, 0.01, 0.0]),  # Very similar
            2: np.array([0.85, 0.15, 0.0]),  # Moderately similar
        }
        labels = {0: "A", 1: "B", 2: "C"}
        sizes = {0: 5, 1: 5, 2: 5}

        near_dups = identify_near_duplicate_clusters(centroids, labels, sizes, similarity_threshold=0.7)

        # Should be sorted descending
        if len(near_dups) > 1:
            for i in range(len(near_dups) - 1):
                assert near_dups[i][2] >= near_dups[i+1][2]


class TestClusterCentroids:
    """Tests for cluster centroid computation."""

    def test_computes_mean_correctly(self):
        """Test that centroids are computed as mean of embeddings."""
        embeddings = np.array([
            [1.0, 2.0],
            [3.0, 4.0],
            [5.0, 6.0],
            [7.0, 8.0]
        ])
        labels = np.array([0, 0, 1, 1])

        centroids = compute_cluster_centroids(embeddings, labels)

        # Cluster 0: mean of [1,2] and [3,4] = [2,3]
        np.testing.assert_array_almost_equal(centroids[0], [2.0, 3.0])

        # Cluster 1: mean of [5,6] and [7,8] = [6,7]
        np.testing.assert_array_almost_equal(centroids[1], [6.0, 7.0])

    def test_ignores_noise_points(self):
        """Test that noise points (label=-1) are ignored."""
        embeddings = np.array([
            [1.0, 1.0],
            [2.0, 2.0],
            [100.0, 100.0]  # Noise point
        ])
        labels = np.array([0, 0, -1])

        centroids = compute_cluster_centroids(embeddings, labels)

        assert -1 not in centroids
        assert 0 in centroids
        np.testing.assert_array_almost_equal(centroids[0], [1.5, 1.5])


class TestClusterQualityMetrics:
    """Tests for comprehensive quality metrics computation."""

    def test_computes_all_metrics(self):
        """Test that all metrics are computed correctly."""
        # Create simple test data
        embeddings = np.random.randn(30, 5)
        cluster_labels = np.array([0]*10 + [1]*10 + [2]*10)

        cluster_assignments = {}
        embeddings_dict = {}
        for i in range(30):
            sid = uuid4()
            cluster_assignments[sid] = int(cluster_labels[i])
            embeddings_dict[sid] = embeddings[i]

        cluster_info = {
            0: {'label': 'Cluster 0', 'size': 10},
            1: {'label': 'Cluster 1', 'size': 10},
            2: {'label': 'Cluster 2', 'size': 10}
        }

        round_id = uuid4()

        metrics = compute_cluster_quality_metrics(
            embeddings=embeddings,
            cluster_labels=cluster_labels,
            cluster_assignments=cluster_assignments,
            embeddings_dict=embeddings_dict,
            cluster_info=cluster_info,
            round_id=round_id
        )

        # Check all fields are populated
        assert isinstance(metrics, ClusterQualityMetrics)
        assert metrics.round_id == round_id
        assert isinstance(metrics.silhouette_score, float)
        assert isinstance(metrics.davies_bouldin_index, float)
        assert isinstance(metrics.near_duplicate_count, int)
        assert isinstance(metrics.near_duplicate_pairs, list)
        assert isinstance(metrics.within_cluster_cohesion, dict)
        assert metrics.singleton_count == 0
        assert metrics.avg_cluster_size == 10.0

    def test_handles_singletons(self):
        """Test metrics computation with singleton clusters."""
        embeddings = np.random.randn(5, 5)
        cluster_labels = np.array([0, 1, 2, 3, 4])  # All singletons

        cluster_assignments = {}
        embeddings_dict = {}
        for i in range(5):
            sid = uuid4()
            cluster_assignments[sid] = i
            embeddings_dict[sid] = embeddings[i]

        cluster_info = {i: {'label': f'Cluster {i}', 'size': 1} for i in range(5)}

        metrics = compute_cluster_quality_metrics(
            embeddings=embeddings,
            cluster_labels=cluster_labels,
            cluster_assignments=cluster_assignments,
            embeddings_dict=embeddings_dict,
            cluster_info=cluster_info,
            round_id=uuid4()
        )

        assert metrics.singleton_count == 5
        assert metrics.avg_cluster_size == 1.0

    def test_raises_on_insufficient_data(self):
        """Test that insufficient data raises ValueError."""
        embeddings = np.random.randn(1, 5)
        cluster_labels = np.array([0])

        with pytest.raises(ValueError, match="at least 2 samples"):
            compute_cluster_quality_metrics(
                embeddings=embeddings,
                cluster_labels=cluster_labels,
                cluster_assignments={uuid4(): 0},
                embeddings_dict={uuid4(): embeddings[0]},
                cluster_info={0: {'label': 'A', 'size': 1}},
                round_id=uuid4()
            )
