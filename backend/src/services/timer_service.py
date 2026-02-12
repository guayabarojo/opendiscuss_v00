"""
Background timer service for broadcasting window status updates.

Checks active rounds every 1 second and broadcasts remaining time
to all connected WebSocket clients.
"""

import asyncio
import logging
from datetime import datetime
from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.api.websocket.connection_manager import connection_manager
from src.database import get_session_factory
from src.models.round import Round
from src.models.protocol_state import RoundStatus

logger = logging.getLogger(__name__)


class TimerService:
    """
    Background service that broadcasts timer updates every second.

    Monitors active rounds and sends real-time countdown updates
    via WebSocket to all connected clients.
    """

    def __init__(self):
        self._running = False
        self._task = None

    async def start(self) -> None:
        """Start the background timer service."""
        if self._running:
            logger.warning("Timer service already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._timer_loop())
        logger.info("Timer service started")

    async def stop(self) -> None:
        """Stop the background timer service."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Timer service stopped")

    async def _timer_loop(self) -> None:
        """Main timer loop - runs every 1 second."""
        while self._running:
            try:
                await self._broadcast_timer_updates()
                await asyncio.sleep(1)  # Broadcast every 1 second
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in timer loop: {e}", exc_info=True)
                await asyncio.sleep(1)  # Continue after error

    async def _broadcast_timer_updates(self) -> None:
        """
        Query active rounds and broadcast timer updates to connected clients.

        Only broadcasts for rounds in SUBMISSION_OPEN status with active WebSocket connections.
        """
        session_factory = get_session_factory()
        async with session_factory() as db:
            # Query all rounds that might need timer updates
            # (SUBMISSION_OPEN or recently closed)
            stmt = select(Round).where(
                Round.status.in_([
                    RoundStatus.SUBMISSION_OPEN,
                    RoundStatus.SUBMISSION_CLOSED
                ])
            )
            result = await db.execute(stmt)
            active_rounds = result.scalars().all()

            current_time = datetime.utcnow()

            for round_obj in active_rounds:
                # Only broadcast if there are active connections
                if connection_manager.get_connection_count(round_obj.round_id) == 0:
                    continue

                # Calculate window status
                window_status = self._calculate_window_status(round_obj, current_time)

                # Broadcast to all connected clients for this round
                await connection_manager.broadcast_to_round(
                    round_obj.round_id,
                    window_status
                )

    def _calculate_window_status(self, round_obj: Round, current_time: datetime) -> dict:
        """
        Calculate window status for a round.

        Args:
            round_obj: Round database model
            current_time: Current UTC time

        Returns:
            Dictionary with timer status
        """
        window_start = round_obj.submission_window_start
        window_end = round_obj.submission_window_end

        if window_start is None or window_end is None:
            return {
                "round_id": str(round_obj.round_id),
                "remaining_seconds": None,
                "is_open": False,
                "status": "NOT_OPEN",
                "current_time": current_time.isoformat() + "Z"
            }

        if current_time < window_start:
            # Before window opens
            remaining = int((window_start - current_time).total_seconds())
            return {
                "round_id": str(round_obj.round_id),
                "remaining_seconds": remaining,
                "is_open": False,
                "status": "BEFORE_WINDOW",
                "current_time": current_time.isoformat() + "Z"
            }

        elif window_start <= current_time < window_end:
            # Window is open (inclusive start, exclusive end)
            remaining = int((window_end - current_time).total_seconds())
            return {
                "round_id": str(round_obj.round_id),
                "remaining_seconds": remaining,
                "is_open": True,
                "status": "OPEN",
                "current_time": current_time.isoformat() + "Z"
            }

        else:
            # Window has closed
            return {
                "round_id": str(round_obj.round_id),
                "remaining_seconds": 0,
                "is_open": False,
                "status": "CLOSED",
                "current_time": current_time.isoformat() + "Z"
            }


# Global singleton instance
timer_service = TimerService()
