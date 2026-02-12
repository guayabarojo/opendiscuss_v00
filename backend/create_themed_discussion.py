"""
Theme-Based Discussion Generator - Realistic Clustering (7±2 clusters)

Simulates real human participation with natural semantic similarity:
- 7 major themes reflecting real community priorities
- Participants assigned to 1-2 themes (consistent viewpoints)
- Responses use theme vocabulary with natural variation
- Expected result: 7±2 clusters per round (Miller's Law)
"""
import asyncio
import random
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy import select

from src.database import get_session_factory
from src.models.discussion import Discussion
from src.models.protocol_state import DiscussionMode, DiscussionStatus
from src.models.participant import Participant
from src.models.round import Round
from src.models.submission import Submission
from src.models.approved_summary import ApprovedSummary
from src.services.clustering_service import execute_clustering_workflow
from src.services.sankey_builder import SankeyBuilder


# 7 Major Themes - Community Priorities (Miller's Law optimal)
THEMES = {
    "cost_efficiency": {
        "name": "Cost Reduction & Financial Efficiency",
        "core_concepts": [
            "reduce operational costs",
            "cut unnecessary expenses",
            "optimize budget allocation",
            "improve financial efficiency",
            "streamline spending",
            "eliminate wasteful practices",
            "maximize cost savings",
            "lower overhead expenses"
        ],
        "weight": 0.18  # ~18 participants
    },
    "transparency": {
        "name": "Transparency & Open Communication",
        "core_concepts": [
            "increase transparency in decisions",
            "improve communication channels",
            "share information openly",
            "provide clear updates",
            "build trust through openness",
            "enable honest dialogue",
            "ensure everyone has access to info",
            "create accountability systems"
        ],
        "weight": 0.16  # ~16 participants
    },
    "innovation": {
        "name": "Innovation & Technology Adoption",
        "core_concepts": [
            "embrace new technologies",
            "modernize our systems",
            "invest in AI and automation",
            "drive digital transformation",
            "adopt cutting-edge solutions",
            "leverage tech for growth",
            "innovate processes",
            "stay ahead of competition"
        ],
        "weight": 0.15  # ~15 participants
    },
    "employee_wellbeing": {
        "name": "Employee Wellbeing & Work Culture",
        "core_concepts": [
            "prioritize employee mental health",
            "support work-life balance",
            "build positive culture",
            "invest in team satisfaction",
            "create supportive environment",
            "focus on morale",
            "reduce burnout",
            "value employee wellness"
        ],
        "weight": 0.14  # ~14 participants
    },
    "sustainability": {
        "name": "Environmental Sustainability",
        "core_concepts": [
            "reduce carbon footprint",
            "adopt eco-friendly practices",
            "invest in renewable energy",
            "prioritize environmental impact",
            "make green choices",
            "promote sustainability",
            "protect the environment",
            "achieve net-zero emissions"
        ],
        "weight": 0.13  # ~13 participants
    },
    "customer_focus": {
        "name": "Customer Experience & Quality",
        "core_concepts": [
            "improve customer satisfaction",
            "enhance service quality",
            "listen to customer feedback",
            "build user-centric products",
            "deliver excellent experience",
            "prioritize customer needs",
            "increase customer loyalty",
            "exceed user expectations"
        ],
        "weight": 0.12  # ~12 participants
    },
    "growth_expansion": {
        "name": "Growth & Market Expansion",
        "core_concepts": [
            "pursue sustainable growth",
            "expand into new markets",
            "scale operations effectively",
            "increase market share",
            "drive business development",
            "capture new opportunities",
            "accelerate growth trajectory",
            "build competitive advantage"
        ],
        "weight": 0.12  # ~12 participants
    }
}


def generate_themed_response(
    theme_key: str,
    question: str,
    round_num: int,
    use_secondary: bool = False
) -> str:
    """
    Generate response addressing the question using theme vocabulary.

    Creates semantic similarity within theme while maintaining natural variation.
    """
    theme = THEMES[theme_key]
    concept = random.choice(theme["core_concepts"])

    # Question-specific framing
    question_lower = question.lower()

    if "priority" in question_lower or "important" in question_lower:
        frames = [
            f"Our top priority must be to {concept}.",
            f"The most important thing is to {concept}.",
            f"We should prioritize efforts to {concept}.",
            f"Nothing is more critical than to {concept}."
        ]
    elif "challenge" in question_lower or "problem" in question_lower:
        frames = [
            f"The biggest challenge is our need to {concept}.",
            f"Our main problem is that we must {concept}.",
            f"We're struggling because we need to {concept}.",
            f"The key issue is our failure to {concept}."
        ]
    elif "solution" in question_lower or "address" in question_lower:
        frames = [
            f"The solution is clear: we must {concept}.",
            f"To solve this, we need to {concept}.",
            f"We can address this by focusing on efforts to {concept}.",
            f"The answer is to {concept}."
        ]
    elif "measure" in question_lower or "success" in question_lower:
        frames = [
            f"Success means we effectively {concept}.",
            f"We'll measure progress by how well we {concept}.",
            f"The metric is whether we can {concept}.",
            f"We'll know we succeeded when we {concept}."
        ]
    elif "resource" in question_lower or "need" in question_lower:
        frames = [
            f"We need resources dedicated to helping us {concept}.",
            f"The key resource requirement is support to {concept}.",
            f"What we need most is capacity to {concept}.",
            f"Resources should enable us to {concept}."
        ]
    elif "obstacle" in question_lower or "overcome" in question_lower:
        frames = [
            f"The main obstacle is our inability to {concept}.",
            f"We can overcome challenges by committing to {concept}.",
            f"The barrier preventing us is our failure to {concept}.",
            f"To overcome this, we must {concept}."
        ]
    elif "communicate" in question_lower:
        frames = [
            f"We should communicate our commitment to {concept}.",
            f"Our message must emphasize how we {concept}.",
            f"Communication should focus on our efforts to {concept}.",
            f"We need to clearly explain how we {concept}."
        ]
    elif "timeline" in question_lower or "when" in question_lower:
        frames = [
            f"We should begin immediately to {concept}.",
            f"The timeline depends on our ability to {concept}.",
            f"Starting now, we can {concept}.",
            f"Within months, we must {concept}."
        ]
    elif "accountability" in question_lower or "track" in question_lower:
        frames = [
            f"Accountability means ensuring we {concept}.",
            f"We'll track our progress on efforts to {concept}.",
            f"Monitoring should focus on whether we {concept}.",
            f"Leadership must be accountable for helping us {concept}."
        ]
    elif "learn" in question_lower or "next" in question_lower:
        frames = [
            f"We learned the importance of efforts to {concept}.",
            f"Next, we should double down on plans to {concept}.",
            f"The key lesson is that we must {concept}.",
            f"Moving forward, let's commit to {concept}."
        ]
    else:
        frames = [
            f"We must {concept}.",
            f"It's essential that we {concept}.",
            f"The focus should be to {concept}.",
            f"Our goal is to {concept}."
        ]

    base_response = random.choice(frames)

    # Add reinforcing statements
    reinforcements = [
        "This is absolutely critical for our success.",
        "I strongly believe this is the right direction.",
        "This will have the greatest positive impact.",
        "We can't afford to delay action on this.",
        "This addresses our core challenge.",
        "The evidence strongly supports this approach.",
        "This aligns with our fundamental values.",
        "I've seen this work effectively elsewhere."
    ]

    response = f"{base_response} {random.choice(reinforcements)}"

    # In later rounds, add continuity
    if round_num > 4:
        connectors = [
            "Building on previous discussions, ",
            "As we've discussed, ",
            "Continuing from earlier rounds, ",
            "Following up on prior points, ",
            "To expand on what we've said, "
        ]
        response = f"{random.choice(connectors).lower()}{response}"

    return response


async def create_themed_discussion():
    """Create 100-participant discussion with theme-based realistic clustering"""

    print("=" * 80)
    print("THEME-BASED DISCUSSION GENERATOR")
    print("Expected Result: 7±2 Natural Clusters Per Round")
    print("=" * 80)

    async_session_factory = get_session_factory()
    async with async_session_factory() as db:
        try:
            # Create discussion
            discussion_id = uuid4()
            discussion = Discussion(
                discussion_id=discussion_id,
                community_id=uuid4(),
                mode=DiscussionMode.HOST_DEFINED,
                host_user_id=uuid4(),
                total_rounds=10,
                status=DiscussionStatus.COMPLETED,
                created_at=datetime.utcnow() - timedelta(hours=12),
                completed_at=datetime.utcnow()
            )
            db.add(discussion)
            await db.flush()

            print(f"\n✅ Discussion created: {discussion_id}")

            # Assign participants to themes
            participants = []
            theme_keys = list(THEMES.keys())

            # Calculate participant distribution based on theme weights
            theme_assignments = []
            for theme_key in theme_keys:
                count = int(100 * THEMES[theme_key]["weight"])
                theme_assignments.extend([theme_key] * count)

            # Fill remaining to reach 100
            while len(theme_assignments) < 100:
                theme_assignments.append(random.choice(theme_keys))

            # Shuffle to randomize order
            random.shuffle(theme_assignments)

            for i in range(100):
                participant_id = uuid4()
                participant = Participant(
                    discussion_id=discussion_id,
                    user_id=uuid4(),
                    first_round=1,
                    participant_id=participant_id,
                    created_at=datetime.utcnow()
                )
                db.add(participant)

                # Primary theme
                primary_theme = theme_assignments[i]

                # 40% of participants have secondary theme (realistic - nuanced views)
                secondary_theme = None
                if random.random() < 0.4:
                    other_themes = [t for t in theme_keys if t != primary_theme]
                    secondary_theme = random.choice(other_themes)

                participants.append({
                    "id": participant_id,
                    "primary": primary_theme,
                    "secondary": secondary_theme
                })

            await db.flush()
            print(f"✅ Created 100 participants")
            print(f"   Theme distribution: {len(theme_keys)} themes with realistic weights")

            # Display theme distribution
            theme_counts = {}
            for p in participants:
                theme_counts[p["primary"]] = theme_counts.get(p["primary"], 0) + 1

            print(f"\n📊 Participant Theme Distribution:")
            for theme_key in sorted(theme_counts.keys(), key=lambda k: theme_counts[k], reverse=True):
                print(f"   {THEMES[theme_key]['name']}: {theme_counts[theme_key]} participants")

            # Create rounds with realistic questions
            questions = [
                "What should be our organization's top priority for the next year?",
                "What is the biggest challenge preventing us from achieving our goals?",
                "What specific actions should we take to address this challenge?",
                "How can we measure success in implementing these changes?",
                "What resources or support do we need to succeed?",
                "What potential obstacles might we face, and how can we overcome them?",
                "How should we communicate these changes to stakeholders?",
                "What timeline is realistic for implementing these initiatives?",
                "How can we ensure accountability and track progress?",
                "What have we learned, and what should be our next steps?"
            ]

            round_objs = []
            for round_num in range(1, 11):
                round_id = uuid4()
                round_obj = Round(
                    round_id=round_id,
                    discussion_id=discussion_id,
                    round_num=round_num,
                    question_text=questions[round_num - 1],
                    status="completed",
                    submission_window_start=datetime.utcnow() - timedelta(hours=11-round_num),
                    submission_window_end=datetime.utcnow() - timedelta(hours=10-round_num),
                    submission_window_duration_sec=3600,
                    created_at=datetime.utcnow()
                )
                db.add(round_obj)
                round_objs.append(round_obj)

            await db.flush()
            print(f"✅ Created 10 rounds with realistic questions\n")

            # Create submissions for each round
            for round_obj in round_objs:
                print(f"Round {round_obj.round_num}: {round_obj.question_text[:60]}...")

                for p in participants:
                    # 75% use primary theme, 20% use secondary (if exists), 5% unique
                    roll = random.random()
                    if roll < 0.75:
                        theme = p["primary"]
                        use_secondary = False
                    elif roll < 0.95 and p["secondary"]:
                        theme = p["secondary"]
                        use_secondary = True
                    else:
                        # Small % are truly unique (realistic outliers)
                        theme = random.choice(theme_keys)
                        use_secondary = False

                    # Generate themed response
                    response_text = generate_themed_response(
                        theme,
                        round_obj.question_text,
                        round_obj.round_num,
                        use_secondary
                    )

                    # Create submission
                    submission_id = uuid4()
                    submission = Submission(
                        submission_id=submission_id,
                        participant_id=p["id"],
                        round_id=round_obj.round_id,
                        submission_text=response_text,
                        submission_type="text",
                        submitted_at=datetime.utcnow(),
                        created_at=datetime.utcnow()
                    )
                    db.add(submission)

                    # Create approved summary
                    summary_id = uuid4()
                    approved_summary = ApprovedSummary(
                        summary_id=summary_id,
                        participant_id=p["id"],
                        round_id=round_obj.round_id,
                        submission_id=submission_id,
                        summary_text=response_text,  # In production, LLM-generated
                        approved_at=datetime.utcnow(),
                        cluster_id=None,  # Set by clustering
                        created_at=datetime.utcnow()
                    )
                    db.add(approved_summary)

                await db.flush()
                print(f"  ✅ Created 100 submissions and summaries")

                # Run clustering
                print(f"  🔄 Clustering...")
                try:
                    clustering_result = await execute_clustering_workflow(
                        round_id=round_obj.round_id,
                        db=db
                    )

                    cluster_count = clustering_result.get("cluster_count", 0)
                    singleton_count = clustering_result.get("singleton_count", 0)

                    if 5 <= cluster_count <= 9:
                        print(f"  🎯 {cluster_count} clusters (Miller's Law range!), {singleton_count} singletons")
                    elif cluster_count > 0:
                        print(f"  ✅ {cluster_count} clusters, {singleton_count} singletons")
                    else:
                        print(f"  ⚠️  {cluster_count} clusters (expected 7±2)")

                except Exception as e:
                    print(f"  ❌ Clustering error: {e}")
                    import traceback
                    traceback.print_exc()

            await db.commit()

            # Generate Sankey
            print(f"\n🎨 Generating Sankey diagram...")
            try:
                builder = SankeyBuilder(db)
                round_ids = [r.round_id for r in round_objs]
                sankey_graph = await builder.build_sankey_graph(
                    discussion_id=discussion_id,
                    rounds=round_ids,
                    include_metadata=True
                )
                print(f"✅ Sankey diagram generated with {len(sankey_graph.columns)} rounds")
            except Exception as e:
                print(f"⚠️  Sankey warning: {e}")

            print("\n" + "=" * 80)
            print("✅ THEME-BASED DISCUSSION COMPLETE")
            print("=" * 80)
            print(f"\nDiscussion ID: {discussion_id}")
            print(f"Participants: 100")
            print(f"Rounds: 10")
            print(f"Themes: 7 (aligned with Miller's Law)")
            print(f"\n🔗 View Results:")
            print(f"   Sankey: http://localhost:3000/discussions/{discussion_id}/sankey")
            print(f"   Inspector: Click '🔍 Inspect Clustering' button on Sankey page")
            print(f"\n📊 Expected Clustering:")
            print(f"   • 5-9 natural clusters per round (7±2 per Miller's Law)")
            print(f"   • Clear semantic groupings matching themes")
            print(f"   • Realistic participant movement across rounds")
            print(f"   • Few singletons (only truly unique perspectives)")
            print("\n" + "=" * 80)

            return discussion_id

        except Exception as e:
            await db.rollback()
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(create_themed_discussion())
