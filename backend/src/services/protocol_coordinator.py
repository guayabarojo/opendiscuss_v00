"""
Protocol Coordinator - Orchestrates round state transitions across sub-protocols.

This service is the central orchestrator for the OpenDiscuss Discussion Protocol,
coordinating state transitions between sub-protocols (submission, summarization,
clustering, Sankey building) and enforcing constitutional guarantees at each step.

Constitutional Responsibilities:
- Intent Fidelity: Validate 100% approved summaries before clustering
- Semantic Accuracy: Validate 100% participant coverage after clustering
- Temporal Transparency: Validate flow accuracy before Sankey completion
- Synchronous Deliberation: Enforce timing constraints throughout round lifecycle

Architecture:
- Event-driven coordination via EventBus subscriptions
- Fail-fast validation using InvariantValidator before state transitions
- Atomic state transitions with database rollback on validation failure
- Comprehensive logging with trace_id correlation for observability
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session_factory
from src.events.event_bus import EventBus
from src.events.event_types import (
    SubmissionWindowClosedEvent,
    SummarizationCompleteEvent,
    ClusteringCompleteEvent,
    SankeyCompleteEvent,
)
from src.models.protocol_state import RoundStatus
from src.models.round import Round
from src.api.error_handlers import InvalidStateTransitionException
from src.logging_config import get_logger, get_trace_id

logger = get_logger(__name__)


class ProtocolCoordinator:
    """
    Orchestrates round state transitions across sub-protocols.

    The ProtocolCoordinator is responsible for:
    1. Subscribing to sub-protocol completion events
    2. Validating constitutional invariants before state transitions
    3. Advancing round status through the state machine
    4. Triggering the next sub-protocol in sequence
    5. Handling errors and invalid state transitions

    State Machine:
        SUBMISSION_CLOSED → SUMMARIZING (on submission_window.closed)
        SUMMARIZING → APPROVING (on summarization.complete)
        APPROVING → CLUSTERING (on approval validation)
        CLUSTERING → SANKEY_BUILDING (on clustering.complete)
        SANKEY_BUILDING → COMPLETE (on sankey.complete)

    Constitutional Enforcement:
        - Before CLUSTERING: Validate Intent Fidelity (100% approved summaries)
        - After CLUSTERING: Validate Semantic Accuracy (100% participant coverage)
        - Before COMPLETE: Validate Temporal Transparency (flow accuracy)
    """

    def __init__(self, event_bus: EventBus, invariant_validator=None):
        """
        Initialize the protocol coordinator.

        Args:
            event_bus: EventBus instance for subscribing to events
            invariant_validator: Optional InvariantValidator instance (injected for testing)
        """
        self.event_bus = event_bus
        self._invariant_validator = invariant_validator
        self._handlers_registered = False

    @property
    def invariant_validator(self):
        """Lazy load InvariantValidator to avoid circular imports."""
        if self._invariant_validator is None:
            from src.services.invariant_validator import InvariantValidator
            self._invariant_validator = InvariantValidator()
        return self._invariant_validator

    async def register_handlers(self) -> None:
        """
        Register event handlers with the event bus.

        This should be called during application startup after the event bus
        is connected. Registers handlers for all sub-protocol completion events.

        Raises:
            RuntimeError: If handlers are already registered or event bus not connected
        """
        if self._handlers_registered:
            logger.warning("ProtocolCoordinator handlers already registered, skipping")
            return

        if not self.event_bus.is_connected():
            raise RuntimeError("Cannot register handlers: EventBus not connected")

        logger.info("Registering ProtocolCoordinator event handlers...")

        # Register handlers for sub-protocol completion events
        await self.event_bus.subscribe(
            "submission_window.closed",
            self.handle_submission_window_closed
        )
        await self.event_bus.subscribe(
            "summarization.complete",
            self.handle_summarization_complete
        )
        await self.event_bus.subscribe(
            "clustering.complete",
            self.handle_clustering_complete
        )
        await self.event_bus.subscribe(
            "sankey.complete",
            self.handle_sankey_complete
        )

        self._handlers_registered = True
        logger.info("ProtocolCoordinator handlers registered successfully")

    async def handle_submission_window_closed(
        self, event: SubmissionWindowClosedEvent
    ) -> None:
        """
        Handle submission window closure event.

        Transitions: SUBMISSION_CLOSED → SUMMARIZING

        Actions:
        1. Validate round is in SUBMISSION_CLOSED state
        2. Advance to SUMMARIZING status
        3. Trigger Spec 3 (Summarization sub-protocol)

        Args:
            event: SubmissionWindowClosedEvent with round_id and submissions

        Raises:
            InvalidStateTransitionException: If round not in valid state
        """
        round_id = event.round_id
        submission_count = len(event.submissions)
        trace_id = get_trace_id() or f"coord-{round_id}"

        logger.info(
            f"[{trace_id}] Processing submission_window.closed for round {round_id} "
            f"({submission_count} submissions)",
            extra={"trace_id": trace_id, "round_id": str(round_id)}
        )

        session_factory = get_session_factory()
        async with session_factory() as db:
            try:
                # Fetch round
                round_obj = await self._fetch_round(db, round_id)

                # Validate current state
                if round_obj.status != RoundStatus.SUBMISSION_CLOSED:
                    raise InvalidStateTransitionException(
                        entity_type="Round",
                        entity_id=str(round_id),
                        from_state=round_obj.status.value,
                        to_state=RoundStatus.SUMMARIZING.value,
                        reason="Round must be in SUBMISSION_CLOSED state"
                    )

                # Advance status
                round_obj.advance_status(RoundStatus.SUMMARIZING)
                await db.commit()

                logger.info(
                    f"[{trace_id}] Round {round_id} transitioned: "
                    f"SUBMISSION_CLOSED → SUMMARIZING",
                    extra={
                        "trace_id": trace_id,
                        "round_id": str(round_id),
                        "submission_count": submission_count
                    }
                )

                # TODO: Trigger Spec 3 (Summarization sub-protocol)
                # This will be implemented when Spec 3 integration is available
                logger.debug(
                    f"[{trace_id}] Triggering Summarization sub-protocol (Spec 3) "
                    f"for {submission_count} submissions"
                )

            except Exception as e:
                await db.rollback()
                logger.error(
                    f"[{trace_id}] Failed to handle submission_window.closed "
                    f"for round {round_id}: {e}",
                    extra={"trace_id": trace_id, "round_id": str(round_id)},
                    exc_info=True
                )
                raise

    async def handle_summarization_complete(
        self, event: SummarizationCompleteEvent
    ) -> None:
        """
        Handle summarization completion event.

        Transitions: SUMMARIZING → APPROVING → CLUSTERING

        Actions:
        1. Validate round is in SUMMARIZING state
        2. Advance to APPROVING status
        3. Validate Intent Fidelity (100% approved summaries)
        4. Advance to CLUSTERING status
        5. Trigger Spec 4 (Clustering sub-protocol)

        Constitutional Guarantee: Intent Fidelity
        - 100% of ApprovedSummaries must have approval_status=APPROVED
        - Zero summaries with unapproved or pending status

        Args:
            event: SummarizationCompleteEvent with round_id and approved_summaries

        Raises:
            InvalidStateTransitionException: If round not in valid state
            ValueError: If Intent Fidelity validation fails
        """
        round_id = event.round_id
        summary_count = len(event.approved_summaries)
        trace_id = get_trace_id() or f"coord-{round_id}"

        logger.info(
            f"[{trace_id}] Processing summarization.complete for round {round_id} "
            f"({summary_count} approved summaries)",
            extra={"trace_id": trace_id, "round_id": str(round_id)}
        )

        session_factory = get_session_factory()
        async with session_factory() as db:
            try:
                # Fetch round
                round_obj = await self._fetch_round(db, round_id)

                # Validate current state
                if round_obj.status != RoundStatus.SUMMARIZING:
                    raise InvalidStateTransitionException(
                        entity_type="Round",
                        entity_id=str(round_id),
                        from_state=round_obj.status.value,
                        to_state=RoundStatus.APPROVING.value,
                        reason="Round must be in SUMMARIZING state"
                    )

                # Advance to APPROVING
                round_obj.advance_status(RoundStatus.APPROVING)
                await db.commit()

                logger.info(
                    f"[{trace_id}] Round {round_id} transitioned: "
                    f"SUMMARIZING → APPROVING",
                    extra={"trace_id": trace_id, "round_id": str(round_id)}
                )

                # Constitutional Validation: Intent Fidelity
                logger.info(
                    f"[{trace_id}] Validating Intent Fidelity before clustering "
                    f"(100% approved summaries required)",
                    extra={"trace_id": trace_id, "round_id": str(round_id)}
                )

                validation_result = await self.invariant_validator.validate_intent_fidelity(
                    db, round_id
                )

                if not validation_result.passed:
                    error_msg = (
                        f"Intent Fidelity validation failed for round {round_id}: "
                        f"{validation_result.message}"
                    )
                    logger.error(
                        f"[{trace_id}] {error_msg}",
                        extra={
                            "trace_id": trace_id,
                            "round_id": str(round_id),
                            "validation_details": validation_result.details
                        }
                    )
                    raise ValueError(error_msg)

                logger.info(
                    f"[{trace_id}] Intent Fidelity validation passed: "
                    f"{validation_result.message}",
                    extra={
                        "trace_id": trace_id,
                        "round_id": str(round_id),
                        "validation_details": validation_result.details
                    }
                )

                # Advance to CLUSTERING
                round_obj.advance_status(RoundStatus.CLUSTERING)
                await db.commit()

                logger.info(
                    f"[{trace_id}] Round {round_id} transitioned: "
                    f"APPROVING → CLUSTERING",
                    extra={"trace_id": trace_id, "round_id": str(round_id)}
                )

                # TODO: Trigger Spec 4 (Clustering sub-protocol)
                logger.debug(
                    f"[{trace_id}] Triggering Clustering sub-protocol (Spec 4) "
                    f"for {summary_count} approved summaries"
                )

            except Exception as e:
                await db.rollback()
                logger.error(
                    f"[{trace_id}] Failed to handle summarization.complete "
                    f"for round {round_id}: {e}",
                    extra={"trace_id": trace_id, "round_id": str(round_id)},
                    exc_info=True
                )
                raise

    async def handle_clustering_complete(
        self, event: ClusteringCompleteEvent
    ) -> None:
        """
        Handle clustering completion event.

        Transitions: CLUSTERING → SANKEY_BUILDING

        Actions:
        1. Validate round is in CLUSTERING state
        2. Validate Semantic Accuracy (100% participant coverage)
        3. Advance to SANKEY_BUILDING status
        4. Trigger Spec 5 (Sankey Construction sub-protocol)

        Constitutional Guarantee: Semantic Accuracy
        - 100% of active participants must be assigned to ThoughtSpace clusters
        - No orphaned participants
        - No forced merging (singleton clusters preserved)

        Args:
            event: ClusteringCompleteEvent with round_id and thought_spaces

        Raises:
            InvalidStateTransitionException: If round not in valid state
            ValueError: If Semantic Accuracy validation fails
        """
        round_id = event.round_id
        cluster_count = len(event.thought_spaces)
        trace_id = get_trace_id() or f"coord-{round_id}"

        logger.info(
            f"[{trace_id}] Processing clustering.complete for round {round_id} "
            f"({cluster_count} thought spaces)",
            extra={"trace_id": trace_id, "round_id": str(round_id)}
        )

        session_factory = get_session_factory()
        async with session_factory() as db:
            try:
                # Fetch round
                round_obj = await self._fetch_round(db, round_id)

                # Validate current state
                if round_obj.status != RoundStatus.CLUSTERING:
                    raise InvalidStateTransitionException(
                        entity_type="Round",
                        entity_id=str(round_id),
                        from_state=round_obj.status.value,
                        to_state=RoundStatus.SANKEY_BUILDING.value,
                        reason="Round must be in CLUSTERING state"
                    )

                # Constitutional Validation: Semantic Accuracy
                logger.info(
                    f"[{trace_id}] Validating Semantic Accuracy "
                    f"(100% participant coverage required)",
                    extra={"trace_id": trace_id, "round_id": str(round_id)}
                )

                validation_result = await self.invariant_validator.validate_semantic_accuracy(
                    db, round_id
                )

                if not validation_result.passed:
                    error_msg = (
                        f"Semantic Accuracy validation failed for round {round_id}: "
                        f"{validation_result.message}"
                    )
                    logger.error(
                        f"[{trace_id}] {error_msg}",
                        extra={
                            "trace_id": trace_id,
                            "round_id": str(round_id),
                            "validation_details": validation_result.details
                        }
                    )
                    raise ValueError(error_msg)

                logger.info(
                    f"[{trace_id}] Semantic Accuracy validation passed: "
                    f"{validation_result.message}",
                    extra={
                        "trace_id": trace_id,
                        "round_id": str(round_id),
                        "validation_details": validation_result.details
                    }
                )

                # Advance to SANKEY_BUILDING
                round_obj.advance_status(RoundStatus.SANKEY_BUILDING)
                await db.commit()

                logger.info(
                    f"[{trace_id}] Round {round_id} transitioned: "
                    f"CLUSTERING → SANKEY_BUILDING",
                    extra={"trace_id": trace_id, "round_id": str(round_id)}
                )

                # TODO: Trigger Spec 5 (Sankey Construction sub-protocol)
                logger.debug(
                    f"[{trace_id}] Triggering Sankey Construction sub-protocol (Spec 5) "
                    f"for {cluster_count} thought spaces"
                )

            except Exception as e:
                await db.rollback()
                logger.error(
                    f"[{trace_id}] Failed to handle clustering.complete "
                    f"for round {round_id}: {e}",
                    extra={"trace_id": trace_id, "round_id": str(round_id)},
                    exc_info=True
                )
                raise

    async def handle_sankey_complete(self, event: SankeyCompleteEvent) -> None:
        """
        Handle Sankey construction completion event.

        Transitions: SANKEY_BUILDING → COMPLETE

        Actions:
        1. Validate round is in SANKEY_BUILDING state
        2. Validate Temporal Transparency (flow accuracy)
        3. Advance to COMPLETE status
        4. Emit round.complete event (handled by existing sankey_complete handler)

        Constitutional Guarantee: Temporal Transparency
        - Flow participant_counts must match actual participant movement
        - Flows computed from participant intersections (not semantic similarity)
        - display_group_id alignment does NOT inflate flow counts

        Args:
            event: SankeyCompleteEvent with round_id and sankey_graph

        Raises:
            InvalidStateTransitionException: If round not in valid state
            ValueError: If Temporal Transparency validation fails
        """
        round_id = event.round_id
        node_count = len(event.sankey_graph.nodes)
        edge_count = len(event.sankey_graph.edges)
        trace_id = get_trace_id() or f"coord-{round_id}"

        logger.info(
            f"[{trace_id}] Processing sankey.complete for round {round_id} "
            f"({node_count} nodes, {edge_count} edges)",
            extra={"trace_id": trace_id, "round_id": str(round_id)}
        )

        session_factory = get_session_factory()
        async with session_factory() as db:
            try:
                # Fetch round
                round_obj = await self._fetch_round(db, round_id)

                # Validate current state
                if round_obj.status != RoundStatus.SANKEY_BUILDING:
                    raise InvalidStateTransitionException(
                        entity_type="Round",
                        entity_id=str(round_id),
                        from_state=round_obj.status.value,
                        to_state=RoundStatus.COMPLETE.value,
                        reason="Round must be in SANKEY_BUILDING state"
                    )

                # Constitutional Validation: Temporal Transparency
                # Only validate if there are flows (multi-round scenario)
                if edge_count > 0:
                    logger.info(
                        f"[{trace_id}] Validating Temporal Transparency "
                        f"(flow accuracy required)",
                        extra={"trace_id": trace_id, "round_id": str(round_id)}
                    )

                    # Validate all flows in the Sankey graph
                    for edge in event.sankey_graph.edges:
                        validation_result = await self.invariant_validator.validate_temporal_transparency(
                            db,
                            edge.source_cluster_id,
                            edge.target_cluster_id,
                            edge.participant_count
                        )

                        if not validation_result.passed:
                            error_msg = (
                                f"Temporal Transparency validation failed for flow "
                                f"{edge.source_cluster_id} → {edge.target_cluster_id}: "
                                f"{validation_result.message}"
                            )
                            logger.error(
                                f"[{trace_id}] {error_msg}",
                                extra={
                                    "trace_id": trace_id,
                                    "round_id": str(round_id),
                                    "source_cluster": str(edge.source_cluster_id),
                                    "target_cluster": str(edge.target_cluster_id),
                                    "validation_details": validation_result.details
                                }
                            )
                            raise ValueError(error_msg)

                    logger.info(
                        f"[{trace_id}] Temporal Transparency validation passed "
                        f"for all {edge_count} flows",
                        extra={"trace_id": trace_id, "round_id": str(round_id)}
                    )

                # Advance to COMPLETE
                round_obj.advance_status(RoundStatus.COMPLETE)
                await db.commit()

                logger.info(
                    f"[{trace_id}] Round {round_id} transitioned: "
                    f"SANKEY_BUILDING → COMPLETE",
                    extra={
                        "trace_id": trace_id,
                        "round_id": str(round_id),
                        "node_count": node_count,
                        "edge_count": edge_count
                    }
                )

                # Note: round.complete event emission is handled by the existing
                # sankey_complete event handler (T040)

            except Exception as e:
                await db.rollback()
                logger.error(
                    f"[{trace_id}] Failed to handle sankey.complete "
                    f"for round {round_id}: {e}",
                    extra={"trace_id": trace_id, "round_id": str(round_id)},
                    exc_info=True
                )
                raise

    async def _fetch_round(self, db: AsyncSession, round_id: UUID) -> Round:
        """
        Fetch a round by ID from the database.

        Args:
            db: Database session
            round_id: Round UUID

        Returns:
            Round object

        Raises:
            ValueError: If round not found
        """
        result = await db.execute(
            select(Round).where(Round.round_id == round_id)
        )
        round_obj = result.scalar_one_or_none()

        if not round_obj:
            raise ValueError(f"Round {round_id} not found")

        return round_obj


# Global coordinator instance
_coordinator: Optional[ProtocolCoordinator] = None


async def get_protocol_coordinator(event_bus: EventBus) -> ProtocolCoordinator:
    """
    Get or create the global protocol coordinator instance.

    Args:
        event_bus: EventBus instance for event subscriptions

    Returns:
        ProtocolCoordinator: The global coordinator instance
    """
    global _coordinator

    if _coordinator is None:
        _coordinator = ProtocolCoordinator(event_bus)
        await _coordinator.register_handlers()

    return _coordinator


async def close_protocol_coordinator() -> None:
    """Close the global protocol coordinator instance."""
    global _coordinator
    _coordinator = None
