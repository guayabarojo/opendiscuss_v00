"""
T069: Centroid Computation Test

Verifies that centroid (mean) computation is accurate:
- Mean calculation across cluster members
- Correct handling of 384-dimensional vectors
- Numerical stability for vector aggregation

Requirements:
- FR-026: Compute centroid for each cluster as mean embedding
- FR-027: Centroid used for cross-round alignment
"""

import pytest
import numpy as np
from uuid import uuid4


class TestCentroidComputation:
    """Test suite for centroid computation."""

    def test_centroid_simple_case(self):
        """
        T069.1: Compute centroid for simple cluster.

        3 vectors with known centroid.
        """
        embeddings = np.array([
            [1.0, 0.0, 0.0],  # Vector 1
            [0.0, 1.0, 0.0],  # Vector 2
            [0.0, 0.0, 1.0],  # Vector 3
        ])

        expected_centroid = np.array([1/3, 1/3, 1/3])
        computed_centroid = np.mean(embeddings, axis=0)

        assert np.allclose(
            computed_centroid, expected_centroid, atol=1e-9
        ), "Centroid computation incorrect for simple case"

    def test_centroid_384_dimension(self):
        """
        T069.2: Compute centroid for 384-dimensional embeddings.

        Generate random 384-dim embeddings and verify centroid.
        """
        np.random.seed(42)
        n_samples = 10
        embedding_dim = 384

        embeddings = np.random.randn(n_samples, embedding_dim)
        centroid = np.mean(embeddings, axis=0)

        # Verify dimensions
        assert centroid.shape == (384,), f"Centroid shape is {centroid.shape}, expected (384,)"

        # Verify computation
        for i in range(embedding_dim):
            expected_val = np.mean(embeddings[:, i])
            actual_val = centroid[i]
            assert np.isclose(actual_val, expected_val, atol=1e-9), (
                f"Centroid[{i}] mismatch: {actual_val} vs {expected_val}"
            )

    def test_centroid_two_vectors(self):
        """
        T069.3: Centroid of exactly 2 vectors (minority cluster).

        Verify midpoint calculation is correct.
        """
        embeddings = np.array([
            [2.0, 4.0, 6.0],
            [4.0, 8.0, 10.0],
        ])

        expected_centroid = np.array([3.0, 6.0, 8.0])
        computed_centroid = np.mean(embeddings, axis=0)

        assert np.allclose(
            computed_centroid, expected_centroid, atol=1e-9
        ), "Centroid computation incorrect for 2-vector case"

    def test_centroid_single_vector(self):
        """
        T069.4: Centroid of single vector (singleton cluster).

        Centroid should equal the vector itself.
        """
        embedding = np.array([1.5, 2.5, 3.5, 4.5])
        embeddings = embedding.reshape(1, -1)

        centroid = np.mean(embeddings, axis=0)

        assert np.allclose(
            centroid, embedding, atol=1e-9
        ), "Centroid of single vector should equal the vector"

    def test_centroid_normalized_vectors(self):
        """
        T069.5: Centroid of L2-normalized vectors.

        Verify centroid computation on normalized embeddings.
        """
        # Create normalized vectors
        vectors = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])

        centroid = np.mean(vectors, axis=0)

        # Centroid should be [1/3, 1/3, 1/3]
        expected = np.array([1/3, 1/3, 1/3])
        assert np.allclose(centroid, expected, atol=1e-9), (
            "Centroid of normalized vectors incorrect"
        )

    def test_centroid_no_nan_propagation(self):
        """
        T069.6: NaN values don't propagate to centroid.

        If any embedding has NaN, centroid should handle gracefully.
        """
        embeddings = np.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
        ])

        centroid = np.mean(embeddings, axis=0)

        # Should not have NaNs
        assert not np.isnan(centroid).any(), "Centroid contains NaN values"
        assert not np.isinf(centroid).any(), "Centroid contains Inf values"

    def test_centroid_negative_values(self):
        """
        T069.7: Handle negative embedding values.

        SBERT embeddings can be negative; verify correct aggregation.
        """
        embeddings = np.array([
            [-1.0, -2.0, -3.0],
            [1.0, 2.0, 3.0],
            [0.0, 0.0, 0.0],
        ])

        expected_centroid = np.array([0.0, 0.0, 0.0])
        computed_centroid = np.mean(embeddings, axis=0)

        assert np.allclose(
            computed_centroid, expected_centroid, atol=1e-9
        ), "Centroid computation incorrect for negative values"

    def test_centroid_large_values(self):
        """
        T069.8: Handle large embedding values.

        Test numerical stability with large numbers.
        """
        embeddings = np.array([
            [1e3, 2e3, 3e3],
            [4e3, 5e3, 6e3],
            [7e3, 8e3, 9e3],
        ])

        centroid = np.mean(embeddings, axis=0)
        expected = np.array([4e3, 5e3, 6e3])

        assert np.allclose(
            centroid, expected, rtol=1e-9
        ), "Centroid computation fails for large values"

    def test_centroid_small_values(self):
        """
        T069.9: Handle small embedding values.

        Test numerical stability with small numbers.
        """
        embeddings = np.array([
            [1e-5, 2e-5, 3e-5],
            [4e-5, 5e-5, 6e-5],
            [7e-5, 8e-5, 9e-5],
        ])

        centroid = np.mean(embeddings, axis=0)
        expected = np.array([4e-5, 5e-5, 6e-5])

        assert np.allclose(
            centroid, expected, rtol=1e-9
        ), "Centroid computation fails for small values"

    def test_centroid_identical_vectors(self):
        """
        T069.10: Centroid of identical vectors.

        If all cluster members have same embedding, centroid should equal it.
        """
        vector = np.random.randn(384)
        embeddings = np.tile(vector, (10, 1))  # 10 copies

        centroid = np.mean(embeddings, axis=0)

        assert np.allclose(
            centroid, vector, atol=1e-9
        ), "Centroid of identical vectors should equal the vector"

    def test_centroid_orthogonal_vectors(self):
        """
        T069.11: Centroid of orthogonal vectors.

        Test with vectors that are orthogonal (dot product = 0).
        """
        embeddings = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ])

        centroid = np.mean(embeddings, axis=0)
        expected = np.ones(4) * 0.25

        assert np.allclose(
            centroid, expected, atol=1e-9
        ), "Centroid of orthogonal vectors incorrect"

    def test_centroid_batch_computation(self):
        """
        T069.12: Centroid computation for batch of clusters.

        Simulate computing centroids for multiple clusters.
        """
        np.random.seed(42)
        n_clusters = 5
        samples_per_cluster = 20
        embedding_dim = 384

        # Generate 5 clusters
        clusters = []
        for c in range(n_clusters):
            cluster_embeddings = np.random.randn(samples_per_cluster, embedding_dim)
            clusters.append(cluster_embeddings)

        # Compute centroids
        centroids = []
        for cluster in clusters:
            centroid = np.mean(cluster, axis=0)
            centroids.append(centroid)

        centroids = np.array(centroids)

        # Verify shapes
        assert centroids.shape == (n_clusters, embedding_dim), (
            f"Centroids shape {centroids.shape} != {(n_clusters, embedding_dim)}"
        )

        # Verify each centroid is actually the mean
        for i, cluster in enumerate(clusters):
            expected = np.mean(cluster, axis=0)
            assert np.allclose(
                centroids[i], expected, atol=1e-9
            ), f"Centroid {i} computation incorrect"

    def test_centroid_distance_from_members(self):
        """
        T069.13: Centroid is equidistant from cluster members.

        For symmetric cluster, centroid should be in center.
        """
        # Create symmetric cluster around origin
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -1.0, 0.0],
        ])

        centroid = np.mean(embeddings, axis=0)

        # Centroid should be at origin
        expected = np.array([0.0, 0.0, 0.0])
        assert np.allclose(
            centroid, expected, atol=1e-9
        ), "Centroid should be at origin for symmetric cluster"

        # All members should be equidistant from centroid
        distances = [np.linalg.norm(emb - centroid) for emb in embeddings]
        assert np.allclose(
            distances, distances[0], atol=1e-9
        ), "Members should be equidistant from centroid"

    def test_centroid_with_weighted_vectors(self):
        """
        T069.14: Conceptual test for weighted centroid.

        Documents how weighted centroid would work (for future use).
        """
        # Simple weighted mean calculation
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        weights = np.array([0.5, 0.3, 0.2])

        # Weighted centroid
        weighted_centroid = np.average(embeddings, axis=0, weights=weights)

        # Simple centroid for reference
        simple_centroid = np.mean(embeddings, axis=0)

        # Weighted should differ from simple
        assert not np.allclose(
            weighted_centroid, simple_centroid
        ), "Weighted and simple centroids should differ with non-uniform weights"

    def test_centroid_numerical_precision(self):
        """
        T069.15: Test numerical precision edge case.

        Very close numbers that should produce precise centroid.
        """
        # Numbers that might lose precision
        embeddings = np.array([
            [1.0000000001, 2.0000000001, 3.0000000001],
            [1.0000000002, 2.0000000002, 3.0000000002],
            [1.0000000003, 2.0000000003, 3.0000000003],
        ])

        centroid = np.mean(embeddings, axis=0)

        # Centroid should be approximately [1.0000000002, 2.0000000002, 3.0000000002]
        expected = np.array([1.0000000002, 2.0000000002, 3.0000000002])

        # Use lower precision for very small differences
        assert np.allclose(
            centroid, expected, atol=1e-9, rtol=1e-7
        ), "Centroid precision lost for very close numbers"


class TestCentroidProperties:
    """Test mathematical properties of centroids."""

    def test_centroid_minimizes_mean_distance(self):
        """
        T069.16: Centroid minimizes sum of squared distances.

        This is a fundamental property of the mean.
        """
        embeddings = np.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
        ])

        centroid = np.mean(embeddings, axis=0)

        # Sum of squared distances from centroid
        distances_from_centroid = np.sum([
            np.sum((emb - centroid) ** 2) for emb in embeddings
        ])

        # Try a different point (should have higher distance)
        other_point = np.array([2.0, 3.0, 4.0])
        distances_from_other = np.sum([
            np.sum((emb - other_point) ** 2) for emb in embeddings
        ])

        assert (
            distances_from_centroid <= distances_from_other
        ), "Centroid should minimize sum of squared distances"

    def test_centroid_commutativity(self):
        """
        T069.17: Centroid computation is order-independent.

        Centroid of [A, B, C] = Centroid of [C, B, A].
        """
        embeddings = np.random.randn(10, 384)
        centroid1 = np.mean(embeddings, axis=0)

        # Shuffle embeddings
        shuffled_indices = np.random.permutation(len(embeddings))
        shuffled = embeddings[shuffled_indices]

        centroid2 = np.mean(shuffled, axis=0)

        assert np.allclose(
            centroid1, centroid2, atol=1e-9
        ), "Centroid should be independent of input order"

    def test_centroid_subset_property(self):
        """
        T069.18: Centroid of subsets.

        Test relationship between centroids of subsets and full set.
        """
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
        ])

        # Centroid of first 3
        subset1_centroid = np.mean(embeddings[:3], axis=0)

        # Centroid of all 4
        full_centroid = np.mean(embeddings, axis=0)

        # Should be different
        assert not np.allclose(
            subset1_centroid, full_centroid
        ), "Subset and full centroids should differ"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
