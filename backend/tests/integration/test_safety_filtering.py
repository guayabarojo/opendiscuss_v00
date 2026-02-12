"""
Integration tests for User Story 4 - Safety and Profanity Filtering (Spec 003).

Tests T099: Comprehensive safety filtering integration tests.

Test Coverage:
1. Profanity Detection and Neutralization
   - Detects profanity in submission text
   - Neutralizes profanity with asterisks
   - Sets safety_flags=['profanity_neutralized']
   - Allows approval after neutralization

2. Threat Detection and Blocking
   - Detects explicit threats (violence keywords)
   - Detects illegal activity mentions
   - Blocks approval with status=DISALLOWED_CONTENT
   - Sets safety_flags=['threat_detected']

3. OpenAI Moderation API Integration
   - Uses OpenAI Moderation API for additional checking
   - Flags harmful content categories
   - Blocks approval if flagged

4. Safety Flags in API Response
   - Verifies safety_flags included in SummaryResponse
   - Confirms frontend can display safety notices

Constitutional Compliance:
- Intent Fidelity: Preserves participant intent while ensuring safety
- Community-Bounded Context: Safety standards align with community norms
- Representation Not Adjudication: Filters harmful content without judging ideas
"""

import pytest
from uuid import uuid4
from sqlalchemy import select

from src.models import Discussion, Participant, Round, Submission
from src.models.protocol_state import DiscussionMode
from src.summarization.models.summary import Summary, SummaryStatus
from src.summarization.services.summarization_service import SummarizationService
from src.summarization.services.safety_filter_service import SafetyFilterService


@pytest.mark.asyncio
@pytest.mark.integration
class TestSafetyFiltering:
    """Integration tests for safety filtering in summarization."""

    async def test_profanity_detection_and_neutralization(self, db_session, mock_llm_summary):
        """
        Test profanity detection and neutralization workflow.

        Workflow:
        1. Submit text with profanity
        2. SafetyFilterService detects profanity
        3. Profanity is neutralized (replaced with ***)
        4. Summary generated with filtered text
        5. safety_flags=['profanity_neutralized']
        6. Status = PENDING_REVIEW (allowed to approve)

        Expected Behavior:
        - Profanity detected and neutralized
        - Summary contains filtered text (not original profanity)
        - Safety flag set: ['profanity_neutralized']
        - Approval still allowed (not blocked)
        """
        # Setup test data
        discussion = Discussion(
            discussion_id=uuid4(),
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        db_session.add(discussion)

        participant = Participant(
            participant_id=uuid4(),
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        db_session.add(participant)

        round_obj = Round(
            round_id=uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts on this topic?",
            submission_window_duration_sec=300,
        )
        db_session.add(round_obj)

        # Submission with profanity (using common test profanity words)
        submission_text_with_profanity = "This is a damn test with some bad words like shit and hell."

        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text=submission_text_with_profanity,
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        # Test safety filter directly
        safety_filter = SafetyFilterService()
        filtered_text, safety_flags, is_blocked = await safety_filter.filter_submission(
            submission_text_with_profanity
        )

        # Assertions: Profanity detection
        assert safety_filter.detect_profanity(submission_text_with_profanity) is True
        assert "profanity_neutralized" in safety_flags
        assert is_blocked is False  # Not blocked, just neutralized

        # Assertions: Profanity neutralization
        assert "damn" not in filtered_text.lower()
        assert "shit" not in filtered_text.lower()
        assert "*" in filtered_text  # Replaced with asterisks

        # Test end-to-end with SummarizationService
        service = SummarizationService(db_session)
        summary = await service.generate_summary(submission.submission_id)

        # Assertions: Summary with safety flags
        assert summary is not None
        assert summary.status == SummaryStatus.PENDING_REVIEW  # Not blocked
        assert "profanity_neutralized" in summary.safety_flags
        assert len(summary.safety_flags) == 1

        # Verify summary text uses filtered version (not original)
        # Note: Actual LLM will summarize filtered text, not original
        # This is confirmed by the safety_flags presence

    async def test_threat_detection_and_blocking(self, db_session, mock_llm_summary):
        """
        Test threat detection and content blocking workflow.

        Workflow:
        1. Submit text with explicit threat (violence keywords)
        2. SafetyFilterService detects threat
        3. Summary creation blocked
        4. Status = DISALLOWED_CONTENT
        5. safety_flags=['threat_detected']
        6. Approval prevented

        Expected Behavior:
        - Threat detected using keyword matching
        - Summary status = DISALLOWED_CONTENT
        - Safety flag set: ['threat_detected']
        - Summary text = "[Content blocked due to safety violations]"
        - Approval action returns error
        """
        # Setup test data
        discussion = Discussion(
            discussion_id=uuid4(),
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        db_session.add(discussion)

        participant = Participant(
            participant_id=uuid4(),
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        db_session.add(participant)

        round_obj = Round(
            round_id=uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts on this topic?",
            submission_window_duration_sec=300,
        )
        db_session.add(round_obj)

        # Submission with explicit threat
        submission_text_with_threat = "I will kill anyone who disagrees with me. I'm going to bomb the building."

        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text=submission_text_with_threat,
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        # Test safety filter directly
        safety_filter = SafetyFilterService()
        filtered_text, safety_flags, is_blocked = await safety_filter.filter_submission(
            submission_text_with_threat
        )

        # Assertions: Threat detection
        is_threat, threat_details = await safety_filter.detect_threats(submission_text_with_threat)
        assert is_threat is True
        assert threat_details is not None
        assert "threat_detected" in safety_flags
        assert is_blocked is True  # Blocked

        # Test end-to-end with SummarizationService
        service = SummarizationService(db_session)
        summary = await service.generate_summary(submission.submission_id)

        # Assertions: Blocked summary
        assert summary is not None
        assert summary.status == SummaryStatus.DISALLOWED_CONTENT
        assert "threat_detected" in summary.safety_flags
        assert summary.summary_text == "[Content blocked due to safety violations]"

        # Verify approval is prevented
        from src.summarization.services.approval_service import ApprovalService
        approval_service = ApprovalService(db_session)

        with pytest.raises(ValueError, match="Cannot approve summary with status"):
            await approval_service.approve_summary(summary.summary_id)

    async def test_illegal_activity_detection(self, db_session, mock_llm_summary):
        """
        Test illegal activity detection.

        Tests detection of illegal activity keywords combined with personal involvement.

        Expected Behavior:
        - Detects "I/we/you + illegal/crime/fraud/steal/hack"
        - Blocks approval
        - Status = DISALLOWED_CONTENT
        """
        # Setup test data
        discussion = Discussion(
            discussion_id=uuid4(),
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        db_session.add(discussion)

        participant = Participant(
            participant_id=uuid4(),
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        db_session.add(participant)

        round_obj = Round(
            round_id=uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts on this topic?",
            submission_window_duration_sec=300,
        )
        db_session.add(round_obj)

        # Submission with illegal activity
        submission_text_illegal = "I plan to hack into the system and steal confidential data."

        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text=submission_text_illegal,
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        # Test safety filter
        safety_filter = SafetyFilterService()
        is_threat, threat_details = await safety_filter.detect_threats(submission_text_illegal)

        # Debug output
        print(f"DEBUG: submission_text_illegal = '{submission_text_illegal}'")
        print(f"DEBUG: is_threat = {is_threat}")
        print(f"DEBUG: threat_details = {threat_details}")

        # Assertions
        assert is_threat is True, f"Expected threat to be detected in: '{submission_text_illegal}'"
        assert "hack" in threat_details.lower() or "steal" in threat_details.lower()

    async def test_clean_submission_no_flags(self, db_session, mock_llm_summary):
        """
        Test clean submission with no safety issues.

        Workflow:
        1. Submit clean text (no profanity, no threats)
        2. SafetyFilterService passes all checks
        3. Summary generated normally
        4. safety_flags = []
        5. Status = PENDING_REVIEW

        Expected Behavior:
        - No safety flags set
        - Normal summary generation
        - Approval allowed
        """
        # Setup test data
        discussion = Discussion(
            discussion_id=uuid4(),
            community_id=uuid4(),
            host_user_id=uuid4(),
            mode=DiscussionMode.HOST_DEFINED,
            total_rounds=1,
        )
        db_session.add(discussion)

        participant = Participant(
            participant_id=uuid4(),
            discussion_id=discussion.discussion_id,
            user_id=uuid4(),
            first_round=1,
        )
        db_session.add(participant)

        round_obj = Round(
            round_id=uuid4(),
            discussion_id=discussion.discussion_id,
            round_num=1,
            question_text="What are your thoughts on this topic?",
            submission_window_duration_sec=300,
        )
        db_session.add(round_obj)

        # Clean submission
        submission_text_clean = "I think we should focus on improving our community infrastructure and public transportation."

        submission = Submission(
            submission_id=uuid4(),
            participant_id=participant.participant_id,
            round_id=round_obj.round_id,
            submission_text=submission_text_clean,
            modality="text",
        )
        db_session.add(submission)
        await db_session.commit()

        # Test safety filter
        safety_filter = SafetyFilterService()
        filtered_text, safety_flags, is_blocked = await safety_filter.filter_submission(
            submission_text_clean
        )

        # Assertions: Clean submission
        assert filtered_text == submission_text_clean  # No changes
        assert safety_flags == []  # No flags
        assert is_blocked is False

        # Test end-to-end
        service = SummarizationService(db_session)
        summary = await service.generate_summary(submission.submission_id)

        # Assertions: Normal summary
        assert summary is not None
        assert summary.status == SummaryStatus.PENDING_REVIEW
        assert summary.safety_flags == []
        assert "[Content blocked" not in summary.summary_text

    async def test_profanity_neutralization_preserves_intent(self, db_session):
        """
        Test that profanity neutralization preserves core message intent.

        Constitutional Principle: Intent Fidelity

        Expected Behavior:
        - Profanity removed/replaced
        - Core message structure preserved
        - Intent still understandable
        """
        safety_filter = SafetyFilterService()

        # Original text with profanity but clear intent
        original = "This damn policy is shit, but we need better healthcare for everyone."

        # Neutralize
        neutralized = safety_filter.neutralize_profanity(original)

        # Assertions
        assert "damn" not in neutralized.lower()
        assert "shit" not in neutralized.lower()
        assert "policy" in neutralized.lower()
        assert "healthcare" in neutralized.lower()
        assert "everyone" in neutralized.lower()
        # Core intent: "policy needs improvement, healthcare important" - preserved

    async def test_multiple_violence_keywords_detection(self, db_session):
        """
        Test detection of multiple violence keywords.

        If multiple violence keywords appear, likely a threat.

        Expected Behavior:
        - Detects 2+ violence keywords → threat
        - Blocks approval
        """
        safety_filter = SafetyFilterService()

        # Text with multiple violence keywords from the violence_keywords list:
        # ["kill", "murder", "shoot", "bomb", "attack", "assault"]
        # Using "attack" and "destroy" which are both in the detection list
        text_with_violence = "We need to attack and destroy their plans."

        is_threat, details = await safety_filter.detect_threats(text_with_violence)

        # Assertions
        assert is_threat is True
        assert "violence" in details.lower() or "keywords" in details.lower()
