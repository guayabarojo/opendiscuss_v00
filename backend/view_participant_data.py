"""
View Participant Data: Raw Input → Summary → Cluster Assignment

Generates a comprehensive table showing:
- Participant ID
- Round Number
- Raw submission text
- Generated summary
- Cluster assignment (with label)

Usage: poetry run python view_participant_data.py <discussion_id>
"""

import asyncio
import sys
import uuid
import csv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.models.submission import Submission
from src.summarization.models.summary import Summary
from src.models.approved_summary import ApprovedSummary
from src.models.thought_space import ThoughtSpace
from src.models.round import Round
from src.models.participant import Participant


async def fetch_participant_data(discussion_id: uuid.UUID, session: AsyncSession):
    """Fetch all participant data for a discussion."""

    # Get all rounds for this discussion
    rounds_result = await session.execute(
        select(Round)
        .where(Round.discussion_id == discussion_id)
        .order_by(Round.round_num)
    )
    rounds = {r.round_id: r.round_num for r in rounds_result.scalars().all()}

    # Get all participants
    participants_result = await session.execute(
        select(Participant)
        .where(Participant.discussion_id == discussion_id)
    )
    participants = {p.participant_id: f"P{str(p.participant_id)[:8]}" for p in participants_result.scalars().all()}

    # Get all thought spaces (clusters) with their labels
    clusters_result = await session.execute(
        select(ThoughtSpace)
        .where(ThoughtSpace.round_id.in_(rounds.keys()))
    )
    clusters_list = clusters_result.scalars().all()

    # Create cluster lookup: cluster_id -> (round_num, cluster_number, label)
    clusters_by_round = {}
    for cluster in clusters_list:
        round_num = rounds[cluster.round_id]
        if round_num not in clusters_by_round:
            clusters_by_round[round_num] = []
        clusters_by_round[round_num].append(cluster)

    # Sort clusters by size within each round and assign numbers
    cluster_lookup = {}
    for round_num, round_clusters in clusters_by_round.items():
        sorted_clusters = sorted(round_clusters, key=lambda c: c.member_count, reverse=True)
        for idx, cluster in enumerate(sorted_clusters, 1):
            label_text = cluster.label_summary[:60] + "..." if len(cluster.label_summary) > 60 else cluster.label_summary
            cluster_lookup[cluster.cluster_id] = (round_num, f"C{idx}", label_text, cluster.member_count)

    # Fetch all submissions with their summaries and clusters
    query = (
        select(
            Submission.submission_id,
            Submission.participant_id,
            Submission.round_id,
            Submission.submission_text,
            Summary.summary_text,
            ApprovedSummary.cluster_id
        )
        .join(Summary, Submission.submission_id == Summary.submission_id)
        .join(ApprovedSummary, Summary.summary_id == ApprovedSummary.summary_id)
        .where(Submission.round_id.in_(rounds.keys()))
        .order_by(Submission.round_id, Submission.participant_id)
    )

    result = await session.execute(query)
    rows = result.all()

    # Build data for DataFrame
    data = []
    for row in rows:
        round_num = rounds[row.round_id]
        participant_label = participants[row.participant_id]

        # Get cluster info
        cluster_info = cluster_lookup.get(row.cluster_id)
        if cluster_info:
            _, cluster_num, cluster_label, cluster_size = cluster_info
        else:
            cluster_num = "N/A"
            cluster_label = "No cluster"
            cluster_size = 0

        data.append({
            "Round": round_num,
            "Participant": participant_label,
            "Raw Input": row.submission_text[:100] + "..." if len(row.submission_text) > 100 else row.submission_text,
            "Summary": row.summary_text[:80] + "..." if len(row.summary_text) > 80 else row.summary_text,
            "Cluster": cluster_num,
            "Cluster Label": cluster_label,
            "Cluster Size": cluster_size
        })

    return data


async def main():
    if len(sys.argv) < 2:
        print("Usage: poetry run python view_participant_data.py <discussion_id>")
        sys.exit(1)

    discussion_id = uuid.UUID(sys.argv[1])

    session_factory = get_session_factory()
    async with session_factory() as session:
        print(f"\n{'='*120}")
        print(f"PARTICIPANT DATA VIEW - Discussion {discussion_id}")
        print(f"{'='*120}\n")

        data = await fetch_participant_data(discussion_id, session)

        if not data:
            print("No data found for this discussion.")
            return

        # Save to CSV
        csv_filename = f"participant_data_{discussion_id}.csv"
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

        print(f"✅ Full data saved to: {csv_filename}\n")

        # Display summary stats
        unique_rounds = set(row['Round'] for row in data)
        unique_participants = set(row['Participant'] for row in data)
        unique_clusters = set(row['Cluster'] for row in data)

        print(f"Total Records: {len(data)}")
        print(f"Rounds: {len(unique_rounds)}")
        print(f"Participants: {len(unique_participants)}")
        print(f"Clusters: {len(unique_clusters)}")

        # Show sample data (first 20 rows)
        print(f"\n{'='*120}")
        print("SAMPLE DATA (First 20 rows)")
        print(f"{'='*120}\n")

        # Print header
        header = f"{'Round':<6} {'Participant':<12} {'Raw Input':<42} {'Summary':<42} {'Cluster':<8} {'Cluster Label':<30}"
        print(header)
        print("-" * 120)

        # Print first 20 rows
        for i, row in enumerate(data[:20]):
            raw = row['Raw Input'][:40] + "..." if len(row['Raw Input']) > 40 else row['Raw Input']
            summary = row['Summary'][:40] + "..." if len(row['Summary']) > 40 else row['Summary']
            label = row['Cluster Label'][:28] + "..." if len(row['Cluster Label']) > 28 else row['Cluster Label']

            print(f"{row['Round']:<6} {row['Participant']:<12} {raw:<42} {summary:<42} {row['Cluster']:<8} {label:<30}")

        # Show cluster distribution per round
        print(f"\n{'='*120}")
        print("CLUSTER DISTRIBUTION BY ROUND")
        print(f"{'='*120}\n")

        for round_num in sorted(unique_rounds):
            round_data = [row for row in data if row['Round'] == round_num]

            # Group by cluster
            cluster_groups = {}
            for row in round_data:
                cluster = row['Cluster']
                if cluster not in cluster_groups:
                    cluster_groups[cluster] = {
                        'label': row['Cluster Label'],
                        'size': row['Cluster Size'],
                        'count': 0
                    }
                cluster_groups[cluster]['count'] += 1

            # Sort by size
            sorted_clusters = sorted(cluster_groups.items(), key=lambda x: x[1]['size'], reverse=True)

            print(f"Round {round_num}:")
            for cluster_id, info in sorted_clusters:
                print(f"  {cluster_id}: {info['count']} participants - \"{info['label']}\"")
            print()

        print(f"\n✅ Complete data available in: {csv_filename}")
        print("   Open in Excel/Sheets to view all raw inputs, summaries, and cluster assignments")


if __name__ == "__main__":
    asyncio.run(main())
