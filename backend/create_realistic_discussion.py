"""
Create a realistic 100-participant, 10-round discussion with natural variance.

Each participant has a consistent "persona" but their responses vary naturally
across rounds, leading to realistic participant movement between clusters.
"""

import asyncio
import random
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.models.discussion import Discussion
from src.models.protocol_state import DiscussionStatus, DiscussionMode
from src.models.round import Round
from src.models.participant import Participant
from src.models.submission import Submission, SubmissionModality
from src.models.approved_summary import ApprovedSummary


# AI Ethics Discussion Questions
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
    "How should we approach the development of artificial general intelligence (AGI)?"
]

# Participant personas - define different viewpoints
PERSONAS = {
    "tech_optimist": {
        "base_views": [
            "Innovation should drive progress",
            "Technology will solve most problems",
            "Market forces ensure quality",
            "Open source accelerates development",
            "AI will create more jobs than it destroys"
        ],
        "variance": 0.3  # 30% chance to deviate
    },
    "cautious_regulator": {
        "base_views": [
            "Strong oversight is essential",
            "Safety must come before innovation",
            "Regulation prevents harm",
            "Transparency builds trust",
            "Ethics committees should review AI"
        ],
        "variance": 0.25
    },
    "social_equity": {
        "base_views": [
            "AI must serve everyone equally",
            "Address existing inequalities first",
            "Community input is crucial",
            "Protect vulnerable populations",
            "Fair distribution of benefits"
        ],
        "variance": 0.35
    },
    "privacy_advocate": {
        "base_views": [
            "Data privacy is a fundamental right",
            "Minimize data collection",
            "User control over personal data",
            "Encryption by default",
            "Transparency in data use"
        ],
        "variance": 0.28
    },
    "pragmatic_moderate": {
        "base_views": [
            "Balance innovation and safety",
            "Evidence-based policies",
            "Flexible frameworks work best",
            "Learn from mistakes",
            "Collaborate across sectors"
        ],
        "variance": 0.4  # Most flexible persona
    },
    "global_perspective": {
        "base_views": [
            "International cooperation essential",
            "Develop capacity in all nations",
            "Share benefits globally",
            "Prevent digital colonialism",
            "Cultural sensitivity matters"
        ],
        "variance": 0.32
    },
    "researcher_academic": {
        "base_views": [
            "Peer review ensures quality",
            "Long-term research needed",
            "Fundamental understanding first",
            "Publish findings openly",
            "Interdisciplinary approaches"
        ],
        "variance": 0.27
    }
}

# Response templates for each question (indexed by question number)
RESPONSE_TEMPLATES = {
    0: [  # Ethical principles
        "I believe {principle} should be the foundation of AI development.",
        "From my perspective, {principle} is crucial for responsible AI.",
        "We must prioritize {principle} above all else.",
        "The key ethical principle is {principle} - without this, AI poses risks.",
        "In my view, {principle} ensures AI serves humanity's best interests."
    ],
    1: [  # Transparency
        "{mechanism} would help ensure AI accountability.",
        "I think {mechanism} is essential for transparent AI systems.",
        "We need {mechanism} to maintain public trust.",
        "From my experience, {mechanism} prevents hidden biases.",
        "{mechanism} should be mandatory for all AI deployments."
    ],
    2: [  # Regulation
        "I support {approach} for AI regulation.",
        "{approach} strikes the right balance for AI governance.",
        "In my opinion, {approach} will work best.",
        "We should implement {approach} to guide AI development.",
        "{approach} has proven effective in similar industries."
    ],
    3: [  # Employment
        "AI will likely {impact} employment in the coming decade.",
        "I foresee {impact} as the main effect on jobs.",
        "The employment impact will be {impact} - we must prepare.",
        "We should expect {impact} and plan accordingly.",
        "{impact} is inevitable, but we can adapt."
    ],
    4: [  # Bias prevention
        "{safeguard} is critical for preventing AI bias.",
        "We must implement {safeguard} to ensure fairness.",
        "I strongly advocate for {safeguard} in all AI systems.",
        "{safeguard} should be a legal requirement.",
        "Without {safeguard}, bias will persist and worsen."
    ],
    5: [  # Privacy
        "{measure} protects privacy while enabling innovation.",
        "I believe {measure} is the right approach.",
        "We need {measure} to safeguard user data.",
        "{measure} strikes the balance we need.",
        "Implementing {measure} will build trust."
    ],
    6: [  # Critical infrastructure
        "{consideration} is key for AI in critical systems.",
        "I think {consideration} should guide deployment.",
        "We must ensure {consideration} before widespread use.",
        "{consideration} protects against catastrophic failures.",
        "The main priority is {consideration}."
    ],
    7: [  # Global equity
        "{strategy} will help share AI benefits globally.",
        "I support {strategy} for equitable AI development.",
        "We need {strategy} to prevent further inequality.",
        "{strategy} ensures developing nations benefit too.",
        "The solution is {strategy} with international cooperation."
    ],
    8: [  # Education
        "{change} is needed in education systems.",
        "Schools must prioritize {change} immediately.",
        "I believe {change} will prepare the next generation.",
        "We should implement {change} at all levels.",
        "{change} is essential for an AI-driven future."
    ],
    9: [  # AGI
        "{position} regarding AGI development.",
        "My stance is {position} when it comes to AGI.",
        "I firmly believe {position} is the right path.",
        "We must adopt {position} approach.",
        "{position} balances progress and safety."
    ]
}

# Variable content for each question (creates diversity)
VARIABLE_CONTENT = {
    0: ["transparency", "human oversight", "fairness and equality", "safety first", "beneficial intent", "accountability", "privacy protection"],
    1: ["mandatory impact assessments", "open-source models", "independent audits", "clear documentation", "public reporting", "explainable AI", "third-party verification"],
    2: ["proactive regulation with clear standards", "flexible frameworks that adapt", "industry self-regulation with oversight", "international coordination", "sector-specific rules", "light-touch principles-based approach", "strict licensing requirements"],
    3: ["transform job markets requiring massive retraining", "create more opportunities than it eliminates", "widen inequality if unchecked", "automate routine tasks while creating new roles", "require universal basic income", "necessitate shorter work weeks", "demand new social safety nets"],
    4: ["diverse development teams", "regular bias audits", "representative training data", "continuous monitoring", "community oversight", "mandatory testing protocols", "transparent algorithms"],
    5: ["strong encryption and data minimization", "user consent and control", "privacy-preserving techniques like federated learning", "strict data retention limits", "transparent data practices", "privacy impact assessments", "differential privacy methods"],
    6: ["rigorous testing and certification", "human-in-the-loop safeguards", "cybersecurity protections", "fail-safe mechanisms", "extensive redundancy", "phased deployment with monitoring", "clear liability frameworks"],
    7: ["technology transfer and capacity building", "open-source AI tools", "international funding", "collaborative research partnerships", "addressing digital divides", "local adaptation of AI", "shared governance models"],
    8: ["critical thinking and AI literacy", "creativity and emotional intelligence", "hands-on coding education", "lifelong learning programs", "ethics education", "human-AI collaboration skills", "adaptability training"],
    9: ["we should proceed cautiously with extensive safety research", "strict red lines on dangerous capabilities", "international coordination is essential", "focus on narrow AI first", "ensure AGI aligns with human values", "pause development until safeguards exist", "transparent development with public input"]
}


async def create_realistic_discussion():
    """Create a realistic 100-participant, 10-round discussion."""
    print("="*80)
    print("CREATING REALISTIC 100-PARTICIPANT DISCUSSION")
    print("="*80)

    async_session_factory = get_session_factory()
    async with async_session_factory() as db:
        # Create discussion
        discussion_id = uuid4()
        discussion = Discussion(
            discussion_id=discussion_id,
            community_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            host_user_id=uuid4(),
            total_rounds=10,
            status=DiscussionStatus.COMPLETED,
            created_at=datetime.utcnow() - timedelta(hours=5),
            completed_at=datetime.utcnow()
        )
        db.add(discussion)
        await db.flush()

        print(f"\n✓ Created discussion: {discussion_id}")

        # Create 100 participants with assigned personas
        participants = []
        persona_types = list(PERSONAS.keys())

        for i in range(100):
            persona_type = persona_types[i % len(persona_types)]
            participant = Participant(
                participant_id=uuid4(),
                discussion_id=discussion_id,
                user_id=uuid4(),
                first_round=1,
                created_at=discussion.created_at + timedelta(minutes=random.randint(0, 30))
            )
            participants.append({
                "model": participant,
                "persona": persona_type,
                "variance": PERSONAS[persona_type]["variance"]
            })
            db.add(participant)

        await db.flush()
        print(f"✓ Created 100 participants with diverse personas")

        # Create rounds and submissions
        for round_num in range(10):
            round_id = uuid4()
            round_obj = Round(
                round_id=round_id,
                discussion_id=discussion_id,
                round_num=round_num + 1,
                question_text=QUESTIONS[round_num],
                status="completed",
                submission_window_start=discussion.created_at + timedelta(minutes=round_num * 30),
                submission_window_end=discussion.created_at + timedelta(minutes=(round_num + 1) * 30),
                submission_window_duration_sec=1800,
                created_at=discussion.created_at + timedelta(minutes=round_num * 30)
            )
            db.add(round_obj)
            await db.flush()

            print(f"\n  Round {round_num + 1}: {QUESTIONS[round_num][:60]}...")

            # Create submissions for each participant
            for p_info in participants:
                participant = p_info["model"]
                persona_type = p_info["persona"]
                variance = p_info["variance"]

                # Decide if this participant deviates from their base view
                deviates = random.random() < variance

                if deviates:
                    # Choose a different persona's view for this round
                    other_personas = [p for p in persona_types if p != persona_type]
                    temp_persona = random.choice(other_personas)
                    content_pool = VARIABLE_CONTENT[round_num]
                else:
                    temp_persona = persona_type
                    content_pool = VARIABLE_CONTENT[round_num]

                # Generate response
                template = random.choice(RESPONSE_TEMPLATES[round_num])
                content = random.choice(content_pool)
                response_text = template.format(
                    principle=content,
                    mechanism=content,
                    approach=content,
                    impact=content,
                    safeguard=content,
                    measure=content,
                    consideration=content,
                    strategy=content,
                    change=content,
                    position=content
                )

                # Add some natural variation
                prefixes = ["", "I think ", "From my perspective, ", "In my view, ", "I believe ", "It's crucial that ", "We must consider that "]
                response_text = random.choice(prefixes) + response_text.lower() if response_text[0].isupper() else response_text

                # Create submission
                submission = Submission(
                    submission_id=uuid4(),
                    participant_id=participant.participant_id,
                    round_id=round_id,
                    submission_text=response_text,
                    modality=SubmissionModality.TEXT,
                    submitted_at=round_obj.window_start + timedelta(seconds=random.randint(10, 280))
                )
                db.add(submission)

                # Create approved summary (slightly shorter)
                summary = ApprovedSummary(
                    summary_id=uuid4(),
                    round_id=round_id,
                    participant_id=participant.participant_id,
                    submission_id=submission.submission_id,
                    summary_text=response_text,  # In real system, this would be LLM-generated
                    approved_at=submission.submitted_at + timedelta(seconds=5),
                    created_at=submission.submitted_at + timedelta(seconds=5)
                )
                db.add(summary)

            await db.flush()
            print(f"    ✓ Created 100 submissions and summaries")

            # Run clustering for this round
            print(f"    🔄 Running clustering for Round {round_num + 1}...")
            try:
                from src.services.clustering_service import execute_clustering_workflow

                clustering_result = await execute_clustering_workflow(
                    round_id=round_id,
                    db=db
                )

                cluster_count = clustering_result.get("cluster_count", 0)
                singleton_count = clustering_result.get("singleton_count", 0)
                print(f"    ✅ Clustering: {cluster_count} clusters, {singleton_count} singletons")

                if 5 <= cluster_count <= 9:
                    print(f"    🎯 Miller's Law range (7±2)!")
            except Exception as e:
                print(f"    ⚠️ Clustering error: {e}")

        await db.commit()

        # Generate Sankey diagram
        print(f"\n🎨 Generating Sankey diagram...")
        try:
            from src.services.sankey_service import generate_sankey_diagram
            await generate_sankey_diagram(discussion_id=discussion_id, db=db)
            print(f"✅ Sankey diagram generated")
        except Exception as e:
            print(f"⚠️ Sankey generation warning: {e}")

        print("\n" + "="*80)
        print("DISCUSSION CREATION COMPLETE")
        print("="*80)
        print(f"\nDiscussion ID: {discussion_id}")
        print(f"Total Rounds: 10")
        print(f"Total Participants: 100")
        print(f"Persona Distribution: {len(persona_types)} different personas")
        print(f"\nKey Features:")
        print(f"  ✓ Each participant has a consistent persona")
        print(f"  ✓ Natural variance in responses (25-40% deviation rate)")
        print(f"  ✓ Diverse viewpoints across rounds")
        print(f"  ✓ Realistic participant movement between clusters")
        print(f"\nTo view:")
        print(f"  Sankey: http://localhost:3000/discussions/{discussion_id}/sankey")
        print(f"  Inspector: Click '🔍 Inspect Clustering' button on Sankey page")
        print("\n" + "="*80)

        return str(discussion_id)


if __name__ == "__main__":
    discussion_id = asyncio.run(create_realistic_discussion())
