"""
Simple Random Distribution Discussion - Natural Variance

Uses pure random selection (no cycling, no weights) to produce natural variance.

Usage: poetry run python create_random_discussion.py
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
from src.summarization.services.summarization_service import SummarizationService

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

RESPONSE_TEMPLATES = {
    0: [
        "Transparency must be the foundation - we need to understand how AI makes decisions.",
        "Human oversight and accountability should be mandatory for all critical AI systems.",
        "Fairness and non-discrimination should be built into AI from the ground up.",
        "Privacy protection is essential - AI shouldn't compromise individual data rights.",
        "Safety and robustness must be tested extensively before deployment.",
        "Beneficial intent - AI should genuinely improve human wellbeing, not just profit.",
        "Democratic values and human rights must guide AI development globally.",
    ],
    1: [
        "Open-source AI models would allow public scrutiny and independent verification.",
        "Mandatory impact assessments before deploying AI in sensitive domains.",
        "Clear documentation of training data sources and potential biases.",
        "Independent oversight boards with technical and ethical expertise.",
        "Real-time monitoring systems to detect and correct AI failures.",
        "Public registers of high-risk AI systems similar to drug approvals.",
        "Whistleblower protections for those who report AI safety concerns.",
    ],
    2: [
        "Proactive regulation is essential to prevent harm before it occurs.",
        "Light-touch regulation might stifle innovation - we need balanced approach.",
        "International coordination is crucial since AI development is global.",
        "Sector-specific regulations make more sense than one-size-fits-all rules.",
        "Self-regulation by industry has failed - government oversight is necessary.",
        "Adaptive regulatory frameworks that evolve with AI capabilities.",
        "Focus on outcomes and harms rather than specific technical approaches.",
    ],
    3: [
        "Universal basic income may become necessary as AI automates jobs.",
        "Massive retraining programs needed for workers displaced by automation.",
        "AI could worsen inequality if benefits concentrate in tech companies.",
        "New job categories will emerge, but transition period will be challenging.",
        "Wealth redistribution mechanisms needed to share AI productivity gains.",
        "Education focus should shift to uniquely human skills AI can't replicate.",
        "Labor unions and worker protections must adapt to AI-driven workplace.",
    ],
    4: [
        "Diverse teams building AI are essential to identify hidden biases.",
        "Regular audits of AI systems for discriminatory outcomes.",
        "Representative training data that reflects human diversity.",
        "Clear accountability when AI systems produce biased results.",
        "Public reporting requirements for fairness metrics.",
        "Community involvement in AI development affecting their lives.",
        "Legal frameworks treating algorithmic discrimination like human discrimination.",
    ],
    5: [
        "Strong encryption and data minimization should be default.",
        "Privacy-preserving AI techniques like federated learning show promise.",
        "Individuals should own and control their personal data.",
        "Opt-in consent models rather than hidden terms of service.",
        "Differential privacy ensures aggregate insights without individual exposure.",
        "Clear boundaries between innovation and surveillance.",
        "Privacy impact assessments required before data collection.",
    ],
    6: [
        "AI in healthcare could save lives through better diagnosis and treatment.",
        "Critical systems need human-in-the-loop safeguards against AI failures.",
        "Extensive testing and certification before deploying AI in infrastructure.",
        "Cybersecurity protections against AI system manipulation.",
        "Clear liability frameworks when AI systems fail in critical applications.",
        "Benefits could be enormous but risks require careful management.",
        "Gradual deployment with continuous monitoring and evaluation.",
    ],
    7: [
        "Technology transfer and capacity building in developing nations essential.",
        "Open-source AI tools can democratize access globally.",
        "International funding for AI infrastructure in underserved regions.",
        "Address digital divide in internet and computing access first.",
        "Local language and cultural considerations in AI development.",
        "Prevent brain drain by supporting AI research in all countries.",
        "Global AI governance should include voices from all nations equally.",
    ],
    8: [
        "Critical thinking and AI literacy should start in elementary school.",
        "Curriculum should emphasize creativity and emotional intelligence.",
        "Hands-on coding and AI ethics education for all students.",
        "Teacher training programs to integrate AI tools effectively.",
        "Lifelong learning programs as career changes become more frequent.",
        "Focus on interdisciplinary skills connecting technology with humanities.",
        "Digital citizenship education including AI's societal impacts.",
    ],
    9: [
        "International coordination essential to prevent dangerous AI race.",
        "Extensive safety research before pursuing AGI capabilities.",
        "Clear red lines on capabilities that shouldn't be developed.",
        "AGI development should be collaborative, not competitive.",
        "Philosophical and ethical frameworks must precede technical development.",
        "Public input and democratic governance over AGI direction.",
        "Commitment to ensuring AGI benefits all humanity, not narrow interests.",
    ],
}


def generate_random_response(round_num: int) -> str:
    """Pure random selection with natural variations."""
    templates = RESPONSE_TEMPLATES[round_num - 1]
    base = random.choice(templates)  # PURE RANDOM - no cycling!

    variations = [
        base,
        f"I believe {base.lower()}",
        f"From my perspective, {base.lower()}",
        f"It's crucial that {base.lower()}",
        f"We must consider that {base.lower()}",
    ]

    return random.choice(variations)


async def create_discussion(session: AsyncSession) -> Discussion:
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
    print(f"✅ Discussion created: {discussion.discussion_id}")
    return discussion


async def create_participants(session: AsyncSession, discussion_id: uuid.UUID) -> List[Participant]:
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
    return participants


async def main():
    print(f"\n{'='*80}")
    print("SIMPLE RANDOM DISTRIBUTION - Natural Variance Test")
    print(f"{'='*80}\n")

    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            discussion = await create_discussion(session)
            participants = await create_participants(session, discussion.discussion_id)

            discussion.status = DiscussionStatus.ACTIVE
            discussion.started_at = datetime.utcnow()
            await session.flush()

            for round_num in range(1, NUM_ROUNDS + 1):
                print(f"Round {round_num}: {QUESTIONS[round_num-1]}")

                stmt = select(Round).where(
                    Round.discussion_id == discussion.discussion_id,
                    Round.round_num == round_num
                )
                result = await session.execute(stmt)
                round_entity = result.scalar_one()

                if round_num == 1:
                    round_entity.open_submission_window()
                else:
                    discussion.current_round_num = round_num
                    round_entity.open_submission_window()
                await session.flush()

                # Create submissions with PURE RANDOM selection
                submissions = []
                for participant in participants:
                    response_text = generate_random_response(round_num)
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

                # Summaries - using actual LLM summarization service
                print(f"  Generating LLM summaries for {len(submissions)} submissions...")
                summarization_service = SummarizationService(db=session)

                summaries = []
                for idx, submission in enumerate(submissions, 1):
                    if idx % 10 == 0:
                        print(f"    Generated {idx}/{len(submissions)} summaries...")

                    # Generate actual LLM summary (using GPT-3.5 for speed)
                    summary = await summarization_service.generate_summary(
                        submission_id=submission.submission_id,
                        use_fallback_model=True  # Use GPT-3.5 for speed in simulations
                    )

                    # Auto-approve for simulation purposes
                    summary.status = SummaryStatus.APPROVED
                    summary.approved_at = datetime.utcnow()
                    summaries.append(summary)

                await session.flush()
                print(f"  ✓ Generated {len(summaries)} LLM summaries")

                # Approved summaries
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
                    session.add(approved)
                await session.flush()

                # Clustering
                from src.api.routes.clustering import execute_full_clustering_workflow
                await execute_full_clustering_workflow(round_id=round_entity.round_id, db=session)

                round_entity.status = RoundStatus.COMPLETE
                round_entity.completed_at = datetime.utcnow()
                await session.commit()
                print(f"  ✅ Round {round_num} complete\n")

            discussion.status = DiscussionStatus.COMPLETED
            discussion.completed_at = datetime.utcnow()
            await session.commit()

            # Generate Sankey
            from src.services.sankey_builder import SankeyBuilder
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
            await session.commit()

            print(f"\n{'='*80}")
            print("✅ RANDOM SIMULATION COMPLETE!")
            print(f"{'='*80}")
            print(f"Discussion ID: {discussion.discussion_id}")
            print(f"View: http://localhost:3000/discussions/{discussion.discussion_id}/sankey\n")

        except Exception as e:
            await session.rollback()
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(main())
