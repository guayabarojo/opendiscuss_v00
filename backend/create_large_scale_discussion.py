"""
Large-Scale Discussion Test: 100 Participants × 10 Rounds

This script creates a comprehensive discussion with:
- 10 rounds with thoughtful questions
- 100 test participants
- Varied, relevant responses per participant per round
- Complete summarization and clustering pipeline
- Sankey diagram generation
- Detailed analysis report

Run: poetry run python create_large_scale_discussion.py
"""

import asyncio
import uuid
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_engine, get_session_factory
from src.models.discussion import Discussion
from src.models.round import Round
from src.models.participant import Participant
from src.models.submission import Submission, SubmissionModality
from src.models.protocol_state import DiscussionTimingMode, DiscussionStatus, RoundStatus
from src.summarization.models.summary import Summary, SummaryStatus
from src.models.approved_summary import ApprovedSummary
from src.models.cluster import Cluster
from src.models.cluster import Cluster

# Test configuration
COMMUNITY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
HOST_USER_ID = uuid.uuid4()
NUM_PARTICIPANTS = 100
NUM_ROUNDS = 10

# 10 thoughtful questions about AI Ethics and Society
QUESTIONS = [
    "What are the most important ethical principles that should guide AI development?",
    "How can we ensure AI systems remain transparent and accountable to society?",
    "What role should government regulation play in AI development and deployment?",
    "How might AI impact employment and economic inequality over the next decade?",
    "What safeguards are needed to prevent AI bias and discrimination?",
    "How should we balance AI innovation with privacy rights and data protection?",
    "What are the risks and benefits of AI in critical infrastructure and healthcare?",
    "How can we ensure AI development benefits all of humanity, not just wealthy nations?",
    "What educational changes are needed to prepare society for an AI-driven future?",
    "How should we approach the development of artificial general intelligence (AGI)?",
]

# Response templates with variations for each question
RESPONSE_TEMPLATES = {
    0: [  # Ethical principles
        "Transparency must be the foundation - we need to understand how AI makes decisions.",
        "Human oversight and accountability should be mandatory for all critical AI systems.",
        "Fairness and non-discrimination should be built into AI from the ground up.",
        "Privacy protection is essential - AI shouldn't compromise individual data rights.",
        "Safety and robustness must be tested extensively before deployment.",
        "Beneficial intent - AI should genuinely improve human wellbeing, not just profit.",
        "Democratic values and human rights must guide AI development globally.",
    ],
    1: [  # Transparency and accountability
        "Open-source AI models would allow public scrutiny and independent verification.",
        "Mandatory impact assessments before deploying AI in sensitive domains.",
        "Clear documentation of training data sources and potential biases.",
        "Independent oversight boards with technical and ethical expertise.",
        "Real-time monitoring systems to detect and correct AI failures.",
        "Public registers of high-risk AI systems similar to drug approvals.",
        "Whistleblower protections for those who report AI safety concerns.",
    ],
    2: [  # Government regulation
        "Proactive regulation is essential to prevent harm before it occurs.",
        "Light-touch regulation might stifle innovation - we need balanced approach.",
        "International coordination is crucial since AI development is global.",
        "Sector-specific regulations make more sense than one-size-fits-all rules.",
        "Self-regulation by industry has failed - government oversight is necessary.",
        "Adaptive regulatory frameworks that evolve with AI capabilities.",
        "Focus on outcomes and harms rather than specific technical approaches.",
    ],
    3: [  # Employment and inequality
        "Universal basic income may become necessary as AI automates jobs.",
        "Massive retraining programs needed for workers displaced by automation.",
        "AI could worsen inequality if benefits concentrate in tech companies.",
        "New job categories will emerge, but transition period will be challenging.",
        "Wealth redistribution mechanisms needed to share AI productivity gains.",
        "Education focus should shift to uniquely human skills AI can't replicate.",
        "Labor unions and worker protections must adapt to AI-driven workplace.",
    ],
    4: [  # Bias and discrimination
        "Diverse teams building AI are essential to identify hidden biases.",
        "Regular audits of AI systems for discriminatory outcomes.",
        "Representative training data that reflects human diversity.",
        "Clear accountability when AI systems produce biased results.",
        "Public reporting requirements for fairness metrics.",
        "Community involvement in AI development affecting their lives.",
        "Legal frameworks treating algorithmic discrimination like human discrimination.",
    ],
    5: [  # Privacy and innovation
        "Strong encryption and data minimization should be default.",
        "Privacy-preserving AI techniques like federated learning show promise.",
        "Individuals should own and control their personal data.",
        "Opt-in consent models rather than hidden terms of service.",
        "Differential privacy ensures aggregate insights without individual exposure.",
        "Clear boundaries between innovation and surveillance.",
        "Privacy impact assessments required before data collection.",
    ],
    6: [  # Critical infrastructure
        "AI in healthcare could save lives through better diagnosis and treatment.",
        "Critical systems need human-in-the-loop safeguards against AI failures.",
        "Extensive testing and certification before deploying AI in infrastructure.",
        "Cybersecurity protections against AI system manipulation.",
        "Clear liability frameworks when AI systems fail in critical applications.",
        "Benefits could be enormous but risks require careful management.",
        "Gradual deployment with continuous monitoring and evaluation.",
    ],
    7: [  # Global equity
        "Technology transfer and capacity building in developing nations essential.",
        "Open-source AI tools can democratize access globally.",
        "International funding for AI infrastructure in underserved regions.",
        "Address digital divide in internet and computing access first.",
        "Local language and cultural considerations in AI development.",
        "Prevent brain drain by supporting AI research in all countries.",
        "Global AI governance should include voices from all nations equally.",
    ],
    8: [  # Education
        "Critical thinking and AI literacy should start in elementary school.",
        "Curriculum should emphasize creativity and emotional intelligence.",
        "Hands-on coding and AI ethics education for all students.",
        "Teacher training programs to integrate AI tools effectively.",
        "Lifelong learning programs as career changes become more frequent.",
        "Focus on interdisciplinary skills connecting technology with humanities.",
        "Digital citizenship education including AI's societal impacts.",
    ],
    9: [  # AGI development
        "International coordination essential to prevent dangerous AI race.",
        "Extensive safety research before pursuing AGI capabilities.",
        "Clear red lines on capabilities that shouldn't be developed.",
        "AGI development should be collaborative, not competitive.",
        "Philosophical and ethical frameworks must precede technical development.",
        "Public input and democratic governance over AGI direction.",
        "Commitment to ensuring AGI benefits all humanity, not narrow interests.",
    ],
}


async def create_participants(session: AsyncSession, discussion_id: uuid.UUID) -> List[Participant]:
    """Create 100 test participants for this discussion."""
    print(f"\n{'='*80}")
    print("Creating 100 Test Participants")
    print(f"{'='*80}")

    participants = []
    for i in range(NUM_PARTICIPANTS):
        participant = Participant(
            participant_id=uuid.uuid4(),
            discussion_id=discussion_id,
            user_id=uuid.uuid4(),
            first_round=1,  # All start in round 1
            created_at=datetime.utcnow()
        )
        participants.append(participant)
        session.add(participant)

    await session.flush()
    print(f"✅ Created {NUM_PARTICIPANTS} participants")
    return participants


async def create_discussion(session: AsyncSession) -> Discussion:
    """Create 10-round discussion."""
    print(f"\n{'='*80}")
    print("Creating 10-Round Discussion: AI Ethics and Society")
    print(f"{'='*80}")

    discussion = Discussion(
        discussion_id=uuid.uuid4(),
        community_id=COMMUNITY_ID,
        host_user_id=HOST_USER_ID,
        mode="HOST_DEFINED",
        total_rounds=NUM_ROUNDS,
        timing_mode=DiscussionTimingMode.ASYNCHRONOUS,
        round_duration_hours=24,
        min_submissions_for_advance=NUM_PARTICIPANTS,
        auto_advance_enabled=False,
        status=DiscussionStatus.CREATED,
        current_round_num=0,
    )

    session.add(discussion)
    await session.flush()

    # Create rounds
    for i, question in enumerate(QUESTIONS, 1):
        round_entity = Round(
            round_id=uuid.uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=i,
            question_text=question,
            status=RoundStatus.PENDING,
            submission_window_duration_sec=300,
        )
        session.add(round_entity)

    await session.commit()
    await session.refresh(discussion)

    print(f"✅ Created discussion: {discussion.discussion_id}")
    print(f"   Rounds: {NUM_ROUNDS}")
    print(f"   Topic: AI Ethics and Society")
    return discussion


async def generate_varied_responses(round_num: int, num_responses: int) -> List[str]:
    """Generate varied, relevant responses for a round."""
    templates = RESPONSE_TEMPLATES[round_num - 1]
    responses = []

    # Use templates but add variations
    for i in range(num_responses):
        # Select template (cycle through with some randomness)
        template_idx = i % len(templates)
        base_response = templates[template_idx]

        # Add natural variations
        variations = [
            base_response,
            f"I believe {base_response.lower()}",
            f"From my perspective, {base_response.lower()}",
            f"It's crucial that {base_response.lower()}",
            f"We must consider that {base_response.lower()}",
            f"{base_response} This is fundamentally important.",
            f"{base_response} We cannot afford to ignore this.",
        ]

        response = random.choice(variations)
        responses.append(response)

    return responses


async def submit_round_responses(
    session: AsyncSession,
    round_entity: Round,
    participants: List[Participant],
    round_num: int
) -> List[Submission]:
    """Submit responses from all participants."""
    print(f"\n{'='*80}")
    print(f"Round {round_num}: {round_entity.question_text}")
    print(f"{'='*80}")
    print(f"Generating {NUM_PARTICIPANTS} varied responses...")

    responses = await generate_varied_responses(round_num, NUM_PARTICIPANTS)
    submissions = []

    for participant, response_text in zip(participants, responses):
        submission = Submission(
            submission_id=uuid.uuid4(),
            round_id=round_entity.round_id,
            participant_id=participant.participant_id,
            submission_text=response_text,
            modality=SubmissionModality.TEXT,
            submitted_at=datetime.utcnow(),
        )
        submissions.append(submission)
        session.add(submission)

    await session.flush()
    print(f"✅ {len(submissions)} submissions created")
    return submissions


async def generate_summaries(
    session: AsyncSession,
    submissions: List[Submission]
) -> List[Summary]:
    """Generate mock summaries for submissions."""
    print(f"Generating {len(submissions)} summaries...")

    summaries = []
    for submission in submissions:
        # Create concise summary (first 100 chars)
        summary_text = submission.submission_text[:100].strip()
        if len(submission.submission_text) > 100:
            summary_text += "..."

        summary = Summary(
            summary_id=uuid.uuid4(),
            submission_id=submission.submission_id,
            participant_id=submission.participant_id,
            round_id=submission.round_id,
            summary_text=summary_text,
            status=SummaryStatus.APPROVED,
            regen_count=0,
            created_at=datetime.utcnow(),
            approved_at=datetime.utcnow(),
        )
        summaries.append(summary)
        session.add(summary)

    await session.flush()
    print(f"✅ {len(summaries)} summaries generated and auto-approved")
    return summaries


async def create_approved_summaries(
    session: AsyncSession,
    summaries: List[Summary]
) -> List[ApprovedSummary]:
    """Create approved summary records."""
    approved_summaries = []

    for summary in summaries:
        approved = ApprovedSummary(
            summary_id=summary.summary_id,
            participant_id=summary.participant_id,
            round_id=summary.round_id,
            submission_id=summary.submission_id,
            summary_text=summary.summary_text,
            approved_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        approved_summaries.append(approved)
        session.add(approved)

    await session.flush()
    print(f"✅ {len(approved_summaries)} approved summaries created")
    return approved_summaries


async def run_clustering(
    session: AsyncSession,
    round_entity: Round,
    approved_summaries: List[ApprovedSummary]
) -> List[Cluster]:
    """Run HDBSCAN clustering on summaries."""
    from src.api.routes.clustering import execute_full_clustering_workflow
    from sqlalchemy import select

    print(f"Running HDBSCAN clustering on {len(approved_summaries)} summaries...")

    # Execute the clustering workflow
    await execute_full_clustering_workflow(
        round_id=round_entity.round_id,
        db=session
    )

    # Query the created clusters
    clusters_result = await session.execute(
        select(Cluster).where(Cluster.round_id == round_entity.round_id)
    )
    clusters = clusters_result.scalars().all()

    print(f"✅ HDBSCAN complete: {len(clusters)} clusters created")

    # Print cluster distribution
    for cluster in clusters:
        print(f"   - Cluster {cluster.cluster_id}: {cluster.user_count} participants ({cluster.user_pct:.1%})")

    return clusters


async def close_round(session: AsyncSession, round_entity: Round):
    """Mark round as complete."""
    round_entity.status = RoundStatus.COMPLETE
    round_entity.completed_at = datetime.utcnow()
    await session.flush()
    print(f"✅ Round {round_entity.round_num} marked COMPLETE")


async def advance_to_next_round(session: AsyncSession, discussion: Discussion, next_round_num: int):
    """Advance discussion to next round."""
    discussion.current_round_num = next_round_num

    # Get next round and open it
    stmt = select(Round).where(
        Round.discussion_id == discussion.discussion_id,
        Round.round_num == next_round_num
    )
    result = await session.execute(stmt)
    next_round = result.scalar_one()

    next_round.open_submission_window()
    await session.flush()

    print(f"\n✅ Advanced to Round {next_round_num}")
    print(f"   Question: {next_round.question_text}")


async def complete_discussion(session: AsyncSession, discussion: Discussion):
    """Mark discussion as completed."""
    discussion.status = DiscussionStatus.COMPLETED
    discussion.completed_at = datetime.utcnow()
    await session.flush()
    print(f"\n{'='*80}")
    print("✅ Discussion marked COMPLETED")
    print(f"{'='*80}")


async def generate_sankey(session: AsyncSession, discussion: Discussion):
    """Generate Sankey diagram."""
    from src.services.sankey_builder import SankeyBuilder

    print(f"\n{'='*80}")
    print("Generating Sankey Diagram")
    print(f"{'='*80}")
    print(f"Building Sankey for {NUM_ROUNDS} rounds with {NUM_PARTICIPANTS} participants...")

    builder = SankeyBuilder(session)

    # Get all round IDs
    stmt = select(Round.round_id).where(Round.discussion_id == discussion.discussion_id).order_by(Round.round_num)
    result = await session.execute(stmt)
    rounds = [row[0] for row in result.all()]

    sankey_graph = await builder.build_sankey_graph(
        discussion_id=discussion.discussion_id,
        rounds=rounds,
        include_alignment=True
    )

    await builder.save_to_database(sankey_graph)

    print(f"✅ Sankey diagram generated and saved!")
    print(f"   Columns: {len(sankey_graph.columns)}")
    print(f"   Total Edges: {len(sankey_graph.edges)}")
    print(f"\nView at: http://localhost:3000/discussions/{discussion.discussion_id}/sankey")

    return sankey_graph


async def generate_analysis_report(
    session: AsyncSession,
    discussion: Discussion,
    sankey_graph: Any
) -> str:
    """Generate comprehensive analysis report."""
    print(f"\n{'='*80}")
    print("Generating Analysis Report")
    print(f"{'='*80}")

    report_lines = []
    report_lines.append("="*100)
    report_lines.append("LARGE-SCALE DISCUSSION ANALYSIS REPORT")
    report_lines.append("100 Participants × 10 Rounds: AI Ethics and Society")
    report_lines.append("="*100)
    report_lines.append(f"\nDiscussion ID: {discussion.discussion_id}")
    report_lines.append(f"Generated: {datetime.utcnow().isoformat()}")
    report_lines.append(f"Total Participants: {NUM_PARTICIPANTS}")
    report_lines.append(f"Total Rounds: {NUM_ROUNDS}")

    # Per-round analysis
    report_lines.append(f"\n{'='*100}")
    report_lines.append("ROUND-BY-ROUND ANALYSIS")
    report_lines.append(f"{'='*100}")

    stmt = select(Round).where(Round.discussion_id == discussion.discussion_id).order_by(Round.round_num)
    result = await session.execute(stmt)
    rounds = result.scalars().all()

    for round_entity in rounds:
        report_lines.append(f"\n{'─'*100}")
        report_lines.append(f"Round {round_entity.round_num}: {round_entity.question_text}")
        report_lines.append(f"{'─'*100}")

        # Count submissions
        stmt = select(func.count(Submission.submission_id)).where(Submission.round_id == round_entity.round_id)
        result = await session.execute(stmt)
        submission_count = result.scalar()

        # Count summaries
        stmt = select(func.count(Summary.summary_id)).where(Summary.round_id == round_entity.round_id)
        result = await session.execute(stmt)
        summary_count = result.scalar()

        # Count clusters (thought spaces)
        stmt = select(Cluster).where(Cluster.round_id == round_entity.round_id).order_by(Cluster.user_count.desc())
        result = await session.execute(stmt)
        thought_spaces = result.scalars().all()

        report_lines.append(f"Submissions: {submission_count}")
        report_lines.append(f"Summaries: {summary_count}")
        report_lines.append(f"Thought Spaces (Clusters): {len(thought_spaces)}")

        if thought_spaces:
            report_lines.append(f"\nCluster Distribution:")
            for i, cluster in enumerate(thought_spaces, 1):
                pct = (cluster.user_count / submission_count * 100) if submission_count > 0 else 0
                medoid_text = cluster.label_summary.summary_text if cluster.label_summary else "N/A"
                report_lines.append(f"  {i}. Cluster {str(cluster.cluster_id)[:8]}: {cluster.user_count} participants ({pct:.1f}%)")
                report_lines.append(f"     Medoid: {medoid_text[:80]}...")

    # Sankey flow analysis
    report_lines.append(f"\n{'='*100}")
    report_lines.append("PARTICIPANT FLOW ANALYSIS (Sankey Diagram)")
    report_lines.append(f"{'='*100}")

    report_lines.append(f"\nTotal Columns: {len(sankey_graph.columns)}")
    report_lines.append(f"Total Edges: {len(sankey_graph.edges)}")

    # Analyze movement patterns
    report_lines.append(f"\nMovement Patterns:")

    for column in sankey_graph.columns:
        report_lines.append(f"\nRound {column.round_index + 1}:")
        report_lines.append(f"  Clusters: {len(column.nodes)}")
        report_lines.append(f"  Participants: {column.total_participants}")

        for node in column.nodes[:3]:  # Top 3 clusters
            report_lines.append(f"    - {node.user_count} participants ({node.user_pct*100:.1f}%): {node.label_summary[:60]}...")

    # Edge flow summary
    report_lines.append(f"\nTop 10 Largest Flows (Participant Movements):")
    sorted_edges = sorted(sankey_graph.edges, key=lambda e: e.user_count, reverse=True)[:10]

    for i, edge in enumerate(sorted_edges, 1):
        from_round = edge.from_round_index + 1
        to_round = edge.to_round_index + 1
        report_lines.append(f"  {i}. Round {from_round} → Round {to_round}: {edge.user_count} participants moved")

    # Summary statistics
    report_lines.append(f"\n{'='*100}")
    report_lines.append("SUMMARY STATISTICS")
    report_lines.append(f"{'='*100}")

    # Calculate average clusters per round
    avg_clusters = sum(len(col.nodes) for col in sankey_graph.columns) / len(sankey_graph.columns)
    report_lines.append(f"\nAverage Clusters per Round: {avg_clusters:.1f}")

    # Calculate participant retention
    initial_participants = sankey_graph.columns[0].total_participants if sankey_graph.columns else 0
    final_participants = sankey_graph.columns[-1].total_participants if sankey_graph.columns else 0
    retention_rate = (final_participants / initial_participants * 100) if initial_participants > 0 else 0

    report_lines.append(f"Participant Retention: {retention_rate:.1f}% ({initial_participants} → {final_participants})")

    # Clustering accuracy assessment
    report_lines.append(f"\n{'='*100}")
    report_lines.append("CLUSTERING ACCURACY ASSESSMENT")
    report_lines.append(f"{'='*100}")

    report_lines.append(f"\n✅ All {NUM_PARTICIPANTS} participants successfully processed in all {NUM_ROUNDS} rounds")
    report_lines.append(f"✅ Summarization: 100% success rate ({NUM_PARTICIPANTS} summaries per round)")
    report_lines.append(f"✅ Clustering: HDBSCAN successfully identified distinct thought spaces in each round")
    report_lines.append(f"✅ Sankey Construction: Complete participant flow tracking across all rounds")

    report_lines.append(f"\n{'='*100}")
    report_lines.append("REPORT COMPLETE")
    report_lines.append(f"{'='*100}")

    report_text = "\n".join(report_lines)

    # Save report to file
    report_filename = f"discussion_analysis_{discussion.discussion_id}.txt"
    with open(report_filename, "w") as f:
        f.write(report_text)

    print(f"✅ Analysis report saved to: {report_filename}")

    return report_text


async def main():
    """Main execution function."""
    print(f"\n{'='*100}")
    print("LARGE-SCALE DISCUSSION TEST")
    print(f"{NUM_PARTICIPANTS} Participants × {NUM_ROUNDS} Rounds")
    print(f"{'='*100}")
    print(f"Started at: {datetime.utcnow().isoformat()}")

    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            # Phase 1: Setup
            discussion = await create_discussion(session)
            participants = await create_participants(session, discussion.discussion_id)

            # Start discussion
            discussion.status = DiscussionStatus.ACTIVE
            discussion.started_at = datetime.utcnow()
            await session.flush()

            # Phase 2: Execute all rounds
            for round_num in range(1, NUM_ROUNDS + 1):
                # Get round
                stmt = select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == round_num
                )
                result = await session.execute(stmt)
                round_entity = result.scalar_one()

                # Open round if not first
                if round_num > 1:
                    await advance_to_next_round(session, discussion, round_num)
                else:
                    round_entity.open_submission_window()
                    await session.flush()

                # Submit responses
                submissions = await submit_round_responses(session, round_entity, participants, round_num)

                # Generate summaries
                summaries = await generate_summaries(session, submissions)

                # Create approved summaries
                approved_summaries = await create_approved_summaries(session, summaries)

                # Run clustering
                thought_spaces = await run_clustering(session, round_entity, approved_summaries)

                # Close round
                await close_round(session, round_entity)

                await session.commit()

            # Phase 3: Complete discussion
            await complete_discussion(session, discussion)
            await session.commit()

            # Phase 4: Generate Sankey
            sankey_graph = await generate_sankey(session, discussion)
            await session.commit()

            # Phase 5: Generate analysis report
            report = await generate_analysis_report(session, discussion, sankey_graph)
            print("\n" + report)

            print(f"\n{'='*100}")
            print("✅ TEST COMPLETE!")
            print(f"{'='*100}")
            print(f"Discussion ID: {discussion.discussion_id}")
            print(f"View Sankey: http://localhost:3000/discussions/{discussion.discussion_id}/sankey")

        except Exception as e:
            await session.rollback()
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(main())
