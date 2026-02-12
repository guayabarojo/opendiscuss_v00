"""
Dropout detection service for tracking participant attrition across rounds.

Implements participant dropout tracking per the constitutional requirement:
no synthetic flows for dropouts (mass shrinks naturally).
"""

import logging
from typing import List
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Participant, ApprovedSummary, Round
from src.models.protocol_state import DropoutReason

logger = logging.getLogger(__name__)


class DropoutDetectionService:
    """
    Service for detecting and marking participant dropouts.

    Constitutional Guarantees:
    - Participants who submit in Round N but not Round N+1 are marked as dropouts
    - Dropout reason set to NO_SUBMISSION
    - last_round set to N (last round where they participated)
    - No synthetic flows created for dropouts (mass shrinks naturally)
    - All dropouts properly tracked for observability
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize DropoutDetectionService with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session

    async def detect_dropouts(
        self,
        source_round_id: UUID,
        target_round_id: UUID
    ) -> List[Participant]:
        """
        Detect participants who submitted in Round N but not Round N+1.

        This implements dropout detection per data-model.md:
        - Query ApprovedSummaries for Round N to get all participants
        - Query ApprovedSummaries for Round N+1 to get continuing participants
        - Identify participant_ids present in N but missing from N+1
        - Update Participant entities:
          - Set last_round = N
          - Set dropout_reason = NO_SUBMISSION
        - Return list of dropped-out Participant entities

        Constitutional Guarantee:
        Dropouts are detected and tracked, but NO synthetic flows are created.
        Mass shrinks naturally when participants leave.

        Args:
            source_round_id: UUID of source round (Round N)
            target_round_id: UUID of target round (Round N+1)

        Returns:
            List of Participant entities that dropped out (with last_round set)

        Raises:
            ValueError: If rounds not consecutive or not found
            RuntimeError: If data validation fails
        """
        logger.info(
            f"Detecting dropouts from round {source_round_id} to {target_round_id}"
        )

        # Validate rounds exist and are consecutive
        source_round = await self._get_round(source_round_id)
        target_round = await self._get_round(target_round_id)

        if not source_round or not target_round:
            raise ValueError(
                f"Rounds not found: source={source_round_id}, target={target_round_id}"
            )

        if target_round.round_num != source_round.round_num + 1:
            raise ValueError(
                f"Rounds must be consecutive. "
                f"Source round_num={source_round.round_num}, "
                f"Target round_num={target_round.round_num}"
            )

        logger.debug(
            f"Validated consecutive rounds: "
            f"Round {source_round.round_num} → Round {target_round.round_num}"
        )

        # Get participants who submitted in Round N
        source_participants = await self._get_participants_in_round(source_round_id)

        # Get participants who submitted in Round N+1
        target_participants = await self._get_participants_in_round(target_round_id)

        logger.debug(
            f"Source round has {len(source_participants)} participants, "
            f"Target round has {len(target_participants)} participants"
        )

        # Identify dropouts: in source but NOT in target
        dropout_participant_ids = source_participants - target_participants

        if not dropout_participant_ids:
            logger.info(
                f"No dropouts detected between rounds "
                f"{source_round.round_num} and {target_round.round_num}"
            )
            return []

        logger.info(
            f"Detected {len(dropout_participant_ids)} dropouts between rounds "
            f"{source_round.round_num} and {target_round.round_num}"
        )

        # Fetch Participant entities for dropouts
        dropout_participants = await self._get_participants_by_ids(
            list(dropout_participant_ids)
        )

        # Mark each participant as dropped out
        updated_participants = []
        for participant in dropout_participants:
            # Validate participant not already marked as dropout
            if participant.last_round is not None:
                logger.warning(
                    f"Participant {participant.participant_id} already marked as "
                    f"dropout at round {participant.last_round}. Skipping."
                )
                continue

            # Mark dropout using the model's method
            try:
                participant.mark_dropout(
                    reason=DropoutReason.NO_SUBMISSION,
                    round_num=source_round.round_num
                )

                updated_participants.append(participant)

                logger.debug(
                    f"Marked participant {participant.participant_id} as dropout "
                    f"(last_round={source_round.round_num}, "
                    f"reason=NO_SUBMISSION)"
                )

            except ValueError as e:
                logger.error(
                    f"Failed to mark participant {participant.participant_id} as "
                    f"dropout: {e}"
                )
                # Continue processing other dropouts even if one fails

        logger.info(
            f"Successfully marked {len(updated_participants)} participants as dropouts"
        )

        return updated_participants

    async def detect_approval_timeouts(
        self,
        round_id: UUID
    ) -> List[Participant]:
        """
        Detect participants who submitted but never approved a summary.

        This handles the case where participants submit during the window but
        fail to approve any summary before the approval deadline.

        Args:
            round_id: UUID of round to check for approval timeouts

        Returns:
            List of Participant entities that timed out on approval

        Raises:
            ValueError: If round not found or approval deadline not set
            RuntimeError: If data validation fails
        """
        logger.info(
            f"Detecting approval timeouts for round {round_id}"
        )

        # Get round and validate approval deadline has passed
        round_entity = await self._get_round(round_id)

        if not round_entity:
            raise ValueError(f"Round not found: {round_id}")

        if round_entity.approval_deadline is None:
            raise ValueError(
                f"Round {round_id} has no approval_deadline set. "
                f"Cannot detect approval timeouts."
            )

        now = datetime.utcnow()
        if now < round_entity.approval_deadline:
            logger.warning(
                f"Approval deadline for round {round_id} has not passed yet "
                f"(deadline: {round_entity.approval_deadline}, now: {now}). "
                f"Skipping timeout detection."
            )
            return []

        # Get participants who submitted but have no approved summary
        # This requires joining Submission with ApprovedSummary
        # Participants with submissions but no approved summaries are timeouts

        # Get all participants who submitted to this round
        result = await self.session.execute(
            select(ApprovedSummary.participant_id)
            .where(ApprovedSummary.round_id == round_id)
        )
        participants_with_approval = set(result.scalars().all())

        # For timeout detection, we need to know who submitted
        # This would require querying Submission table, which may be ephemeral
        # For now, we'll document this as a TODO and return empty list
        # The main dropout detection (NO_SUBMISSION) is the critical path

        logger.debug(
            f"Approval timeout detection not yet fully implemented. "
            f"Found {len(participants_with_approval)} participants with approvals."
        )

        # TODO: Implement full approval timeout detection
        # Requires querying Submission table to find participants who submitted
        # but have no entries in ApprovedSummary for this round

        return []

    async def _get_round(self, round_id: UUID) -> Round:
        """
        Fetch Round entity by ID.

        Args:
            round_id: UUID of round

        Returns:
            Round entity or None if not found
        """
        result = await self.session.execute(
            select(Round).where(Round.round_id == round_id)
        )
        return result.scalar_one_or_none()

    async def _get_participants_in_round(self, round_id: UUID) -> set[UUID]:
        """
        Get all participant_ids who have approved summaries in a round.

        Args:
            round_id: UUID of round

        Returns:
            Set of participant UUIDs
        """
        result = await self.session.execute(
            select(ApprovedSummary.participant_id)
            .where(ApprovedSummary.round_id == round_id)
        )
        return set(result.scalars().all())

    async def _get_participants_by_ids(
        self,
        participant_ids: List[UUID]
    ) -> List[Participant]:
        """
        Fetch Participant entities by IDs.

        Args:
            participant_ids: List of participant UUIDs

        Returns:
            List of Participant entities
        """
        if not participant_ids:
            return []

        result = await self.session.execute(
            select(Participant).where(
                Participant.participant_id.in_(participant_ids)
            )
        )
        return list(result.scalars().all())

    async def get_round_dropouts(
        self,
        round_id: UUID,
        discussion_id: UUID
    ) -> List[UUID]:
        """
        Get participant IDs who were active in previous round but didn't submit in current round.

        T066: Query to identify dropouts for a specific round.

        Args:
            round_id: UUID of current round
            discussion_id: UUID of parent discussion

        Returns:
            List of participant_ids who dropped out (were active but didn't submit)

        Raises:
            ValueError: If round not found or is first round (no dropouts possible)
        """
        logger.info(f"Querying dropouts for round {round_id}")

        # Get the round to find previous round
        round_entity = await self._get_round(round_id)
        if not round_entity:
            raise ValueError(f"Round not found: {round_id}")

        if round_entity.round_num == 1:
            logger.info("Round 1 has no dropouts (no previous round)")
            return []

        # Find the previous round
        prev_round_num = round_entity.round_num - 1
        prev_round_result = await self.session.execute(
            select(Round).where(
                Round.discussion_id == discussion_id,
                Round.round_num == prev_round_num
            )
        )
        prev_round = prev_round_result.scalar_one_or_none()

        if not prev_round:
            raise ValueError(
                f"Previous round not found: round_num={prev_round_num}, "
                f"discussion_id={discussion_id}"
            )

        # Get participants who submitted in previous round
        prev_participants = await self._get_participants_in_round(prev_round.round_id)

        # Get participants who submitted in current round
        current_participants = await self._get_participants_in_round(round_id)

        # Dropouts = in previous but NOT in current
        dropout_ids = prev_participants - current_participants

        logger.info(
            f"Found {len(dropout_ids)} dropouts for round {round_entity.round_num}: "
            f"{len(prev_participants)} in previous round, "
            f"{len(current_participants)} in current round"
        )

        return list(dropout_ids)


async def get_dropout_detection_service(
    session: AsyncSession
) -> DropoutDetectionService:
    """
    Factory function to create DropoutDetectionService instance.

    Args:
        session: Async SQLAlchemy session

    Returns:
        DropoutDetectionService instance
    """
    return DropoutDetectionService(session)
