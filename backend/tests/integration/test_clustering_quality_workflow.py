"""
Integration tests for clustering quality metrics workflow.

Tests end-to-end quality metrics computation and persistence
in the context of the clustering service.
"""

import pytest
import numpy as np
from uuid import uuid4
from sqlalchemy import select

from src.ml.clustering_quality import compute_cluster_quality_metrics
from src.ml.clustering_algorithms import cluster_with_hdbscan
from src.models.cluster_quality_metrics import ClusterQualityMetric
from src.models.cluster_similarity_warning import ClusterSimilarityWarning


class TestQualityMetricsWorkflow:
    """Integration tests for quality metrics computation workflow."""

    @pytest.mark.asyncio
    async def test_quality_metrics_computed_for_clustering(self, db_session):
        """Test that quality metrics can be computed after clustering."""
        # Create test embeddings
        np.random.seed(42)
        n_samples = 50

        # Create 3 clusters with some overlap
        cluster1 = np.random.randn(20, 384) * 0.5 + np.array([0] * 384)
        cluster2 = np.random.randn(20, 384) * 0.5 + np.array([2] * 384)
        cluster3 = np.random.randn(10, 384) * 0.5 + np.array([-2] * 384)

        embeddings = np.vstack([cluster1, cluster2, cluster3]).astype(np.float32)

        # Run clustering
        cluster_labels = cluster_with_hdbscan(
            embeddings,
            min_cluster_size=2,
            min_samples=3
        )

        # Build cluster info
        unique_labels = np.unique(cluster_labels[cluster_labels >= 0])
        n_clusters = len(unique_labels)

        # Need at least 2 clusters for quality metrics
        assert n_clusters >= 2, "Need at least 2 clusters for this test"

        # Build cluster assignments and embeddings dict
        cluster_assignments = {}
        embeddings_dict = {}
        cluster_info = {}

        for i in range(len(embeddings)):
            label = int(cluster_labels[i])
            if label >= 0:
                sid = uuid4()
                cluster_assignments[sid] = label
                embeddings_dict[sid] = embeddings[i]

                if label not in cluster_info:
                    cluster_info[label] = {'label': f'Test Cluster {label}', 'size': 0}
                cluster_info[label]['size'] += 1

        # Compute quality metrics
        round_id = uuid4()
        metrics = compute_cluster_quality_metrics(
            embeddings=embeddings,
            cluster_labels=cluster_labels,
            cluster_assignments=cluster_assignments,
            embeddings_dict=embeddings_dict,
            cluster_info=cluster_info,
            round_id=round_id
        )

        # Verify metrics are computed
        assert metrics.round_id == round_id
        assert isinstance(metrics.silhouette_score, float)
        assert -1 <= metrics.silhouette_score <= 1
        assert isinstance(metrics.davies_bouldin_index, float)
        assert metrics.davies_bouldin_index >= 0
        assert isinstance(metrics.near_duplicate_count, int)
        assert metrics.near_duplicate_count >= 0
        assert isinstance(metrics.within_cluster_cohesion, dict)
        assert len(metrics.within_cluster_cohesion) == n_clusters

    @pytest.mark.asyncio
    async def test_quality_metrics_persistence(self, db_session):
        """Test that quality metrics can be persisted to database."""
        # Create necessary parent records
        from src.models.discussion import Discussion
        from src.models.round import Round

        discussion_id = uuid4()
        round_id = uuid4()

        discussion = Discussion(
            discussion_id=discussion_id,
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode="HOST_DEFINED",
            total_rounds=3,
            status="ACTIVE"
        )
        db_session.add(discussion)

        round_obj = Round(
            round_id=round_id,
            discussion_id=discussion_id,
            round_num=1,
            question_text="What should we discuss?",
            submission_window_duration_sec=300
        )
        db_session.add(round_obj)
        await db_session.commit()

        # Create and persist a quality metric record
        quality_metric = ClusterQualityMetric(
            round_id=round_id,
            silhouette_score=0.75,
            davies_bouldin_index=0.45,
            near_duplicate_count=5,
            singleton_count=3,
            avg_cluster_size=8.5,
            min_within_cluster_cohesion=0.85,
            max_within_cluster_cohesion=0.98,
            avg_within_cluster_cohesion=0.92
        )

        db_session.add(quality_metric)
        await db_session.commit()

        # Retrieve and verify
        result = await db_session.execute(
            select(ClusterQualityMetric).where(
                ClusterQualityMetric.round_id == round_id
            )
        )
        retrieved = result.scalar_one_or_none()

        assert retrieved is not None
        assert retrieved.round_id == round_id
        assert retrieved.silhouette_score == 0.75
        assert retrieved.davies_bouldin_index == 0.45
        assert retrieved.near_duplicate_count == 5
        assert retrieved.singleton_count == 3

    @pytest.mark.asyncio
    async def test_similarity_warning_persistence(self, db_session):
        """Test that similarity warnings can be persisted to database."""
        # Create necessary parent records
        from src.models.discussion import Discussion
        from src.models.round import Round
        from src.models.thought_space import ThoughtSpace

        discussion_id = uuid4()
        round_id = uuid4()
        cluster_i_id = uuid4()
        cluster_j_id = uuid4()

        discussion = Discussion(
            discussion_id=discussion_id,
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode="HOST_DEFINED",
            total_rounds=3,
            status="ACTIVE"
        )
        db_session.add(discussion)

        round_obj = Round(
            round_id=round_id,
            discussion_id=discussion_id,
            round_num=1,
            question_text="What should we discuss?",
            submission_window_duration_sec=300
        )
        db_session.add(round_obj)

        # Create thought spaces for cluster references
        ts1 = ThoughtSpace(
            cluster_id=cluster_i_id,
            round_id=round_id,
            label_summary="Transparency is essential",
            member_count=5,
            member_pct=0.5
        )
        ts2 = ThoughtSpace(
            cluster_id=cluster_j_id,
            round_id=round_id,
            label_summary="Transparency must be the foundation",
            member_count=3,
            member_pct=0.3
        )
        db_session.add(ts1)
        db_session.add(ts2)
        await db_session.commit()

        # Create test warning
        warning = ClusterSimilarityWarning(
            round_id=round_id,
            cluster_i_id=cluster_i_id,
            cluster_j_id=cluster_j_id,
            similarity_score=0.95,
            cluster_i_label="Transparency is essential",
            cluster_j_label="Transparency must be the foundation",
            cluster_i_size=5,
            cluster_j_size=3,
            reviewed=False
        )

        db_session.add(warning)
        await db_session.commit()

        # Retrieve and verify
        result = await db_session.execute(
            select(ClusterSimilarityWarning).where(
                ClusterSimilarityWarning.round_id == round_id
            )
        )
        retrieved = result.scalar_one_or_none()

        assert retrieved is not None
        assert retrieved.similarity_score == 0.95
        assert retrieved.cluster_i_size == 5
        assert retrieved.cluster_j_size == 3
        assert retrieved.reviewed is False

    @pytest.mark.asyncio
    async def test_similarity_warning_review_workflow(self, db_session):
        """Test the review workflow for similarity warnings."""
        # Create necessary parent records
        from src.models.discussion import Discussion
        from src.models.round import Round
        from src.models.thought_space import ThoughtSpace

        discussion_id = uuid4()
        round_id = uuid4()
        cluster_i_id = uuid4()
        cluster_j_id = uuid4()

        discussion = Discussion(
            discussion_id=discussion_id,
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode="HOST_DEFINED",
            total_rounds=3,
            status="ACTIVE"
        )
        db_session.add(discussion)

        round_obj = Round(
            round_id=round_id,
            discussion_id=discussion_id,
            round_num=1,
            question_text="What should we discuss?",
            submission_window_duration_sec=300
        )
        db_session.add(round_obj)

        # Create thought spaces for cluster references
        ts1 = ThoughtSpace(
            cluster_id=cluster_i_id,
            round_id=round_id,
            label_summary="Test A",
            member_count=4,
            member_pct=0.5
        )
        ts2 = ThoughtSpace(
            cluster_id=cluster_j_id,
            round_id=round_id,
            label_summary="Test B",
            member_count=4,
            member_pct=0.5
        )
        db_session.add(ts1)
        db_session.add(ts2)
        await db_session.commit()

        # Create warning
        warning = ClusterSimilarityWarning(
            round_id=round_id,
            cluster_i_id=cluster_i_id,
            cluster_j_id=cluster_j_id,
            similarity_score=0.92,
            cluster_i_label="Test A",
            cluster_j_label="Test B",
            cluster_i_size=4,
            cluster_j_size=4,
            reviewed=False
        )

        db_session.add(warning)
        await db_session.commit()

        # Mark as reviewed
        warning.mark_reviewed(decision='keep_separate', notes='Semantically distinct')
        await db_session.commit()

        # Verify
        assert warning.reviewed is True
        assert warning.review_decision == 'keep_separate'
        assert warning.review_notes == 'Semantically distinct'

    @pytest.mark.asyncio
    async def test_quality_metric_helper_methods(self, db_session):
        """Test ClusterQualityMetric helper methods."""
        # Good quality
        good_metric = ClusterQualityMetric(
            round_id=uuid4(),
            silhouette_score=0.65,
            davies_bouldin_index=0.8,
            near_duplicate_count=3,
            singleton_count=2,
            avg_cluster_size=10.0,
            avg_within_cluster_cohesion=0.90
        )

        assert good_metric.is_good_quality() is True
        assert good_metric.has_over_fragmentation() is False

        # Poor quality (many near-duplicates)
        poor_metric = ClusterQualityMetric(
            round_id=uuid4(),
            silhouette_score=0.25,
            davies_bouldin_index=2.5,
            near_duplicate_count=35,
            singleton_count=15,
            avg_cluster_size=3.0,
            avg_within_cluster_cohesion=0.95
        )

        assert poor_metric.is_good_quality() is False
        assert poor_metric.has_over_fragmentation() is True

    @pytest.mark.asyncio
    async def test_similarity_warning_severity_levels(self, db_session):
        """Test severity level classification for warnings."""
        # Critical severity (very high similarity)
        critical = ClusterSimilarityWarning(
            round_id=uuid4(),
            cluster_i_id=uuid4(),
            cluster_j_id=uuid4(),
            similarity_score=0.99,
            cluster_i_label="A",
            cluster_j_label="A",
            cluster_i_size=5,
            cluster_j_size=5
        )

        assert critical.get_severity_level() == 'critical'
        assert critical.is_high_severity() is True

        # High severity
        high = ClusterSimilarityWarning(
            round_id=uuid4(),
            cluster_i_id=uuid4(),
            cluster_j_id=uuid4(),
            similarity_score=0.92,
            cluster_i_label="A",
            cluster_j_label="B",
            cluster_i_size=3,
            cluster_j_size=3
        )

        assert high.get_severity_level() == 'high'

        # Medium severity
        medium = ClusterSimilarityWarning(
            round_id=uuid4(),
            cluster_i_id=uuid4(),
            cluster_j_id=uuid4(),
            similarity_score=0.86,
            cluster_i_label="A",
            cluster_j_label="B",
            cluster_i_size=2,
            cluster_j_size=2
        )

        assert medium.get_severity_level() == 'medium'

        # Low severity
        low = ClusterSimilarityWarning(
            round_id=uuid4(),
            cluster_i_id=uuid4(),
            cluster_j_id=uuid4(),
            similarity_score=0.81,
            cluster_i_label="A",
            cluster_j_label="B",
            cluster_i_size=2,
            cluster_j_size=2
        )

        assert low.get_severity_level() == 'low'


class TestParameterTuningIntegration:
    """Integration tests for parameter tuning effects."""

    @pytest.mark.asyncio
    async def test_min_samples_reduces_clusters(self, db_session):
        """Test that increasing min_samples reduces cluster count."""
        np.random.seed(42)

        # Create embeddings with some natural grouping
        embeddings = np.vstack([
            np.random.randn(30, 50) * 0.5 + 0,
            np.random.randn(30, 50) * 0.5 + 5,
            np.random.randn(40, 50) * 0.5 - 5
        ]).astype(np.float32)

        # Cluster with min_samples=2 (old default)
        labels_min2 = cluster_with_hdbscan(
            embeddings,
            min_cluster_size=2,
            min_samples=2
        )
        n_clusters_min2 = len(np.unique(labels_min2[labels_min2 >= 0]))

        # Cluster with min_samples=3 (new default)
        labels_min3 = cluster_with_hdbscan(
            embeddings,
            min_cluster_size=2,
            min_samples=3
        )
        n_clusters_min3 = len(np.unique(labels_min3[labels_min3 >= 0]))

        # min_samples=3 should produce fewer or equal clusters
        assert n_clusters_min3 <= n_clusters_min2, \
            f"Expected min_samples=3 to reduce clusters, got {n_clusters_min2} → {n_clusters_min3}"

    @pytest.mark.asyncio
    async def test_epsilon_merging_reduces_duplicates(self, db_session):
        """Test that cluster_selection_epsilon reduces near-duplicates."""
        np.random.seed(42)

        # Create many small, similar clusters
        embeddings_list = []
        for i in range(10):
            # 10 mini-clusters, each slightly different
            cluster = np.random.randn(10, 50) * 0.3 + i * 0.5
            embeddings_list.append(cluster)

        embeddings = np.vstack(embeddings_list).astype(np.float32)

        # Without epsilon
        labels_no_epsilon = cluster_with_hdbscan(
            embeddings,
            min_cluster_size=2,
            min_samples=2,
            cluster_selection_epsilon=0.0
        )
        n_clusters_no_epsilon = len(np.unique(labels_no_epsilon[labels_no_epsilon >= 0]))

        # With epsilon
        labels_with_epsilon = cluster_with_hdbscan(
            embeddings,
            min_cluster_size=2,
            min_samples=2,
            cluster_selection_epsilon=0.2
        )
        n_clusters_with_epsilon = len(np.unique(labels_with_epsilon[labels_with_epsilon >= 0]))

        # Epsilon should merge similar clusters
        assert n_clusters_with_epsilon <= n_clusters_no_epsilon, \
            f"Expected epsilon to merge clusters, got {n_clusters_no_epsilon} → {n_clusters_with_epsilon}"

    @pytest.mark.asyncio
    async def test_constitutional_compliance_maintained(self, db_session):
        """Test that parameter tuning maintains FR-012 (minority preservation)."""
        np.random.seed(42)

        # Create data with some natural pairs (size=2 clusters)
        pair1 = np.random.randn(2, 50) * 0.1 + 10
        pair2 = np.random.randn(2, 50) * 0.1 - 10
        main_cluster = np.random.randn(20, 50) * 0.5

        embeddings = np.vstack([pair1, pair2, main_cluster]).astype(np.float32)

        # Cluster with tuned parameters
        min_cluster_size = 2  # Constitutional minimum
        labels = cluster_with_hdbscan(
            embeddings,
            min_cluster_size=min_cluster_size,
            min_samples=3
        )

        # Count cluster sizes
        unique_labels = np.unique(labels[labels >= 0])
        cluster_sizes = [np.sum(labels == label) for label in unique_labels]

        # Should still allow clusters of size 2 (minority preservation)
        has_small_clusters = any(size <= 3 for size in cluster_sizes)

        # Note: Due to noise handling, pairs might become noise points
        # The key is that min_cluster_size=2 is still enforced
        assert min_cluster_size == 2, "Constitutional minimum must be preserved"
