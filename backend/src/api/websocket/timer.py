"""
WebSocket endpoint for real-time countdown timer broadcasts.
Provides sub-second accuracy window status updates to connected clients.
"""

from uuid import UUID
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.websocket.connection_manager import connection_manager
from src.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/rounds/{round_id}/timer")
async def countdown_timer_websocket(
    websocket: WebSocket,
    round_id: UUID
):
    """
    WebSocket endpoint for real-time countdown timer updates.

    Clients connect to this endpoint and receive timer updates every second
    with remaining time in the submission window.

    Message format:
    {
        "round_id": "uuid",
        "remaining_seconds": 123,
        "is_open": true,
        "status": "OPEN",
        "current_time": "2026-02-01T12:00:00Z"
    }

    Args:
        websocket: WebSocket connection
        round_id: UUID of the round to monitor
    """
    # Accept connection and register with manager
    await connection_manager.connect(websocket, round_id)

    try:
        # Keep connection alive and wait for disconnect
        # The timer service (T057) will broadcast updates to all connections
        while True:
            # Wait for any message from client (keep-alive or ping)
            # We don't process messages, just keep connection alive
            try:
                data = await websocket.receive_text()
                # Echo back for keep-alive
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(f"WebSocket error for round {round_id}: {e}")

    finally:
        # Unregister connection
        await connection_manager.disconnect(websocket, round_id)
