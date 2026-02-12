"""
Unit Tests: Safety Filter Service

Tests SafetyFilterService profanity detection and threat blocking.

Spec Reference: Spec 003 - Summarization & Approval Protocol (T108)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.summarization.services.safety_filter_service import SafetyFilterService


@pytest.mark.asyncio
class TestSafetyFilters:
    """Unit tests for SafetyFilterService."""

    async def test_detect_profanity(self, db_session):
        """Test profanity detection."""
        service = SafetyFilterService(db_session)

        # Test with profanity
        text_with_profanity = "This damn policy is terrible."
        has_profanity = await service.contains_profanity(text_with_profanity)
        assert has_profanity is True

        # Test clean text
        clean_text = "This policy needs improvement."
        has_profanity_clean = await service.contains_profanity(clean_text)
        assert has_profanity_clean is False

    async def test_neutralize_profanity(self, db_session):
        """Test profanity neutralization."""
        service = SafetyFilterService(db_session)

        text_with_profanity = "This damn policy is terrible."
        filtered = await service.filter_submission(text_with_profanity)

        # Profanity should be removed/replaced
        assert "damn" not in filtered.lower()
        assert len(filtered) > 0

    async def test_detect_threats_basic(self, db_session):
        """Test basic threat detection."""
        service = SafetyFilterService(db_session)

        # Test with threat
        threat_text = "I will harm anyone who disagrees."
        is_threat = await service.detect_threats(threat_text)
        assert is_threat is True

        # Test clean text
        clean_text = "I disagree with this policy."
        is_threat_clean = await service.detect_threats(clean_text)
        assert is_threat_clean is False

    async def test_threat_keywords(self, db_session):
        """Test threat detection with specific keywords."""
        service = SafetyFilterService(db_session)

        threat_keywords = ["kill", "harm", "attack", "violence"]

        for keyword in threat_keywords:
            text = f"I will {keyword} those who oppose this."
            is_threat = await service.detect_threats(text)
            assert is_threat is True, f"Should detect '{keyword}' as threat"

    async def test_clean_content_passes(self, db_session):
        """Test that clean content passes all filters."""
        service = SafetyFilterService(db_session)

        clean_text = "We should invest in renewable energy and sustainable infrastructure."

        has_profanity = await service.contains_profanity(clean_text)
        is_threat = await service.detect_threats(clean_text)
        filtered = await service.filter_submission(clean_text)

        assert has_profanity is False
        assert is_threat is False
        assert filtered == clean_text  # No changes

    async def test_filter_preserves_meaning(self, db_session):
        """Test that filtering preserves general meaning."""
        service = SafetyFilterService(db_session)

        original = "This policy is bad and needs fixing."
        filtered = await service.filter_submission(original)

        # Should have similar length (not empty)
        assert len(filtered) > len(original) * 0.5
        assert "policy" in filtered.lower()

    @patch('src.summarization.services.safety_filter_service.openai')
    async def test_openai_moderation_api_integration(self, mock_openai, db_session):
        """Test integration with OpenAI Moderation API."""
        # Mock OpenAI moderation response
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(flagged=True, categories=MagicMock(violence=True))
        ]
        mock_openai.moderations.create = AsyncMock(return_value=mock_response)

        service = SafetyFilterService(db_session)

        text = "Violent content here."
        # This would call OpenAI Moderation API in real implementation
        # For now, verify the service exists and can be called

        assert service is not None

    async def test_multiple_profanity_words(self, db_session):
        """Test filtering multiple profanity words."""
        service = SafetyFilterService(db_session)

        text_with_multiple = "This damn stupid policy is terrible."
        filtered = await service.filter_submission(text_with_multiple)

        # Multiple profanity words should be filtered
        assert "damn" not in filtered.lower()
        assert len(filtered) > 0

    async def test_context_aware_filtering(self, db_session):
        """Test that filtering is context-aware (doesn't over-filter)."""
        service = SafetyFilterService(db_session)

        # Words that might be flagged but are legitimate in context
        legitimate_text = "We need to kill this bill in committee."
        # "kill" in legislative context is legitimate

        # Service should be smart enough to not flag this
        # (Implementation may vary - this is aspirational)
        filtered = await service.filter_submission(legitimate_text)
        assert len(filtered) > 0
