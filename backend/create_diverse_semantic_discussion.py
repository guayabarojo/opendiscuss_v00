"""
Diverse Semantic Discussion - Realistic Multi-Cluster Formation

Creates semantically distinct responses that naturally form 4-7 clusters per round
with balanced distribution (15-30% each cluster).
"""

import asyncio
import uuid
import random
from datetime import datetime
from typing import List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.models.discussion import Discussion
from src.models.round import Round
from src.models.participant import Participant
from src.models.submission import Submission, SubmissionModality
from src.models.protocol_state import DiscussionTimingMode, DiscussionStatus, RoundStatus
from src.summarization.models.summary import Summary, SummaryStatus
from src.models.approved_summary import ApprovedSummary

COMMUNITY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
HOST_USER_ID = uuid.uuid4()
NUM_PARTICIPANTS = 100
NUM_ROUNDS = 10

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

# Semantically DISTINCT viewpoints per question (designed to cluster separately)
QUESTION_RESPONSES = {
    1: {  # Ethical principles
        "regulatory": [
            "Strong government oversight boards must approve all AI systems before deployment.",
            "Mandatory safety testing protocols similar to pharmaceutical trials are essential.",
            "Legal accountability frameworks with clear liability for AI failures.",
        ],
        "privacy": [
            "End-to-end encryption and data minimization must be default requirements.",
            "Users should own their data with explicit opt-in consent for any collection.",
            "Ban surveillance AI and facial recognition in public spaces entirely.",
        ],
        "equity": [
            "Ensure AI benefits reach underserved communities, not just wealthy elites.",
            "Prohibit algorithmic discrimination through mandatory fairness audits.",
            "Require diverse teams in AI development to prevent encoded biases.",
        ],
        "innovation": [
            "Focus on breakthrough potential - AI could solve climate change and disease.",
            "Light regulatory touch to encourage rapid advancement and experimentation.",
            "Trust market competition to naturally select beneficial AI applications.",
        ],
        "workers": [
            "Guarantee universal basic income as AI automates manufacturing jobs.",
            "Strengthen union rights to negotiate workplace AI deployment terms.",
            "Fund massive retraining programs for displaced workers immediately.",
        ],
    },
    2: {  # Transparency and accountability
        "open_source": [
            "All AI models should be open-source for public inspection and verification.",
            "Require publishing training data sources and preprocessing methodologies.",
            "Academic peer review of AI systems before commercial deployment.",
        ],
        "auditing": [
            "Independent third-party audits quarterly with published results.",
            "Real-time monitoring systems tracking AI decision patterns for bias.",
            "Whistleblower protections and rewards for reporting AI safety issues.",
        ],
        "liability": [
            "Hold companies legally liable for AI harms with strict liability standard.",
            "Establish victim compensation funds financed by AI companies.",
            "Criminal penalties for executives who deploy unsafe AI knowingly.",
        ],
        "transparency": [
            "Require plain-language explanations of AI decisions to affected individuals.",
            "Public registry of all high-risk AI systems like drug approval databases.",
            "Mandate explainable AI techniques rather than black-box neural networks.",
        ],
    },
    3: {  # Government regulation
        "heavy_regulation": [
            "Proactive precautionary principle - ban first, allow only if proven safe.",
            "Create dedicated federal AI regulatory agency with enforcement powers.",
            "International treaty coordinating global AI governance standards.",
        ],
        "light_touch": [
            "Voluntary industry self-regulation with government guidance principles.",
            "Fast-track approval processes to avoid stifling innovation cycles.",
            "Focus enforcement on actual harms, not hypothetical future risks.",
        ],
        "sector_specific": [
            "Different rules for healthcare AI versus entertainment recommendation systems.",
            "Risk-based tiers - strict for critical infrastructure, relaxed for low-stakes.",
            "Industry-specific regulatory bodies rather than one-size-fits-all approach.",
        ],
        "no_regulation": [
            "Market forces and consumer choice provide better oversight than bureaucracy.",
            "Regulation will push development to countries with lax oversight.",
            "Innovation velocity matters more than regulatory caution for competitiveness.",
        ],
    },
    4: {  # Employment and inequality
        "ubi": [
            "Universal basic income funded by taxing AI productivity gains heavily.",
            "Decouple income from employment as automation makes work optional.",
            "Guarantee housing, healthcare, education regardless of job status.",
        ],
        "retraining": [
            "Massive federal retraining programs teaching AI-adjacent skills quickly.",
            "Employer-funded transition support for displaced workers mandatorily.",
            "Apprenticeship programs connecting unemployed to emerging AI-era jobs.",
        ],
        "inequality": [
            "AI profits consolidate with tech oligarchs while workers face unemployment.",
            "Wealth redistribution through progressive taxation on AI companies.",
            "Break up monopolistic AI companies to prevent excessive concentration.",
        ],
        "optimism": [
            "AI will create more jobs than it destroys, like previous technology shifts.",
            "Focus on uniquely human skills like creativity that AI cannot replicate.",
            "Economic growth from AI raises living standards for everyone overall.",
        ],
    },
    5: {  # Bias and discrimination
        "algorithmic_audits": [
            "Mandatory bias testing across demographic groups before deployment.",
            "Continuous monitoring for discriminatory patterns in production systems.",
            "Public reporting of fairness metrics with standardized methodologies.",
        ],
        "diverse_teams": [
            "Require minimum demographic diversity in AI development teams.",
            "Include affected communities in design decisions for systems impacting them.",
            "Train developers on implicit bias and fairness considerations thoroughly.",
        ],
        "data_quality": [
            "Representative training datasets reflecting true population diversity.",
            "Remove historical bias from training data through careful curation.",
            "Oversample minority groups to prevent underrepresentation in models.",
        ],
        "legal_framework": [
            "Treat algorithmic discrimination identically to human discrimination legally.",
            "Private right of action allowing individuals to sue for AI bias.",
            "Government enforcement of anti-discrimination laws in AI contexts.",
        ],
    },
    6: {  # Privacy vs Innovation
        "privacy_first": [
            "Ban data collection beyond strict necessity principle absolutely.",
            "GDPR-style right to deletion and portability of personal data.",
            "Prohibit selling personal data to third parties without explicit consent.",
        ],
        "innovation_priority": [
            "Data access enables AI breakthroughs - restrictions slow progress substantially.",
            "Anonymization and aggregation protect privacy while enabling innovation.",
            "Trust companies to self-regulate data practices with market pressure.",
        ],
        "balanced": [
            "Privacy-preserving techniques like federated learning and differential privacy.",
            "Sector-specific rules - strict for health data, relaxed for public information.",
            "Strong defaults protecting privacy but allowing opt-in for beneficial uses.",
        ],
        "transparency": [
            "Clear terms of service explaining exactly what data is collected and why.",
            "User control dashboards showing data usage and allowing selective deletion.",
            "Ban hidden tracking and require conspicuous notice for data collection.",
        ],
    },
    7: {  # Critical infrastructure
        "cautious": [
            "Extensive safety certification required before deploying in infrastructure.",
            "Human override capabilities mandatory for all critical AI systems.",
            "Gradual rollout with continuous monitoring rather than rapid deployment.",
        ],
        "optimistic": [
            "AI in healthcare diagnostics saves lives through earlier disease detection.",
            "Smart grids with AI optimize energy distribution reducing blackouts.",
            "Autonomous systems handle infrastructure more reliably than humans.",
        ],
        "liability": [
            "Clear liability standards establishing who is responsible when AI fails.",
            "Insurance requirements for companies deploying AI in critical systems.",
            "Victim compensation mechanisms funded by infrastructure operators.",
        ],
        "cybersecurity": [
            "Harden AI systems against adversarial attacks and manipulation attempts.",
            "Air-gap critical infrastructure AI from internet connectivity.",
            "Regular penetration testing and security audits for infrastructure AI.",
        ],
    },
    8: {  # Global equity
        "technology_transfer": [
            "Share AI technology with developing nations through open licensing.",
            "Train AI talent in Global South through international education programs.",
            "Fund AI infrastructure deployment in underserved regions globally.",
        ],
        "digital_divide": [
            "Address internet access inequality before worrying about AI equity.",
            "Provide computing resources to regions lacking tech infrastructure.",
            "Translate AI systems into local languages for non-English speakers.",
        ],
        "governance": [
            "Give developing nations equal voice in international AI governance.",
            "Prevent brain drain by supporting local AI research ecosystems.",
            "Stop AI colonialism where Western values dominate global development.",
        ],
        "local_solutions": [
            "Develop AI addressing local problems like agricultural optimization.",
            "Respect cultural contexts rather than imposing Western AI approaches.",
            "Support indigenous data sovereignty and culturally-appropriate AI.",
        ],
    },
    9: {  # Education
        "ai_literacy": [
            "Teach AI concepts starting in elementary school curriculum.",
            "Critical thinking about AI-generated content and misinformation.",
            "Hands-on coding and machine learning projects for students.",
        ],
        "human_skills": [
            "Emphasize creativity, empathy, and uniquely human capabilities.",
            "Arts and humanities become more valuable in AI-dominated economy.",
            "Collaboration and emotional intelligence as core curriculum focus.",
        ],
        "lifelong_learning": [
            "Frequent career transitions require continuous skill updates.",
            "Employer-sponsored upskilling programs throughout working life.",
            "Make college and vocational training free for retraining workers.",
        ],
        "teacher_training": [
            "Train educators to effectively integrate AI tools in teaching.",
            "Use AI for personalized learning paths adapted to each student.",
            "Teachers as mentors and guides rather than information transmitters.",
        ],
    },
    10: {  # AGI
        "safety_first": [
            "Extensive safety research before pursuing artificial general intelligence.",
            "International cooperation to prevent dangerous AI capability races.",
            "Commitment ensuring AGI benefits all humanity, not narrow interests.",
        ],
        "capability_limits": [
            "Clear red lines on capabilities that should never be developed.",
            "Ban autonomous weapon systems and manipulation technologies.",
            "Human oversight requirements for any general intelligence systems.",
        ],
        "governance": [
            "Democratic control over AGI development direction and deployment.",
            "Public input through deliberative processes shaping AGI priorities.",
            "Government ownership of AGI to prevent private monopolization.",
        ],
        "philosophical": [
            "Develop ethical frameworks before pursuing advanced AI capabilities.",
            "Consider consciousness and moral status of potential AGI systems.",
            "Ensure human values and rights guide AGI development fundamentally.",
        ],
    },
}


def assign_viewpoints(num_participants: int, num_viewpoints: int) -> List[int]:
    """Assign participants to viewpoints with realistic distribution."""
    # Create varied distribution (not perfectly equal)
    base_size = num_participants // num_viewpoints
    remainder = num_participants % num_viewpoints

    # Add some natural variance
    distribution = []
    for i in range(num_viewpoints):
        size = base_size
        if i < remainder:
            size += 1
        # Add random variance (±10%)
        variance = random.randint(-base_size // 10, base_size // 10)
        size = max(5, size + variance)  # Minimum 5 per viewpoint
        distribution.append(size)

    # Normalize to exactly num_participants
    while sum(distribution) < num_participants:
        distribution[random.randint(0, num_viewpoints - 1)] += 1
    while sum(distribution) > num_participants:
        idx = random.randint(0, num_viewpoints - 1)
        if distribution[idx] > 5:
            distribution[idx] -= 1

    # Create assignment list
    assignments = []
    for viewpoint_idx, count in enumerate(distribution):
        assignments.extend([viewpoint_idx] * count)

    random.shuffle(assignments)
    return assignments


async def create_discussion(session: AsyncSession) -> Discussion:
    """Create discussion."""
    print(f"\n{'='*80}")
    print("Creating Semantically Diverse Discussion")
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
    return discussion


async def create_participants(session: AsyncSession, discussion_id: uuid.UUID) -> List[Participant]:
    """Create 100 participants."""
    print(f"\n{'='*80}")
    print("Creating 100 Participants")
    print(f"{'='*80}")

    participants = []
    for i in range(NUM_PARTICIPANTS):
        participant = Participant(
            participant_id=uuid.uuid4(),
            discussion_id=discussion_id,
            user_id=uuid.uuid4(),
            first_round=1,
            created_at=datetime.utcnow()
        )
        participants.append(participant)
        session.add(participant)

    await session.flush()
    print(f"✅ Created {NUM_PARTICIPANTS} participants")
    return participants


async def submit_round_responses(
    session: AsyncSession,
    round_entity: Round,
    participants: List[Participant],
    round_num: int
) -> List[Submission]:
    """Submit semantically distinct responses."""
    print(f"\n{'='*80}")
    print(f"Round {round_num}: {round_entity.question_text}")
    print(f"{'='*80}")

    responses_dict = QUESTION_RESPONSES[round_num]
    viewpoints = list(responses_dict.keys())

    # Assign participants to viewpoints with variance
    assignments = assign_viewpoints(NUM_PARTICIPANTS, len(viewpoints))

    # Show distribution
    from collections import Counter
    distribution = Counter(assignments)
    print(f"Viewpoint distribution:")
    for i, viewpoint in enumerate(viewpoints):
        count = distribution[i]
        print(f"  {viewpoint}: {count} participants ({count/NUM_PARTICIPANTS*100:.1f}%)")

    submissions = []
    for participant, viewpoint_idx in zip(participants, assignments):
        viewpoint = viewpoints[viewpoint_idx]
        response_options = responses_dict[viewpoint]
        response_text = random.choice(response_options)

        # Add minor variation
        if random.random() < 0.3:
            response_text += " This is critically important."

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
    print(f"✅ {len(submissions)} semantically distinct submissions created")
    return submissions


async def generate_summaries(session: AsyncSession, submissions: List[Submission]) -> List[Summary]:
    """Generate summaries."""
    summaries = []
    for submission in submissions:
        summary_text = submission.submission_text[:150].strip()
        if len(submission.submission_text) > 150:
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
    print(f"✅ {len(summaries)} summaries generated")
    return summaries


async def create_approved_summaries(session: AsyncSession, summaries: List[Summary]) -> List[ApprovedSummary]:
    """Create approved summaries."""
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
    print(f"✅ {len(approved_summaries)} approved summaries")
    return approved_summaries


async def run_clustering(session: AsyncSession, round_entity: Round, approved_summaries: List[ApprovedSummary]):
    """Run clustering."""
    from src.api.routes.clustering import execute_full_clustering_workflow
    from src.models.cluster import Cluster

    print(f"Running HDBSCAN clustering...")
    await execute_full_clustering_workflow(round_id=round_entity.round_id, db=session)

    clusters_result = await session.execute(
        select(Cluster).where(Cluster.round_id == round_entity.round_id)
    )
    clusters = clusters_result.scalars().all()

    print(f"✅ Clustering complete: {len(clusters)} clusters")
    for cluster in sorted(clusters, key=lambda c: c.user_count, reverse=True):
        print(f"   - {cluster.user_count} participants ({cluster.user_pct:.1%})")


async def close_round(session: AsyncSession, round_entity: Round):
    """Close round."""
    round_entity.status = RoundStatus.COMPLETE
    round_entity.completed_at = datetime.utcnow()
    await session.flush()


async def advance_to_next_round(session: AsyncSession, discussion: Discussion, next_round_num: int):
    """Advance to next round."""
    discussion.current_round_num = next_round_num
    stmt = select(Round).where(
        Round.discussion_id == discussion.discussion_id,
        Round.round_num == next_round_num
    )
    result = await session.execute(stmt)
    next_round = result.scalar_one()
    next_round.open_submission_window()
    await session.flush()
    print(f"\n✅ Advanced to Round {next_round_num}")


async def complete_discussion(session: AsyncSession, discussion: Discussion):
    """Complete discussion."""
    discussion.status = DiscussionStatus.COMPLETED
    discussion.completed_at = datetime.utcnow()
    await session.flush()
    print(f"\n{'='*80}")
    print("✅ Discussion COMPLETED")
    print(f"{'='*80}")


async def generate_sankey(session: AsyncSession, discussion: Discussion):
    """Generate Sankey."""
    from src.services.sankey_builder import SankeyBuilder

    print(f"\n{'='*80}")
    print("Generating Sankey Diagram")
    print(f"{'='*80}")

    builder = SankeyBuilder(session)
    stmt = select(Round.round_id).where(Round.discussion_id == discussion.discussion_id).order_by(Round.round_num)
    result = await session.execute(stmt)
    rounds = [row[0] for row in result.all()]

    sankey_graph = await builder.build_sankey_graph(
        discussion_id=discussion.discussion_id,
        rounds=rounds,
        include_alignment=True
    )
    await builder.save_to_database(sankey_graph)

    print(f"✅ Sankey generated!")
    print(f"   View at: http://localhost:3000/discussions/{discussion.discussion_id}/sankey")


async def main():
    """Run simulation."""
    print(f"\n{'='*100}")
    print("SEMANTICALLY DIVERSE DISCUSSION SIMULATION")
    print(f"Balanced Multi-Cluster Formation with 15-30% per Cluster")
    print(f"{'='*100}")

    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            discussion = await create_discussion(session)
            participants = await create_participants(session, discussion.discussion_id)

            discussion.status = DiscussionStatus.ACTIVE
            discussion.started_at = datetime.utcnow()
            await session.flush()

            for round_num in range(1, NUM_ROUNDS + 1):
                stmt = select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == round_num
                )
                result = await session.execute(stmt)
                round_entity = result.scalar_one()

                if round_num > 1:
                    await advance_to_next_round(session, discussion, round_num)
                else:
                    round_entity.open_submission_window()
                    await session.flush()

                submissions = await submit_round_responses(session, round_entity, participants, round_num)
                summaries = await generate_summaries(session, submissions)
                approved_summaries = await create_approved_summaries(session, summaries)
                await run_clustering(session, round_entity, approved_summaries)
                await close_round(session, round_entity)
                await session.commit()

            await complete_discussion(session, discussion)
            await session.commit()

            await generate_sankey(session, discussion)
            await session.commit()

            print(f"\n{'='*100}")
            print("✅ SIMULATION COMPLETE!")
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
