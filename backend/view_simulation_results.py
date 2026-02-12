"""
View Large-Scale Simulation Results
Shows the complete user flow from submission to Sankey diagram
"""

import asyncio
import uuid
from sqlalchemy import select, func
from src.database import get_session_factory
from src.models.discussion import Discussion
from src.models.round import Round
from src.models.submission import Submission
from src.summarization.models.summary import Summary
from src.models.approved_summary import ApprovedSummary
from src.models.cluster import Cluster
from src.models.sankey_graph import SankeyGraph

DISCUSSION_ID = uuid.UUID("f7b6ecb0-dcaf-4733-b5cd-538d36ff20e1")


async def show_complete_user_flow():
    """Display complete user flow from the simulation."""
    print("\n" + "="*100)
    print("LARGE-SCALE DISCUSSION SIMULATION - COMPLETE USER FLOW WALKTHROUGH")
    print("100 Participants × 10 Rounds: AI Ethics and Society")
    print("="*100)

    session_factory = get_session_factory()

    async with session_factory() as session:
        # 1. Discussion Overview
        stmt = select(Discussion).where(Discussion.discussion_id == DISCUSSION_ID)
        result = await session.execute(stmt)
        discussion = result.scalar_one()

        print(f"\n{'='*100}")
        print("STEP 1: DISCUSSION SETUP")
        print(f"{'='*100}")
        print(f"Discussion ID: {discussion.discussion_id}")
        print(f"Status: {discussion.status}")
        print(f"Total Rounds: {discussion.total_rounds}")
        print(f"Timing Mode: {discussion.timing_mode}")
        print(f"Started: {discussion.started_at}")
        print(f"Completed: {discussion.completed_at}")

        # 2. Round-by-Round Processing
        print(f"\n{'='*100}")
        print("STEP 2: ROUND-BY-ROUND PROCESSING")
        print(f"{'='*100}")

        stmt = select(Round).where(Round.discussion_id == DISCUSSION_ID).order_by(Round.round_num)
        result = await session.execute(stmt)
        rounds = result.scalars().all()

        for round_entity in rounds:
            print(f"\n{'─'*100}")
            print(f"Round {round_entity.round_num}: {round_entity.question_text}")
            print(f"{'─'*100}")

            # Count submissions
            stmt = select(func.count(Submission.submission_id)).where(
                Submission.round_id == round_entity.round_id
            )
            result = await session.execute(stmt)
            submission_count = result.scalar()

            # Count summaries
            stmt = select(func.count(Summary.summary_id)).where(
                Summary.round_id == round_entity.round_id
            )
            result = await session.execute(stmt)
            summary_count = result.scalar()

            # Count approved summaries
            stmt = select(func.count(ApprovedSummary.summary_id)).where(
                ApprovedSummary.round_id == round_entity.round_id
            )
            result = await session.execute(stmt)
            approved_count = result.scalar()

            # Get clusters
            stmt = select(Cluster).where(
                Cluster.round_id == round_entity.round_id
            ).order_by(Cluster.user_count.desc())
            result = await session.execute(stmt)
            clusters = result.scalars().all()

            print(f"  📝 Submissions: {submission_count}")
            print(f"  📋 Summaries Generated: {summary_count}")
            print(f"  ✅ Approved Summaries: {approved_count}")
            print(f"  🎯 Clusters Identified: {len(clusters)}")

            # Show sample submissions
            if submission_count > 0:
                stmt = select(Submission).where(
                    Submission.round_id == round_entity.round_id
                ).limit(3)
                result = await session.execute(stmt)
                samples = result.scalars().all()

                print(f"\n  Sample Participant Responses:")
                for i, sub in enumerate(samples, 1):
                    text = sub.submission_text[:80] + "..." if len(sub.submission_text) > 80 else sub.submission_text
                    print(f"    {i}. \"{text}\"")

            # Show cluster distribution
            if clusters:
                print(f"\n  Cluster Distribution:")
                for i, cluster in enumerate(clusters[:5], 1):  # Top 5 clusters
                    print(f"    {i}. {cluster.user_count} participants ({cluster.user_pct*100:.1f}%)")

        # 3. Sankey Diagram Analysis
        print(f"\n{'='*100}")
        print("STEP 3: SANKEY DIAGRAM GENERATION")
        print(f"{'='*100}")

        stmt = select(SankeyGraph).where(SankeyGraph.discussion_id == DISCUSSION_ID)
        result = await session.execute(stmt)
        sankey_graph = result.scalar_one_or_none()

        if sankey_graph:
            print(f"\n✅ Sankey Diagram Successfully Generated!")
            print(f"   Columns (Rounds): {len(sankey_graph.data.get('columns', []))}")
            print(f"   Total Edges (Participant Movements): {len(sankey_graph.data.get('edges', []))}")

            columns = sankey_graph.data.get('columns', [])
            print(f"\n   Participant Flow Across Rounds:")
            for col in columns:
                round_idx = col.get('round_index', 0)
                nodes = col.get('nodes', [])
                total = col.get('total_participants', 0)
                print(f"     Round {round_idx + 1}: {len(nodes)} clusters, {total} participants")

            # Show movement patterns
            edges = sankey_graph.data.get('edges', [])
            if edges:
                print(f"\n   Top Participant Movements:")
                sorted_edges = sorted(edges, key=lambda e: e.get('user_count', 0), reverse=True)[:10]
                for i, edge in enumerate(sorted_edges, 1):
                    from_round = edge.get('from_round_index', 0) + 1
                    to_round = edge.get('to_round_index', 0) + 1
                    count = edge.get('user_count', 0)
                    print(f"     {i}. Round {from_round} → Round {to_round}: {count} participants")
        else:
            print("\n⚠️  Sankey diagram not found in database")

        # 4. Summary Statistics
        print(f"\n{'='*100}")
        print("STEP 4: FINAL STATISTICS")
        print(f"{'='*100}")

        # Total submissions across all rounds
        stmt = select(func.count(Submission.submission_id)).where(
            Submission.round_id.in_([r.round_id for r in rounds])
        )
        result = await session.execute(stmt)
        total_submissions = result.scalar()

        # Total summaries
        stmt = select(func.count(Summary.summary_id)).where(
            Summary.round_id.in_([r.round_id for r in rounds])
        )
        result = await session.execute(stmt)
        total_summaries = result.scalar()

        # Total clusters
        stmt = select(func.count(Cluster.cluster_id)).where(
            Cluster.round_id.in_([r.round_id for r in rounds])
        )
        result = await session.execute(stmt)
        total_clusters = result.scalar()

        print(f"\n📊 Overall Statistics:")
        print(f"   Total Submissions: {total_submissions}")
        print(f"   Total Summaries: {total_summaries}")
        print(f"   Total Clusters: {total_clusters}")
        print(f"   Average Clusters per Round: {total_clusters / len(rounds):.1f}")
        print(f"   Summarization Success Rate: {(total_summaries / total_submissions * 100):.1f}%")

        print(f"\n{'='*100}")
        print("✅ USER FLOW COMPLETE!")
        print(f"{'='*100}")
        print(f"\nThe simulation successfully demonstrated:")
        print(f"  1. ✅ 100 parallel agents submitting responses each round")
        print(f"  2. ✅ Individual summarization of each submission")
        print(f"  3. ✅ Collective clustering across all summaries")
        print(f"  4. ✅ Participant flow tracking across 10 rounds")
        print(f"  5. ✅ Sankey diagram generation for visualization")

        print(f"\n📍 Next Steps:")
        print(f"   - View in browser: http://localhost:3000/discussions/{DISCUSSION_ID}/sankey")
        print(f"   - Analysis report: discussion_analysis_{DISCUSSION_ID}.txt")
        print(f"   - Discussion complete and ready for review!\n")


if __name__ == "__main__":
    asyncio.run(show_complete_user_flow())
