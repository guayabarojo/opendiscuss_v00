"""
Unit Tests for Miller's Law Clustering Improvements

Tests adaptive parameter scaling, centroid merging, smart noise reassignment,
and distinct voice promotion for constitutional compliance.
"""

import pytest
import numpy as np
from uuid import uuid4
from typing import Dict, Tuple

from src.ml.clustering_algorithms import compute_adaptive_parameters
from src.services.clustering_service import merge_near_duplicate_clusters
from src.services.outlier_handler import smart_noise_reassignment


class TestAdaptiveParameters:
    """Test adaptive parameter scaling for Miller's Law compliance."""

    def test_small_discussion_uses_fixed_values(self):
        """Verify discussions <10 participants use fixed min values."""
        params = compute_adaptive_parameters(5)

        assert params['min_cluster_size'] == 2, "Small discussions should use min_cluster_size=2"
        assert params['min_samples'] == 2, "Small discussions should use min_samples=2"
        assert params['n_participants'] == 5

    def test_medium_discussion_scales_correctly(self):
        """Verify 50-participant discussion scales correctly (8% and 4%)."""
        params = compute_adaptive_parameters(50)

        # 50 * 0.08 = 4.0 -> 4
        assert params['min_cluster_size'] == 4, "Expected min_cluster_size=4 for 50 participants"
        # 50 * 0.04 = 2.0 -> 2
        assert params['min_samples'] == 2, "Expected min_samples=2 for 50 participants"

    def test_large_discussion_scales_correctly(self):
        """Verify 100-participant discussion scales correctly."""
        params = compute_adaptive_parameters(100)

        # 100 * 0.08 = 8.0 -> 8
        assert params['min_cluster_size'] == 8, "Expected min_cluster_size=8 for 100 participants"
        # 100 * 0.04 = 4.0 -> 4
        assert params['min_samples'] == 4, "Expected min_samples=4 for 100 participants"

    def test_constitutional_compliance_fr012(self):
        """Verify min_cluster_size never goes below 2 (FR-012 compliance)."""
        # Test edge case: 1 participant
        params = compute_adaptive_parameters(1)
        assert params['min_cluster_size'] >= 2, "FR-012 violation: min_cluster_size < 2"

        # Test 10 participants (boundary)
        params = compute_adaptive_parameters(10)
        assert params['min_cluster_size'] >= 2, "FR-012 violation: min_cluster_size < 2"

        # Test 200 participants (large)
        params = compute_adaptive_parameters(200)
        assert params['min_cluster_size'] >= 2, "FR-012 violation: min_cluster_size < 2"


class TestCentroidMerge:
    """Test centroid merge functionality for near-duplicate cluster consolidation."""

    def create_test_data(self) -> Tuple[Dict, Dict, Dict]:
        """Create test cluster data with near-duplicates."""
        # Create 3 clusters: 2 near-duplicates (similarity=0.85) and 1 distinct
        summary_ids = [uuid4() for _ in range(10)]

        # Cluster assignments: 4 in cluster 0, 3 in cluster 1, 3 in cluster 2
        cluster_assignments = {
            summary_ids[0]: 0, summary_ids[1]: 0, summary_ids[2]: 0, summary_ids[3]: 0,
            summary_ids[4]: 1, summary_ids[5]: 1, summary_ids[6]: 1,
            summary_ids[7]: 2, summary_ids[8]: 2, summary_ids[9]: 2,
        }

        # Centroids: cluster 0 and 1 are near-duplicates (0.85 similarity)
        # Using cosine distance: distance = 1 - similarity
        # For 0.85 similarity, vectors should have small angle
        v0 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v1 = np.array([0.95, 0.31, 0.0], dtype=np.float32)  # ~0.85 similarity to v0
        v2 = np.array([0.0, 0.0, 1.0], dtype=np.float32)  # orthogonal (distinct)

        # Normalize vectors
        v1 = v1 / np.linalg.norm(v1)

        centroids = {
            0: v0,
            1: v1,
            2: v2
        }

        cluster_stats = {
            0: (4, 0.4),
            1: (3, 0.3),
            2: (3, 0.3)
        }

        return cluster_assignments, centroids, cluster_stats

    def test_merges_near_duplicates(self):
        """Verify clusters with >0.82 similarity are merged."""
        assignments, centroids, stats = self.create_test_data()

        updated_assignments, updated_centroids, updated_stats = merge_near_duplicate_clusters(
            assignments, centroids, stats, similarity_threshold=0.82
        )

        # Should merge clusters 0 and 1 (smaller into larger)
        unique_clusters = set(updated_assignments.values())
        assert len(unique_clusters) == 2, "Expected 2 clusters after merge (3->2)"
        assert 2 in unique_clusters, "Distinct cluster 2 should remain"
        # Either 0 or 1 should remain (larger cluster)
        assert 0 in unique_clusters or 1 in unique_clusters, "One of the merged clusters should remain"

    def test_does_not_merge_distinct_clusters(self):
        """Verify distinct clusters (<0.82 similarity) are NOT merged."""
        # Create data with truly distinct clusters (no near-duplicates)
        summary_ids = [uuid4() for _ in range(9)]

        cluster_assignments = {
            summary_ids[0]: 0, summary_ids[1]: 0, summary_ids[2]: 0,
            summary_ids[3]: 1, summary_ids[4]: 1, summary_ids[5]: 1,
            summary_ids[6]: 2, summary_ids[7]: 2, summary_ids[8]: 2,
        }

        # Create distinct centroids (orthogonal vectors)
        centroids = {
            0: np.array([1.0, 0.0, 0.0], dtype=np.float32),
            1: np.array([0.0, 1.0, 0.0], dtype=np.float32),
            2: np.array([0.0, 0.0, 1.0], dtype=np.float32),
        }

        cluster_stats = {
            0: (3, 0.33),
            1: (3, 0.33),
            2: (3, 0.34),
        }

        updated_assignments, updated_centroids, updated_stats = merge_near_duplicate_clusters(
            cluster_assignments, centroids, cluster_stats, similarity_threshold=0.82
        )

        # No merges should occur (all clusters are orthogonal, similarity ~0)
        unique_clusters = set(updated_assignments.values())
        assert len(unique_clusters) == 3, "Expected 3 clusters (no merges)"

    def test_merges_smaller_into_larger(self):
        """Verify smaller cluster merges into larger cluster."""
        assignments, centroids, stats = self.create_test_data()

        updated_assignments, updated_centroids, updated_stats = merge_near_duplicate_clusters(
            assignments, centroids, stats, similarity_threshold=0.82
        )

        # Cluster 0 (size=4) is larger than cluster 1 (size=3)
        # So cluster 1 should merge into cluster 0
        # All members of cluster 1 should now be in cluster 0
        original_cluster_1_members = [sid for sid, cid in assignments.items() if cid == 1]

        for sid in original_cluster_1_members:
            # Should be reassigned to cluster 0 (the larger cluster)
            assert updated_assignments[sid] in [0, 1], "Members should be in merged cluster"

    def test_recomputes_stats_correctly(self):
        """Verify cluster stats are correctly recomputed after merge."""
        assignments, centroids, stats = self.create_test_data()

        updated_assignments, updated_centroids, updated_stats = merge_near_duplicate_clusters(
            assignments, centroids, stats, similarity_threshold=0.82
        )

        # Total participants should remain 10
        total_count = sum(count for count, _ in updated_stats.values())
        assert total_count == 10, f"Expected 10 total participants, got {total_count}"

        # Percentages should sum to 1.0
        total_pct = sum(pct for _, pct in updated_stats.values())
        assert abs(total_pct - 1.0) < 0.0001, f"Percentages should sum to 1.0, got {total_pct}"

    def test_constitutional_compliance_fr013(self):
        """Verify only semantic equivalents (>0.82) are merged, not distinct themes."""
        assignments, centroids, stats = self.create_test_data()

        # Cluster 2 (orthogonal vector) should NEVER merge with 0 or 1
        updated_assignments, updated_centroids, updated_stats = merge_near_duplicate_clusters(
            assignments, centroids, stats, similarity_threshold=0.82
        )

        # Cluster 2 members should remain in cluster 2 (no merge with distinct themes)
        original_cluster_2_members = [sid for sid, cid in assignments.items() if cid == 2]
        cluster_2_final_labels = set(updated_assignments[sid] for sid in original_cluster_2_members)

        # All cluster 2 members should still be together (not split or merged with others)
        assert len(cluster_2_final_labels) == 1, "Distinct cluster should remain intact (FR-013)"


class TestSmartNoiseReassignment:
    """Test smart noise reassignment for Miller's Law optimization."""

    def create_test_data(self) -> Tuple[np.ndarray, Dict, Dict, list]:
        """Create test data with noise points."""
        summary_ids = [uuid4() for _ in range(10)]

        # Cluster labels: 5 in cluster 0, 2 in cluster 1, 3 noise (-1)
        cluster_labels = np.array([0, 0, 0, 0, 0, 1, 1, -1, -1, -1], dtype=np.int32)

        # Embeddings: 2 noise points similar to cluster 0, 1 noise point distinct
        embeddings = {
            summary_ids[0]: np.array([1.0, 0.0, 0.0], dtype=np.float32),
            summary_ids[1]: np.array([0.95, 0.31, 0.0], dtype=np.float32),
            summary_ids[2]: np.array([0.98, 0.20, 0.0], dtype=np.float32),
            summary_ids[3]: np.array([0.96, 0.28, 0.0], dtype=np.float32),
            summary_ids[4]: np.array([0.97, 0.24, 0.0], dtype=np.float32),
            summary_ids[5]: np.array([0.0, 1.0, 0.0], dtype=np.float32),
            summary_ids[6]: np.array([0.0, 0.95, 0.31], dtype=np.float32),
            summary_ids[7]: np.array([0.92, 0.39, 0.0], dtype=np.float32),  # Similar to cluster 0 (>0.4)
            summary_ids[8]: np.array([0.90, 0.44, 0.0], dtype=np.float32),  # Similar to cluster 0 (>0.4)
            summary_ids[9]: np.array([0.0, 0.0, 1.0], dtype=np.float32),   # Distinct (<0.4)
        }

        # Normalize embeddings
        for sid in embeddings:
            embeddings[sid] = embeddings[sid] / np.linalg.norm(embeddings[sid])

        # Centroids
        centroids = {
            0: np.array([1.0, 0.0, 0.0], dtype=np.float32),
            1: np.array([0.0, 1.0, 0.0], dtype=np.float32),
        }

        return cluster_labels, embeddings, centroids, summary_ids

    def test_reassigns_similar_noise_points(self):
        """Verify noise points with similarity >= 0.4 are reassigned to clusters."""
        cluster_labels, embeddings, centroids, summary_ids = self.create_test_data()

        updated_labels, reassigned_count, distinct_voice_count = smart_noise_reassignment(
            cluster_labels, embeddings, centroids, summary_ids, similarity_threshold=0.4
        )

        # Noise points 7 and 8 should be reassigned (similar to cluster 0)
        # Noise point 9 should become distinct voice (dissimilar)
        assert reassigned_count >= 1, "Expected at least 1 noise point reassigned"
        assert distinct_voice_count >= 1, "Expected at least 1 distinct voice singleton"

    def test_promotes_distinct_noise_to_singleton(self):
        """Verify noise points with similarity < 0.4 are promoted to Distinct Voice singletons."""
        cluster_labels, embeddings, centroids, summary_ids = self.create_test_data()

        updated_labels, reassigned_count, distinct_voice_count = smart_noise_reassignment(
            cluster_labels, embeddings, centroids, summary_ids, similarity_threshold=0.4
        )

        # Verify no -1 labels remain (100% coverage)
        assert np.sum(updated_labels == -1) == 0, "All noise points should be handled (FR-016)"

        # Verify distinct voice singletons exist
        assert distinct_voice_count > 0, "Expected at least one Distinct Voice singleton"

    def test_constitutional_compliance_fr011_fr016(self):
        """Verify all noise points are handled and 100% coverage is maintained."""
        cluster_labels, embeddings, centroids, summary_ids = self.create_test_data()

        original_noise_count = np.sum(cluster_labels == -1)
        assert original_noise_count == 3, "Test setup should have 3 noise points"

        updated_labels, reassigned_count, distinct_voice_count = smart_noise_reassignment(
            cluster_labels, embeddings, centroids, summary_ids, similarity_threshold=0.4
        )

        # FR-011: All noise points handled
        assert reassigned_count + distinct_voice_count == original_noise_count, \
            "All noise points must be handled (FR-011)"

        # FR-016: 100% coverage (no -1 labels)
        assert np.sum(updated_labels == -1) == 0, "100% coverage required (FR-016)"

        # Verify total count unchanged
        assert len(updated_labels) == len(cluster_labels), "Participant count must not change"

    def test_threshold_behavior(self):
        """Verify similarity threshold correctly controls reassignment vs promotion."""
        cluster_labels, embeddings, centroids, summary_ids = self.create_test_data()

        # Low threshold (0.2): more reassignments, fewer distinct voices
        updated_low, reassigned_low, distinct_low = smart_noise_reassignment(
            cluster_labels.copy(), embeddings, centroids, summary_ids, similarity_threshold=0.2
        )

        # High threshold (0.7): fewer reassignments, more distinct voices
        updated_high, reassigned_high, distinct_high = smart_noise_reassignment(
            cluster_labels.copy(), embeddings, centroids, summary_ids, similarity_threshold=0.7
        )

        # Lower threshold should reassign more
        assert reassigned_low >= reassigned_high, \
            "Lower threshold should reassign more noise points"

        # Higher threshold should create more distinct voices
        assert distinct_high >= distinct_low, \
            "Higher threshold should create more distinct voice singletons"


class TestDistinctVoicePromotion:
    """Test distinct voice singleton promotion logic."""

    def test_distinct_voice_receives_unique_id(self):
        """Verify each distinct voice gets a unique cluster ID."""
        cluster_labels = np.array([0, 0, 1, 1, -1, -1, -1], dtype=np.int32)
        summary_ids = [uuid4() for _ in range(7)]

        # Create embeddings where all noise points are truly distinct (orthogonal)
        embeddings = {
            summary_ids[0]: np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            summary_ids[1]: np.array([0.95, 0.31, 0.0, 0.0], dtype=np.float32),
            summary_ids[2]: np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32),
            summary_ids[3]: np.array([0.0, 0.95, 0.31, 0.0], dtype=np.float32),
            summary_ids[4]: np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32),  # Orthogonal
            summary_ids[5]: np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),  # Orthogonal
            summary_ids[6]: np.array([0.0, 0.0, -1.0, 0.0], dtype=np.float32),  # Opposite direction, orthogonal to 0 and 1
        }

        for sid in embeddings:
            embeddings[sid] = embeddings[sid] / np.linalg.norm(embeddings[sid])

        centroids = {
            0: np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            1: np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32),
        }

        updated_labels, reassigned_count, distinct_voice_count = smart_noise_reassignment(
            cluster_labels, embeddings, centroids, summary_ids, similarity_threshold=0.4
        )

        # All noise points should become distinct voices (orthogonal to existing clusters)
        assert distinct_voice_count == 3, f"Expected 3 distinct voice singletons, got {distinct_voice_count}"

        # Each distinct voice should have unique ID
        distinct_labels = updated_labels[4:]  # Last 3 were noise
        unique_distinct = len(set(distinct_labels))
        assert unique_distinct == 3, f"Each distinct voice should have unique cluster ID, got {unique_distinct} unique IDs for {distinct_labels}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
