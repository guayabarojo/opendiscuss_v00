#!/usr/bin/env python3
"""
Create sample data for OpenDiscuss UI testing
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.models.discussion import Discussion
from src.models.round import Round
from src.models.participant import Participant
from src.models.submission import Submission
from src.models.approved_summary import ApprovedSummary
from src.models.thought_space import ThoughtSpace
from src.models.flow import Flow
from src.models.protocol_state import (
    DiscussionMode,
    DiscussionStatus,
    RoundStatus,
    SubmissionModality,
)


async def create_sample_data():
    """Create sample discussions, rounds, and participants for testing"""

    print("🎨 Creating sample data for OpenDiscuss...")
    print("")

    session_factory = get_session_factory()
    async with session_factory() as db:

        # Create sample community and user IDs
        community_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        host_user_id = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")

        print("1️⃣  Creating Discussion: Remote Work Policy")

        # Create a sample discussion
        discussion = Discussion(
            discussion_id=uuid.uuid4(),
            community_id=community_id,
            host_user_id=host_user_id,
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
            current_round_num=0,
            status=DiscussionStatus.CREATED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(discussion)
        await db.flush()

        print(f"   ✓ Discussion created: {discussion.discussion_id}")
        print(f"   Status: {discussion.status}")
        print(f"   Total rounds: {discussion.total_rounds}")

        # Create rounds with questions
        questions = [
            "What are your thoughts on remote work?",
            "How can we improve team collaboration remotely?",
            "What tools would help our team work better together?",
        ]

        print("")
        print("2️⃣  Creating Rounds")

        rounds = []
        for i, question in enumerate(questions, 1):
            round_obj = Round(
                round_id=uuid.uuid4(),
                discussion_id=discussion.discussion_id,
                round_num=i,
                question_text=question,
                status=RoundStatus.PENDING,
                submission_window_duration_sec=300,  # 5 minutes
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(round_obj)
            rounds.append(round_obj)
            print(f"   ✓ Round {i}: {question[:50]}...")

        await db.flush()

        # Create sample participants
        print("")
        print("3️⃣  Creating Participants (5 users)")

        participant_user_ids = [
            uuid.uuid4() for _ in range(5)
        ]

        participants = []
        for idx, user_id in enumerate(participant_user_ids, 1):
            participant = Participant(
                participant_id=uuid.uuid4(),
                discussion_id=discussion.discussion_id,
                user_id=user_id,
                first_round=1,
                last_round=None,  # Still active
                dropout_reason=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(participant)
            participants.append(participant)
            print(f"   ✓ Participant {idx}: {participant.participant_id}")

        await db.flush()

        # Commit all changes
        await db.commit()

        print("")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ Sample data created successfully!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("")
        print("📊 Summary:")
        print(f"   Discussion ID: {discussion.discussion_id}")
        print(f"   Community ID: {community_id}")
        print(f"   Host User ID: {host_user_id}")
        print(f"   Rounds: {len(rounds)}")
        print(f"   Participants: {len(participants)}")
        print("")
        print("🌐 Test the UI:")
        print(f"   Frontend: http://localhost:3000")
        print(f"   API Docs: http://localhost:8000/docs")
        print("")
        print("📝 Try these API calls:")
        print(f"   GET /discussions/{discussion.discussion_id}")
        print(f"   POST /discussions/{discussion.discussion_id}/start")
        print("")


async def create_completed_discussion_with_report():
    """Create a completed discussion with full Sankey data for report viewing"""

    print("🎨 Creating completed discussion with Sankey report...")
    print("")

    session_factory = get_session_factory()
    async with session_factory() as db:

        # Create sample IDs
        community_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        host_user_id = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")

        print("1️⃣  Creating Completed Discussion")

        # Create completed discussion
        discussion = Discussion(
            discussion_id=uuid.uuid4(),
            community_id=community_id,
            host_user_id=host_user_id,
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
            current_round_num=2,
            status=DiscussionStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(minutes=30),
            completed_at=datetime.utcnow(),
            created_at=datetime.utcnow() - timedelta(minutes=35),
            updated_at=datetime.utcnow(),
        )
        db.add(discussion)
        await db.flush()

        print(f"   ✓ Discussion: {discussion.discussion_id}")
        print(f"   Status: {discussion.status} (ready for report)")

        # Create 2 rounds
        print("")
        print("2️⃣  Creating Rounds (2 completed)")

        round1 = Round(
            round_id=uuid.uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are the main benefits of remote work?",
            status=RoundStatus.COMPLETE,
            submission_window_start=datetime.utcnow() - timedelta(minutes=30),
            submission_window_end=datetime.utcnow() - timedelta(minutes=25),
            submission_window_duration_sec=300,
            completed_at=datetime.utcnow() - timedelta(minutes=20),
            created_at=datetime.utcnow() - timedelta(minutes=35),
            updated_at=datetime.utcnow() - timedelta(minutes=20),
        )
        db.add(round1)

        round2 = Round(
            round_id=uuid.uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=2,
            question_text="How can we improve remote collaboration?",
            status=RoundStatus.COMPLETE,
            submission_window_start=datetime.utcnow() - timedelta(minutes=15),
            submission_window_end=datetime.utcnow() - timedelta(minutes=10),
            submission_window_duration_sec=300,
            completed_at=datetime.utcnow(),
            created_at=datetime.utcnow() - timedelta(minutes=20),
            updated_at=datetime.utcnow(),
        )
        db.add(round2)
        await db.flush()

        print(f"   ✓ Round 1: {round1.question_text}")
        print(f"   ✓ Round 2: {round2.question_text}")

        # Create 6 participants
        print("")
        print("3️⃣  Creating Participants (6 users)")

        participants = []
        for i in range(6):
            participant = Participant(
                participant_id=uuid.uuid4(),
                discussion_id=discussion.discussion_id,
                user_id=uuid.uuid4(),
                first_round=1,
                last_round=2,  # Completed both rounds
                dropout_reason=None,
                created_at=datetime.utcnow() - timedelta(minutes=35),
                updated_at=datetime.utcnow(),
            )
            db.add(participant)
            participants.append(participant)

        await db.flush()
        print(f"   ✓ Created {len(participants)} participants")

        # Create thought spaces for Round 1 (2 clusters)
        print("")
        print("4️⃣  Creating ThoughtSpaces for Round 1")

        ts1_r1 = ThoughtSpace(
            cluster_id=uuid.uuid4(),
            round_id=round1.round_id,
            label_summary="Flexibility and work-life balance",
            member_count=4,
            member_pct=0.67,
            display_group_id=1,
            created_at=datetime.utcnow() - timedelta(minutes=20),
            updated_at=datetime.utcnow() - timedelta(minutes=20),
        )
        db.add(ts1_r1)

        ts2_r1 = ThoughtSpace(
            cluster_id=uuid.uuid4(),
            round_id=round1.round_id,
            label_summary="Reduced commute and cost savings",
            member_count=2,
            member_pct=0.33,
            display_group_id=2,
            created_at=datetime.utcnow() - timedelta(minutes=20),
            updated_at=datetime.utcnow() - timedelta(minutes=20),
        )
        db.add(ts2_r1)
        await db.flush()

        print(f"   ✓ Cluster 1: {ts1_r1.label_summary} ({ts1_r1.member_count} members)")
        print(f"   ✓ Cluster 2: {ts2_r1.label_summary} ({ts2_r1.member_count} members)")

        # Create approved summaries for Round 1
        for i, participant in enumerate(participants):
            cluster = ts1_r1 if i < 4 else ts2_r1
            summary = ApprovedSummary(
                summary_id=uuid.uuid4(),
                participant_id=participant.participant_id,
                round_id=round1.round_id,
                submission_id=None,
                summary_text=f"Sample summary {i+1} for cluster",
                cluster_id=cluster.cluster_id,
                approved_at=datetime.utcnow() - timedelta(minutes=22),
                created_at=datetime.utcnow() - timedelta(minutes=22),
            )
            db.add(summary)

        await db.flush()

        # Create thought spaces for Round 2 (3 clusters)
        print("")
        print("5️⃣  Creating ThoughtSpaces for Round 2")

        ts1_r2 = ThoughtSpace(
            cluster_id=uuid.uuid4(),
            round_id=round2.round_id,
            label_summary="Better communication tools needed",
            member_count=3,
            member_pct=0.50,
            display_group_id=1,
            created_at=datetime.utcnow() - timedelta(minutes=5),
            updated_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db.add(ts1_r2)

        ts2_r2 = ThoughtSpace(
            cluster_id=uuid.uuid4(),
            round_id=round2.round_id,
            label_summary="Regular video meetings important",
            member_count=2,
            member_pct=0.33,
            display_group_id=2,
            created_at=datetime.utcnow() - timedelta(minutes=5),
            updated_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db.add(ts2_r2)

        ts3_r2 = ThoughtSpace(
            cluster_id=uuid.uuid4(),
            round_id=round2.round_id,
            label_summary="Async communication works better",
            member_count=1,
            member_pct=0.17,
            display_group_id=3,
            created_at=datetime.utcnow() - timedelta(minutes=5),
            updated_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db.add(ts3_r2)
        await db.flush()

        print(f"   ✓ Cluster 1: {ts1_r2.label_summary} ({ts1_r2.member_count} members)")
        print(f"   ✓ Cluster 2: {ts2_r2.label_summary} ({ts2_r2.member_count} members)")
        print(f"   ✓ Cluster 3: {ts3_r2.label_summary} ({ts3_r2.member_count} members)")

        # Create approved summaries for Round 2 and flows
        print("")
        print("6️⃣  Creating Flows (participant movement)")

        # Flow 1: ts1_r1 -> ts1_r2 (3 participants)
        flow1_participants = participants[:3]
        for participant in flow1_participants:
            summary = ApprovedSummary(
                summary_id=uuid.uuid4(),
                participant_id=participant.participant_id,
                round_id=round2.round_id,
                submission_id=None,
                summary_text=f"Round 2 summary for {participant.participant_id}",
                cluster_id=ts1_r2.cluster_id,
                approved_at=datetime.utcnow() - timedelta(minutes=7),
                created_at=datetime.utcnow() - timedelta(minutes=7),
            )
            db.add(summary)

        flow1 = Flow(
            flow_id=uuid.uuid4(),
            source_cluster_id=ts1_r1.cluster_id,
            target_cluster_id=ts1_r2.cluster_id,
            participant_count=3,
            participant_ids=[p.participant_id for p in flow1_participants],
            created_at=datetime.utcnow() - timedelta(minutes=5),
            updated_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db.add(flow1)
        print(f"   ✓ Flow: Cluster 1 → Cluster 1 (3 participants)")

        # Flow 2: ts1_r1 -> ts2_r2 (1 participant)
        flow2_participant = [participants[3]]
        summary = ApprovedSummary(
            summary_id=uuid.uuid4(),
            participant_id=flow2_participant[0].participant_id,
            round_id=round2.round_id,
            submission_id=None,
            summary_text="Moved to video meetings cluster",
            cluster_id=ts2_r2.cluster_id,
            approved_at=datetime.utcnow() - timedelta(minutes=7),
            created_at=datetime.utcnow() - timedelta(minutes=7),
        )
        db.add(summary)

        flow2 = Flow(
            flow_id=uuid.uuid4(),
            source_cluster_id=ts1_r1.cluster_id,
            target_cluster_id=ts2_r2.cluster_id,
            participant_count=1,
            participant_ids=[p.participant_id for p in flow2_participant],
            created_at=datetime.utcnow() - timedelta(minutes=5),
            updated_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db.add(flow2)
        print(f"   ✓ Flow: Cluster 1 → Cluster 2 (1 participant)")

        # Flow 3: ts2_r1 -> ts2_r2 (1 participant)
        flow3_participant = [participants[4]]
        summary = ApprovedSummary(
            summary_id=uuid.uuid4(),
            participant_id=flow3_participant[0].participant_id,
            round_id=round2.round_id,
            submission_id=None,
            summary_text="Stayed in similar cluster",
            cluster_id=ts2_r2.cluster_id,
            approved_at=datetime.utcnow() - timedelta(minutes=7),
            created_at=datetime.utcnow() - timedelta(minutes=7),
        )
        db.add(summary)

        flow3 = Flow(
            flow_id=uuid.uuid4(),
            source_cluster_id=ts2_r1.cluster_id,
            target_cluster_id=ts2_r2.cluster_id,
            participant_count=1,
            participant_ids=[p.participant_id for p in flow3_participant],
            created_at=datetime.utcnow() - timedelta(minutes=5),
            updated_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db.add(flow3)
        print(f"   ✓ Flow: Cluster 2 → Cluster 2 (1 participant)")

        # Flow 4: ts2_r1 -> ts3_r2 (1 participant)
        flow4_participant = [participants[5]]
        summary = ApprovedSummary(
            summary_id=uuid.uuid4(),
            participant_id=flow4_participant[0].participant_id,
            round_id=round2.round_id,
            submission_id=None,
            summary_text="Moved to async communication",
            cluster_id=ts3_r2.cluster_id,
            approved_at=datetime.utcnow() - timedelta(minutes=7),
            created_at=datetime.utcnow() - timedelta(minutes=7),
        )
        db.add(summary)

        flow4 = Flow(
            flow_id=uuid.uuid4(),
            source_cluster_id=ts2_r1.cluster_id,
            target_cluster_id=ts3_r2.cluster_id,
            participant_count=1,
            participant_ids=[p.participant_id for p in flow4_participant],
            created_at=datetime.utcnow() - timedelta(minutes=5),
            updated_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db.add(flow4)
        print(f"   ✓ Flow: Cluster 2 → Cluster 3 (1 participant)")

        await db.flush()
        await db.commit()

        print("")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ Completed discussion with Sankey data created!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("")
        print("📊 Summary:")
        print(f"   Discussion ID: {discussion.discussion_id}")
        print(f"   Status: {discussion.status}")
        print(f"   Rounds: 2 (both complete)")
        print(f"   Participants: 6")
        print(f"   ThoughtSpaces Round 1: 2")
        print(f"   ThoughtSpaces Round 2: 3")
        print(f"   Flows: 4")
        print("")
        print("🌐 View the Sankey Report:")
        print(f"   Frontend: http://localhost:3000/reports/{discussion.discussion_id}")
        print(f"   API: GET /discussions/{discussion.discussion_id}/report")
        print("")


if __name__ == "__main__":
    print("OpenDiscuss Sample Data Creator")
    print("=" * 50)
    print("")
    print("This will create:")
    print("1. A new discussion ready to start")
    print("2. A completed discussion with Sankey report data")
    print("")

    asyncio.run(create_sample_data())
    print("")
    asyncio.run(create_completed_discussion_with_report())

    print("")
    print("✅ All sample data created!")
    print("")
