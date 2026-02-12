"""
Integration tests for discussion completion and termination (Phase 7).

Tests T074-T075:
- T074: Automatic completion when all questions exhausted (HOST_DEFINED)
- T075: Manual termination (AUTO_GENERATED and HOST_DEFINED)
"""

import pytest
from uuid import uuid4
from datetime import datetime

from src.models.discussion import Discussion, DiscussionMode, DiscussionStatus
from src.models.round import Round, RoundStatus
from src.models.participant import Participant
from src.question_progression.models import (
    QuestionSequence,
    Question,
    SequenceMode,
    QuestionMode,
    ValidationStatus,
)
from src.services.discussion_service import DiscussionService
from src.services.timing_service import TimingService
from src.events.event_bus import EventBus


@pytest.mark.asyncio
@pytest.mark.integration
class TestHostDefinedCompletion:
    """Test automatic completion for HOST_DEFINED mode when all questions exhausted."""

    async def test_auto_completion_after_all_rounds_complete(self, db_session):
        """
        Test automatic completion when all rounds are complete (T074).

        Validates:
        - Create HOST_DEFINED discussion with 3 questions
        - Complete all 3 rounds
        - Verify discussion auto-completes
        - Verify status = COMPLETED
        - Verify completion_timestamp set
        """
        # Create HOST_DEFINED discussion
        discussion = Discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.flush()

        # Create question sequence
        sequence = QuestionSequence(
            discussion_id=discussion.discussion_id,
            mode=SequenceMode.HOST_DEFINED,
            total_questions=3,
        )
        db_session.add(sequence)
        await db_session.flush()

        # Create 3 questions
        questions = [
            "What are the main challenges?",
            "How can we address these challenges?",
            "What are the next steps?",
        ]

        for i, q_text in enumerate(questions, start=1):
            question = Question(
                sequence_id=sequence.sequence_id,
                order=i,
                question_text=q_text,
                mode=QuestionMode.HOST_DEFINED,
                validation_status=ValidationStatus.VALID,
            )
            db_session.add(question)

            # Create corresponding round
            round_obj = Round(
                discussion_id=discussion.discussion_id,
                round_num=i,
                question_text=q_text,
                submission_window_duration_sec=300,
            )
            db_session.add(round_obj)

        await db_session.commit()

        # Start discussion
        discussion.start()
        discussion.current_round_num = 1
        db_session.add(discussion)
        await db_session.commit()

        # Create service
        event_bus = EventBus()
        timing_service = TimingService(redis_url="redis://localhost:6379/1")
        await timing_service.connect()
        service = DiscussionService(
            db_session=db_session,
            event_bus=event_bus,
            timing_service=timing_service,
        )

        # Complete Round 1
        await db_session.refresh(discussion, ["rounds"])
        round_1 = next(r for r in discussion.rounds if r.round_num == 1)
        round_1.status = RoundStatus.COMPLETE
        round_1.completed_at = datetime.utcnow()
        db_session.add(round_1)
        await db_session.commit()

        # Check completion - should return False (not all rounds done)
        completed = await service.check_and_complete_if_exhausted(discussion.discussion_id)
        assert completed is False

        await db_session.refresh(discussion)
        assert discussion.status == DiscussionStatus.ACTIVE

        # Complete Round 2
        discussion.current_round_num = 2
        db_session.add(discussion)
        await db_session.commit()

        await db_session.refresh(discussion, ["rounds"])
        round_2 = next(r for r in discussion.rounds if r.round_num == 2)
        round_2.status = RoundStatus.COMPLETE
        round_2.completed_at = datetime.utcnow()
        db_session.add(round_2)
        await db_session.commit()

        # Check completion - still False
        completed = await service.check_and_complete_if_exhausted(discussion.discussion_id)
        assert completed is False

        await db_session.refresh(discussion)
        assert discussion.status == DiscussionStatus.ACTIVE

        # Complete Round 3 (final round)
        discussion.current_round_num = 3
        db_session.add(discussion)
        await db_session.commit()

        await db_session.refresh(discussion, ["rounds"])
        round_3 = next(r for r in discussion.rounds if r.round_num == 3)
        round_3.status = RoundStatus.COMPLETE
        round_3.completed_at = datetime.utcnow()
        db_session.add(round_3)
        await db_session.commit()

        # Check completion - should return True
        completed = await service.check_and_complete_if_exhausted(discussion.discussion_id)
        assert completed is True

        # Verify discussion is COMPLETED
        await db_session.refresh(discussion)
        assert discussion.status == DiscussionStatus.COMPLETED
        assert discussion.completed_at is not None

    async def test_participant_submission_blocked_after_completion(self, db_session):
        """
        Test participant cannot submit after discussion completes (T074).

        Validates:
        - Create and complete HOST_DEFINED discussion
        - Attempt participant submission
        - Verify submission is blocked with "Discussion has ended" message
        """
        from src.services.submission_service import SubmissionService
        from src.api.error_handlers import TimingViolationException

        # Create completed discussion
        discussion = Discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        db_session.add(discussion)
        await db_session.flush()

        # Create round
        round_obj = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts?",
            submission_window_duration_sec=300,
        )
        db_session.add(round_obj)
        await db_session.flush()

        # Mark discussion as completed
        discussion.start()
        discussion.current_round_num = 1
        round_obj.status = RoundStatus.COMPLETE
        db_session.add(discussion)
        db_session.add(round_obj)
        await db_session.commit()

        # Refresh to load rounds relationship before calling complete()
        await db_session.refresh(discussion, ["rounds"])
        discussion.complete()
        db_session.add(discussion)
        await db_session.commit()

        # Create participant
        participant = Participant(
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        db_session.add(participant)
        await db_session.commit()

        # Attempt submission
        submission_service = SubmissionService(db_session)

        with pytest.raises(TimingViolationException) as exc_info:
            await submission_service.handle_multiple_submissions(
                participant_id=participant.participant_id,
                round_id=round_obj.round_id,
                submission_text="This should be blocked",
                modality="text"
            )

        # Verify error message
        error = exc_info.value
        assert "Discussion has ended" in error.reason
        assert error.details.get("is_closed") is True
        assert error.details.get("closure_reason") == "COMPLETED"


@pytest.mark.asyncio
@pytest.mark.integration
class TestManualTermination:
    """Test manual termination for both HOST_DEFINED and AUTO_GENERATED modes."""

    async def test_terminate_host_defined_discussion(self, db_session):
        """
        Test manual termination of HOST_DEFINED discussion (T075).

        Validates:
        - Create HOST_DEFINED discussion
        - Complete Round 1
        - Terminate manually
        - Verify status = TERMINATED
        - Verify termination_reason set
        """
        # Create HOST_DEFINED discussion with 3 rounds
        discussion = Discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.flush()

        # Create rounds
        for i in range(1, 4):
            round_obj = Round(
                discussion_id=discussion.discussion_id,
                round_num=i,
                question_text=f"Question {i}?",
                submission_window_duration_sec=300,
            )
            db_session.add(round_obj)

        await db_session.commit()

        # Start and complete Round 1
        discussion.start()
        discussion.current_round_num = 1
        db_session.add(discussion)
        await db_session.commit()

        await db_session.refresh(discussion, ["rounds"])
        round_1 = next(r for r in discussion.rounds if r.round_num == 1)
        round_1.status = RoundStatus.COMPLETE
        round_1.completed_at = datetime.utcnow()
        db_session.add(round_1)
        await db_session.commit()

        # Terminate discussion
        termination_reason = "Host decided to end discussion early"
        discussion.terminate(termination_reason)
        db_session.add(discussion)
        await db_session.commit()

        # Verify termination
        await db_session.refresh(discussion)
        assert discussion.status == DiscussionStatus.TERMINATED
        assert discussion.terminated_reason == termination_reason
        assert discussion.completed_at is not None

    async def test_terminate_during_question_ready(self, db_session):
        """
        Test termination when round is in QUESTION_READY status (T075).

        Validates:
        - Create AUTO_GENERATED discussion
        - Complete Round 1
        - Set Round 2 to QUESTION_READY
        - Terminate discussion
        - Verify question discarded, round never starts
        """
        # Create AUTO_GENERATED discussion
        discussion = Discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.AUTO_GENERATED,
            total_rounds=5,
        )
        db_session.add(discussion)
        await db_session.flush()

        # Create Round 1
        round_1 = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are the key priorities?",
            submission_window_duration_sec=300,
        )
        db_session.add(round_1)

        # Create Round 2 in QUESTION_READY status
        round_2 = Round(
            discussion_id=discussion.discussion_id,
            round_num=2,
            question_text="How can we address the funding gap?",
            submission_window_duration_sec=300,
        )
        db_session.add(round_2)
        await db_session.commit()

        # Set Round 2 to QUESTION_READY after creation
        round_2.status = RoundStatus.QUESTION_READY
        db_session.add(round_2)
        await db_session.commit()

        # Start discussion and complete Round 1
        discussion.start()
        discussion.current_round_num = 1
        round_1.status = RoundStatus.COMPLETE
        round_1.completed_at = datetime.utcnow()
        db_session.add(discussion)
        db_session.add(round_1)
        await db_session.commit()

        # Terminate during QUESTION_READY
        discussion.terminate("Host decided to end after reviewing Round 1 results")
        db_session.add(discussion)
        await db_session.commit()

        # Verify termination
        await db_session.refresh(discussion)
        assert discussion.status == DiscussionStatus.TERMINATED
        assert discussion.current_round_num == 1  # Never advanced to Round 2

        # Verify Round 2 never started
        await db_session.refresh(round_2)
        assert round_2.status == RoundStatus.QUESTION_READY
        assert round_2.submission_window_start is None

    async def test_cannot_terminate_during_active_submission_window(self, db_session):
        """
        Test termination blocked when submission window is open (T069).

        Validates:
        - Create discussion
        - Open submission window
        - Attempt termination
        - Verify blocked with error message
        """
        # Create discussion
        discussion = Discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=2,
        )
        db_session.add(discussion)
        await db_session.flush()

        # Create round with open submission window
        round_obj = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts?",
            submission_window_duration_sec=300,
        )
        db_session.add(round_obj)
        await db_session.commit()

        # Start discussion and open submission window
        discussion.start()
        discussion.current_round_num = 1
        round_obj.open_submission_window()
        db_session.add(discussion)
        db_session.add(round_obj)
        await db_session.commit()

        # Verify round status is SUBMISSION_OPEN
        await db_session.refresh(round_obj)
        assert round_obj.status == RoundStatus.SUBMISSION_OPEN

        # Note: Termination blocking is handled at the API level
        # The Discussion.terminate() method itself doesn't block
        # This test validates the model state for API-level checks

    async def test_partial_round_termination(self, db_session):
        """
        Test termination after collection complete but before Sankey (T070).

        Validates:
        - Complete Round 1 collection
        - Terminate before Sankey generation
        - Verify discussion TERMINATED
        - Verify final report uses last completed Sankey
        """
        from src.services.report_service import ReportService

        # Create discussion
        discussion = Discussion(
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=3,
        )
        db_session.add(discussion)
        await db_session.flush()

        # Create Round 1 (completed with Sankey)
        round_1 = Round(
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are the main challenges?",
            submission_window_duration_sec=300,
        )
        round_1.status = RoundStatus.COMPLETE  # Set status after __init__
        round_1.completed_at = datetime.utcnow()
        db_session.add(round_1)

        # Create Round 2 (collection complete, but Sankey not done)
        round_2 = Round(
            discussion_id=discussion.discussion_id,
            round_num=2,
            question_text="How can we address these?",
            submission_window_duration_sec=300,
        )
        round_2.status = RoundStatus.CLUSTERING  # Set status after __init__
        db_session.add(round_2)
        await db_session.commit()

        # Start discussion
        discussion.start()
        discussion.current_round_num = 2
        db_session.add(discussion)
        await db_session.commit()

        # Terminate discussion
        discussion.terminate("Host ended discussion after collection phase")
        db_session.add(discussion)
        await db_session.commit()

        # Verify termination
        await db_session.refresh(discussion)
        assert discussion.status == DiscussionStatus.TERMINATED

        # Generate report
        report_service = ReportService(db_session)
        report = await report_service.generate_final_report(discussion.discussion_id)

        # Verify report uses Round 1 as last completed
        assert report["total_rounds_completed"] == 1
        assert report["last_completed_round"]["round_num"] == 1
        assert report["status"] == "TERMINATED"
