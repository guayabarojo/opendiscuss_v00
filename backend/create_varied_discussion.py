"""
Sophisticated Discussion Generator with Realistic Variance

Creates discussions with N participants and M rounds where:
- Participants have evolving viewpoints influenced by prior rounds
- Responses show natural diversity and disagreement
- No artificial uniformity - realistic clustering behavior

Usage:
    poetry run python create_varied_discussion.py --participants 100 --rounds 10
"""

import asyncio
import argparse
import random
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from sqlalchemy import select

from src.database import get_session_factory
from src.models.discussion import Discussion
from src.models.protocol_state import DiscussionStatus, DiscussionMode, RoundStatus
from src.models.round import Round
from src.models.participant import Participant
from src.models.submission import Submission, SubmissionModality
from src.models.approved_summary import ApprovedSummary
from src.models.cluster import Cluster
from sqlalchemy import select


# Question bank for various topics
QUESTION_BANKS = {
    "ai_ethics": [
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
    ],
    "climate": [
        "What are the most effective strategies to reduce carbon emissions globally?",
        "How should we balance economic growth with environmental sustainability?",
        "What role should nuclear energy play in our clean energy future?",
        "How can we ensure a just transition for workers in fossil fuel industries?",
        "What are the most promising carbon capture technologies?",
    ],
    "healthcare": [
        "How can we make healthcare more accessible and affordable?",
        "What role should technology play in modern healthcare delivery?",
        "How should we balance patient privacy with medical research needs?",
        "What are the most effective ways to address mental health in communities?",
        "How can we reduce healthcare disparities across different populations?",
    ]
}


class ParticipantPersona:
    """Represents a participant with evolving viewpoints"""

    def __init__(self, participant_id: UUID):
        self.participant_id = participant_id

        # Core traits (stable throughout discussion)
        self.openness = random.uniform(0.3, 0.9)  # Willingness to change views
        self.expertise = random.uniform(0.1, 0.8)  # Knowledge level
        self.engagement = random.uniform(0.4, 1.0)  # Response quality/length

        # Initial stance on key dimensions
        self.pro_regulation = random.uniform(0.0, 1.0)
        self.pro_innovation = random.uniform(0.0, 1.0)
        self.community_focus = random.uniform(0.0, 1.0)
        self.risk_tolerance = random.uniform(0.0, 1.0)

        # Memory of previous round themes (influences future responses)
        self.remembered_themes: List[str] = []

    def evolve_views(self, round_num: int, influential_themes: List[str]):
        """Adjust viewpoints based on what participant saw in previous rounds"""
        if not influential_themes or self.openness < 0.3:
            return  # Closed-minded participants don't change much

        # Open participants gradually shift toward themes they've seen
        shift_amount = self.openness * 0.15 * random.uniform(0.5, 1.5)

        for theme in influential_themes[-3:]:  # Last 3 rounds influence most
            if "regulat" in theme.lower() or "oversight" in theme.lower():
                self.pro_regulation += shift_amount * random.choice([-1, 1])
            if "innovate" in theme.lower() or "progress" in theme.lower():
                self.pro_innovation += shift_amount * random.choice([-1, 1])
            if "community" in theme.lower() or "equity" in theme.lower():
                self.community_focus += shift_amount * random.choice([-1, 1])

        # Clamp values to [0, 1]
        self.pro_regulation = max(0, min(1, self.pro_regulation))
        self.pro_innovation = max(0, min(1, self.pro_innovation))
        self.community_focus = max(0, min(1, self.community_focus))

        # Remember themes for next round
        self.remembered_themes.extend(influential_themes[-2:])
        if len(self.remembered_themes) > 5:
            self.remembered_themes = self.remembered_themes[-5:]


def generate_response(persona: ParticipantPersona, question: str, round_num: int) -> str:
    """Generate a response that reflects participant's current viewpoints"""

    # Base response fragments
    regulatory_responses = [
        "Strong oversight is essential",
        "We need clear regulations and accountability",
        "Government must play an active role",
        "Independent audits should be mandatory",
        "Regulatory frameworks ensure safety",
        "Self-regulation has proven insufficient",
        "Proactive policy prevents harm",
    ]

    innovation_responses = [
        "Innovation drives progress",
        "We must not stifle technological advancement",
        "Market forces encourage quality",
        "Flexible approaches allow experimentation",
        "Breakthrough solutions need room to develop",
        "Over-regulation could push innovation elsewhere",
        "Rapid iteration helps us learn faster",
    ]

    community_responses = [
        "We must ensure equitable access for all",
        "Community input is crucial",
        "Protect vulnerable populations first",
        "Benefits should be widely distributed",
        "Local contexts matter in implementation",
        "Address existing inequalities",
        "Diverse perspectives strengthen outcomes",
    ]

    pragmatic_responses = [
        "Balance is key in this issue",
        "Evidence should guide our decisions",
        "We need both protection and progress",
        "Context-specific solutions work best",
        "Learn from successes and failures",
        "Collaborative approaches are most effective",
        "Stakeholder engagement improves outcomes",
    ]

    # Select response based on persona's current views
    response_parts = []

    # Add regulatory perspective if pro_regulation is high
    if persona.pro_regulation > 0.6:
        response_parts.append(random.choice(regulatory_responses))
    elif persona.pro_regulation < 0.3:
        response_parts.append("Excessive regulation can be counterproductive")

    # Add innovation perspective
    if persona.pro_innovation > 0.6:
        response_parts.append(random.choice(innovation_responses))
    elif persona.pro_innovation < 0.3:
        response_parts.append("We should proceed cautiously and deliberately")

    # Add community perspective
    if persona.community_focus > 0.6:
        response_parts.append(random.choice(community_responses))

    # Fill in with pragmatic if response is thin
    if len(response_parts) < 2:
        response_parts.append(random.choice(pragmatic_responses))

    # Add references to previous rounds (if participant remembers)
    if persona.remembered_themes and random.random() < 0.3:
        remembered = random.choice(persona.remembered_themes)
        response_parts.insert(0, f"Building on previous discussions about {remembered}")

    # Vary response style based on engagement
    if persona.engagement > 0.7:
        # Detailed, multi-point response
        response = f"I believe {response_parts[0].lower()}. " + \
                  f"Additionally, {response_parts[1].lower() if len(response_parts) > 1 else 'we must consider all perspectives'}. " + \
                  f"In my view, this requires {random.choice(['careful consideration', 'immediate action', 'ongoing dialogue', 'practical implementation'])}."
    elif persona.engagement > 0.4:
        # Moderate response
        response = f"{response_parts[0]}. {response_parts[1] if len(response_parts) > 1 else 'This is crucial for our future.'}."
    else:
        # Brief response
        response = response_parts[0] + "."

    # Add question-specific keywords for relevance
    if "employ" in question.lower() or "job" in question.lower():
        response += " This especially matters for workforce impacts."
    elif "privacy" in question.lower() or "data" in question.lower():
        response += " Privacy considerations are paramount."
    elif "global" in question.lower() or "international" in question.lower():
        response += " We need international cooperation on this."
    elif "education" in question.lower():
        response += " Educational reform is essential."

    return response


async def create_varied_discussion(
    num_participants: int = 100,
    num_rounds: int = 10,
    topic: str = "ai_ethics"
):
    """Create a discussion with realistic variance"""

    print("="*80)
    print(f"CREATING DISCUSSION: {num_participants} participants × {num_rounds} rounds")
    print("="*80)

    questions = QUESTION_BANKS.get(topic, QUESTION_BANKS["ai_ethics"])[:num_rounds]
    if len(questions) < num_rounds:
        print(f"⚠️  Only {len(questions)} questions available for topic '{topic}'")
        num_rounds = len(questions)

    async_session_factory = get_session_factory()
    async with async_session_factory() as db:
        # Create discussion
        discussion_id = uuid4()
        discussion = Discussion(
            discussion_id=discussion_id,
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            host_user_id=uuid4(),
            total_rounds=num_rounds,
            status=DiscussionStatus.COMPLETED,
            created_at=datetime.utcnow() - timedelta(hours=num_rounds),
            completed_at=datetime.utcnow()
        )
        db.add(discussion)
        await db.flush()

        print(f"\n✓ Created discussion: {discussion_id}")
        print(f"  Topic: {topic}")
        print(f"  Participants: {num_participants}")
        print(f"  Rounds: {num_rounds}")

        # Create participants with personas
        personas: Dict[UUID, ParticipantPersona] = {}
        for i in range(num_participants):
            participant_id = uuid4()
            participant = Participant(
                discussion_id=discussion_id,
                user_id=uuid4(),
                first_round=1,
                participant_id=participant_id,
                created_at=datetime.utcnow()
            )
            db.add(participant)
            personas[participant_id] = ParticipantPersona(participant_id)

        await db.flush()
        print(f"\n✓ Created {num_participants} participants with unique personas")
        print(f"  Openness range: {min(p.openness for p in personas.values()):.2f} - {max(p.openness for p in personas.values()):.2f}")
        print(f"  Engagement range: {min(p.engagement for p in personas.values()):.2f} - {max(p.engagement for p in personas.values()):.2f}")

        # Track themes for evolution
        round_themes: List[str] = []

        # Create rounds and responses
        for round_num in range(num_rounds):
            round_id = uuid4()
            round_obj = Round(
                discussion_id=discussion_id,
                round_num=round_num + 1,
                question_text=questions[round_num],
                submission_window_duration_sec=300,
                round_id=round_id
            )
            db.add(round_obj)
            await db.flush()

            print(f"\n  Round {round_num + 1}: {questions[round_num][:60]}...")

            # Evolve personas based on previous round
            if round_num > 0:
                for persona in personas.values():
                    persona.evolve_views(round_num, round_themes)

            # Generate varied responses
            round_theme_samples = []
            for participant_id, persona in personas.items():
                # Some participants might skip a round (dropout simulation)
                if random.random() < 0.02:  # 2% skip rate per round
                    continue

                response_text = generate_response(persona, questions[round_num], round_num)
                round_theme_samples.append(response_text[:50])

                # Create submission
                submission_time = datetime.utcnow() - timedelta(hours=(num_rounds - round_num), minutes=random.randint(1, 29))
                submission = Submission(
                    submission_id=uuid4(),
                    participant_id=participant_id,
                    round_id=round_id,
                    submission_text=response_text,
                    modality=SubmissionModality.TEXT,
                    submitted_at=submission_time
                )
                db.add(submission)

                # Create approved summary
                summary = ApprovedSummary(
                    summary_id=uuid4(),
                    round_id=round_id,
                    participant_id=participant_id,
                    submission_id=submission.submission_id,
                    summary_text=response_text,
                    approved_at=submission_time + timedelta(seconds=5),
                    created_at=submission_time + timedelta(seconds=5)
                )
                db.add(summary)

            await db.flush()

            # Remember themes for next round
            if round_theme_samples:
                round_themes.append(random.choice(round_theme_samples))

            actual_responses = len([p for p in personas.values()]) - int(num_participants * 0.02 * (round_num + 1))
            print(f"    ✓ Created ~{actual_responses} varied responses")

        await db.commit()

        # Run clustering on all rounds
        print("\n" + "="*80)
        print("Running HDBSCAN Clustering on All Rounds")
        print("="*80)

        from src.api.routes.clustering import execute_full_clustering_workflow

        stmt = select(Round).where(Round.discussion_id == discussion_id).order_by(Round.round_num)
        result = await db.execute(stmt)
        rounds = result.scalars().all()

        for round_obj in rounds:
            print(f"\nRound {round_obj.round_num}: Clustering...")

            # Execute clustering workflow
            await execute_full_clustering_workflow(
                round_id=round_obj.round_id,
                db=db
            )

            # Query created clusters
            clusters_result = await db.execute(
                select(Cluster).where(Cluster.round_id == round_obj.round_id)
            )
            clusters = clusters_result.scalars().all()

            print(f"  ✓ {len(clusters)} clusters created")
            for cluster in clusters[:5]:  # Show top 5
                print(f"     - {cluster.user_count} participants ({cluster.user_pct:.1%})")

            # Mark round complete
            round_obj.status = RoundStatus.COMPLETE
            round_obj.completed_at = datetime.utcnow()

        await db.commit()

        # Generate Sankey diagram
        print("\n" + "="*80)
        print("Generating Sankey Diagram")
        print("="*80)

        from src.services.sankey_builder import SankeyBuilder

        builder = SankeyBuilder(db)
        round_ids = [r.round_id for r in rounds]

        sankey_graph = await builder.build_sankey_graph(
            discussion_id=discussion_id,
            rounds=round_ids,
            include_alignment=True
        )

        await builder.save_to_database(sankey_graph)

        print(f"✓ Sankey diagram generated!")
        print(f"  Columns: {len(sankey_graph.columns)}")
        print(f"  Edges: {len(sankey_graph.edges)}")

        await db.commit()

        print("\n" + "="*80)
        print("✅ DISCUSSION CREATION COMPLETE")
        print("="*80)
        print(f"\nDiscussion ID: {discussion_id}")
        print(f"View Sankey: http://localhost:3000/discussions/{discussion_id}/sankey")
        print(f"\n📊 Expected Clustering:")
        print(f"  • Natural cluster count (NOT forced to 7)")
        print(f"  • Diverse cluster sizes based on actual response similarity")
        print(f"  • Realistic participant movement across rounds")
        print(f"  • Viewpoint evolution visible in cluster transitions")
        print("\n" + "="*80)

        return str(discussion_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate discussion with realistic variance")
    parser.add_argument("--participants", type=int, default=100, help="Number of participants")
    parser.add_argument("--rounds", type=int, default=10, help="Number of rounds")
    parser.add_argument("--topic", type=str, default="ai_ethics",
                       choices=["ai_ethics", "climate", "healthcare"],
                       help="Discussion topic")

    args = parser.parse_args()

    asyncio.run(create_varied_discussion(
        num_participants=args.participants,
        num_rounds=args.rounds,
        topic=args.topic
    ))
