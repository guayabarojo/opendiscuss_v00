"""
Quick Clustering Quality Baseline Script

Measures clustering quality for existing discussion to establish baseline.

Usage:
    python backend/quick_clustering_baseline.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from uuid import UUID

import numpy as np
from sklearn.metrics import silhouette_score, davies_bouldin_score
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_session_factory
from src.models.thought_space import ThoughtSpace
from src.models.round import Round
from src.models.approved_summary import ApprovedSummary
from src.models.embedding import Embedding


async def get_round_clustering_data(round_id: UUID, db: AsyncSession) -> Dict:
    """Fetch clustering data for a round."""

    # Get all thought spaces (clusters) for this round
    result = await db.execute(
        select(ThoughtSpace).where(ThoughtSpace.round_id == round_id)
    )
    thought_spaces = result.scalars().all()

    if not thought_spaces:
        return None

    # Create a mapping from cluster_id to numeric label (for sklearn metrics)
    cluster_id_to_label = {ts.cluster_id: i for i, ts in enumerate(thought_spaces)}

    # Get all approved summaries with embeddings for this round
    result = await db.execute(
        select(ApprovedSummary, Embedding)
        .join(Embedding, ApprovedSummary.summary_id == Embedding.summary_id)
        .where(ApprovedSummary.round_id == round_id)
    )
    summary_embeddings = result.all()

    if not summary_embeddings:
        return None

    # Build embeddings and cluster assignments
    embeddings = []
    cluster_labels = []
    summary_to_cluster = {}

    for approved_summary, embedding_obj in summary_embeddings:
        # Deserialize embedding vector
        embedding_vector = embedding_obj.get_vector_as_numpy()
        embeddings.append(embedding_vector)

        # Find which cluster this summary belongs to
        cluster_label = -1  # noise by default (shouldn't happen in our system)
        if approved_summary.cluster_id is not None:
            cluster_label = cluster_id_to_label.get(approved_summary.cluster_id, -1)

        cluster_labels.append(cluster_label)
        summary_to_cluster[approved_summary.summary_id] = cluster_label

    if not embeddings:
        return None

    # Build cluster info (using numeric labels for consistency)
    cluster_info = {}
    for thought_space in thought_spaces:
        numeric_label = cluster_id_to_label[thought_space.cluster_id]

        cluster_info[numeric_label] = {
            'cluster_id': thought_space.cluster_id,
            'label': thought_space.label_summary[:100],  # Truncate for display
            'size': thought_space.member_count,
            'centroid': None  # Will compute from embeddings
        }

    return {
        'embeddings': np.array(embeddings),
        'cluster_labels': np.array(cluster_labels),
        'clusters': cluster_info,
        'summary_to_cluster': summary_to_cluster
    }


def compute_cluster_centroids(embeddings: np.ndarray, cluster_labels: np.ndarray) -> Dict[int, np.ndarray]:
    """Compute centroid (mean embedding) for each cluster."""
    centroids = {}
    unique_labels = set(cluster_labels)

    for label in unique_labels:
        if label == -1:  # Skip noise
            continue
        mask = cluster_labels == label
        cluster_embeddings = embeddings[mask]
        centroids[label] = cluster_embeddings.mean(axis=0)

    return centroids


def compute_within_cluster_cohesion(embeddings: np.ndarray, cluster_labels: np.ndarray) -> Dict[int, float]:
    """Compute average pairwise cosine similarity within each cluster."""
    cohesion = {}
    unique_labels = set(cluster_labels)

    for label in unique_labels:
        if label == -1:  # Skip noise
            continue

        mask = cluster_labels == label
        cluster_embeddings = embeddings[mask]

        if len(cluster_embeddings) == 1:
            cohesion[label] = 1.0  # Perfect cohesion for singleton
        else:
            # Compute pairwise similarities
            similarities = cosine_similarity(cluster_embeddings)
            # Get upper triangle (excluding diagonal)
            n = len(similarities)
            upper_tri = similarities[np.triu_indices(n, k=1)]
            cohesion[label] = float(upper_tri.mean()) if len(upper_tri) > 0 else 1.0

    return cohesion


def identify_near_duplicates(
    centroids: Dict[int, np.ndarray],
    cluster_info: Dict,
    threshold: float = 0.8
) -> List[Tuple[int, int, float, str, str]]:
    """Identify cluster pairs with high centroid similarity."""
    near_duplicates = []
    labels = sorted(centroids.keys())

    for i, label_i in enumerate(labels):
        for label_j in labels[i+1:]:
            centroid_i = centroids[label_i]
            centroid_j = centroids[label_j]

            # Compute cosine similarity
            similarity = float(cosine_similarity(
                centroid_i.reshape(1, -1),
                centroid_j.reshape(1, -1)
            )[0, 0])

            if similarity >= threshold:
                near_duplicates.append((
                    label_i,
                    label_j,
                    similarity,
                    cluster_info[label_i]['label'],
                    cluster_info[label_j]['label']
                ))

    # Sort by similarity descending
    near_duplicates.sort(key=lambda x: x[2], reverse=True)
    return near_duplicates


async def analyze_round(round_id: UUID, db: AsyncSession) -> Dict:
    """Analyze clustering quality for a single round."""

    print(f"\n{'='*80}")
    print(f"Analyzing Round: {round_id}")
    print(f"{'='*80}")

    data = await get_round_clustering_data(round_id, db)
    if data is None:
        print("❌ No clustering data found for this round")
        return None

    embeddings = data['embeddings']
    cluster_labels = data['cluster_labels']
    cluster_info = data['clusters']

    # Filter out noise (-1) for quality metrics
    valid_mask = cluster_labels != -1
    valid_embeddings = embeddings[valid_mask]
    valid_labels = cluster_labels[valid_mask]

    if len(valid_embeddings) < 2:
        print("❌ Insufficient data for quality metrics")
        return None

    # Compute metrics
    num_clusters = len(set(valid_labels))
    num_noise = int((cluster_labels == -1).sum())

    print(f"\n📊 Basic Statistics:")
    print(f"  Total submissions: {len(embeddings)}")
    print(f"  Clusters formed: {num_clusters}")
    print(f"  Noise points: {num_noise}")

    # Cluster size distribution
    cluster_sizes = {}
    for label in set(valid_labels):
        size = int((valid_labels == label).sum())
        cluster_sizes[label] = size

    singleton_count = sum(1 for size in cluster_sizes.values() if size == 1)
    pair_count = sum(1 for size in cluster_sizes.values() if size == 2)
    small_count = sum(1 for size in cluster_sizes.values() if 3 <= size <= 5)
    medium_count = sum(1 for size in cluster_sizes.values() if size > 5)

    print(f"\n📏 Cluster Size Distribution:")
    print(f"  Singletons (size=1): {singleton_count}")
    print(f"  Pairs (size=2): {pair_count}")
    print(f"  Small (size=3-5): {small_count}")
    print(f"  Medium (size>5): {medium_count}")

    # Silhouette Score
    if num_clusters > 1:
        silhouette = silhouette_score(valid_embeddings, valid_labels, metric='cosine')
        print(f"\n🎯 Silhouette Score: {silhouette:.3f}")
        if silhouette > 0.5:
            print("  ✅ GOOD - Strong cluster separation")
        elif silhouette > 0.3:
            print("  ⚠️  FAIR - Moderate separation, some overlap")
        else:
            print("  ❌ POOR - Weak separation, significant overlap")
    else:
        silhouette = None
        print("\n🎯 Silhouette Score: N/A (only 1 cluster)")

    # Davies-Bouldin Index
    if num_clusters > 1:
        db_index = davies_bouldin_score(valid_embeddings, valid_labels)
        print(f"\n📐 Davies-Bouldin Index: {db_index:.3f}")
        if db_index < 1.0:
            print("  ✅ EXCELLENT - Very good separation")
        elif db_index < 2.0:
            print("  ⚠️  FAIR - Acceptable separation")
        else:
            print("  ❌ POOR - Clusters overlap significantly")
    else:
        db_index = None
        print("\n📐 Davies-Bouldin Index: N/A (only 1 cluster)")

    # Within-cluster cohesion
    cohesion = compute_within_cluster_cohesion(valid_embeddings, valid_labels)

    if cohesion:
        avg_cohesion = np.mean(list(cohesion.values()))
        min_cohesion = np.min(list(cohesion.values()))
        max_cohesion = np.max(list(cohesion.values()))

        print(f"\n🔗 Within-Cluster Cohesion:")
        print(f"  Average: {avg_cohesion:.3f}")
        print(f"  Range: [{min_cohesion:.3f}, {max_cohesion:.3f}]")

        # Show clusters with low cohesion
        low_cohesion_clusters = [(label, score) for label, score in cohesion.items() if score < 0.5]
        if low_cohesion_clusters:
            print(f"\n  ⚠️  Low cohesion clusters (< 0.5):")
            for label, score in sorted(low_cohesion_clusters, key=lambda x: x[1]):
                cluster_label_text = cluster_info[label]['label']
                cluster_size = cluster_info[label]['size']
                print(f"    Cluster {label} ({cluster_size}p): {score:.3f} - \"{cluster_label_text}\"")

    # Near-duplicate detection
    centroids = compute_cluster_centroids(valid_embeddings, valid_labels)
    near_duplicates = identify_near_duplicates(centroids, cluster_info, threshold=0.8)

    print(f"\n🔍 Near-Duplicate Analysis (similarity > 0.8):")
    if near_duplicates:
        print(f"  Found {len(near_duplicates)} potentially duplicate cluster pairs:\n")
        for i, (label_i, label_j, similarity, text_i, text_j) in enumerate(near_duplicates, 1):
            size_i = cluster_info[label_i]['size']
            size_j = cluster_info[label_j]['size']
            print(f"  {i}. Similarity: {similarity:.3f}")
            print(f"     Cluster {label_i} ({size_i}p): \"{text_i}\"")
            print(f"     Cluster {label_j} ({size_j}p): \"{text_j}\"")
            print()
    else:
        print("  ✅ No near-duplicate clusters found")

    return {
        'round_id': round_id,
        'num_submissions': len(embeddings),
        'num_clusters': num_clusters,
        'num_noise': num_noise,
        'silhouette_score': silhouette,
        'davies_bouldin_index': db_index,
        'avg_cohesion': avg_cohesion if cohesion else None,
        'near_duplicate_count': len(near_duplicates),
        'near_duplicates': near_duplicates,
        'cluster_sizes': cluster_sizes
    }


async def analyze_discussion(discussion_id: UUID):
    """Analyze all rounds in a discussion."""

    session_factory = get_session_factory()
    async with session_factory() as db:
        # Get all rounds for this discussion
        result = await db.execute(
            select(Round)
            .where(Round.discussion_id == discussion_id)
            .order_by(Round.round_num)
        )
        rounds = result.scalars().all()

        if not rounds:
            print(f"❌ No rounds found for discussion {discussion_id}")
            return

        print(f"\n{'='*80}")
        print(f"CLUSTERING QUALITY BASELINE REPORT")
        print(f"Discussion ID: {discussion_id}")
        print(f"Total Rounds: {len(rounds)}")
        print(f"{'='*80}")

        all_metrics = []

        for round_obj in rounds:
            metrics = await analyze_round(round_obj.round_id, db)
            if metrics:
                all_metrics.append(metrics)

        # Summary across all rounds
        if all_metrics:
            print(f"\n{'='*80}")
            print(f"SUMMARY ACROSS ALL ROUNDS")
            print(f"{'='*80}")

            avg_silhouette = np.mean([m['silhouette_score'] for m in all_metrics if m['silhouette_score'] is not None])
            avg_db_index = np.mean([m['davies_bouldin_index'] for m in all_metrics if m['davies_bouldin_index'] is not None])
            total_near_duplicates = sum(m['near_duplicate_count'] for m in all_metrics)
            avg_near_duplicates = total_near_duplicates / len(all_metrics)

            print(f"\n📊 Average Metrics:")
            print(f"  Silhouette Score: {avg_silhouette:.3f}")
            print(f"  Davies-Bouldin Index: {avg_db_index:.3f}")
            print(f"  Near-Duplicates per Round: {avg_near_duplicates:.1f}")
            print(f"  Total Near-Duplicates: {total_near_duplicates}")

            print(f"\n💡 Recommendations:")
            if avg_silhouette < 0.3:
                print("  ⚠️  Silhouette score is LOW - significant cluster overlap detected")
                print("     → Consider increasing min_samples parameter (test 3, 4, 5)")

            if avg_db_index > 2.0:
                print("  ⚠️  Davies-Bouldin index is HIGH - poor cluster separation")
                print("     → Consider adding cluster_selection_epsilon (test 0.05, 0.1)")

            if avg_near_duplicates > 2:
                print(f"  ⚠️  High near-duplicate count ({avg_near_duplicates:.1f} per round)")
                print("     → Near-duplicate clusters suggest over-fragmentation")
                print("     → Tuning min_samples and epsilon should help")

            if avg_silhouette > 0.5 and avg_db_index < 1.5 and total_near_duplicates < 5:
                print("  ✅ Clustering quality is GOOD overall")
                print("     → Current parameters are working well")


async def main():
    """Run baseline analysis on known discussion."""

    # Use the 10-round discussion from user context
    discussion_id = UUID("d4f27873-7c28-4d00-9084-ed2fb0d74b7e")

    await analyze_discussion(discussion_id)


if __name__ == "__main__":
    asyncio.run(main())
