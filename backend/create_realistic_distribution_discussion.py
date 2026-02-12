"""
Create Realistic Discussion with Natural Cluster Distribution

This script creates a more realistic simulation with:
- Majority opinions (larger clusters)
- Minority viewpoints (smaller clusters)
- Some outliers
- Natural variation in cluster sizes

Usage: poetry run python create_realistic_distribution_discussion.py
"""

import asyncio
import uuid
import random
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.models.discussion import Discussion
from src.models.round import Round
from src.models.participant import Participant
from src.models.submission import Submission, SubmissionModality
from src.models.protocol_state import DiscussionTimingMode, DiscussionStatus, RoundStatus
from src.summarization.models.summary import Summary, SummaryStatus
from src.models.approved_summary import ApprovedSummary

# Configuration
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

# Response templates with natural distribution weights
# Format: (template, weight) where higher weight = more common opinion
RESPONSE_TEMPLATES = {
    0: [  # Ethical principles - varied popularity
        ("Transparency must be the foundation - we need to understand how AI makes decisions.", 35),  # Majority view
        ("Human oversight and accountability should be mandatory for all critical AI systems.", 25),
        ("Fairness and non-discrimination should be built into AI from the ground up.", 15),
        ("Privacy protection is essential - AI shouldn't compromise individual data rights.", 10),
        ("Safety and robustness must be tested extensively before deployment.", 8),
        ("Beneficial intent - AI should genuinely improve human wellbeing, not just profit.", 5),
        ("Democratic values and human rights must guide AI development globally.", 2),  # Minority view
    ],
    1: [  # Transparency - varied weights
        ("We need mandatory impact assessments before deploying AI in sensitive domains.", 30),
        ("Open-source AI models would allow public scrutiny and independent verification.", 25),
        ("Clear documentation of training data sources and potential biases is critical.", 18),
        ("Independent oversight boards with technical and ethical expertise should monitor AI.", 12),
        ("Real-time monitoring systems to detect and correct AI failures are necessary.", 8),
        ("Public registers of high-risk AI systems similar to drug approvals would help.", 5),
        ("Whistleblower protections for those who report AI safety concerns are vital.", 2),
    ],
    2: [  # Regulation
        ("Proactive regulation is essential to prevent harm before it occurs.", 28),
        ("Light-touch regulation might stifle innovation - we need balanced approach.", 26),
        ("International coordination is crucial since AI development is global.", 20),
        ("Sector-specific regulations make more sense than one-size-fits-all rules.", 14),
        ("Self-regulation by industry has failed - government oversight is necessary.", 8),
        ("Adaptive regulatory frameworks that evolve with AI capabilities are needed.", 3),
        ("Focus on outcomes and harms rather than specific technical approaches.", 1),
    ],
    3: [  # Employment
        ("Universal basic income may become necessary as AI automates jobs.", 32),
        ("Massive retraining programs needed for workers displaced by automation.", 28),
        ("AI could worsen inequality if benefits concentrate in tech companies.", 18),
        ("New job categories will emerge, but transition period will be challenging.", 12),
        ("Wealth redistribution mechanisms needed to share AI productivity gains.", 6),
        ("Education focus should shift to uniquely human skills AI can't replicate.", 3),
        ("Labor unions and worker protections must adapt to AI-driven workplace.", 1),
    ],
    4: [  # Bias
        ("Diverse teams building AI are essential to identify hidden biases.", 30),
        ("Regular audits of AI systems for discriminatory outcomes are critical.", 26),
        ("Representative training data that reflects human diversity is fundamental.", 20),
        ("Clear accountability when AI systems produce biased results must be established.", 12),
        ("Public reporting requirements for fairness metrics should be mandatory.", 7),
        ("Community involvement in AI development affecting their lives is important.", 4),
        ("Legal frameworks treating algorithmic discrimination like human discrimination needed.", 1),
    ],
    5: [  # Privacy
        ("Strong encryption and data minimization should be default in all AI systems.", 34),
        ("Privacy-preserving AI techniques like federated learning show great promise.", 28),
        ("Individuals should own and control their personal data, not corporations.", 18),
        ("Opt-in consent models rather than hidden terms of service are essential.", 10),
        ("Differential privacy ensures aggregate insights without individual exposure.", 6),
        ("Clear boundaries between innovation and surveillance must be maintained.", 3),
        ("Privacy impact assessments required before any data collection.", 1),
    ],
    6: [  # Critical infrastructure
        ("AI in healthcare could save lives through better diagnosis and treatment.", 32),
        ("Critical systems need human-in-the-loop safeguards against AI failures.", 30),
        ("Extensive testing and certification before deploying AI in infrastructure mandatory.", 20),
        ("Cybersecurity protections against AI system manipulation are crucial.", 10),
        ("Clear liability frameworks when AI systems fail in critical applications needed.", 5),
        ("Benefits could be enormous but risks require careful management.", 2),
        ("Gradual deployment with continuous monitoring and evaluation is wise.", 1),
    ],
    7: [  # Global equity
        ("Technology transfer and capacity building in developing nations essential.", 28),
        ("Open-source AI tools can democratize access globally.", 26),
        ("International funding for AI infrastructure in underserved regions needed.", 22),
        ("Address digital divide in internet and computing access first.", 14),
        ("Local language and cultural considerations in AI development matter.", 6),
        ("Prevent brain drain by supporting AI research in all countries.", 3),
        ("Global AI governance should include voices from all nations equally.", 1),
    ],
    8: [  # Education
        ("Critical thinking and AI literacy should start in elementary school.", 30),
        ("Curriculum should emphasize creativity and emotional intelligence.", 28),
        ("Hands-on coding and AI ethics education for all students is important.", 20),
        ("Teacher training programs to integrate AI tools effectively are needed.", 12),
        ("Lifelong learning programs as career changes become more frequent.", 6),
        ("Focus on interdisciplinary skills connecting technology with humanities.", 3),
        ("Digital citizenship education including AI's societal impacts is crucial.", 1),
    ],
    9: [  # AGI
        ("International coordination essential to prevent dangerous AI race.", 35),
        ("Extensive safety research before pursuing AGI capabilities is critical.", 30),
        ("Clear red lines on capabilities that shouldn't be developed.", 18),
        ("AGI development should be collaborative, not competitive.", 10),
        ("Philosophical and ethical frameworks must precede technical development.", 5),
        ("Public input and democratic governance over AGI direction needed.", 1),
        ("Commitment to ensuring AGI benefits all humanity, not narrow interests.", 1),
    ],
}


def select_weighted_response(templates_with_weights: List[tuple]) -> str:
    """Select a response using weighted random selection."""
    templates = [t[0] for t in templates_with_weights]
    weights = [t[1] for t in templates_with_weights]

    selected = random.choices(templates, weights=weights, k=1)[0]

    # Add natural variations
    variations = [
        selected,
        f"I believe {selected.lower()}",
        f"From my perspective, {selected.lower()}",
        f"It's crucial that {selected.lower()}",
        f"We must consider that {selected.lower()}",
        f"{selected} This is fundamentally important.",
        f"{selected} We cannot afford to ignore this.",
    ]

    return random.choice(variations)


async def create_discussion(session: AsyncSession) -> Discussion:
    """Create discussion with 10 rounds."""
    print(f"\n{'='*80}")
    print("Creating Realistic 10-Round Discussion")
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
    print(f"   Topic: AI Ethics with Realistic Distributions")
    return discussion


async def create_participants(session: AsyncSession, discussion_id: uuid.UUID) -> List[Participant]:
    """Create participants."""
    print(f"\n{'='*80}")
    print(f"Creating {NUM_PARTICIPANTS} Participants")
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
    """Submit responses with realistic weighted distribution."""
    print(f"\n{'='*80}")
    print(f"Round {round_num}: {round_entity.question_text}")
    print(f"{'='*80}")

    templates_with_weights = RESPONSE_TEMPLATES[round_num - 1]
    submissions = []

    for participant in participants:
        response_text = select_weighted_response(templates_with_weights)

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
    print(f"✅ {len(submissions)} submissions created with weighted distribution")
    return submissions


async def generate_summaries(session: AsyncSession, submissions: List[Submission]) -> List[Summary]:
    """Generate summaries."""
    summaries = []
    for submission in submissions:
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
    print(f"✅ {len(approved_summaries)} approved summaries created")
    return approved_summaries


async def run_clustering(session: AsyncSession, round_entity: Round, approved_summaries: List[ApprovedSummary]):
    """Run clustering."""
    from src.api.routes.clustering import execute_full_clustering_workflow

    print(f"Running HDBSCAN clustering...")
    await execute_full_clustering_workflow(round_id=round_entity.round_id, db=session)
    print(f"✅ Clustering complete")


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


async def complete_discussion(session: AsyncSession, discussion: Discussion):
    """Complete discussion."""
    discussion.status = DiscussionStatus.COMPLETED
    discussion.completed_at = datetime.utcnow()
    await session.flush()
    print(f"\n{'='*80}")
    print("✅ Discussion Completed")
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
    """Main execution."""
    print(f"\n{'='*80}")
    print("REALISTIC DISTRIBUTION SIMULATION")
    print(f"{'='*80}")

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

            print(f"\n{'='*80}")
            print("✅ SIMULATION COMPLETE!")
            print(f"{'='*80}")
            print(f"Discussion ID: {discussion.discussion_id}")
            print(f"Sankey: http://localhost:3000/discussions/{discussion.discussion_id}/sankey")

        except Exception as e:
            await session.rollback()
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(main())
