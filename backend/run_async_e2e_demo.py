"""
Complete E2E Async Discussion Demo - Full Backend Workflow

This script runs a complete async discussion through the full backend pipeline:
1. Create async discussion (with 2 rounds for speed)
2. Start discussion (opens Round 1)
3. Submit participant responses
4. Trigger summarization (with mock LLM)
5. Auto-approve summaries
6. Trigger clustering (HDBSCAN + SBERT)
7. Advance to next round
8. Repeat for round 2
9. Complete discussion
10. Generate Sankey diagram

Topic: AI in Education 2026
Participants: 3 (Alice, Bob, Charlie)
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_engine, get_session_factory
from src.models.discussion import Discussion
from src.models.round import Round
from src.models.participant import Participant
from src.models.submission import Submission, SubmissionModality
from src.models.protocol_state import DiscussionTimingMode, DiscussionStatus, RoundStatus
from src.summarization.models.summary import Summary, SummaryStatus
from src.models.approved_summary import ApprovedSummary
from src.models.thought_space import ThoughtSpace

# Test data
COMMUNITY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
HOST_USER_ID = uuid.uuid4()

PARTICIPANTS = [
    {"user_id": uuid.uuid4(), "name": "Alice"},
    {"user_id": uuid.uuid4(), "name": "Bob"},
    {"user_id": uuid.uuid4(), "name": "Charlie"},
]

ROUND_RESPONSES = {
    1: {  # Benefits of AI in Education
        "Alice": "AI tutoring systems provide personalized learning paths that adapt to each student's pace and learning style. This helps struggling students catch up while challenging advanced learners appropriately.",
        "Bob": "Automated grading saves teachers enormous time on assignments and tests, allowing them to focus more on mentorship and creative lesson planning. AI can now grade essays with surprising accuracy.",
        "Charlie": "AI translation tools break down language barriers in diverse classrooms. Students can learn complex subjects in their native language while gradually developing English skills.",
    },
    2: {  # Concerns about AI in Education
        "Alice": "Over-reliance on AI could reduce students' critical thinking skills. They need to struggle with problems independently to develop deep understanding, not just get instant AI-generated answers.",
        "Bob": "Data privacy is my biggest worry with educational AI systems. These tools collect sensitive information about children's learning patterns, mistakes, and even emotional states.",
        "Charlie": "AI could widen educational inequality if only wealthy schools can afford the best systems. We must ensure equitable access to AI educational tools across all communities.",
    },
}


async def create_discussion(session: AsyncSession) -> Discussion:
    """Create async discussion with 2 rounds."""
    print("\n" + "="*80)
    print("STEP 1: Creating Async Discussion")
    print("="*80)

    discussion = Discussion(
        discussion_id=uuid.uuid4(),
        community_id=COMMUNITY_ID,
        host_user_id=HOST_USER_ID,
        mode="HOST_DEFINED",
        total_rounds=2,  # 2 rounds for faster demo
        timing_mode=DiscussionTimingMode.ASYNCHRONOUS,
        round_duration_hours=24,
        min_submissions_for_advance=3,
        auto_advance_enabled=False,
        status=DiscussionStatus.CREATED,
        current_round_num=0,
    )

    session.add(discussion)
    await session.flush()

    # Create rounds
    questions = [
        "What are the most promising benefits of AI in education for 2026?",
        "What concerns should we address as AI becomes more prevalent in classrooms?",
    ]

    for i, question in enumerate(questions, 1):
        round_entity = Round(
            round_id=uuid.uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=i,
            question_text=question,
            status=RoundStatus.PENDING,
            submission_window_duration_sec=300,  # 5 minutes (constraint requires 180-360)
        )
        session.add(round_entity)

    await session.commit()
    await session.refresh(discussion)

    print(f"✅ Created discussion: {discussion.discussion_id}")
    print(f"   Mode: {discussion.timing_mode}")
    print(f"   Rounds: {discussion.total_rounds}")
    print(f"   Topic: AI in Education 2026")

    return discussion


async def start_discussion(session: AsyncSession, discussion: Discussion) -> Round:
    """Start discussion and open Round 1."""
    print("\n" + "="*80)
    print("STEP 2: Starting Discussion (Opening Round 1)")
    print("="*80)

    # Update discussion status
    await session.execute(
        update(Discussion)
        .where(Discussion.discussion_id == discussion.discussion_id)
        .values(
            status=DiscussionStatus.ACTIVE,
            current_round_num=1,
            started_at=datetime.utcnow(),
        )
    )

    # Get Round 1
    result = await session.execute(
        select(Round).where(
            Round.discussion_id == discussion.discussion_id,
            Round.round_num == 1
        )
    )
    round1 = result.scalar_one()

    # Open submission window
    now = datetime.utcnow()
    await session.execute(
        update(Round)
        .where(Round.round_id == round1.round_id)
        .values(
            status=RoundStatus.SUBMISSION_OPEN,
            submission_window_start=now,
            submission_window_end=now + timedelta(hours=24),
        )
    )

    # Create participants
    for p_data in PARTICIPANTS:
        participant = Participant(
            participant_id=uuid.uuid4(),
            discussion_id=discussion.discussion_id,
            user_id=p_data["user_id"],
            first_round=1,
        )
        session.add(participant)
        p_data["participant_id"] = participant.participant_id

    await session.commit()
    await session.refresh(round1)

    print(f"✅ Discussion started")
    print(f"   Round 1: {round1.question_text}")
    print(f"   Status: {round1.status}")
    print(f"   Participants: {len(PARTICIPANTS)}")

    return round1


async def submit_responses(
    session: AsyncSession,
    round_entity: Round,
    round_num: int
) -> list[Submission]:
    """Submit participant responses."""
    print("\n" + "="*80)
    print(f"STEP 3: Submitting Responses (Round {round_num})")
    print("="*80)

    submissions = []
    for p_data in PARTICIPANTS:
        text = ROUND_RESPONSES[round_num][p_data["name"]]

        submission = Submission(
            submission_id=uuid.uuid4(),
            participant_id=p_data["participant_id"],
            round_id=round_entity.round_id,
            submission_text=text,
            modality=SubmissionModality.TEXT,
            submitted_at=datetime.utcnow(),
            summary_status="pending",
        )
        session.add(submission)
        submissions.append(submission)

        print(f"✅ {p_data['name']}: \"{text[:60]}...\"")

    await session.commit()
    print(f"\n✅ {len(submissions)} submissions received")

    return submissions


async def generate_summaries(
    session: AsyncSession,
    submissions: list[Submission]
) -> list[Summary]:
    """Generate summaries using mock LLM."""
    print("\n" + "="*80)
    print("STEP 4: Generating Summaries (Mock LLM)")
    print("="*80)

    from src.llm.openai_client import generate_summary_llm

    summaries = []
    for submission in submissions:
        # Generate mock summary
        prompt = f"Summarize this in 2 sentences:\n\nText to summarize: {submission.submission_text}"
        summary_text = await generate_summary_llm(prompt)

        # Create summary record
        # Get participant_id and round_id from submission
        result = await session.execute(
            select(Submission).where(Submission.submission_id == submission.submission_id)
        )
        sub = result.scalar_one()

        summary = Summary(
            summary_id=uuid.uuid4(),
            submission_id=submission.submission_id,
            participant_id=sub.participant_id,
            round_id=sub.round_id,
            summary_text=summary_text,
            status=SummaryStatus.APPROVED,  # Auto-approve for demo
            approved_at=datetime.utcnow(),
        )
        session.add(summary)
        summaries.append(summary)

        print(f"✅ Summary for {submission.submission_id}: \"{summary_text[:50]}...\"")

    await session.commit()
    print(f"\n✅ {len(summaries)} summaries generated and auto-approved")

    return summaries


async def create_approved_summaries(
    session: AsyncSession,
    summaries: list[Summary],
    submissions: list[Submission]
) -> list[ApprovedSummary]:
    """Create approved_summary records."""
    print("\n" + "="*80)
    print("STEP 5: Creating Approved Summary Records")
    print("="*80)

    approved_summaries = []
    for summary in summaries:
        # Find corresponding submission
        submission = next(s for s in submissions if s.submission_id == summary.submission_id)

        approved_summary = ApprovedSummary(
            summary_id=summary.summary_id,
            participant_id=submission.participant_id,
            round_id=submission.round_id,
            submission_id=submission.submission_id,
            summary_text=summary.summary_text,
            approved_at=datetime.utcnow(),
        )
        session.add(approved_summary)
        approved_summaries.append(approved_summary)

    await session.commit()
    print(f"✅ {len(approved_summaries)} approved summaries created")

    return approved_summaries


async def run_clustering(
    session: AsyncSession,
    round_entity: Round,
    approved_summaries: list[ApprovedSummary]
) -> list[ThoughtSpace]:
    """Run real HDBSCAN clustering with SBERT embeddings."""
    print("\n" + "="*80)
    print("STEP 6: Running HDBSCAN Clustering (with SBERT embeddings)")
    print("="*80)

    from src.services.embedding_service import generate_embeddings
    from src.services.clustering_service import cluster_embeddings, calculate_cluster_stats
    import numpy as np
    from scipy.spatial.distance import cosine

    # Get summary texts
    summary_texts = [s.summary_text for s in approved_summaries]
    summary_ids = [s.summary_id for s in approved_summaries]

    print(f"   Generating embeddings for {len(summary_texts)} summaries...")

    # Generate SBERT embeddings
    embeddings = await generate_embeddings(summary_texts, normalize=True)
    print(f"   ✅ Generated {embeddings.shape[0]} embeddings (dimension: {embeddings.shape[1]})")

    # Run HDBSCAN clustering
    print(f"   Running HDBSCAN clustering...")
    cluster_assignments = await cluster_embeddings(
        embeddings=embeddings,
        summary_ids=summary_ids,
        min_cluster_size=2
    )

    # Count clusters
    unique_labels = set(cluster_assignments.values())
    cluster_count = len([l for l in unique_labels if l >= 0])
    noise_count = sum(1 for l in cluster_assignments.values() if l == -1)

    print(f"   ✅ HDBSCAN complete: {cluster_count} clusters, {noise_count} outliers")

    # Calculate cluster statistics
    print(f"   Calculating cluster statistics...")
    cluster_stats = await calculate_cluster_stats(cluster_assignments, session)
    print(f"   ✅ Statistics calculated for {len(cluster_stats)} clusters")

    # Calculate centroids and select medoids
    print(f"   Calculating centroids and selecting medoids...")
    centroids = {}
    label_summaries = {}

    for cluster_label in cluster_stats.keys():
        # Get all embeddings for this cluster
        cluster_summary_ids = [
            sid for sid, label in cluster_assignments.items()
            if label == cluster_label
        ]
        cluster_indices = [summary_ids.index(sid) for sid in cluster_summary_ids]
        cluster_embeddings = embeddings[cluster_indices]

        # Centroid is mean of all embeddings
        centroid = np.mean(cluster_embeddings, axis=0)
        centroids[cluster_label] = centroid

        # Select medoid: summary closest to centroid
        min_distance = float('inf')
        medoid_id = None
        for i, sid in enumerate(cluster_summary_ids):
            idx = summary_ids.index(sid)
            distance = cosine(embeddings[idx], centroid)
            if distance < min_distance:
                min_distance = distance
                medoid_id = sid

        label_summaries[cluster_label] = medoid_id

    print(f"   ✅ Calculated {len(centroids)} cluster centroids")

    # Persist thought spaces to database
    print(f"   Persisting thought spaces to database...")
    thought_spaces = []

    for cluster_label, (member_count, member_pct) in cluster_stats.items():
        cluster_id = uuid.uuid4()
        centroid = centroids[cluster_label]
        medoid_id = label_summaries[cluster_label]

        # Get medoid text
        medoid_summary = next(s for s in approved_summaries if s.summary_id == medoid_id)
        label_text = medoid_summary.summary_text[:200]  # Truncate to 200 chars

        # Create ThoughtSpace
        thought_space = ThoughtSpace(
            cluster_id=cluster_id,
            round_id=round_entity.round_id,
            label_summary=label_text,
            centroid_vector=centroid.tolist(),  # Store as JSON
            member_count=member_count,
            member_pct=member_pct,
        )
        session.add(thought_space)
        thought_spaces.append(thought_space)

        # Assign approved summaries to this thought space
        for sid, label in cluster_assignments.items():
            if label == cluster_label:
                summary = next(s for s in approved_summaries if s.summary_id == sid)
                summary.cluster_id = cluster_id

    await session.commit()
    print(f"\n✅ Real HDBSCAN clustering complete: {len(thought_spaces)} thought spaces created")

    return thought_spaces


async def close_round(session: AsyncSession, round_entity: Round):
    """Close round and mark as complete."""
    print("\n" + "="*80)
    print(f"STEP 7: Closing Round {round_entity.round_num}")
    print("="*80)

    await session.execute(
        update(Round)
        .where(Round.round_id == round_entity.round_id)
        .values(
            status=RoundStatus.COMPLETE,
            submission_window_end=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
    )

    await session.commit()
    print(f"✅ Round {round_entity.round_num} closed and marked COMPLETE")


async def advance_to_next_round(
    session: AsyncSession,
    discussion: Discussion,
    next_round_num: int
) -> Round:
    """Advance to next round."""
    print("\n" + "="*80)
    print(f"STEP 8: Advancing to Round {next_round_num}")
    print("="*80)

    # Update discussion
    await session.execute(
        update(Discussion)
        .where(Discussion.discussion_id == discussion.discussion_id)
        .values(current_round_num=next_round_num)
    )

    # Get next round
    result = await session.execute(
        select(Round).where(
            Round.discussion_id == discussion.discussion_id,
            Round.round_num == next_round_num
        )
    )
    next_round = result.scalar_one()

    # Open submission window
    now = datetime.utcnow()
    await session.execute(
        update(Round)
        .where(Round.round_id == next_round.round_id)
        .values(
            status=RoundStatus.SUBMISSION_OPEN,
            submission_window_start=now,
            submission_window_end=now + timedelta(hours=24),
        )
    )

    await session.commit()
    await session.refresh(next_round)

    print(f"✅ Advanced to Round {next_round_num}")
    print(f"   Question: {next_round.question_text}")

    return next_round


async def complete_discussion(session: AsyncSession, discussion: Discussion):
    """Mark discussion as complete."""
    print("\n" + "="*80)
    print("STEP 9: Completing Discussion")
    print("="*80)

    await session.execute(
        update(Discussion)
        .where(Discussion.discussion_id == discussion.discussion_id)
        .values(
            status=DiscussionStatus.COMPLETED,
            completed_at=datetime.utcnow(),
        )
    )

    await session.commit()
    print("✅ Discussion marked COMPLETED")


async def generate_sankey(session: AsyncSession, discussion: Discussion):
    """Generate Sankey diagram."""
    print("\n" + "="*80)
    print("STEP 10: Generating Sankey Diagram")
    print("="*80)

    from src.services.sankey_builder import SankeyBuilder

    builder = SankeyBuilder(session)

    # Get all rounds
    result = await session.execute(
        select(Round)
        .where(Round.discussion_id == discussion.discussion_id)
        .order_by(Round.round_num)
    )
    rounds = result.scalars().all()
    round_ids = [r.round_id for r in rounds]

    print(f"   Building Sankey for {len(round_ids)} rounds...")

    # Build Sankey graph
    sankey_graph = await builder.build_sankey_graph(
        discussion_id=discussion.discussion_id,
        rounds=round_ids,
        include_alignment=True
    )

    # Save to database
    await builder.save_to_database(sankey_graph)

    print(f"✅ Sankey diagram generated and saved to database!")
    print(f"   Columns: {len(sankey_graph.columns)}")
    # Count nodes from columns
    total_nodes = sum(len(col.nodes) for col in sankey_graph.columns)
    print(f"   Total Nodes: {total_nodes}")
    print(f"\n   View at: http://localhost:3000/discussions/{discussion.discussion_id}/sankey")


async def main():
    """Run complete async discussion E2E demo."""
    print("\n" + "="*80)
    print("ASYNC DISCUSSION E2E DEMO - AI IN EDUCATION 2026")
    print("="*80)
    print(f"Started at: {datetime.utcnow().isoformat()}")

    engine = get_engine()
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            # Create discussion
            discussion = await create_discussion(session)

            # Start discussion
            round1 = await start_discussion(session, discussion)

            # === ROUND 1 ===
            submissions1 = await submit_responses(session, round1, round_num=1)
            summaries1 = await generate_summaries(session, submissions1)
            approved1 = await create_approved_summaries(session, summaries1, submissions1)
            clusters1 = await run_clustering(session, round1, approved1)
            await close_round(session, round1)

            # Advance to Round 2
            round2 = await advance_to_next_round(session, discussion, next_round_num=2)

            # === ROUND 2 ===
            submissions2 = await submit_responses(session, round2, round_num=2)
            summaries2 = await generate_summaries(session, submissions2)
            approved2 = await create_approved_summaries(session, summaries2, submissions2)
            clusters2 = await run_clustering(session, round2, approved2)
            await close_round(session, round2)

            # Complete discussion
            await complete_discussion(session, discussion)

            # Generate Sankey diagram
            await generate_sankey(session, discussion)

            # Final summary
            print("\n" + "="*80)
            print("✅ DEMO COMPLETE!")
            print("="*80)
            print(f"\nDiscussion ID: {discussion.discussion_id}")
            print(f"Live View: http://localhost:3000/discussions/{discussion.discussion_id}/live")
            print(f"Sankey View: http://localhost:3000/discussions/{discussion.discussion_id}/sankey")
            print(f"Report View: http://localhost:3000/discussions/{discussion.discussion_id}/report")
            print(f"\nCompleted at: {datetime.utcnow().isoformat()}")

            # Save discussion ID
            with open('/tmp/e2e_discussion_id.txt', 'w') as f:
                f.write(str(discussion.discussion_id))

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
