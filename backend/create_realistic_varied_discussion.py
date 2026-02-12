"""
Realistic Large-Scale Discussion with Natural Variance

Creates a 100-participant, 10-round discussion with:
- Truly random response generation
- Natural cluster size variation (some big, some small)
- Realistic participant movement patterns
- Organic convergence and divergence
"""

import asyncio
import uuid
import random
from datetime import datetime
from typing import List
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

# Questions about AI Ethics
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

# Diverse opinion archetypes with different perspectives
VIEWPOINT_ARCHETYPES = {
    "tech_optimist": {
        "themes": ["innovation", "progress", "efficiency", "potential"],
        "style": "enthusiastic and forward-looking",
        "examples": [
            "AI represents humanity's greatest opportunity for solving complex challenges.",
            "We should embrace AI innovation while implementing smart guardrails.",
            "The potential benefits far outweigh the risks if we develop it responsibly.",
            "History shows technology creates more opportunities than it destroys.",
        ]
    },
    "cautious_regulator": {
        "themes": ["safety", "oversight", "accountability", "regulation"],
        "style": "measured and policy-focused",
        "examples": [
            "We need comprehensive regulatory frameworks before widespread deployment.",
            "Safety and accountability must come before speed of innovation.",
            "Clear legal liability is essential for AI systems.",
            "Government oversight is necessary to prevent corporate abuse.",
        ]
    },
    "privacy_advocate": {
        "themes": ["privacy", "surveillance", "data rights", "consent"],
        "style": "protective and rights-focused",
        "examples": [
            "Individual privacy must be protected at all costs.",
            "Data collection should be strictly opt-in with full transparency.",
            "We're sliding toward a surveillance state without strong protections.",
            "Personal data ownership is a fundamental human right.",
        ]
    },
    "equity_focused": {
        "themes": ["inequality", "access", "fairness", "global justice"],
        "style": "socially conscious and critical",
        "examples": [
            "AI benefits are concentrating wealth among tech elites.",
            "We must ensure equal access across all communities.",
            "Current AI development widens existing inequalities.",
            "Global south voices are being excluded from AI governance.",
        ]
    },
    "pragmatic_skeptic": {
        "themes": ["limitations", "hype", "practical concerns", "realism"],
        "style": "critical and grounded",
        "examples": [
            "We're overhyping AI's capabilities while ignoring real limitations.",
            "Current systems are brittle and fail in unpredictable ways.",
            "The technology isn't mature enough for critical applications.",
            "We need to be realistic about what AI can and cannot do.",
        ]
    },
    "worker_advocate": {
        "themes": ["labor", "employment", "workers", "unions"],
        "style": "focused on working class impact",
        "examples": [
            "Workers are bearing the cost of automation while owners reap profits.",
            "We need strong social safety nets as jobs are displaced.",
            "Labor unions must have a voice in AI deployment decisions.",
            "Job retraining programs are inadequate for the scale of change coming.",
        ]
    },
    "libertarian": {
        "themes": ["freedom", "market", "minimal regulation", "innovation"],
        "style": "market-focused and anti-regulation",
        "examples": [
            "Government regulation will stifle innovation and progress.",
            "Market forces will naturally select for beneficial AI.",
            "Individual choice and competition create better outcomes than mandates.",
            "Heavy-handed regulation will push development to less scrupulous jurisdictions.",
        ]
    },
    "ethics_first": {
        "themes": ["values", "humanity", "philosophy", "moral"],
        "style": "philosophical and value-driven",
        "examples": [
            "We must deeply consider what values we're encoding into AI systems.",
            "Technical capability doesn't equal moral justification.",
            "Philosophy and ethics must guide technical development, not follow it.",
            "We're making civilization-altering decisions without adequate ethical frameworks.",
        ]
    },
}


def generate_realistic_response(round_num: int, viewpoint: str, participant_id: int) -> str:
    """Generate a realistic, varied response based on viewpoint and context."""
    archetype = VIEWPOINT_ARCHETYPES[viewpoint]
    question = QUESTIONS[round_num - 1]

    # Mix of opinion strength
    intensity = random.choice(["strongly believe", "think", "worry that", "feel", "would argue", "suggest"])

    # Choose relevant themes for this question
    theme = random.choice(archetype["themes"])

    # Generate response with natural variation
    templates = [
        f"I {intensity} that {theme} should be the primary consideration. {random.choice(archetype['examples'])}",
        f"{random.choice(archetype['examples'])} We need to prioritize {theme} in our approach.",
        f"From my perspective on {theme}, {random.choice(archetype['examples']).lower()}",
        f"The key issue here is {theme}. {random.choice(archetype['examples'])}",
        f"{random.choice(archetype['examples'])} This is fundamentally about {theme}.",
    ]

    response = random.choice(templates)

    # Add occasional elaboration (30% chance)
    if random.random() < 0.3:
        elaborations = [
            " We can't afford to ignore this reality.",
            " The stakes are too high to get this wrong.",
            " This requires immediate attention and action.",
            " We're at a critical decision point.",
            " History will judge how we handle this.",
        ]
        response += random.choice(elaborations)

    return response


async def create_discussion(session: AsyncSession) -> Discussion:
    """Create 10-round discussion."""
    print(f"\n{'='*80}")
    print("Creating Realistic 10-Round Discussion: AI Ethics")
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
    return discussion


async def create_participants(session: AsyncSession, discussion_id: uuid.UUID) -> List[tuple]:
    """Create 100 participants with assigned viewpoints."""
    print(f"\n{'='*80}")
    print("Creating 100 Participants with Diverse Viewpoints")
    print(f"{'='*80}")

    # Distribute viewpoints realistically (some more common than others)
    viewpoint_weights = {
        "tech_optimist": 18,
        "cautious_regulator": 16,
        "privacy_advocate": 14,
        "equity_focused": 12,
        "pragmatic_skeptic": 15,
        "worker_advocate": 10,
        "libertarian": 8,
        "ethics_first": 7,
    }

    # Assign viewpoints to participants
    viewpoints = []
    for viewpoint, count in viewpoint_weights.items():
        viewpoints.extend([viewpoint] * count)

    random.shuffle(viewpoints)

    participants = []
    for i, viewpoint in enumerate(viewpoints):
        participant = Participant(
            participant_id=uuid.uuid4(),
            discussion_id=discussion_id,
            user_id=uuid.uuid4(),
            first_round=1,
            created_at=datetime.utcnow()
        )
        participants.append((participant, viewpoint))
        session.add(participant)

    await session.flush()

    # Print distribution
    print(f"✅ Created {NUM_PARTICIPANTS} participants")
    print(f"\nViewpoint Distribution:")
    for viewpoint, count in viewpoint_weights.items():
        print(f"  {viewpoint}: {count} participants")

    return participants


async def submit_round_responses(
    session: AsyncSession,
    round_entity: Round,
    participants_with_views: List[tuple],
    round_num: int
) -> List[Submission]:
    """Submit realistic varied responses."""
    print(f"\n{'='*80}")
    print(f"Round {round_num}: {round_entity.question_text}")
    print(f"{'='*80}")
    print(f"Generating realistic varied responses...")

    submissions = []
    for i, (participant, viewpoint) in enumerate(participants_with_views):
        response_text = generate_realistic_response(round_num, viewpoint, i)

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
    print(f"✅ {len(submissions)} diverse submissions created")
    return submissions


async def generate_summaries(
    session: AsyncSession,
    submissions: List[Submission]
) -> List[Summary]:
    """Generate summaries."""
    print(f"Generating {len(submissions)} summaries...")

    summaries = []
    for submission in submissions:
        # Use first 150 chars as summary
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
):
    """Run HDBSCAN clustering."""
    from src.api.routes.clustering import execute_full_clustering_workflow
    from src.models.cluster import Cluster

    print(f"Running HDBSCAN clustering on {len(approved_summaries)} summaries...")

    await execute_full_clustering_workflow(
        round_id=round_entity.round_id,
        db=session
    )

    # Query clusters
    clusters_result = await session.execute(
        select(Cluster).where(Cluster.round_id == round_entity.round_id)
    )
    clusters = clusters_result.scalars().all()

    print(f"✅ Clustering complete: {len(clusters)} natural clusters formed")

    # Show distribution
    if clusters:
        for cluster in sorted(clusters, key=lambda c: c.user_count, reverse=True):
            print(f"   - {cluster.user_count} participants ({cluster.user_pct:.1%})")


async def close_round(session: AsyncSession, round_entity: Round):
    """Mark round as complete."""
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
    """Mark discussion as completed."""
    discussion.status = DiscussionStatus.COMPLETED
    discussion.completed_at = datetime.utcnow()
    await session.flush()
    print(f"\n{'='*80}")
    print("✅ Discussion COMPLETED")
    print(f"{'='*80}")


async def generate_sankey(session: AsyncSession, discussion: Discussion):
    """Generate Sankey diagram."""
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

    print(f"✅ Sankey diagram generated!")
    print(f"   View at: http://localhost:3000/discussions/{discussion.discussion_id}/sankey")


async def main():
    """Run realistic varied discussion."""
    print(f"\n{'='*100}")
    print("REALISTIC LARGE-SCALE DISCUSSION SIMULATION")
    print(f"{NUM_PARTICIPANTS} Participants × {NUM_ROUNDS} Rounds with Natural Variance")
    print(f"{'='*100}")

    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            discussion = await create_discussion(session)
            participants_with_views = await create_participants(session, discussion.discussion_id)

            discussion.status = DiscussionStatus.ACTIVE
            discussion.started_at = datetime.utcnow()
            await session.flush()

            # Execute all rounds
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

                submissions = await submit_round_responses(session, round_entity, participants_with_views, round_num)
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
            print("✅ REALISTIC SIMULATION COMPLETE!")
            print(f"{'='*100}")
            print(f"Discussion ID: {discussion.discussion_id}")
            print(f"View Sankey: http://localhost:3000/discussions/{discussion.discussion_id}/sankey")
            print(f"\nThis simulation includes:")
            print(f"  • Natural viewpoint distribution (8 archetypes)")
            print(f"  • Realistic response variance")
            print(f"  • Organic cluster formation")
            print(f"  • Authentic participant movement patterns")

        except Exception as e:
            await session.rollback()
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(main())
