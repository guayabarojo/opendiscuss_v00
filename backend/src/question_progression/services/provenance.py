"""
ProvenanceTracker for recording question generation metadata.

Persists provenance records for audit, debugging, and quality monitoring.
"""

from datetime import datetime
from typing import Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.question_progression.models import QuestionProvenance
from src.logging_config import get_logger

logger = get_logger(__name__)


class ProvenanceTracker:
    """
    Service for tracking provenance metadata for auto-generated questions.

    Records:
    - Generation timestamp and latency
    - Sankey hash (for reproducibility)
    - LLM model and token usage
    - Retry count and validation attempts
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize ProvenanceTracker.

        Args:
            db_session: Database session for persistence
        """
        self.db_session = db_session

    async def record(
        self,
        question_id: UUID,
        provenance_data: Dict[str, Any]
    ) -> QuestionProvenance:
        """
        Create and persist a QuestionProvenance record.

        Args:
            question_id: UUID of the question
            provenance_data: Dictionary containing provenance metadata:
                - input_round_id: Round that triggered generation
                - generation_timestamp: When question was generated
                - generation_latency_ms: Total generation time
                - input_sankey_hash: SHA-256 of Sankey JSON
                - llm_model: Model identifier
                - prompt_tokens: Input token count
                - completion_tokens: Output token count
                - retry_count: Number of API retries
                - validation_attempts: Number of validation attempts
                - previous_questions_count: Number of prior questions

        Returns:
            Created QuestionProvenance entity

        Raises:
            ValueError: If required fields are missing
        """
        # Validate required fields
        required_fields = [
            "input_round_id",
            "generation_timestamp",
            "generation_latency_ms",
            "input_sankey_hash",
            "llm_model",
            "prompt_tokens",
            "completion_tokens",
            "retry_count",
            "validation_attempts",
            "previous_questions_count"
        ]

        missing_fields = [field for field in required_fields if field not in provenance_data]
        if missing_fields:
            raise ValueError(f"Missing required provenance fields: {missing_fields}")

        logger.info(
            "Recording question provenance",
            extra={
                "question_id": str(question_id),
                "input_round_id": str(provenance_data["input_round_id"]),
                "latency_ms": provenance_data["generation_latency_ms"],
                "retry_count": provenance_data["retry_count"],
                "validation_attempts": provenance_data["validation_attempts"]
            }
        )

        # Create QuestionProvenance entity
        provenance = QuestionProvenance(
            question_id=question_id,
            input_round_id=provenance_data["input_round_id"],
            generation_timestamp=provenance_data["generation_timestamp"],
            generation_latency_ms=provenance_data["generation_latency_ms"],
            input_sankey_hash=provenance_data["input_sankey_hash"],
            llm_model=provenance_data["llm_model"],
            prompt_tokens=provenance_data["prompt_tokens"],
            completion_tokens=provenance_data["completion_tokens"],
            retry_count=provenance_data["retry_count"],
            validation_attempts=provenance_data["validation_attempts"],
            previous_questions_count=provenance_data["previous_questions_count"]
        )

        self.db_session.add(provenance)
        await self.db_session.flush()  # Get provenance_id

        logger.info(
            "Question provenance recorded",
            extra={
                "provenance_id": str(provenance.provenance_id),
                "question_id": str(question_id),
                "sankey_hash": provenance_data["input_sankey_hash"][:16]
            }
        )

        return provenance

    async def get_by_question(
        self,
        question_id: UUID
    ) -> QuestionProvenance:
        """
        Get provenance record for a question.

        Args:
            question_id: UUID of the question

        Returns:
            QuestionProvenance entity or None if not found
        """
        from sqlalchemy import select

        result = await self.db_session.execute(
            select(QuestionProvenance).where(
                QuestionProvenance.question_id == question_id
            )
        )
        return result.scalar_one_or_none()
