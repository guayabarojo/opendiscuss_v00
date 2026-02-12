"""
Parameter Tuning A/B Test Script

Compares clustering quality with different parameters on historical discussion data.

Tests:
- Baseline: min_samples=2, cluster_selection_epsilon=0.0 (old defaults)
- Tuned: min_samples=3, cluster_selection_epsilon=0.0 (new default)
- Aggressive: min_samples=4, cluster_selection_epsilon=0.1 (further tuning)

Usage:
    python backend/test_parameter_tuning.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_session_factory
from src.models.thought_space import ThoughtSpace
from src.models.round import Round
from src.models.approved_summary import ApprovedSummary
from src.models.embedding import Embedding
from src.ml.clustering_algorithms import cluster_with_hdbscan
from src.ml.clustering_quality import (
    compute_cluster_quality_metrics,
    compute_cluster_centroids,
    identify_near_duplicate_clusters
)


async def get_round_data(round_id: UUID, db: AsyncSession) -> Dict:
    """Fetch embeddings and metadata for a round."""

    # Get approved summaries with embeddings
    result = await db.execute(
        select(ApprovedSummary, Embedding)
        .join(Embedding, ApprovedSummary.summary_id == Embedding.summary_id)
        .where(ApprovedSummary.round_id == round_id)
    )
    summary_embeddings = result.all()

    if not summary_embeddings:
        return None

    # Build embeddings array and summary IDs
    embeddings = []
    summary_ids = []

    for approved_summary, embedding_obj in summary_embeddings:
        embedding_vector = embedding_obj.get_vector_as_numpy()
        embeddings.append(embedding_vector)
        summary_ids.append(approved_summary.summary_id)

    return {
        'embeddings': np.array(embeddings),
        'summary_ids': summary_ids,
        'round_id': round_id
    }


async def test_clustering_config(
    embeddings: np.ndarray,
    summary_ids: List[UUID],
    round_id: UUID,
    min_samples: int,
    cluster_selection_epsilon: float,
    config_name: str
) -> Dict:
    """Run clustering with specific parameters and compute quality metrics."""

    print(f"\n{'='*80}")
    print(f"Testing Configuration: {config_name}")
    print(f"  min_samples: {min_samples}")
    print(f"  cluster_selection_epsilon: {cluster_selection_epsilon}")
    print(f"{'='*80}")

    # Run clustering
    cluster_labels = cluster_with_hdbscan(
        embeddings,
        min_cluster_size=2,
        min_samples=min_samples,
        cluster_selection_epsilon=cluster_selection_epsilon
    )

    # Build cluster info
    unique_labels = np.unique(cluster_labels[cluster_labels >= 0])
    n_clusters = len(unique_labels)
    n_noise = int((cluster_labels == -1).sum())

    print(f"\n📊 Basic Results:")
    print(f"  Clusters formed: {n_clusters}")
    print(f"  Noise points: {n_noise}")

    # Cluster size distribution
    singleton_count = 0
    pair_count = 0
    small_count = 0
    medium_count = 0

    cluster_info = {}
    cluster_assignments = {}
    embeddings_dict = {}

    for i, summary_id in enumerate(summary_ids):
        label = int(cluster_labels[i])
        if label >= 0:
            cluster_assignments[summary_id] = label
            embeddings_dict[summary_id] = embeddings[i]

            if label not in cluster_info:
                cluster_info[label] = {
                    'label': f'Cluster {label}',
                    'size': 0
                }
            cluster_info[label]['size'] += 1

    # Count cluster sizes
    for label, info in cluster_info.items():
        size = info['size']
        if size == 1:
            singleton_count += 1
        elif size == 2:
            pair_count += 1
        elif 3 <= size <= 5:
            small_count += 1
        else:
            medium_count += 1

    print(f"\n📏 Cluster Size Distribution:")
    print(f"  Singletons (size=1): {singleton_count}")
    print(f"  Pairs (size=2): {pair_count}")
    print(f"  Small (size=3-5): {small_count}")
    print(f"  Medium (size>5): {medium_count}")

    # Compute quality metrics if we have enough clusters
    if n_clusters >= 2:
        try:
            quality_metrics = compute_cluster_quality_metrics(
                embeddings=embeddings,
                cluster_labels=cluster_labels,
                cluster_assignments=cluster_assignments,
                embeddings_dict=embeddings_dict,
                cluster_info=cluster_info,
                round_id=round_id,
                near_duplicate_threshold=0.8
            )

            print(f"\n🎯 Quality Metrics:")
            print(f"  Silhouette Score: {quality_metrics.silhouette_score:.3f}")
            print(f"  Davies-Bouldin Index: {quality_metrics.davies_bouldin_index:.3f}")
            print(f"  Near-Duplicate Count: {quality_metrics.near_duplicate_count}")
            print(f"  Avg Within-Cluster Cohesion: {quality_metrics.avg_within_cohesion:.3f}")

            if quality_metrics.near_duplicate_count > 0:
                print(f"\n⚠️  Top 5 Near-Duplicate Pairs:")
                for i, (label_i, label_j, sim, _, _) in enumerate(quality_metrics.near_duplicate_pairs[:5], 1):
                    size_i = cluster_info[label_i]['size']
                    size_j = cluster_info[label_j]['size']
                    print(f"  {i}. Cluster {label_i} ({size_i}p) <-> Cluster {label_j} ({size_j}p): {sim:.3f}")

            return {
                'config_name': config_name,
                'n_clusters': n_clusters,
                'n_noise': n_noise,
                'singleton_count': singleton_count,
                'near_duplicate_count': quality_metrics.near_duplicate_count,
                'silhouette_score': quality_metrics.silhouette_score,
                'davies_bouldin_index': quality_metrics.davies_bouldin_index,
                'avg_cohesion': quality_metrics.avg_within_cohesion
            }
        except Exception as e:
            print(f"\n❌ Error computing quality metrics: {e}")
            return None
    else:
        print(f"\n⚠️  Not enough clusters for quality metrics (need ≥2, got {n_clusters})")
        return None


async def run_comparison():
    """Run A/B comparison on historical discussion."""

    discussion_id = UUID("d4f27873-7c28-4d00-9084-ed2fb0d74b7e")

    print("="*80)
    print("CLUSTERING PARAMETER TUNING TEST")
    print("="*80)
    print(f"Discussion: {discussion_id}")
    print(f"Testing 3 configurations on Round 1 data")
    print()

    session_factory = get_session_factory()
    async with session_factory() as db:
        # Get round 1
        result = await db.execute(
            select(Round)
            .where(Round.discussion_id == discussion_id)
            .order_by(Round.round_num)
            .limit(1)
        )
        round_obj = result.scalar_one_or_none()

        if not round_obj:
            print("❌ Round not found")
            return

        print(f"Round ID: {round_obj.round_id}")
        print(f"Round Number: {round_obj.round_num}")
        print()

        # Get round data
        data = await get_round_data(round_obj.round_id, db)
        if not data:
            print("❌ No data found for round")
            return

        print(f"Loaded {len(data['embeddings'])} embeddings")
        print()

        # Test configurations
        configs = [
            {
                'name': 'BASELINE (Old)',
                'min_samples': 2,
                'epsilon': 0.0
            },
            {
                'name': 'TUNED (New Default)',
                'min_samples': 3,
                'epsilon': 0.0
            },
            {
                'name': 'AGGRESSIVE',
                'min_samples': 4,
                'epsilon': 0.1
            }
        ]

        results = []
        for config in configs:
            result = await test_clustering_config(
                embeddings=data['embeddings'],
                summary_ids=data['summary_ids'],
                round_id=round_obj.round_id,
                min_samples=config['min_samples'],
                cluster_selection_epsilon=config['epsilon'],
                config_name=config['name']
            )
            if result:
                results.append(result)

        # Print comparison
        print("\n" + "="*80)
        print("COMPARISON SUMMARY")
        print("="*80)
        print(f"\n{'Config':<25} {'Clusters':<10} {'Noise':<8} {'Singles':<10} {'Near-Dups':<12} {'Silhouette':<12}")
        print("-" * 80)

        for r in results:
            print(f"{r['config_name']:<25} {r['n_clusters']:<10} {r['n_noise']:<8} "
                  f"{r['singleton_count']:<10} {r['near_duplicate_count']:<12} "
                  f"{r['silhouette_score']:<12.3f}")

        print("\n" + "="*80)
        print("KEY OBSERVATIONS:")
        print("="*80)

        if len(results) >= 2:
            baseline = results[0]
            tuned = results[1]

            cluster_reduction = baseline['n_clusters'] - tuned['n_clusters']
            dup_reduction = baseline['near_duplicate_count'] - tuned['near_duplicate_count']
            dup_pct_reduction = (dup_reduction / baseline['near_duplicate_count'] * 100) if baseline['near_duplicate_count'] > 0 else 0

            print(f"\n✅ Cluster Reduction: {baseline['n_clusters']} → {tuned['n_clusters']} "
                  f"({cluster_reduction} fewer clusters, {cluster_reduction/baseline['n_clusters']*100:.1f}% reduction)")

            print(f"\n✅ Near-Duplicate Reduction: {baseline['near_duplicate_count']} → {tuned['near_duplicate_count']} "
                  f"({dup_reduction} fewer pairs, {dup_pct_reduction:.1f}% reduction)")

            if tuned['near_duplicate_count'] < 10:
                print(f"\n🎯 SUCCESS: Near-duplicates reduced to acceptable level (<10)")
            else:
                print(f"\n⚠️  Still {tuned['near_duplicate_count']} near-duplicates. Consider AGGRESSIVE config.")

            print(f"\n📊 Minority Preservation:")
            print(f"  Baseline singletons: {baseline['singleton_count']}")
            print(f"  Tuned singletons: {tuned['singleton_count']}")
            if tuned['singleton_count'] > 0:
                print(f"  ✅ Minorities still preserved (constitutional compliance maintained)")


async def main():
    """Run the comparison test."""
    await run_comparison()


if __name__ == "__main__":
    asyncio.run(main())
